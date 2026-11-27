"""Cliente MCP apontado ao AgentCore Gateway.

O Gateway sobe com `authorizerType: AWS_IAM`, então a requisição precisa vir
assinada com a execution role do Runtime — é o que `mcp_client/sigv4.py` faz.

Não há aqui um context manager de sessão. Desde o Strands 1.53 o `MCPClient` é
um `ToolProvider` com `continue_on_error`: ele abre a sessão, lista as tools e,
se o handshake falhar, devolve `[]` com um WARNING em vez de derrubar a
invocação. Basta entregá-lo em `tools=[...]` que o Agent cuida do ciclo de
vida. O que sobra para esta função são as falhas que o Strands *não* trata: uma
URL ausente ou malformada e uma credencial que não resolve, que só explodiria
na hora da requisição.

O transporte é montado aqui, e não pelo `MCPClient(url=...)`, por causa do
timeout de conexão (ver `TIMEOUT`). O preço é que o `MCPClient` deixa de
validar a URL: com `transport_callable` ele não a vê, então a checagem de
esquema abaixo é só nossa.
"""

import contextlib
import logging
import re
from typing import Optional
from urllib.parse import urlparse

import httpx
from mcp.client.streamable_http import streamable_http_client
from strands.tools.mcp.mcp_client import MCPClient

from config.settings import settings
from mcp_client.sigv4 import AuthSigV4

logger = logging.getLogger(__name__)

# Nome do serviço na assinatura, o mesmo que aparece no host do gateway.
SERVICE = "bedrock-agentcore"

# Conexão curta: com o connect padrão do MCP (30s), um gateway que não responde
# segura a primeira invocação de cada contêiner por 30s antes de o
# continue_on_error degradar para []. O startup_timeout do MCPClient não ajuda
# sozinho — o stop() dele espera a thread de fundo, que fica presa no connect.
# O resto segue os padrões do MCP: 30s por operação e 300s de leitura SSE.
TIMEOUT = httpx.Timeout(30.0, read=300.0, connect=3.0)

# <id>.gateway.bedrock-agentcore.<região>.amazonaws.com
_GATEWAY_HOST_REGION = re.compile(r"\.gateway\.bedrock-agentcore\.([a-z0-9-]+)\.")


def _signing_region(url: str) -> str:
    """A região com que assinar a requisição ao gateway.

    A assinatura SigV4 só vale se a região bater com a do host, então a fonte
    confiável é a própria URL — AWS_REGION pode estar ausente ou ser a região
    do Runtime, que nem sempre é a do gateway. AWS_REGION e, por último,
    us-east-1 só valem para uma URL fora do padrão (dev local).
    """
    match = _GATEWAY_HOST_REGION.search(url)
    return match.group(1) if match else (settings.aws_region or "us-east-1")


@contextlib.asynccontextmanager
async def _transport(url: str, auth: httpx.Auth):
    async with httpx.AsyncClient(auth=auth, timeout=TIMEOUT, follow_redirects=True) as http:
        async with streamable_http_client(url, http_client=http) as streams:
            yield streams


def get_gateway_mcp_client() -> Optional[MCPClient]:
    """O cliente do Gateway, ou None quando não há gateway utilizável.

    Rodar sem gateway é caminho suportado: o agente segue com as tools locais.
    As três checagens abaixo existem para que esta função nunca levante — uma
    URL ausente, mal formada ou sem esquema, e credenciais que não resolvem,
    degradam para None em vez de propagar a exceção do `urlparse` ou do
    assinador. Um host *errado* não entra aqui: isso falha na conexão, não na
    construção, e lá o `continue_on_error` já cobre — em no máximo 3s.
    """
    # .strip(): "   " é truthy em Python e passaria pelo guard de vazio.
    url = (settings.gateway_url or "").strip()
    if not url:
        logger.warning("GATEWAY_URL ausente; o agente roda sem as tools do gateway")
        return None

    try:
        # urlparse pode levantar ValueError sozinho para entrada malformada
        # (ex.: "https://[mygateway" — "Invalid IPv6 URL"), antes mesmo de a
        # checagem de esquema rodar.
        valid_scheme = urlparse(url).scheme in ("http", "https")
    except ValueError:
        valid_scheme = False
    if not valid_scheme:
        logger.warning(
            "GATEWAY_URL sem esquema http/https válido (%r); o agente roda sem "
            "as tools do gateway",
            url,
        )
        return None

    auth = AuthSigV4(SERVICE, _signing_region(url))
    if auth.credentials is None:
        logger.warning(
            "nenhuma credencial AWS resolvida; o agente roda sem as tools do gateway"
        )
        return None

    return MCPClient(lambda: _transport(url, auth), continue_on_error=True)
