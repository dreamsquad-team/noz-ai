from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuração do agente, lida de variáveis de ambiente.

    `memory_id` e `gateway_url` são injetados em deploy pelo CDK gerado, a
    partir dos recursos declarados em agentcore.json.
    `AWS_REGION` vem do ambiente gerenciado do contêiner quando presente, com
    a resolução própria do boto3 como fallback; nada aqui o injeta. `LOG_LEVEL`
    é lido por `configure_logging` (config/log.py) em `main.py`, na importação
    do módulo. O .env local existe só para desenvolvimento.
    """

    # O CLI deriva o nome da env var do nome do recurso em agentcore.json:
    # `MEMORY_${name.toUpperCase()}_ID` (AgentCoreMemory.js:185). Com o recurso
    # chamado "noz_ai", o nome é MEMORY_NOZ_AI_ID —
    # se você renomear o recurso, renomeie o alias junto, ou o agente sobe sem
    # memória em silêncio. MEMORY_ID fica aceito para o dev local; a ordem
    # define a precedência.
    memory_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices(
            "MEMORY_NOZ_AI_ID",
            "MEMORY_ID",
        ),
    )
    aws_region: Optional[str] = Field(default=None, alias="AWS_REGION")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Gateway declarado no MESMO agentcore.json: o CDK injeta sozinho
    # AGENTCORE_GATEWAY_${NOME}_URL, com `-` virando `_` e a URL resolvida no
    # deploy (AgentCoreMcp.js:235). Não há connection nem ARN para copiar
    # depois do primeiro deploy. Se você renomear o gateway, renomeie o alias
    # junto (tests/test_settings.py falha se divergirem) — senão o agente sobe
    # sem as tools do gateway, em silêncio.
    #
    # Para um gateway de OUTRO projeto, declare uma `connection` com `id`
    # explícito no runtime; a variável passa a ser GATEWAY_${ID}_URL
    # (wire-connections.js:189) e este alias precisa ser trocado por ela.
    #
    # GATEWAY_URL fica aceito para o dev local.
    gateway_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices(
            "AGENTCORE_GATEWAY_NOZ_AI_URL",
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
