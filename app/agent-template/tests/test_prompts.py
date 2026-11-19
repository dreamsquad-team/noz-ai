import pytest

from prompts.load import load_prompt


def test_load_prompt_returns_v1_content():
    prompt = load_prompt()
    assert prompt.strip()
    assert "NUNCA invente números" in prompt


def test_load_prompt_is_not_the_generated_placeholder():
    """Guarda de regressão: o main.py gerado usava um prompt genérico
    hardcoded. Se ele voltar, este teste cai."""
    assert "helpful assistant" not in load_prompt()


def test_load_prompt_accepts_explicit_version():
    assert load_prompt("v1") == load_prompt()


def test_load_prompt_unknown_version_raises():
    with pytest.raises(FileNotFoundError):
        load_prompt("v99")
