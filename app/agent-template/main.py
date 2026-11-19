from typing import Any
from strands import tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from config.log import configure_logging
from config.settings import settings
from mcp_client.client import get_gateway_mcp_client
from agent.factory import build_agent

configure_logging(settings.log_level)

app = BedrockAgentCoreApp()
log = app.logger

_INLINE_FUNCTION_NAMES = set()


# TROCAR POR PROJETO: tool de exemplo. Apague-a (e o `add_numbers` em
# `tools = build_tools(...)` abaixo) ou substitua pelas tools do cliente.
@tool
def add_numbers(a: int, b: int) -> int:
    """Return the sum of two numbers"""
    return a + b


def build_tools(local_tools: list, gateway_client) -> list:
    """Junta as tools locais às do Gateway, quando há um gateway utilizável.

    O `gateway_client` entra na lista como ele mesmo: desde o Strands 1.53 o
    `MCPClient` é um `ToolProvider`, então o Agent abre a sessão, lista as
    tools e — graças ao `continue_on_error` que `get_gateway_mcp_client()`
    liga — segue com `[]` se o gateway estiver fora do ar, em vez de derrubar
    a invocação.

    O None precisa ser filtrado: `get_gateway_mcp_client()` devolve None
    quando não há gateway configurado, e um None na lista faz o registry do
    Strands logar "unrecognized tool specification" a cada montagem de agente.
    """
    return [*local_tools, gateway_client] if gateway_client else list(local_tools)


# Construído uma vez por processo, e não por invocação: o MCPClient é o mesmo
# objeto para todos os agentes em cache, e reabrir a conexão a cada chamada
# custaria um handshake por invocação.
tools = build_tools([add_numbers], get_gateway_mcp_client())


def agent_factory():
    cache = {}

    def get_or_create_agent(session_id, user_id):
        key = f"{session_id}/{user_id}"
        if key not in cache:
            cache[key] = build_agent(session_id, user_id, tools)
        return cache[key]

    return get_or_create_agent


get_or_create_agent = agent_factory()


def strip_trailing_tool_use(messages: Any) -> list[dict]:
    """Strip toolUse blocks from the tail until the last message has none."""
    if not isinstance(messages, list):
        raise ValueError("messages must be a list")

    messages = list(messages)
    while messages:
        last = messages[-1]
        if not isinstance(last, dict):
            raise ValueError("each message must be an object")
        original_content = last.get("content", [])
        if not isinstance(original_content, list) or not all(
            isinstance(block, dict) for block in original_content
        ):
            raise ValueError(
                "each message content value must be a list of content blocks"
            )

        content = [block for block in original_content if "toolUse" not in block]
        if len(content) == len(original_content):
            break
        if content:
            messages[-1] = {**last, "content": content}
            break
        messages.pop()

    return messages


def _extract_prompt(payload: dict):
    """Accept validated harness messages, tool results, or a plain prompt string."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    if "messages" in payload:
        return strip_trailing_tool_use(payload["messages"])
    if "tool_results" in payload:
        tool_results = payload["tool_results"]
        if not isinstance(tool_results, list) or not all(
            isinstance(tool_result, dict)
            and isinstance(tool_result.get("toolUseId"), str)
            for tool_result in tool_results
        ):
            raise ValueError(
                "tool_results must contain objects with a toolUseId string"
            )
        return [
            {
                "role": "user",
                "content": [
                    {
                        "toolResult": {
                            "toolUseId": tr["toolUseId"],
                            "status": tr.get("status", "success"),
                            "content": tr.get("content", []),
                        }
                    }
                    for tr in tool_results
                ],
            }
        ]
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt:
        prompt = payload.get("input")
    if not isinstance(prompt, str) or not prompt:
        raise ValueError("prompt (or input) must be a non-empty string")
    return prompt


def _has_inline_function_call(messages) -> bool:
    """Return True if messages contains an assistant toolUse for an inline function tool."""
    if not _INLINE_FUNCTION_NAMES or not isinstance(messages, list):
        return False
    for msg in messages:
        if msg.get("role") == "assistant":
            for block in msg.get("content", []):
                if (
                    isinstance(block, dict)
                    and block.get("toolUse", {}).get("name") in _INLINE_FUNCTION_NAMES
                ):
                    return True
    return False


def _is_inline_function_call(event: dict) -> bool:
    """Check if a contentBlockStart event is for an inline function tool."""
    if not _INLINE_FUNCTION_NAMES:
        return False
    cbs = event.get("contentBlockStart", {})
    start = cbs.get("start", {})
    tool_use = start.get("toolUse") if isinstance(start, dict) else None
    return tool_use is not None and tool_use.get("name") in _INLINE_FUNCTION_NAMES


@app.entrypoint
async def invoke(payload, context):
    log.info("Invoking Agent.....")

    prompt = _extract_prompt(payload)

    session_id = getattr(context, "session_id", "default-session")
    # O RequestContext do SDK instalado (bedrock_agentcore/runtime/context.py)
    # não tem `user_id` — só session_id, request_headers e request. Esse
    # getattr fica como compatibilidade futura; na prática, hoje, a
    # identidade vem sempre de payload["actor_id"] (ou do default), e é
    # portanto forjável pelo chamador. A fonte não forjável que já existe é
    # context.request_headers["Authorization"]; ligar essa identidade é o
    # trabalho do access_token adiado (ver spec da migração), e é ali que a
    # decisão de confiança na identidade deve ser tomada.
    user_id = (
        getattr(context, "user_id", None) or payload.get("actor_id") or "default-user"
    )
    agent = get_or_create_agent(session_id, user_id)

    # Identidade com False de propósito: só o booleano explícito liga o
    # fallback. "" ou 0 não devem desligar o streaming por acidente.
    if payload.get("stream", True) is False:
        result = await agent.invoke_async(prompt)
        try:
            return {"text": result.message["content"][0]["text"]}
        except (KeyError, IndexError, TypeError) as e:
            log.error(f"malformed agent result: {e}", exc_info=True)
            raise ValueError(f"malformed agent result: {e}") from e

    return _stream(agent, prompt)


async def _stream(agent, prompt):
    """Async generator: o SDK inspeciona o tipo do retorno da invoke e
    responde text/event-stream quando é isto."""
    async for event in agent.stream_async(prompt):
        if not isinstance(event, dict) or "event" not in event:
            continue
        cbs = event["event"].get("contentBlockStart")
        if cbs is not None and not cbs.get("start"):
            continue
        yield event


if __name__ == "__main__":
    app.run()
