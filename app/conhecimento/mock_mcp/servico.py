"""Lógica do MCP mockado, sem depender do servidor (testável direto).

Contrato provisório (o que o agente espera do MCP da NOZ):
- toda consulta exige `id_empresa`; nunca devolve dado de outra empresa;
- listas paginadas por cursor opaco: {"itens": [...], "proximo_cursor": str | None};
- leitura incremental: `atualizado_desde` (conteúdos) e `desde`/`ate` (eventos).
"""

from datetime import datetime, timezone

from mock_mcp import dados

LIMITE_PADRAO = 50
LIMITE_MAXIMO = 200


class ErroMcp(ValueError):
    """Erro de consulta com mensagem clara para o agente (sem stack trace)."""


def _empresa(id_empresa):
    if not isinstance(id_empresa, str) or not id_empresa.strip():
        raise ErroMcp("id_empresa é obrigatório")
    if not any(e["id_empresa"] == id_empresa for e in dados.EMPRESAS):
        raise ErroMcp(f"empresa não encontrada: {id_empresa}")
    return id_empresa


def _data(valor, nome):
    if valor is None or valor == "":
        return None
    try:
        dt = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError as e:
        raise ErroMcp(f"{nome} inválido (use ISO 8601): {valor}") from e
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _inicio(cursor):
    if cursor in (None, ""):
        return 0
    try:
        n = int(cursor)
    except (TypeError, ValueError) as e:
        raise ErroMcp(f"cursor inválido: {cursor}") from e
    if n < 0:
        raise ErroMcp(f"cursor inválido: {cursor}")
    return n


def _limite(limite):
    if limite is None:
        return LIMITE_PADRAO
    if not isinstance(limite, int) or limite < 1:
        raise ErroMcp("limite deve ser um inteiro maior que zero")
    return min(limite, LIMITE_MAXIMO)


def _paginar(itens, cursor, limite):
    ini = _inicio(cursor)
    lim = _limite(limite)
    fim = ini + lim
    return {"itens": itens[ini:fim], "proximo_cursor": str(fim) if fim < len(itens) else None}


def listar_empresas(cursor=None, limite=None):
    """Lista as empresas. É a única consulta sem `id_empresa`: o agente descobre os tenants por aqui."""
    return _paginar(list(dados.EMPRESAS), cursor, limite)


def listar_usuarios(id_empresa, cursor=None, limite=None):
    emp = _empresa(id_empresa)
    return _paginar([u for u in dados.USUARIOS if u["id_empresa"] == emp], cursor, limite)


def listar_conteudos(id_empresa, atualizado_desde=None, cursor=None, limite=None):
    emp = _empresa(id_empresa)
    desde = _data(atualizado_desde, "atualizado_desde")
    itens = [
        c
        for c in dados.CONTEUDOS
        if c["id_empresa"] == emp and (desde is None or _data(c["atualizado_em"], "atualizado_em") > desde)
    ]
    return _paginar(itens, cursor, limite)


def listar_eventos(id_empresa, desde=None, ate=None, cursor=None, limite=None):
    emp = _empresa(id_empresa)
    ini, fim = _data(desde, "desde"), _data(ate, "ate")
    if ini and fim and fim <= ini:
        raise ErroMcp("'ate' deve ser posterior a 'desde'")
    itens = []
    for e in dados.EVENTOS:
        if e["id_empresa"] != emp:
            continue
        quando = _data(e["ocorrido_em"], "ocorrido_em")
        if (ini is None or quando > ini) and (fim is None or quando <= fim):
            itens.append(e)
    return _paginar(itens, cursor, limite)
