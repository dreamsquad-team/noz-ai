from pathlib import Path

# Resolvido a partir do __file__ e não do CWD: sob CodeZip o código é extraído
# junto das dependências, e o v1.txt viaja ao lado deste módulo.
_PROMPTS_DIR = Path(__file__).resolve().parent


def load_prompt(version: str = "v1") -> str:
    """Lê o system prompt versionado que viaja junto deste módulo."""
    return (_PROMPTS_DIR / f"{version}.txt").read_text(encoding="utf-8")
