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

    # Assinar as requisições ao MCP com SigV4 (Gateway real). `false` só vale
    # para um MCP local (mock em 127.0.0.1); o cliente recusa desligar a
    # assinatura para qualquer outro host.
    mcp_sigv4: bool = Field(default=True, alias="MCP_SIGV4")

    # Teto de páginas por leitura (tools/leitura.py). Estourar vira erro, não
    # dado parcial silencioso.
    mcp_max_paginas: int = Field(default=200, ge=1, alias="MCP_MAX_PAGINAS")

    # Limites POR CONSULTA (custo do modelo e latência). O agente não guarda
    # nada; passou do limite, ele responde com o que coube (os itens mais
    # recentes) e avisa em `avisos`.
    max_eventos: int = Field(default=2000, ge=1, alias="MAX_EVENTOS")
    max_conteudos: int = Field(default=100, ge=1, alias="MAX_CONTEUDOS")
    max_usuarios_grupo: int = Field(default=50, ge=1, alias="MAX_USUARIOS_GRUPO")
    janela_padrao_dias: int = Field(default=90, ge=1, alias="JANELA_PADRAO_DIAS")
    # Prazo suave de uma consulta de grupo: passou dele, para de somar usuários e avisa.
    timeout_consulta_s: int = Field(default=60, ge=1, alias="TIMEOUT_CONSULTA_S")

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
