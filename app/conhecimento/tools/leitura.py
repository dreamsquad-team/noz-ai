"""Leitura dos dados da NOZ via MCP (T05).

Camada fina entre o agente e o MCP. O resto do código só conhece `Leitor` e os modelos de `agent/dominio.py`; o
formato do MCP (nomes das tools, paginação, campos) fica aqui. Trocar o mock pelo MCP real (T12) mexe neste arquivo
e em `agent/dominio.py`, e só.

O agente não guarda nada: cada consulta pede ao MCP só o necessário (eventos de UM usuário, conteúdos por ids,
usuários de UMA tag), sempre dentro de uma empresa.

O `Leitor` recebe um `Chamador`, uma função `(nome_da_tool, argumentos) -> payload`. Em produção é
`chamador_do_cliente(MCPClient)`; nos testes pode ser qualquer função.

Garantias:
- `id_empresa` é obrigatório e nenhum item de outra empresa passa (vazamento vira erro, não filtro silencioso);
- pagina até esgotar, com teto de páginas; estourar o teto ou repetir cursor é erro, nunca dado parcial;
- teto de itens (`max_itens`): passou dele, fica com os mais recentes e marca `Leitura.truncada`, para a resposta avisar;
- item malformado é descartado e contado (`Leitura.descartados`), com log do que foi descartado, sem derrubar a leitura;
- erro do MCP vira `ErroLeitura` com mensagem clara, sem stack trace do servidor.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from agent.dominio import Conteudo, Empresa, Evento, Usuario
from config.settings import settings

logger = logging.getLogger(__name__)

Chamador = Callable[[str, dict[str, Any]], Any]
T = TypeVar("T", bound=BaseModel)

IDS_POR_CHAMADA = 50  # conteúdos por ids são pedidos em blocos, para não estourar o limite do MCP


class ErroLeitura(RuntimeError):
    """Falha ao ler do MCP. A mensagem é segura para log e para o agente."""


class ErroIsolamento(ErroLeitura):
    """O MCP devolveu dado de outra empresa ou de outro usuário. Nunca é tratado como falha comum: aborta a consulta."""


@dataclass
class Leitura(Generic[T]):
    itens: list[T] = field(default_factory=list)
    descartados: int = 0  # itens malformados que não viraram modelo
    truncada: bool = False  # o teto de itens cortou a leitura (ficaram os mais recentes)
    total_lido: int = 0  # quantos itens o MCP devolveu antes do corte


def _iso(valor: datetime | str | None) -> str | None:
    if valor is None:
        return None
    return valor.isoformat() if isinstance(valor, datetime) else str(valor)


def _texto_obrigatorio(nome: str, valor: Any) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ErroLeitura(f"{nome} é obrigatório")
    return valor


class Leitor:
    def __init__(self, chamar: Chamador, max_paginas: int | None = None):
        self._chamar = chamar
        self._max_paginas = max_paginas or settings.mcp_max_paginas

    # --- leituras ---

    def ler_empresas(self) -> Leitura[Empresa]:
        return self._ler("listar_empresas", {}, Empresa, id_empresa=None)

    def ler_usuarios(self, id_empresa: str, tag: str | None = None, max_itens: int | None = None) -> Leitura[Usuario]:
        emp = _texto_obrigatorio("id_empresa", id_empresa)
        args = {"id_empresa": emp, "tag": _texto_obrigatorio("tag", tag) if tag is not None else None}
        leitura = self._ler("listar_usuarios", args, Usuario, emp)
        return self._limitar(leitura, max_itens, chave=lambda u: u.id_usuario)

    def ler_conteudos(
        self, id_empresa: str, ids: list[str] | None = None, max_itens: int | None = None
    ) -> Leitura[Conteudo]:
        """Conteúdos da empresa, todos ou só os `ids` (que não existem simplesmente não vêm)."""
        emp = _texto_obrigatorio("id_empresa", id_empresa)
        if ids is None:
            leitura = self._ler("listar_conteudos", {"id_empresa": emp}, Conteudo, emp)
        else:
            leitura = Leitura()
            unicos = list(dict.fromkeys(ids))
            for i in range(0, len(unicos), IDS_POR_CHAMADA):
                parte = self._ler(
                    "listar_conteudos", {"id_empresa": emp, "ids": unicos[i : i + IDS_POR_CHAMADA]}, Conteudo, emp
                )
                leitura.itens += parte.itens
                leitura.descartados += parte.descartados
                leitura.total_lido += parte.total_lido
        return self._limitar(leitura, max_itens, chave=lambda c: c.atualizado_em)

    def ler_eventos(
        self,
        id_empresa: str,
        desde: datetime | str | None = None,
        ate: datetime | str | None = None,
        id_usuario: str | None = None,
        max_itens: int | None = None,
    ) -> Leitura[Evento]:
        """Eventos da empresa na janela (desde, ate], todos ou só os de `id_usuario`. Com teto, ficam os mais recentes."""
        emp = _texto_obrigatorio("id_empresa", id_empresa)
        args = {
            "id_empresa": emp,
            "desde": _iso(desde),
            "ate": _iso(ate),
            "id_usuario": _texto_obrigatorio("id_usuario", id_usuario) if id_usuario is not None else None,
        }
        leitura = self._ler("listar_eventos", args, Evento, emp)
        if id_usuario is not None and any(e.id_usuario != id_usuario for e in leitura.itens):
            raise ErroIsolamento("listar_eventos: o MCP devolveu evento de outro usuário; leitura interrompida")
        return self._limitar(leitura, max_itens, chave=lambda e: e.ocorrido_em)

    # --- teto de itens ---

    @staticmethod
    def _limitar(leitura: Leitura[T], max_itens: int | None, chave) -> Leitura[T]:
        leitura.total_lido = leitura.total_lido or len(leitura.itens)
        if max_itens is not None and len(leitura.itens) > max_itens:
            leitura.itens = sorted(leitura.itens, key=chave)[-max_itens:]  # os mais recentes
            leitura.truncada = True
        return leitura

    # --- paginação ---

    def _ler(self, tool: str, args: dict, modelo: type[T], id_empresa: str | None) -> Leitura[T]:
        args = {k: v for k, v in args.items() if v is not None}
        leitura: Leitura[T] = Leitura()
        cursor: str | None = None
        vistos: set[str] = set()

        for _ in range(self._max_paginas):
            pagina = self._chamar(tool, {**args, **({"cursor": cursor} if cursor else {})})
            itens, proximo = self._desembrulhar(tool, pagina)
            leitura.total_lido += len(itens)
            for bruto in itens:
                self._aceitar(tool, bruto, modelo, id_empresa, leitura)
            if proximo is None:
                return leitura
            if proximo in vistos or proximo == cursor:
                raise ErroLeitura(f"{tool}: o MCP repetiu o cursor {proximo!r}; leitura interrompida")
            vistos.add(proximo)
            cursor = proximo

        raise ErroLeitura(
            f"{tool}: passou de {self._max_paginas} páginas sem terminar; leitura interrompida "
            "(aumente MCP_MAX_PAGINAS ou estreite a janela)"
        )

    @staticmethod
    def _desembrulhar(tool: str, pagina: Any) -> tuple[list, str | None]:
        if not isinstance(pagina, dict) or not isinstance(pagina.get("itens"), list):
            raise ErroLeitura(f"{tool}: resposta fora do formato esperado ({{itens, proximo_cursor}})")
        proximo = pagina.get("proximo_cursor")
        if proximo is not None and not isinstance(proximo, str):
            raise ErroLeitura(f"{tool}: proximo_cursor deve ser texto ou nulo")
        return pagina["itens"], proximo or None

    @staticmethod
    def _aceitar(tool: str, bruto: Any, modelo: type[T], id_empresa: str | None, leitura: Leitura[T]) -> None:
        if not isinstance(bruto, dict):
            leitura.descartados += 1
            logger.warning("%s: item descartado (não é objeto)", tool)
            return
        if id_empresa is not None and bruto.get("id_empresa") != id_empresa:
            # Violação do isolamento por empresa: nunca seguir adiante com esse dado.
            raise ErroIsolamento(f"{tool}: o MCP devolveu item de outra empresa (esperado {id_empresa!r}); leitura interrompida")
        try:
            leitura.itens.append(modelo.model_validate(bruto))
        except ValidationError as e:
            leitura.descartados += 1
            campos = sorted({".".join(map(str, err["loc"])) for err in e.errors()})
            logger.warning("%s: item descartado (campos inválidos: %s)", tool, ", ".join(campos))


# --- adaptador do cliente MCP (a única parte que fala o protocolo) ---

def chamador_do_cliente(cliente) -> Chamador:
    """Chamador sobre um `strands MCPClient` já iniciado (`with cliente:`)."""

    def chamar(nome: str, args: dict[str, Any]) -> Any:
        res = cliente.call_tool_sync(str(uuid.uuid4()), nome, args)
        texto = "".join(b.get("text", "") for b in res.get("content", []) if isinstance(b, dict))
        if res.get("status") == "error":
            raise ErroLeitura(f"{nome}: {texto or 'erro do MCP sem mensagem'}")
        try:
            return json.loads(texto)
        except json.JSONDecodeError as e:
            raise ErroLeitura(f"{nome}: resposta do MCP não é JSON") from e

    return chamar
