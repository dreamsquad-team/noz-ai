"""Construção dos perfis (T07). Código puro e determinístico: sem modelo, sem rede, sem relógio, sem estado.

O agente não guarda nada e não pontua nada: cada perfil é uma análise estruturada, calculada na hora, dos dados da NOZ.
Mesmos dados, mesmo perfil.

O que cada perfil diz (só fatos, nenhum peso):
- usuário: por assunto, quantos eventos (e de que tipo) o usuário teve sobre conteúdos com aquele assunto na janela,
  quando foi o último e quais eventos sustentam (até `MAX_EVIDENCIAS`, os mais recentes). Canal e dispositivo mais usados;
- empresa: por assunto, em quantos conteúdos ele aparece e quais (até `MAX_EVIDENCIAS`);
- grupo: por assunto, quantos usuários do grupo o têm e eventos que o sustentam.

O assunto de cada conteúdo vem do tema (`tools/tema.py`). Evento sem conteúdo, de conteúdo desconhecido ou sem tema não
gera assunto (mas conta para canal, dispositivo e `eventos_considerados`). Sem evidência, sem assunto.
A ordem é sempre: mais eventos (ou conteúdos, ou usuários) primeiro; empate pelo mais recente e depois pelo nome.
"""

from collections import Counter, defaultdict
from datetime import datetime

from agent.contract import (
    InteresseGrupo,
    InteresseUsuario,
    PerfilEmpresa,
    PerfilGrupo,
    PerfilUsuario,
    TemaConteudo,
    TemaEmpresa,
)
from agent.dominio import Evento

MAX_TOPICOS = 20  # assuntos listados por perfil; passou disso, os mais frequentes ficam e um aviso é acrescentado
MAX_EVIDENCIAS = 5


def _mais_comum(valores: list[str | None]) -> str | None:
    contagem = Counter(v for v in valores if v)
    if not contagem:
        return None
    # desempate alfabético: o resultado não depende da ordem de chegada
    return sorted(contagem.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def _limitar(itens: list, avisos: list[str], o_que: str) -> list:
    if len(itens) > MAX_TOPICOS:
        avisos.append(f"listados só os {MAX_TOPICOS} assuntos mais frequentes, de {len(itens)} {o_que}")
    return itens[:MAX_TOPICOS]


def construir_perfil_usuario(
    id_empresa: str,
    id_usuario: str,
    eventos: list[Evento],
    temas: dict[str, TemaConteudo],
    desde: datetime,
    ate: datetime,
    avisos: list[str] | None = None,
) -> PerfilUsuario:
    """Perfil do usuário a partir dos `eventos` da janela (desde, ate]. `temas` mapeia id_conteudo -> tema."""
    for e in eventos:
        if e.id_empresa != id_empresa or e.id_usuario != id_usuario:
            raise ValueError("evento de outra empresa ou outro usuário no perfil de %s/%s" % (id_empresa, id_usuario))
    for t in temas.values():
        if t.id_empresa != id_empresa:
            raise ValueError("tema de outra empresa no perfil de %s/%s" % (id_empresa, id_usuario))

    por_topico: dict[str, list[Evento]] = defaultdict(list)
    for e in eventos:
        tema = temas.get(e.id_conteudo) if e.id_conteudo else None
        for topico in dict.fromkeys(tema.topicos if tema else []):
            por_topico[topico].append(e)

    interesses = []
    for topico, evs in por_topico.items():
        recentes = sorted(evs, key=lambda e: (e.ocorrido_em, e.id_evento), reverse=True)
        interesses.append(
            InteresseUsuario(
                topico=topico,
                eventos=len(evs),
                por_tipo=dict(sorted(Counter(e.tipo for e in evs).items())),
                ultimo_evento_em=recentes[0].ocorrido_em,
                evidencias=[e.id_evento for e in recentes[:MAX_EVIDENCIAS]],
            )
        )
    interesses.sort(key=lambda i: (-i.eventos, -i.ultimo_evento_em.timestamp(), i.topico))

    avisos = list(avisos or [])
    return PerfilUsuario(
        id_empresa=id_empresa,
        id_usuario=id_usuario,
        interesses=_limitar(interesses, avisos, "encontrados"),
        canal_preferido=_mais_comum([e.canal for e in eventos]),
        dispositivo_preferido=_mais_comum([e.dispositivo for e in eventos]),
        janela_desde=desde,
        janela_ate=ate,
        eventos_considerados=len(eventos),
        avisos=avisos,
    )


def construir_perfil_empresa(id_empresa: str, temas: list[TemaConteudo], avisos: list[str] | None = None) -> PerfilEmpresa:
    """Assuntos sobre os quais a empresa publica, a partir dos temas dos seus conteúdos."""
    por_topico: dict[str, list[str]] = defaultdict(list)
    for t in sorted(temas, key=lambda t: t.id_conteudo):
        if t.id_empresa != id_empresa:
            raise ValueError("tema de outra empresa no perfil da empresa %s" % id_empresa)
        for topico in dict.fromkeys(t.topicos):
            por_topico[topico].append(t.id_conteudo)

    assuntos = [
        TemaEmpresa(topico=topico, conteudos=len(ids), evidencias=ids[:MAX_EVIDENCIAS]) for topico, ids in por_topico.items()
    ]
    assuntos.sort(key=lambda a: (-a.conteudos, a.topico))

    avisos = list(avisos or [])
    return PerfilEmpresa(
        id_empresa=id_empresa,
        temas=_limitar(assuntos, avisos, "encontrados"),
        conteudos_considerados=len(temas),
        avisos=avisos,
    )


def construir_perfil_grupo(
    id_empresa: str,
    tag: str,
    perfis: list[PerfilUsuario],
    desde: datetime,
    ate: datetime,
    avisos: list[str] | None = None,
) -> PerfilGrupo:
    """Assuntos presentes nos usuários do grupo: por assunto, quantos usuários o têm."""
    for p in perfis:
        if p.id_empresa != id_empresa:
            raise ValueError("perfil de outra empresa no grupo %s/%s" % (id_empresa, tag))

    usuarios: dict[str, int] = defaultdict(int)
    eventos: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
    for p in perfis:
        for i in p.interesses:
            usuarios[i.topico] += 1
            eventos[i.topico].append((i.ultimo_evento_em, i.evidencias[0]))  # o evento mais recente de cada usuário

    assuntos = []
    for topico, n in usuarios.items():
        recentes = sorted(eventos[topico], key=lambda x: (x[0], x[1]), reverse=True)
        assuntos.append(
            InteresseGrupo(
                topico=topico, usuarios=n, evidencias=list(dict.fromkeys(ev for _, ev in recentes))[:MAX_EVIDENCIAS]
            )
        )
    ultimo = {t: max(d for d, _ in v) for t, v in eventos.items()}
    assuntos.sort(key=lambda a: (-a.usuarios, -ultimo[a.topico].timestamp(), a.topico))

    avisos = list(avisos or [])
    return PerfilGrupo(
        id_empresa=id_empresa,
        tag=tag,
        usuarios_considerados=len(perfis),
        interesses=_limitar(assuntos, avisos, "encontrados"),
        janela_desde=desde,
        janela_ate=ate,
        avisos=avisos,
    )
