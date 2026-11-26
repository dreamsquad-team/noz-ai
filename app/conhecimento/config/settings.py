from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuração do agente, lida de variáveis de ambiente.

    Sem AgentCore Memory neste agente (decisão do projeto). `gateway_url` aponta para o
    Gateway com o MCP da NOZ (ou do mock).
    `AWS_REGION` vem do ambiente gerenciado do contêiner quando presente, com
    a resolução própria do boto3 como fallback; nada aqui o injeta. `LOG_LEVEL`
    é lido por `configure_logging` (config/log.py) em `main.py`, na importação
    do módulo. O .env local existe só para desenvolvimento.
    """

    aws_region: Optional[str] = Field(default=None, alias="AWS_REGION")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # URL do AgentCore Gateway que expõe o MCP da NOZ (ou do mock). Como o
    # Gateway será declarado (agentcore.json ou Terraform) ainda está em
    # decisão; até lá a URL vem de GATEWAY_URL, e o alias específico do
    # deploy será acrescentado quando o recurso existir. Sem URL, o agente
    # roda sem as tools do gateway.
    gateway_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices(
            "GATEWAY_URL",
        ),
    )

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "populate_by_name": True,
        # O DotEnvSettingsSource devolve TODAS as chaves do arquivo; sem
        # "ignore" o pydantic recusa as que não têm campo e a subida quebra.
        "extra": "ignore",
        # Silencia o warning do pydantic para campos com prefixo "model_"
        # (MODEL_ID entra aqui quando os parâmetros do modelo forem migrados).
        "protected_namespaces": (),
    }


settings = Settings()
