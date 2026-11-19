import json
from pathlib import Path

import pytest

from agent.contract import ProvaEntrada, ProvaSaida

PASTA = Path(__file__).parent.parent / "contracts"
EXEMPLOS = PASTA / "exemplos"


def carregar(caminho):
    return json.loads(caminho.read_text(encoding="utf-8"))


@pytest.mark.parametrize("nome, modelo", [("entrada", ProvaEntrada), ("saida", ProvaSaida)])
def test_schema_salvo_esta_atualizado(nome, modelo):
    salvo = carregar(PASTA / f"{nome}.schema.json")
    assert salvo == modelo.model_json_schema(), (
        f"{nome}.schema.json desatualisado. Rode: uv run python -m contracts.gerar_schemas"
    )


@pytest.mark.parametrize("arquivo", sorted(EXEMPLOS.glob("entrada_*.json")), ids=lambda p: p.name)
def test_exemplo_de_entrada_e_valido(arquivo):
    ProvaEntrada.model_validate(carregar(arquivo))


@pytest.mark.parametrize("arquivo", sorted(EXEMPLOS.glob("saida_*.json")), ids=lambda p: p.name)
def test_exemplo_de_saida_e_valido(arquivo):
    ProvaSaida.model_validate(carregar(arquivo))
    