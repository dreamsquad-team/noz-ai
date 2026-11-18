import json
from pathlib import Path

from agent.contract import ProvaEntrada, ProvaSaida

PASTA = Path(__file__).parent


def gerar():
    for nome, modelo in (("entrada", ProvaEntrada), ("saida", ProvaSaida)):
        schema = modelo.model_json_schema()
        caminho = PASTA / f"{nome}.schema.json"
        caminho.write_text(
            json.dumps(schema, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    gerar()