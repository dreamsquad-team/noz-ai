import datetime

import httpx
import pytest
from botocore import auth as botocore_auth

from mcp_client import client as mcp_client
from mcp_client import sigv4
from mcp_client.sigv4 import AuthSigV4


class FakeCreds:
    access_key = "AKIAFAKE"
    secret_key = "segredo"
    token = None

    def get_frozen_credentials(self):
        return self


@pytest.fixture(autouse=True)
def clear_session_cache():
    """_process_session é @lru_cache; sem limpar, o boto3.Session (ou o
    Session falso) de um teste vaza para o próximo."""
    sigv4._process_session.cache_clear()
    yield
    sigv4._process_session.cache_clear()


@pytest.fixture
def auth(monkeypatch):
    monkeypatch.setattr(
        "mcp_client.sigv4.boto3.Session",
        lambda: type("S", (), {"get_credentials": lambda self: FakeCreds()})(),
    )
    return AuthSigV4("bedrock-agentcore", "us-east-1")


def test_the_request_goes_out_signed(auth):
    request = httpx.Request(
        "POST",
        "https://x.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
        json={"jsonrpc": "2.0"},
    )

    signed = next(auth.auth_flow(request))

    assert "AWS4-HMAC-SHA256" in signed.headers["authorization"]
    assert "bedrock-agentcore" in signed.headers["authorization"]


def test_the_signature_covers_the_body():
    """SigV4 assina o hash do payload; sem requires_request_body o httpx
    entrega o corpo vazio e o gateway recusa com 403."""
    assert AuthSigV4.requires_request_body is True


def test_the_signature_is_correct_even_with_a_previous_authorization(auth, monkeypatch):
    """O botocore já remove um Authorization pré-existente antes de assinar
    (SigV4Auth._modify_request_before_signing, comentário original: "This
    could be a retry"); o filtro em auth_flow é redundante com isso hoje —
    cinto e suspensório proposital. O que importa é que a assinatura final
    saia idêntica à de uma requisição limpa, não que a palavra "lixo" suma
    do header."""
    fixed_moment = datetime.datetime(2024, 1, 1, 12, 0, 0)
    monkeypatch.setattr(
        botocore_auth, "get_current_datetime", lambda remove_tzinfo=True: fixed_moment
    )

    clean = httpx.Request(
        "POST",
        "https://x.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
        json={"jsonrpc": "2.0"},
    )
    dirty = httpx.Request(
        "POST",
        "https://x.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
        headers={"authorization": "AWS4-HMAC-SHA256 lixo-de-antes"},
        json={"jsonrpc": "2.0"},
    )

    signed_clean = next(auth.auth_flow(clean))
    signed_dirty = next(auth.auth_flow(dirty))

    assert signed_dirty.headers["authorization"] == signed_clean.headers["authorization"]


def test_credentials_that_raise_become_none(monkeypatch):
    """Um provider de container pode levantar CredentialRetrievalError em vez
    de devolver None numa falha transitória. AuthSigV4 não pode deixar isso
    escapar: get_gateway_mcp_client() confere `credentials` antes de usar o
    assinador, e para isso precisa de um valor, não de uma exceção."""

    class SessionThatRaises:
        def get_credentials(self):
            raise RuntimeError("CredentialRetrievalError simulado")

    monkeypatch.setattr("mcp_client.sigv4.boto3.Session", lambda: SessionThatRaises())

    assert AuthSigV4("bedrock-agentcore", "us-east-1").credentials is None


def test_the_boto3_session_is_reused_across_invocations(monkeypatch):
    """get_gateway_mcp_client() roda por invocação; sem o cache, cada
    AuthSigV4 abriria uma boto3.Session nova e perderia o
    RefreshableCredentials já resolvido pelo provider de container/IMDS."""
    calls = {"n": 0}

    def fake_session():
        calls["n"] += 1
        return type("S", (), {"get_credentials": lambda self: FakeCreds()})()

    monkeypatch.setattr("mcp_client.sigv4.boto3.Session", fake_session)

    AuthSigV4("bedrock-agentcore", "us-east-1")
    AuthSigV4("bedrock-agentcore", "us-east-1")
    AuthSigV4("bedrock-agentcore", "us-east-1")

    assert calls["n"] == 1


# --- get_gateway_mcp_client: construção e degradação -------------------------
#
# As guardas abaixo cobrem o que o Strands NÃO cobre. A partir da 1.53 o
# MCPClient é um ToolProvider com continue_on_error, que já degrada para []
# quando o handshake falha — por isso não há aqui um context manager próprio
# de sessão. Mas com transport_callable o MCPClient não valida a URL, e uma
# credencial que não resolve só explodiria na hora da requisição. Nenhum dos
# dois pode derrubar a invocação.


def test_without_a_gateway_url_there_is_no_client(monkeypatch):
    """Rodar sem gateway é caminho suportado: o agente segue com as tools
    locais."""
    monkeypatch.setattr(mcp_client.settings, "gateway_url", None)
    assert mcp_client.get_gateway_mcp_client() is None


def test_a_url_of_only_spaces_also_yields_no_client(monkeypatch):
    """"   " é truthy em Python; o strip() é o que o barra no guard de vazio."""
    monkeypatch.setattr(mcp_client.settings, "gateway_url", "   ")
    assert mcp_client.get_gateway_mcp_client() is None


def test_a_url_without_an_http_scheme_also_yields_no_client(monkeypatch):
    """Uma URL não-vazia mas sem esquema (ex.: substituição de CDK truncada)
    passa pelo guard de string vazia. Com transport_callable o MCPClient não a
    valida, então sem a checagem de esquema ela só falharia na conexão."""
    monkeypatch.setattr(mcp_client.settings, "gateway_url", "not-a-url")
    assert mcp_client.get_gateway_mcp_client() is None


def test_a_malformed_ipv6_url_also_yields_no_client(monkeypatch):
    """urlparse levanta ValueError ("Invalid IPv6 URL") sozinho para esta
    entrada, antes mesmo de a checagem de esquema rodar — o guard de esquema
    por si só não basta para nunca levantar."""
    monkeypatch.setattr(mcp_client.settings, "gateway_url", "https://[mygateway")
    assert mcp_client.get_gateway_mcp_client() is None


def test_without_aws_credentials_there_is_no_client(monkeypatch):
    """Se a cadeia de credenciais não resolve nada, get_frozen_credentials()
    só explodiria (AttributeError opaco) na hora da requisição. Detectar na
    construção troca isso por uma degradação explícita."""
    monkeypatch.setattr(
        mcp_client.settings,
        "gateway_url",
        "https://x.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
    )
    monkeypatch.setattr(
        "mcp_client.sigv4.boto3.Session",
        lambda: type("S", (), {"get_credentials": lambda self: None})(),
    )
    assert mcp_client.get_gateway_mcp_client() is None


def test_with_a_url_the_client_is_built(monkeypatch):
    captured = {}

    def fake_mcp_client(transport_callable, **kwargs):
        captured.update(kwargs, transport_callable=transport_callable)
        return "cliente"

    class FakeAuthSigV4:
        def __init__(self, service, region):
            self.service = service
            self.region = region
            self.credentials = "assinador-credentials"

    monkeypatch.setattr(
        mcp_client.settings,
        "gateway_url",
        "https://x.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
    )
    monkeypatch.setattr(mcp_client, "MCPClient", fake_mcp_client)
    monkeypatch.setattr(mcp_client, "AuthSigV4", FakeAuthSigV4)

    assert mcp_client.get_gateway_mcp_client() == "cliente"
    assert callable(captured["transport_callable"])


def test_the_gateway_connect_is_short():
    """Gateway que não responde não pode segurar a primeira invocação do
    contêiner pelos 30s do connect padrão do MCP. Medido: 30,1s antes, 3s com
    connect=3."""
    assert mcp_client.TIMEOUT.connect <= 5
    assert mcp_client.TIMEOUT.read == 300.0  # leitura SSE segue o padrão do MCP


def test_the_transport_uses_the_timeout_and_the_signer(monkeypatch):
    import asyncio
    import contextlib

    seen = {}

    @contextlib.asynccontextmanager
    async def fake_streamable(url, http_client):
        seen["url"] = url
        seen["timeout"] = http_client.timeout
        seen["auth"] = http_client.auth
        yield ("r", "w", lambda: None)

    monkeypatch.setattr(mcp_client, "streamable_http_client", fake_streamable)
    signer = httpx.BasicAuth("u", "p")

    async def open_it():
        async with mcp_client._transport("https://gw/mcp", signer) as streams:
            return streams

    assert asyncio.run(open_it())[:2] == ("r", "w")
    assert seen["url"] == "https://gw/mcp"
    assert seen["timeout"] == mcp_client.TIMEOUT
    assert seen["auth"] is signer


def test_the_client_degrades_instead_of_failing_the_invocation(monkeypatch):
    """continue_on_error é o que substitui o context manager de sessão que
    versões antigas do Strands exigiam: um gateway fora do ar vira tools=[]
    e um WARNING, não uma invocação derrubada."""
    captured = {}

    monkeypatch.setattr(
        mcp_client.settings,
        "gateway_url",
        "https://x.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
    )
    monkeypatch.setattr(
        mcp_client, "MCPClient", lambda *args, **kwargs: captured.update(kwargs)
    )
    monkeypatch.setattr(
        mcp_client,
        "AuthSigV4",
        lambda service, region: type("A", (), {"credentials": "x"})(),
    )

    mcp_client.get_gateway_mcp_client()

    assert captured["continue_on_error"] is True


def test_the_exa_boilerplate_is_gone():
    """Guarda de regressão: o endpoint de exemplo não pode voltar."""
    assert not hasattr(mcp_client, "EXAMPLE_MCP_ENDPOINT")


def test_the_degradation_warning_goes_to_the_module_logger(monkeypatch):
    """O session id vem do filtro em config/log.py, no handler raiz; o aviso
    sai pelo logger do módulo e propaga até lá."""
    captured = []
    monkeypatch.setattr(
        mcp_client.logger, "warning", lambda *a, **k: captured.append(a)
    )
    monkeypatch.setattr(mcp_client.settings, "gateway_url", None)

    assert mcp_client.get_gateway_mcp_client() is None
    assert len(captured) == 1
    assert "GATEWAY_URL" in captured[0][0]


# --- região da assinatura ----------------------------------------------------


def _region_signed_for(monkeypatch, url, aws_region):
    """Devolve a região com que o AuthSigV4 foi construído."""
    seen = {}

    class FakeAuthSigV4:
        def __init__(self, service, region):
            seen["region"] = region
            self.credentials = "x"

    monkeypatch.setattr(mcp_client.settings, "gateway_url", url)
    monkeypatch.setattr(mcp_client.settings, "aws_region", aws_region)
    monkeypatch.setattr(mcp_client, "MCPClient", lambda *a, **kw: object())
    monkeypatch.setattr(mcp_client, "AuthSigV4", FakeAuthSigV4)
    mcp_client.get_gateway_mcp_client()
    return seen["region"]


def test_the_signing_region_comes_from_the_gateway_url(monkeypatch):
    """A região da assinatura tem que ser a do host do gateway, senão o
    gateway devolve 403. A URL é a fonte confiável: AWS_REGION pode estar
    ausente, ou ser a região do Runtime e não a do gateway."""
    region = _region_signed_for(
        monkeypatch,
        "https://g1.gateway.bedrock-agentcore.sa-east-1.amazonaws.com/mcp",
        aws_region=None,
    )
    assert region == "sa-east-1"


def test_the_url_region_wins_over_aws_region(monkeypatch):
    region = _region_signed_for(
        monkeypatch,
        "https://g1.gateway.bedrock-agentcore.eu-west-1.amazonaws.com/mcp",
        aws_region="us-east-1",
    )
    assert region == "eu-west-1"


def test_a_non_agentcore_url_falls_back_to_aws_region(monkeypatch):
    """Dev local contra um endpoint que não segue o padrão do host."""
    region = _region_signed_for(
        monkeypatch, "http://localhost:8000/mcp", aws_region="ap-south-1"
    )
    assert region == "ap-south-1"
