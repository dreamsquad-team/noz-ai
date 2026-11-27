"""Servidor MCP mockado da NOZ (contrato provisório).

Uso local:
    uv run python -m mock_mcp.server                 # stdio
    uv run python -m mock_mcp.server --http 8765     # HTTP em http://127.0.0.1:8765/mcp
"""

import sys

from mcp.server.fastmcp import FastMCP

from mock_mcp import servico

mcp = FastMCP("noz-mock", host="127.0.0.1")


@mcp.tool()
def listar_empresas(cursor: str | None = None, limite: int | None = None) -> dict:
    """Lista as empresas (tenants). Resposta: {itens, proximo_cursor}."""
    return servico.listar_empresas(cursor, limite)


@mcp.tool()
def listar_usuarios(id_empresa: str, cursor: str | None = None, limite: int | None = None) -> dict:
    """Lista os usuários de UMA empresa (id_empresa é obrigatório)."""
    return servico.listar_usuarios(id_empresa, cursor, limite)


@mcp.tool()
def listar_conteudos(
    id_empresa: str,
    atualizado_desde: str | None = None,
    cursor: str | None = None,
    limite: int | None = None,
) -> dict:
    """Lista conteúdos de UMA empresa. `atualizado_desde` (ISO 8601) faz leitura incremental."""
    return servico.listar_conteudos(id_empresa, atualizado_desde, cursor, limite)


@mcp.tool()
def listar_eventos(
    id_empresa: str,
    desde: str | None = None,
    ate: str | None = None,
    cursor: str | None = None,
    limite: int | None = None,
) -> dict:
    """Lista eventos de UMA empresa no período (desde, ate], em ordem cronológica."""
    return servico.listar_eventos(id_empresa, desde, ate, cursor, limite)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--http":
        mcp.settings.port = int(argv[1]) if len(argv) > 1 else 8765
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
