"""O template não pode carregar resíduo de cliente.

Este arquivo existe porque o resíduo entra por um caminho previsível: alguém
porta código de um projeto que já está em produção e traz junto o nome do
cliente, um id de conta, um bucket, o modelo que ele escolheu. Cada um desses
é invisível numa revisão rápida e só aparece quando o *próximo* cliente abre o
arquivo e encontra o nome do anterior — ou pior, quando um id de conta alheio
vai parar numa policy.

Ao reaproveitar o template para um cliente novo, NÃO acrescente o nome dele
aqui. Acrescente o nome do cliente que passou pelo template e deixou rastro.
"""

from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[3]  # AgentTemplate/

# Só extensões de conteúdo do projeto. AGENTS.md e .llm-context/ são gerados
# pelo CLI e falam de "insights" como feature da AWS, não de cliente.
EXTENSIONS = {".py", ".txt", ".json", ".toml"}
SCANNED = ("agentcore/agentcore.json", "agentcore/aws-targets.json", "app", "lambda")
SKIP_DIRS = {".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules"}
SKIP_NAMES = {"uv.lock", "test_template_is_agnostic.py"}

# (rastro, o que ele seria)
RESIDUE = (
    ("fazero", "nome de cliente"),
    ("fazerorcamento", "nome de cliente"),
    ("orçamento", "domínio de cliente"),
    ("orcamento", "domínio de cliente"),
    ("insightsagent", "nome de runtime de cliente"),
    ("966084228276", "id de conta AWS de cliente"),
    ("gpt-5.6-luna", "modelo escolhido por um cliente"),
    ("bucket-teste", "bucket de cliente"),
)


def _files():
    for entry in SCANNED:
        root = PROJECT / entry
        if root.is_file():
            yield root
            continue
        for path in root.rglob("*"):
            if (
                path.is_file()
                and path.suffix in EXTENSIONS
                and path.name not in SKIP_NAMES
                and not (set(path.relative_to(PROJECT).parts) & SKIP_DIRS)
            ):
                yield path


@pytest.mark.parametrize("trace,what", RESIDUE)
def test_no_client_residue(trace, what):
    found = [
        f"{path.relative_to(PROJECT)}:{n}"
        for path in _files()
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if trace in line.lower()
    ]
    assert not found, f"{what} ({trace!r}) em: {', '.join(found)}"
