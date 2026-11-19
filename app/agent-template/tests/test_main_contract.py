import asyncio
import inspect

import pytest

import main


class FakeResult:
    message = {"content": [{"text": "resposta final"}]}


class FakeAgent:
    async def invoke_async(self, prompt):
        return FakeResult()

    async def stream_async(self, prompt):
        yield {"event": {"contentBlockDelta": {"delta": {"text": "oi"}}}}
        yield {"sem_a_chave_event": True}
        yield {"event": {"contentBlockStart": {"start": {}}}}


class Ctx:
    """Dublê de contexto.

    O RequestContext real do SDK instalado
    (bedrock_agentcore/runtime/context.py) só tem session_id,
    request_headers e request — não tem `user_id`. Este dublê fabrica o
    atributo de propósito, para fixar a lógica de precedência que os testes
    abaixo cobrem: um caminho forward-compatible, não o comportamento atual
    em produção.
    """

    session_id = "sess-1"
    user_id = "user-1"


class CtxSemUsuario:
    session_id = "sess-1"


def _use_fake_agent(monkeypatch, registro=None):
    def fake_get(session_id, user_id):
        if registro is not None:
            registro["user_id"] = user_id
        return FakeAgent()

    monkeypatch.setattr(main, "get_or_create_agent", fake_get)


async def _collect(agen):
    return [event async for event in agen]


def test_stream_false_returns_a_plain_dict(monkeypatch):
    _use_fake_agent(monkeypatch)
    result = asyncio.run(main.invoke({"prompt": "oi", "stream": False}, Ctx()))
    assert result == {"text": "resposta final"}


def test_default_returns_an_async_generator(monkeypatch):
    _use_fake_agent(monkeypatch)
    result = asyncio.run(main.invoke({"prompt": "oi"}, Ctx()))
    assert inspect.isasyncgen(result)


def test_stream_true_returns_an_async_generator(monkeypatch):
    _use_fake_agent(monkeypatch)
    result = asyncio.run(main.invoke({"prompt": "oi", "stream": True}, Ctx()))
    assert inspect.isasyncgen(result)


def test_non_boolean_stream_value_does_not_disable_streaming(monkeypatch):
    """Só o booleano false liga o fallback: "" ou 0 não devem desligar o
    streaming por acidente."""
    _use_fake_agent(monkeypatch)
    for valor in ("", 0, "false", None):
        result = asyncio.run(main.invoke({"prompt": "oi", "stream": valor}, Ctx()))
        assert inspect.isasyncgen(result), f"valor {valor!r} desligou o streaming"


def test_stream_drops_malformed_events(monkeypatch):
    _use_fake_agent(monkeypatch)

    async def run():
        agen = await main.invoke({"prompt": "oi"}, Ctx())
        return await _collect(agen)

    eventos = asyncio.run(run())

    assert len(eventos) == 1
    assert "contentBlockDelta" in eventos[0]["event"]


def test_context_user_id_is_used(monkeypatch):
    """Cobre um caminho que o SDK instalado não exercita hoje: RequestContext
    não tem `user_id` (ver docstring de Ctx). Se um dia o SDK ganhar esse
    campo, este teste já fixa que ele deve ser preferido."""
    registro = {}
    _use_fake_agent(monkeypatch, registro)
    asyncio.run(main.invoke({"prompt": "oi", "stream": False}, Ctx()))
    assert registro["user_id"] == "user-1"


def test_payload_actor_id_is_the_fallback(monkeypatch):
    registro = {}
    _use_fake_agent(monkeypatch, registro)
    asyncio.run(
        main.invoke(
            {"prompt": "oi", "stream": False, "actor_id": "actor-42"},
            CtxSemUsuario(),
        )
    )
    assert registro["user_id"] == "actor-42"


def test_context_user_id_wins_over_payload_actor_id(monkeypatch):
    """Fixa a precedência de context.user_id sobre actor_id do payload — mas
    hoje o RequestContext do SDK instalado não tem `user_id` (ver docstring
    de Ctx), então na prática a identidade vem sempre de actor_id/default, e
    é forjável pelo chamador. Este teste cobre o caminho forward-compatible,
    não o comportamento atual em produção."""
    registro = {}
    _use_fake_agent(monkeypatch, registro)
    asyncio.run(
        main.invoke({"prompt": "oi", "stream": False, "actor_id": "actor-42"}, Ctx())
    )
    assert registro["user_id"] == "user-1"


def test_falls_back_to_default_user(monkeypatch):
    registro = {}
    _use_fake_agent(monkeypatch, registro)
    asyncio.run(main.invoke({"prompt": "oi", "stream": False}, CtxSemUsuario()))
    assert registro["user_id"] == "default-user"


# --- _extract_prompt: alias "input" e validação de prompt vazio/ausente ---


def test_extract_prompt_accepts_input_as_alias_for_prompt():
    assert main._extract_prompt({"input": "pergunta por alias"}) == "pergunta por alias"


def test_extract_prompt_prompt_wins_when_both_present():
    assert main._extract_prompt({"prompt": "P", "input": "I"}) == "P"


def test_extract_prompt_raises_when_neither_key_present():
    with pytest.raises(ValueError):
        main._extract_prompt({})


def test_extract_prompt_raises_on_empty_string_prompt():
    with pytest.raises(ValueError):
        main._extract_prompt({"prompt": ""})


# --- invoke: guarda de forma da resposta no fallback síncrono ---


def test_stream_false_with_malformed_result_raises_a_clear_error(monkeypatch):
    class FakeResultMalformado:
        message = {"content": []}

    class FakeAgentMalformado:
        async def invoke_async(self, prompt):
            return FakeResultMalformado()

    monkeypatch.setattr(
        main, "get_or_create_agent", lambda session_id, user_id: FakeAgentMalformado()
    )

    with pytest.raises(ValueError):
        asyncio.run(main.invoke({"prompt": "oi", "stream": False}, Ctx()))


# --- invoke: payload precisa ser validado antes de qualquer payload.get() ---


def test_non_dict_payload_raises_value_error_not_attribute_error(monkeypatch):
    _use_fake_agent(monkeypatch)
    with pytest.raises(ValueError):
        asyncio.run(main.invoke(["not", "a", "dict"], Ctx()))
