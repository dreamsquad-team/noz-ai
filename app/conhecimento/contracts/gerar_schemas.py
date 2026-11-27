import json
from pathlib import Path

from agent.contract import CONTRATOS

PASTA = Path(__file__).parent


def gerar():
    for nome, modelo in CONTRATOS.items():
        caminho = PASTA / f"{nome}.schema.json"
        caminho.write_text(
            json.dumps(modelo.model_json_schema(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    gerar()
