import json
import pytest
from pathlib import Path

from config.settings import Settings

# _env_file=None isola cada teste de qualquer .env que exista no diretório —
# senão um arquivo local mudaria o resultado dependendo da máquina.


def test_memory_id_from_cli_injected_var(monkeypatch):
    monkeypatch.setenv("MEMORY_NOZ_AI_ID", "mem-do-cli")
    monkeypatch.delenv("MEMORY_ID", raising=False)
    assert Settings(_env_file=None).memory_id == "mem-do-cli"


def test_memory_id_from_local_dev_var(monkeypatch):
    monkeypatch.delenv("MEMORY_NOZ_AI_ID", raising=False)
    monkeypatch.setenv("MEMORY_ID", "mem-do-dev-local")
    assert Settings(_env_file=None).memory_id == "mem-do-dev-local"


def test_cli_var_wins_over_local_dev_var(monkeypatch):
    monkeypatch.setenv("MEMORY_NOZ_AI_ID", "mem-do-cli")
    monkeypatch.setenv("MEMORY_ID", "mem-do-dev-local")
    assert Settings(_env_file=None).memory_id == "mem-do-cli"


def test_memory_id_absent_is_none(monkeypatch):
    monkeypatch.delenv("MEMORY_NOZ_AI_ID", raising=False)
    monkeypatch.delenv("MEMORY_ID", raising=False)
    assert Settings(_env_file=None).memory_id is None


def test_log_level_defaults_to_info(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    assert Settings(_env_file=None).log_level == "INFO"


def test_aws_region_is_read_from_env(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    assert Settings(_env_file=None).aws_region == "us-east-1"


def test_dotenv_with_unknown_keys_does_not_raise(tmp_path, monkeypatch):
    """extra='ignore' — sem isso o pydantic-settings recusa chaves do .env
    que não têm campo correspondente, e a subida quebra."""
    monkeypatch.delenv("MEMORY_NOZ_AI_ID", raising=False)
    monkeypatch.delenv("MEMORY_ID", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("MEMORY_ID=mem-local\nCHAVE_SEM_CAMPO=qualquer\n")

    settings = Settings(_env_file=str(env_file))

    assert settings.memory_id == "mem-local"


# --- As env vars que o CDK injeta -------------------------------------------
#
# Os dois testes abaixo são a guarda que faltava. O nome da variável não é
# escolha nossa: o CDK o deriva do agentcore.json. Um rename lá, sem o rename
# correspondente aqui, faz o recurso subir e o agente nunca enxergá-lo — sem
# erro, sem log, sem nada. Foi exatamente o que aconteceu quando o recurso de
# memória foi renomeado e o alias ficou para trás.

AGENTCORE_JSON = Path(__file__).resolve().parents[3] / "agentcore" / "agentcore.json"


def _spec() -> dict:
    return json.loads(AGENTCORE_JSON.read_text(encoding="utf-8"))


def test_the_memory_alias_matches_the_resource_name_in_agentcore_json(monkeypatch):
    """O CDK injeta MEMORY_${name.toUpperCase()}_ID a partir do nome do
    recurso (AgentCoreMemory.js:185)."""
    memories = _spec()["memories"]
    assert memories, "agentcore.json precisa declarar ao menos uma memória"
    var = f"MEMORY_{memories[0]['name'].upper()}_ID"

    monkeypatch.delenv("MEMORY_ID", raising=False)
    monkeypatch.setenv(var, "mem-do-cli")

    assert Settings(_env_file=None).memory_id == "mem-do-cli", (
        f"{var} não é aceita pelo Settings: o agente subiria sem memória, "
        "em silêncio"
    )


@pytest.mark.skip(reason="gateway removido nesta task (ATHENA-946); reativar quando o gateway voltar")
def test_the_gateway_alias_matches_the_gateway_name_in_agentcore_json(monkeypatch):
    """Para um gateway declarado no MESMO agentcore.json, o CDK injeta
    AGENTCORE_GATEWAY_${NOME}_URL sozinho — com `-` virando `_` e a URL
    resolvida no deploy (AgentCoreMcp.js:235). Não há `connection`, nem ARN
    para copiar depois do primeiro deploy: a connection só existe para
    gateway de OUTRO projeto, e aí o nome da variável passa a vir do `id` dela
    (GATEWAY_${ID}_URL)."""
    gateways = _spec()["agentCoreGateways"]
    assert gateways, "agentcore.json precisa declarar o gateway do projeto"
    var = f"AGENTCORE_GATEWAY_{gateways[0]['name'].upper().replace('-', '_')}_URL"

    monkeypatch.delenv("GATEWAY_URL", raising=False)
    monkeypatch.setenv(var, "https://exemplo.gateway.amazonaws.com/mcp")

    assert Settings(_env_file=None).gateway_url == "https://exemplo.gateway.amazonaws.com/mcp", (
        f"{var} não é aceita pelo Settings: o gateway subiria mudo"
    )
