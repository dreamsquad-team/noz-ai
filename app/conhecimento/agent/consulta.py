"""O agente de Conhecimento responde a UMA consulta por vez (T08). Não guarda nada (D13).

Cada consulta é de uma pessoa, uma empresa, um conteúdo ou um grupo. O fluxo é código; o modelo só entra para extrair
o tema dos conteúdos (em lote, `tools/tema.py`). Para responder:

1. valida a consulta (`id_empresa` obrigatório, janela coerente);
2. lê do MCP só o necessário, dentro da empresa: eventos de UM usuário, conteúdos por ids, usuários de UMA tag;
3. extrai os temas necessários;
4. calcula o perfil em código (`agent/perfis.py`);
5. responde com a janela usada e `avisos` do que limitou ou degradou a resposta. Nada é gravado.

Limites por consulta (`Limites`): passou deles, a resposta usa os itens mais recentes e AVISA; nunca finge que cobriu tudo.
O que vale só durante a consulta (por exemplo, os temas já extraídos para montar um perfil de grupo) é descartado
ao final dela.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

from agent.contract import (
    ConsultaPerfilEmpresa,
    ConsultaPerfilGrupo,
    ConsultaPerfilUsuario,
    ConsultaTemaConteudo,
    PerfilEmpresa,
    PerfilGrupo,
    PerfilUsuario,
    TemaConteudo,
)
from agent.perfis import construir_perfil_empresa, construir_perfil_grupo, construir_perfil_usuario
from config.settings import settings
from tools.leitura import ErroIsolamento, ErroLeitura, Leitor
from tools.tema import GeradorLote, extrair_temas

logger = logging.getLogger(__name__)

MAX_AVISOS_GRUPO = 5


class ErroConsulta(RuntimeError):
    """A consulta não pôde ser respondida (entidade inexistente, MCP ou modelo indisponível). Mensagem segura."""


@dataclass(frozen=True)
class Limites:
    max_eventos: int
    max_conteudos: int
    max_usuarios_grupo: int
    janela_padrao_dias: int
    timeout_s: int

    @classmethod
    def das_configuracoes(cls) -> "Limites":
        return cls(
            max_eventos=settings.max_eventos,
            max_conteudos=settings.max_conteudos,
            max_usuarios_grupo=settings.max_usuarios_grupo,
            janela_padrao_dias=settings.janela_padrao_dias,
            timeout_s=settings.timeout_consulta_s,
        )


def _utc(dt: datetime | None) -> datetime | None:
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _janela(consulta, agora: datetime, limites: Limites) -> tuple[datetime, datetime]:
    ate = _utc(consulta.ate) or agora
    desde = _utc(consulta.desde) or ate - timedelta(days=limites.janela_padrao_dias)
    if ate <= desde:
        raise ErroConsulta("a janela é vazia: 'ate' deve ser posterior a 'desde'")
    return desde, ate


def responder(
    consulta,
    leitor: Leitor,
    gerar_tema: GeradorLote,
    agora: datetime | None = None,
    limites: Limites | None = None,
) -> BaseModel:
    """Responde a uma consulta. Levanta `ErroConsulta` com mensagem clara quando não dá."""
    agora = _utc(agora) or datetime.now(timezone.utc)
    limites = limites or Limites.das_configuracoes()
    try:
        if isinstance(consulta, ConsultaPerfilUsuario):
            desde, ate = _janela(consulta, agora, limites)
            return _perfil_usuario(consulta.id_empresa, consulta.id_usuario, desde, ate, leitor, gerar_tema, limites, {})
        if isinstance(consulta, ConsultaTemaConteudo):
            return _tema_conteudo(consulta, leitor, gerar_tema)
        if isinstance(consulta, ConsultaPerfilEmpresa):
            return _perfil_empresa(consulta, leitor, gerar_tema, limites)
        if isinstance(consulta, ConsultaPerfilGrupo):
            desde, ate = _janela(consulta, agora, limites)
            return _perfil_grupo(consulta, desde, ate, leitor, gerar_tema, limites)
    except ErroIsolamento as e:
        logger.error("isolamento violado pelo MCP: %s", e)
        raise ErroConsulta(f"consulta interrompida: {e}") from e
    except ErroLeitura as e:
        raise ErroConsulta(str(e)) from e
    except ValueError as e:  # contrato de perfis recusou dado de outra empresa/usuário
        logger.error("dado inconsistente no cálculo: %s", e)
        raise ErroConsulta("dado inconsistente recebido do MCP; consulta interrompida") from e
    raise ErroConsulta(f"consulta não suportada: {type(consulta).__name__}")


# --- perfil do usuário ---

def _perfil_usuario(emp, uid, desde, ate, leitor, gerar, limites, temas: dict[str, TemaConteudo]) -> PerfilUsuario:
    """`temas` é o que já foi extraído NESTA consulta (usado para não repetir trabalho num grupo)."""
    avisos: list[str] = []
    eventos = leitor.ler_eventos(emp, desde, ate, id_usuario=uid, max_itens=limites.max_eventos)
    if eventos.truncada:
        avisos.append(f"considerados só os {limites.max_eventos} eventos mais recentes, de {eventos.total_lido} na janela")
    if eventos.descartados:
        avisos.append(f"{eventos.descartados} evento(s) malformado(s) descartado(s)")

    # conteúdos citados, do mais recente para o mais antigo (o teto fica com os mais recentes)
    ids: list[str] = []
    for e in sorted(eventos.itens, key=lambda e: e.ocorrido_em, reverse=True):
        if e.id_conteudo and e.id_conteudo not in ids:
            ids.append(e.id_conteudo)
    if len(ids) > limites.max_conteudos:
        avisos.append(f"tema extraído só dos {limites.max_conteudos} conteúdos mais recentes, de {len(ids)} acessados")
        ids = ids[: limites.max_conteudos]

    faltam = [i for i in ids if i not in temas]
    if faltam:
        conteudos = leitor.ler_conteudos(emp, ids=faltam)
        inexistentes = len(set(faltam)) - len(conteudos.itens) - conteudos.descartados
        if inexistentes > 0:
            avisos.append(f"{inexistentes} conteúdo(s) citado(s) nos eventos não foram encontrados")
        if conteudos.descartados:
            avisos.append(f"{conteudos.descartados} conteúdo(s) malformado(s) descartado(s)")
        extraidos = extrair_temas(conteudos.itens, gerar)
        temas.update(extraidos.temas)
        avisos += extraidos.avisos

    return construir_perfil_usuario(emp, uid, eventos.itens, {i: temas[i] for i in ids if i in temas}, desde, ate, avisos)


# --- tema do conteúdo ---

def _tema_conteudo(consulta: ConsultaTemaConteudo, leitor, gerar) -> TemaConteudo:
    conteudos = leitor.ler_conteudos(consulta.id_empresa, ids=[consulta.id_conteudo])
    if not conteudos.itens:
        # a mesma mensagem para "não existe" e "é de outra empresa"
        raise ErroConsulta(f"conteúdo não encontrado: {consulta.id_conteudo}")
    extraidos = extrair_temas(conteudos.itens, gerar)
    if consulta.id_conteudo in extraidos.falhas:
        raise ErroConsulta(f"não foi possível extrair o tema do conteúdo agora ({'; '.join(extraidos.avisos)})")
    tema = extraidos.temas[consulta.id_conteudo]
    return tema.model_copy(update={"avisos": [*tema.avisos, *extraidos.avisos]})


# --- perfil da empresa ---

def _perfil_empresa(consulta: ConsultaPerfilEmpresa, leitor, gerar, limites) -> PerfilEmpresa:
    emp = consulta.id_empresa
    conteudos = leitor.ler_conteudos(emp, max_itens=limites.max_conteudos)
    avisos: list[str] = []
    if conteudos.truncada:
        avisos.append(f"considerados só os {limites.max_conteudos} conteúdos mais recentes, de {conteudos.total_lido}")
    if conteudos.descartados:
        avisos.append(f"{conteudos.descartados} conteúdo(s) malformado(s) descartado(s)")
    extraidos = extrair_temas(conteudos.itens, gerar)
    if conteudos.itens and not extraidos.temas:
        raise ErroConsulta(f"não foi possível extrair os temas agora ({'; '.join(extraidos.avisos)})")
    return construir_perfil_empresa(emp, list(extraidos.temas.values()), [*avisos, *extraidos.avisos])


# --- perfil do grupo ---

def _perfil_grupo(consulta: ConsultaPerfilGrupo, desde, ate, leitor, gerar, limites) -> PerfilGrupo:
    emp = consulta.id_empresa
    usuarios = leitor.ler_usuarios(emp, tag=consulta.tag, max_itens=limites.max_usuarios_grupo)
    avisos: list[str] = []
    if not usuarios.itens:
        return construir_perfil_grupo(emp, consulta.tag, [], desde, ate, [f"nenhum usuário com a tag {consulta.tag!r} na empresa"])
    if usuarios.truncada:
        avisos.append(f"considerados só {limites.max_usuarios_grupo} usuários do grupo, de {usuarios.total_lido}")

    temas: dict[str, TemaConteudo] = {}  # só desta consulta: evita extrair o mesmo tema para cada usuário
    perfis: list[PerfilUsuario] = []
    inicio = time.monotonic()
    ignorados = 0
    for i, u in enumerate(usuarios.itens):
        if time.monotonic() - inicio > limites.timeout_s:
            avisos.append(f"tempo esgotado: considerados {i} de {len(usuarios.itens)} usuários do grupo")
            break
        try:
            perfis.append(_perfil_usuario(emp, u.id_usuario, desde, ate, leitor, gerar, limites, temas))
        except ErroIsolamento:
            raise  # nunca é "falha de um usuário": o MCP vazou dado
        except ErroLeitura:
            ignorados += 1
    if ignorados:
        avisos.append(f"{ignorados} usuário(s) ignorado(s) por falha na leitura")
    if not perfis:
        raise ErroConsulta("não foi possível ler os dados de nenhum usuário do grupo")

    distintos = list(dict.fromkeys(a for p in perfis for a in p.avisos))
    avisos += distintos[:MAX_AVISOS_GRUPO]
    if len(distintos) > MAX_AVISOS_GRUPO:
        avisos.append(f"mais {len(distintos) - MAX_AVISOS_GRUPO} aviso(s) de usuários omitido(s)")
    return construir_perfil_grupo(emp, consulta.tag, perfis, desde, ate, avisos)
