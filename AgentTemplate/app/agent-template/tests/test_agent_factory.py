import pytest

from agent import factory
from prompts.load import load_prompt


class FakeAgent:
    """Captura os kwargs que o build_agent monta, sem construir um Agent real."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs


@pytest.fixture
def captured(monkeypatch):
    """Isola o build_agent de Bedrock e de AgentCore Memory."""
    built = {}

    def fake_agent(**kwargs):
        built.update(kwargs)
        return FakeAgent(**kwargs)

    monkeypatch.setattr(factory, "Agent", fake_agent)
    monkeypatch.setattr(factory, "load_model", lambda: "modelo-falso")
    monkeypatch.setattr(
        factory, "get_memory_session_manager", lambda s, u: "sessao-falsa"
    )
    return built


def test_system_prompt_comes_from_the_prompt_file(captured):
    factory.build_agent("sess-1", "user-1", tools=[])
    assert captured["system_prompt"] == load_prompt()


def test_system_prompt_is_not_the_generated_placeholder(captured):
    factory.build_agent("sess-1", "user-1", tools=[])
    assert "helpful assistant" not in captured["system_prompt"]


def test_tools_are_passed_through_untouched(captured):
    sentinela = object()
    factory.build_agent("sess-1", "user-1", tools=[sentinela])
    assert captured["tools"] == [sentinela]


def test_model_and_session_manager_are_forwarded(captured):
    factory.build_agent("sess-1", "user-1", tools=[])
    assert captured["model"] == "modelo-falso"
    assert captured["session_manager"] == "sessao-falsa"


def test_session_and_user_reach_the_memory_manager(monkeypatch):
    vistos = {}
    captured = {}

    def fake_agent(**kwargs):
        captured.update(kwargs)
        return FakeAgent(**kwargs)

    def fake_memory(session_id, user_id):
        vistos["args"] = (session_id, user_id)
        return None

    monkeypatch.setattr(factory, "Agent", fake_agent)
    monkeypatch.setattr(factory, "load_model", lambda: "modelo-falso")
    monkeypatch.setattr(factory, "get_memory_session_manager", fake_memory)

    factory.build_agent("sess-1", "user-1", tools=[])

    assert vistos["args"] == ("sess-1", "user-1")
    assert captured["session_manager"] is None
