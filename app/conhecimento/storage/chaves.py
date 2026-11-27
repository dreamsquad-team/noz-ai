"""Chaves da tabela de perfis (DynamoDB).

Toda chave começa com o id da empresa: é isso que mantém o isolamento por tenant
no armazenamento. Nenhuma função aqui aceita `empresa_id` vazio e nenhum id pode
conter o separador, para que `A#...` nunca colida com outra empresa.

Modelo (ver terraform/modules/perfis-dynamodb/README.md):
    PK = "<empresa_id>#<tipo>#<id>"     SK = "ATUAL" (versão vigente) | "HIST#<iso8601>"
    GSI por-empresa: empresa_id (hash) + tipo_id = "<tipo>#<id>" (range)
"""

from enum import Enum

SEPARADOR = "#"
SK_ATUAL = "ATUAL"
SK_HIST = "HIST"


class Tipo(str, Enum):
    USUARIO = "usuario"
    EMPRESA = "empresa"
    CONTEUDO = "conteudo"
    GRUPO = "grupo"


def _validar(nome: str, valor: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{nome} é obrigatório")
    if SEPARADOR in valor:
        raise ValueError(f"{nome} não pode conter {SEPARADOR!r}")
    return valor


def tipo_id(tipo: Tipo, id_: str) -> str:
    """Parte do range do índice por empresa: '<tipo>#<id>'."""
    return f"{Tipo(tipo).value}{SEPARADOR}{_validar('id', id_)}"


def pk(empresa_id: str, tipo: Tipo, id_: str) -> str:
    """Chave de partição: sempre prefixada pelo id da empresa."""
    return f"{_validar('empresa_id', empresa_id)}{SEPARADOR}{tipo_id(tipo, id_)}"


def sk_atual() -> str:
    return SK_ATUAL


def sk_hist(iso8601: str) -> str:
    return f"{SK_HIST}{SEPARADOR}{_validar('iso8601', iso8601)}"


def chave(empresa_id: str, tipo: Tipo, id_: str, sk: str = SK_ATUAL) -> dict:
    """Key completa para GetItem/UpdateItem."""
    return {"PK": pk(empresa_id, tipo, id_), "SK": sk}


def atributos_indexados(empresa_id: str, tipo: Tipo, id_: str) -> dict:
    """Atributos que todo item precisa para entrar no índice por empresa."""
    return {"empresa_id": _validar("empresa_id", empresa_id), "tipo_id": tipo_id(tipo, id_)}


def empresa_da_chave(pk_: str) -> str:
    """Empresa dona de uma PK (para conferir que o item lido é da empresa pedida)."""
    return pk_.split(SEPARADOR, 1)[0]
