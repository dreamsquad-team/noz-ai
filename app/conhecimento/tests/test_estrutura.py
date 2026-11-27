from config.settings import Settings


def test_settings_sem_gateway_nem_memoria(monkeypatch):
    monkeypatch.delenv("GATEWAY_URL", raising=False)
    monkeypatch.delenv("GATEWAY_URL", raising=False)
    s = Settings(_env_file=None)
    assert s.gateway_url is None
    assert not hasattr(s, "memory_id")


def test_prompt_carrega():
    from prompts.load import load_prompt

    assert load_prompt()
