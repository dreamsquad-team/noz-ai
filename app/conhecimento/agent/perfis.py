"""Construção dos perfis (T07). Código puro e determinístico: sem modelo, sem rede, sem relógio, sem estado.

O agente não guarda nada: cada perfil é calculado na hora, a partir dos eventos da janela e dos temas dos conteúdos
acessados. Mesmos dados, mesmo perfil.

Como o interesse é calculado:
- cada evento sobre um conteúdo que tem tema soma pontos a cada tópico do tema: `PESO_EVENTO[tipo]` (comentar vale
  mais que clicar), reduzidos pela idade do evento (meia-vida de `MEIA_VIDA_DIAS` dias, contada até o fim da janela);
- o peso do interesse (0 a 1) é `1 - exp(-pontos / K_SATURACAO)`: um evento isolado dá pouco peso, vários dão
  mais, e nunca passa de 1;
- evidência: ids dos eventos mais recentes que sustentam o tópico. Sem evidência, sem interesse;
- perfil da empresa: tópicos dos temas dos conteúdos que ela publica, pesados pela quantidade de conteúdos;
- perfil do grupo: peso médio do tópico entre os usuários do grupo (quem não tem o tópico conta 0).

⚠️ Os números abaixo (pesos, meia-vida, saturação) são pontos de partida, para calibrar na avaliação (T13).
"""

import math
from collections import Counter, defaultdict
from datetime import datetime

from agent.contract import Interesse, PerfilEmpresa, PerfilGrupo, PerfilUsuario, TemaConteudo
from agent.dominio import Evento

PESO_EVENTO = {"acesso": 1.0, "clique": 1.0, "comentario": 2.0}
MEIA_VIDA_DIAS = 30.0
K_SATURACAO = 10.0  # ~10 pontos (≈10 eventos recentes) dão peso 0,63; com 3, tudo saturava em 1,0 no mock
MAX_INTERESSES = 10
MIN_PESO = 0.05
MAX_EVIDENCIAS = 5


def peso_de_pontos(pontos: float) -> float:
    return round(1 - math.exp(-pontos / K_SATURACAO), 2)


def decaimento(de: datetime, para: datetime) -> float:
    """Fator entre 0 e 1 pela idade; datas fora de ordem não aumentam o valor."""
    dias = max(0.0, (para - de).total_seconds() / 86400)
    return 0.5 ** (dias / MEIA_VIDA_DIAS)


def _mais_comum(valores: list[str | None]) -> str | None:
    contagem = Counter(v for v in valores if v)
    if not contagem:
        return None
    # desempate alfabético: o resultado não depende da ordem de chegada
    return sorted(contagem.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def construir_perfil_usuario(
    id_empresa: str,
    id_usuario: str,
    eventos: list[Evento],
    temas: dict[str, TemaConteudo],
    desde: datetime,
    ate: datetime,
    avisos: list[str] | None = None,
) -> PerfilUsuario:
    """Perfil do usuário a partir dos `eventos` da janela (desde, ate].

    `temas` mapeia id_conteudo -> tema. Evento sem conteúdo, de conteúdo desconhecido ou sem tema não gera
    interesse (mas conta para canal e dispositivo).
    """
    for e in eventos:
        if e.id_empresa != id_empresa or e.id_usuario != id_usuario:
            raise ValueError("evento de outra empresa ou outro usuário no perfil de %s/%s" % (id_empresa, id_usuario))
    for t in temas.values():
        if t.id_empresa != id_empresa:
            raise ValueError("tema de outra empresa no perfil de %s/%s" % (id_empresa, id_usuario))

    pontos: dict[str, float] = defaultdict(float)
    evidencias: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
    for e in eventos:
        tema = temas.get(e.id_conteudo) if e.id_conteudo else None
        if tema is None:
            continue
        ponto = PESO_EVENTO[e.tipo] * decaimento(e.ocorrido_em, ate)
        for topico in tema.topicos:
            pontos[topico] += ponto
            evidencias[topico].append((e.ocorrido_em, e.id_evento))

    interesses = []
    for topico, p in pontos.items():
        peso = peso_de_pontos(p)
        if peso < MIN_PESO:
            continue
        recentes = [ident for _, ident in sorted(evidencias[topico], key=lambda x: x[0], reverse=True)]
        interesses.append((peso, topico, list(dict.fromkeys(recentes))[:MAX_EVIDENCIAS]))
    interesses.sort(key=lambda x: (-x[0], x[1]))

    return PerfilUsuario(
        id_empresa=id_empresa,
        id_usuario=id_usuario,
        interesses=[Interesse(topico=t, peso=p, evidencias=ev) for p, t, ev in interesses[:MAX_INTERESSES]],
        canal_preferido=_mais_comum([e.canal for e in eventos]),
        dispositivo_preferido=_mais_comum([e.dispositivo for e in eventos]),
        janela_desde=desde,
        janela_ate=ate,
        eventos_considerados=len(eventos),
        avisos=list(avisos or []),
    )


def construir_perfil_empresa(id_empresa: str, temas: list[TemaConteudo], avisos: list[str] | None = None) -> PerfilEmpresa:
    """Temas sobre os quais a empresa publica, a partir dos temas dos seus conteúdos."""
    por_topico: dict[str, list[str]] = defaultdict(list)
    for t in sorted(temas, key=lambda t: t.id_conteudo):
        if t.id_empresa != id_empresa:
            raise ValueError("tema de outra empresa no perfil da empresa %s" % id_empresa)
        for topico in t.topicos:
            por_topico[topico].append(t.id_conteudo)

    ordenados = sorted(
        ((peso_de_pontos(len(ids)), topico, ids) for topico, ids in por_topico.items()), key=lambda x: (-x[0], x[1])
    )
    return PerfilEmpresa(
        id_empresa=id_empresa,
        temas=[
            Interesse(topico=t, peso=p, evidencias=ids[:MAX_EVIDENCIAS])
            for p, t, ids in ordenados[:MAX_INTERESSES]
            if p >= MIN_PESO
        ],
        conteudos_considerados=len(temas),
        avisos=list(avisos or []),
    )


def construir_perfil_grupo(
    id_empresa: str,
    tag: str,
    perfis: list[PerfilUsuario],
    desde: datetime,
    ate: datetime,
    avisos: list[str] | None = None,
) -> PerfilGrupo:
    """Interesse médio do grupo: média do peso de cada tópico entre os usuários considerados."""
    for p in perfis:
        if p.id_empresa != id_empresa:
            raise ValueError("perfil de outra empresa no grupo %s/%s" % (id_empresa, tag))

    soma: dict[str, float] = defaultdict(float)
    evidencias: dict[str, list[tuple[float, str]]] = defaultdict(list)
    for p in perfis:
        for i in p.interesses:
            soma[i.topico] += i.peso
            evidencias[i.topico] += [(i.peso, ev) for ev in i.evidencias]

    n = len(perfis)
    ordenados = []
    for topico, total in soma.items():
        peso = round(total / n, 2)
        if peso < MIN_PESO:
            continue
        # evidências dos usuários em que o interesse é mais forte; desempate pelo id (resultado estável)
        melhores = [ev for _, ev in sorted(evidencias[topico], key=lambda x: (-x[0], x[1]))]
        ordenados.append((peso, topico, list(dict.fromkeys(melhores))[:MAX_EVIDENCIAS]))
    ordenados.sort(key=lambda x: (-x[0], x[1]))

    return PerfilGrupo(
        id_empresa=id_empresa,
        tag=tag,
        usuarios_considerados=n,
        interesses=[Interesse(topico=t, peso=p, evidencias=ev) for p, t, ev in ordenados[:MAX_INTERESSES]],
        janela_desde=desde,
        janela_ate=ate,
        avisos=list(avisos or []),
    )
