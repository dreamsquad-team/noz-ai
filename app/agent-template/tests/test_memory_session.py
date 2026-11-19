from memory import session


class FakeManager:
    """Substitui o AgentCoreMemorySessionManager real, que abriria cliente boto."""

    def __init__(self, config, region):
        self.config = config
        self.region = region


def test_returns_none_without_memory_id(monkeypatch):
    monkeypatch.setattr(session.settings, "memory_id", None)
    assert session.get_memory_session_manager("sess-1", "actor-1") is None


def test_passes_settings_values_through(monkeypatch):
    monkeypatch.setattr(session, "AgentCoreMemorySessionManager", FakeManager)
    monkeypatch.setattr(session.settings, "memory_id", "mem-123")
    monkeypatch.setattr(session.settings, "aws_region", "us-east-1")

    manager = session.get_memory_session_manager("sess-1", "actor-1")

    assert manager.region == "us-east-1"
    assert manager.config.memory_id == "mem-123"
    assert manager.config.session_id == "sess-1"
    assert manager.config.actor_id == "actor-1"


def test_synthesizes_session_id_when_absent(monkeypatch):
    """Chamadas OAuth/CUSTOM_JWT chegam sem session header, e o
    AgentCoreMemoryConfig recusa None."""
    monkeypatch.setattr(session, "AgentCoreMemorySessionManager", FakeManager)
    monkeypatch.setattr(session.settings, "memory_id", "mem-123")

    manager = session.get_memory_session_manager(None, "actor-1")

    assert manager.config.session_id
