"""De onde o agente lê os dados: MCP real ou MCP mockado, sempre explícito (nunca um no lugar do outro)."""

import contextlib
from typing import Iterator

from mock_mcp import servico
from tools.leitura import ErroLeitura, Leitor, chamador_do_cliente


class ErroConfiguracao(RuntimeError):
    """O agente não está configurado para o que foi pedido."""


def _chamador_mock_em_processo(nome: str, args: dict):
    try:
        return getattr(servico, nome)(**args)
    except servico.ErroMcp as e:
        raise ErroLeitura(f"{nome}: {e}") from e


@contextlib.contextmanager
def abrir_leitor(modo: str) -> Iterator[Leitor]:
    """`mock`: dados fictícios em processo. `real`: MCP da NOZ pelo Gateway; sem endpoint, falha com mensagem clara."""
    if modo == "mock":
        yield Leitor(_chamador_mock_em_processo)
        return
    if modo != "real":
        raise ErroConfiguracao(f"modo inválido: {modo!r} (use 'real' ou 'mock')")

    from mcp_client.client import get_gateway_mcp_client

    cliente = get_gateway_mcp_client()
    if cliente is None:
        raise ErroConfiguracao(
            "modo 'real' exige um MCP utilizável: defina GATEWAY_URL (e credenciais AWS). "
            "Para dados fictícios, peça modo 'mock' explicitamente."
        )
    with cliente:
        yield Leitor(chamador_do_cliente(cliente))
