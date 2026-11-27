"""Entrypoint do agente de Conhecimento no AgentCore Runtime.

Responde a UMA consulta por invocação, sem guardar nada. O campo `tipo` escolhe a consulta:

    {"tipo": "perfil_usuario", "id_empresa": "emp-tintas", "id_usuario": "u-1", "modo": "real"}
    {"tipo": "perfil_empresa", "id_empresa": "emp-tintas"}
    {"tipo": "tema_conteudo",  "id_empresa": "emp-tintas", "id_conteudo": "c-1"}
    {"tipo": "perfil_grupo",   "id_empresa": "emp-tintas", "tag": "pintor"}

Sucesso: o perfil/tema em JSON (ver `contracts/`). Falha: {"erro": "mensagem clara"}, sem stack trace.
"""

import asyncio

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from pydantic import TypeAdapter, ValidationError

from agent.consulta import ErroConsulta, responder
from agent.contract import Consulta
from agent.fonte import ErroConfiguracao, abrir_leitor
from config.log import configure_logging
from config.settings import settings
from tools.tema import gerador_bedrock

configure_logging(settings.log_level)

app = BedrockAgentCoreApp()
log = app.logger

_CONSULTA = TypeAdapter(Consulta)


def _responder(consulta) -> dict:
    with abrir_leitor(consulta.modo) as leitor:
        return responder(consulta, leitor, gerador_bedrock()).model_dump(mode="json")


@app.entrypoint
async def invoke(payload, context=None):
    try:
        consulta = _CONSULTA.validate_python(payload)
    except ValidationError as e:
        detalhes = [{"campo": ".".join(map(str, x["loc"])), "msg": x["msg"]} for x in e.errors()]
        return {"erro": f"consulta inválida: {len(detalhes)} problema(s)", "detalhes": detalhes}
    try:
        # o fluxo é síncrono (cliente MCP e boto3 bloqueantes); fora do loop para não travar o runtime
        return await asyncio.to_thread(_responder, consulta)
    except (ErroConfiguracao, ErroConsulta) as e:
        log.error("consulta %s falhou: %s", consulta.tipo, e)
        return {"erro": str(e)}


if __name__ == "__main__":
    app.run()
