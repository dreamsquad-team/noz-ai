import json
from pathlib import Path
from uuid import uuid4

import boto3

from agent.contract import ProvaEntrada, ProvaSaida

MODELO = "us.anthropic.claude-haiku-5-5"
LIMITE_CONFIANCA = 0.75
PASTA = Path(__file__).parent

SISTEMA = (
    "Você valida comprovações de desafios. Compare a evidência com as regras e responda "
    'APENAS um JSON: {"cumpre": true ou false, "confianca": número de 0 a 1, '
    '"justificativa": "motivo curto"}.'
)


def montar_entrada(arquivo):
    return ProvaEntrada(
        id_envio=str(uuid4()),
        id_desafio="desafio-compra-500",
        id_empresa="empresa-teste",
        tipo="foto",
        conteudo=f"notas/{arquivo}",
        descricao="Nota fiscal da minha compra",
        regras_desafio={
            "nome": "Compra acima de R$ 500",
            "descricao": "Gastar mais de R$ 500,00 em uma loja e enviar a nota fiscal",
            "tipo_medicao": "vezes",
        },
        contexto_extra=(
            "Ambiente de teste: as notas são fictícias e trazem a marca de documento de teste. "
            "Isso é esperado, avalie apenas o valor total da compra."
        ),
    )


def decidir(cumpre, confianca):
    if confianca < LIMITE_CONFIANCA:
        return "para_analise"
    return "aprovado" if cumpre else "reprovado"


def avaliar(arquivo):
    prova = montar_entrada(arquivo)
    imagem = (PASTA / prova.conteudo).read_bytes()
    texto = (
        f"Regras: {prova.regras_desafio.nome}. {prova.regras_desafio.descricao}.\n"
        f"Descrição do participante: {prova.descricao}\n"
        f"Contexto: {prova.contexto_extra}"
    )
    cliente = boto3.client("bedrock-runtime", region_name="us-east-1")
    resposta = cliente.converse(
        modelId=MODELO,
        system=[{"text": SISTEMA}],
        messages=[{"role": "user", "content": [
            {"image": {"format": "png", "source": {"bytes": imagem}}},
            {"text": texto},
        ]}],
        inferenceConfig={"maxTokens": 500},
    )
    blocos = resposta["output"]["message"]["content"]
    bruto = next(b["text"] for b in blocos if "text" in b)
    dados = json.loads(bruto[bruto.index("{"): bruto.rindex("}") + 1])
    return ProvaSaida(
        id_envio=prova.id_envio,
        status=decidir(dados["cumpre"], dados["confianca"]),
        confianca=dados["confianca"],
        justificativa=dados["justificativa"],
    )


if __name__ == "__main__":
    for arquivo in ("nf_acima.png", "nf_abaixo.png"):
        print(arquivo, "->", avaliar(arquivo).model_dump_json(indent=2))
