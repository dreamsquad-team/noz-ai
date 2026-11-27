"""Invoca o runtime do Conhecimento na AWS (AgentCore), sem depender da versão da AWS CLI.

    export AWS_PROFILE=noz AWS_DEFAULT_REGION=us-east-1
    uv run python scripts/invocar_runtime.py --tipo usuario --empresa emp-tintas --usuario u-emp-tintas-20
    uv run python scripts/invocar_runtime.py --tipo usuario --empresa emp-tintas --usuario u-emp-tintas-01
    uv run python scripts/invocar_runtime.py --tipo empresa --empresa emp-tintas
    uv run python scripts/invocar_runtime.py --tipo grupo   --empresa emp-tintas --tag pintor
    uv run python scripts/invocar_runtime.py --tipo conteudo --empresa emp-tintas --conteudo c-emp-tintas-005

Para testar LOCAL (agente na sua máquina, modelo na AWS): em um terminal, `AWS_PROFILE=noz uv run python main.py`; em
outro, os mesmos comandos acima com `--local`.

Os parâmetros são os mesmos de `scripts/testar.py consultar`. O ARN do runtime vem de `--arn`, da variável RUNTIME_ARN
ou, se nenhum dos dois existir, de `terraform output runtime_arn` no ambiente prod/conhecimento. `--dry-run` só mostra
o que seria enviado.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA))

import testar  # noqa: E402  (reaproveita a montagem e a validação da consulta e a checagem de conta)

TERRAFORM = PASTA.parent.parent.parent / "terraform" / "environments" / "prod" / "conhecimento"


def _arn(args) -> str | None:
    if args.arn or os.environ.get("RUNTIME_ARN"):
        return args.arn or os.environ["RUNTIME_ARN"]
    try:
        saida = subprocess.run(
            ["terraform", f"-chdir={TERRAFORM}", "output", "-raw", "runtime_arn"],
            capture_output=True, text=True, timeout=60, check=True,
        )
        return saida.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _invocar_local(payload: dict, porta: int) -> int:
    """POST no agente local. As credenciais AWS (para o Bedrock) são as do terminal ONDE O AGENTE FOI INICIADO."""
    import urllib.error
    import urllib.request

    url = f"http://127.0.0.1:{porta}/invocations"
    print("Agente local:", url)
    pedido = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST"
    )
    inicio = time.monotonic()
    try:
        with urllib.request.urlopen(pedido, timeout=300) as r:
            status, corpo = r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        status, corpo = e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        print(f"\nNão consegui falar com o agente local na porta {porta} ({e}).")
        print("Ele está rodando? Em outro terminal:  cd app/conhecimento && AWS_PROFILE=noz uv run python main.py")
        return 1
    _mostrar(status, corpo, time.monotonic() - inicio)
    return 0


def _mostrar(status, corpo: str, tempo: float) -> None:
    print(f"\n== resposta (HTTP {status}, {tempo:.2f}s) ==")
    try:
        print(json.dumps(json.loads(corpo), ensure_ascii=False, indent=2))
    except json.JSONDecodeError:
        print(corpo)


def main() -> int:
    p = argparse.ArgumentParser(description="Invoca o runtime do Conhecimento (na AWS ou local)")
    p.add_argument("--tipo", choices=["usuario", "empresa", "conteudo", "grupo"], required=True)
    p.add_argument("--empresa", required=True)
    p.add_argument("--usuario")
    p.add_argument("--conteudo", action="append")
    p.add_argument("--tag")
    p.add_argument("--desde")
    p.add_argument("--ate")
    p.add_argument("--modo", choices=["mock", "real"], default="mock")
    p.add_argument("--arn", help="ARN do runtime (padrão: RUNTIME_ARN ou terraform output)")
    p.add_argument("--local", action="store_true", help="chama o agente rodando na sua máquina (uv run python main.py) em vez do runtime na AWS")
    p.add_argument("--porta", type=int, default=8080, help="porta do agente local (padrão 8080)")
    p.add_argument("--dry-run", action="store_true", help="só mostra o payload, não invoca")
    args = p.parse_args()

    try:
        consulta = testar._montar_consulta(args)
    except Exception as e:  # validação do contrato ou argumento faltando
        print(f"Consulta inválida: {e}")
        return 2
    payload = consulta.model_dump(mode="json", exclude_none=True)

    print("Payload:", json.dumps(payload, ensure_ascii=False))
    if args.dry_run:
        return 0

    if args.local:
        return _invocar_local(payload, args.porta)

    if not testar._conferir_conta():
        return 1
    arn = _arn(args)
    if not arn:
        print("Não achei o ARN do runtime. Use --arn, defina RUNTIME_ARN ou rode no ambiente com acesso ao state do Terraform.")
        return 2
    print("Runtime:", arn)

    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    cliente = boto3.client("bedrock-agentcore", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    inicio = time.monotonic()
    try:
        resposta = cliente.invoke_agent_runtime(
            agentRuntimeArn=arn,
            runtimeSessionId=str(uuid.uuid4()),  # 36 caracteres; o mínimo da API é 33
            contentType="application/json",
            accept="application/json",
            payload=json.dumps(payload).encode("utf-8"),
        )
        corpo = resposta["response"].read().decode("utf-8")
    except ClientError as e:
        erro = e.response.get("Error", {})
        print(f"\nA AWS recusou a chamada: {erro.get('Code')}: {erro.get('Message')}")
        return 1
    except BotoCoreError as e:
        print(f"\nFalha ao chamar a AWS: {type(e).__name__}: {e}")
        return 1
    tempo = time.monotonic() - inicio

    _mostrar(resposta.get("statusCode"), corpo, tempo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
