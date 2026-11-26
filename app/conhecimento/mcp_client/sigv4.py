"""Assinatura SigV4 para o cliente MCP.

Um AgentCore Gateway com `authorizerType: AWS_IAM` exige que a requisição HTTP
do MCP venha assinada com a execution role do Runtime. Nem o Strands nem o
`mcp` trazem um provider de SigV4 pronto; `httpx.Auth` é o gancho que os dois
aceitam — o `MCPClient` recebe esta classe em `auth_provider=`.
"""

import logging
from functools import lru_cache

import boto3
import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _process_session() -> boto3.Session:
    """Uma boto3.Session por processo, igual ao load_model() do modelo.

    `get_gateway_mcp_client()` pode rodar mais de uma vez na vida do
    contêiner; sem este cache, cada AuthSigV4 abriria uma Session nova e
    perderia o RefreshableCredentials já resolvido pelo provider
    (container/IMDS). Um contêiner quente que hoje sobrevive a um soluço
    transitório no endpoint de credenciais — porque a credencial já resolvida
    continua válida enquanto o refresh falha — passaria a depender de resolver
    do zero toda vez, sem essa rede de segurança.
    """
    return boto3.Session()


class AuthSigV4(httpx.Auth):
    """Assina cada requisição com as credenciais do ambiente."""

    # SigV4 inclui o hash do payload na assinatura; sem isto o httpx chama o
    # auth_flow antes de o corpo existir e o gateway devolve 403.
    requires_request_body = True

    def __init__(self, service: str, region: str):
        self._service = service
        self._region = region
        # get_frozen_credentials() a cada assinatura é o que respeita a
        # rotação do provider. None quando a cadeia de credenciais não resolve
        # nada, ou quando a resolução levanta (ex.: CredentialRetrievalError de
        # um provider de container numa falha transitória) —
        # get_gateway_mcp_client() confere isto antes de montar o cliente, e
        # para isso precisa de um valor em vez de uma exceção.
        try:
            self._credentials = _process_session().get_credentials()
        except Exception:
            logger.warning("falha ao resolver credenciais AWS", exc_info=True)
            self._credentials = None

    @property
    def credentials(self):
        return self._credentials

    def auth_flow(self, request: httpx.Request):
        aws_request = AWSRequest(
            method=request.method,
            url=str(request.url),
            data=request.content,
            # O SigV4Auth.add_auth do botocore já remove um Authorization
            # pré-existente antes de assinar (é o próprio comentário dele:
            # "This could be a retry"). O filtro abaixo é redundante com isso
            # hoje — cinto e suspensório proposital, para não depender de um
            # detalhe de implementação de uma lib de terceiros.
            headers={
                k: v for k, v in request.headers.items() if k.lower() != "authorization"
            },
        )
        SigV4Auth(
            self._credentials.get_frozen_credentials(), self._service, self._region
        ).add_auth(aws_request)
        request.headers.update(dict(aws_request.headers))
        yield request
