"""Tema do conteúdo (T06): `Conteudo` -> `TemaConteudo`, em lote e sem guardar nada.

O agente não persiste temas: cada consulta gera os que precisa. Para custar pouco, vários conteúdos vão numa só
chamada ao modelo (lote) e os lotes rodam em paralelo.

- só texto; conteúdo vazio ou curto demais vira "sem tema" sem chamar o modelo;
- cada texto é truncado com segurança e entra no prompt como dado não confiável;
- só voltam temas dos ids enviados (um texto malicioso não consegue fazer o modelo "responder" por outro conteúdo);
- falha do modelo num lote não derruba os outros: os conteúdos afetados saem em `falhas`, com um aviso;
- o modelo é injetável (`GeradorLote`), então os testes não dependem do Bedrock.
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, Field

from agent.contract import TemaConteudo
from agent.dominio import Conteudo
from tools.seguranca import como_dado

logger = logging.getLogger(__name__)

PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "tema_lote_v1.txt").read_text(encoding="utf-8")
MIN_CARACTERES = 20  # abaixo disso (título + texto) não há tema para extrair
MAX_CARACTERES = 2000  # truncamento do texto de cada conteúdo enviado ao modelo
MAX_TOPICOS = 5
TAMANHO_LOTE = 10  # conteúdos por chamada ao modelo
MAX_PARALELO = 4  # chamadas ao modelo ao mesmo tempo
ID_VALIDO = re.compile(r"^[\w.:\-]{1,128}$")  # o id vai para o prompt: só caracteres seguros


class ItemTema(BaseModel):
    """O que o modelo devolve para um conteúdo."""

    id_conteudo: str
    topicos: list[str] = Field(default_factory=list, description="1 a 5 tópicos; vazio se não houver tema")
    categoria: str | None = None
    resumo: str | None = None
    idioma: str | None = None


class SaidaTemaLote(BaseModel):
    temas: list[ItemTema] = Field(default_factory=list, description="Um item por conteúdo recebido")


# (system_prompt, entrada) -> SaidaTemaLote
GeradorLote = Callable[[str, str], SaidaTemaLote]


@dataclass
class ResultadoTemas:
    temas: dict[str, TemaConteudo] = field(default_factory=dict)  # por id_conteudo; "sem tema" tem topicos vazio
    falhas: list[str] = field(default_factory=list)  # ids sem tema por falha do modelo ou id inválido
    avisos: list[str] = field(default_factory=list)


def truncar(texto: str, limite: int = MAX_CARACTERES) -> str:
    """Corta no limite sem partir uma palavra no meio."""
    if len(texto) <= limite:
        return texto
    corte = texto[:limite]
    ultimo_espaco = corte.rfind(" ")
    return (corte[:ultimo_espaco] if ultimo_espaco > limite // 2 else corte).rstrip()


def _tema(c: Conteudo, topicos: list[str] | None = None, item: ItemTema | None = None, avisos=None) -> TemaConteudo:
    return TemaConteudo(
        id_empresa=c.id_empresa,
        id_conteudo=c.id_conteudo,
        topicos=topicos or [],
        categoria=(item.categoria or None) if item else None,
        resumo=(item.resumo or None) if item else None,
        idioma=((item.idioma if item else None) or c.idioma),
        avisos=avisos or [],
    )


def _limpar(topicos: list[str]) -> list[str]:
    vistos: list[str] = []
    for t in topicos:
        t = " ".join(str(t).split()).lower()
        if t and t not in vistos:
            vistos.append(t)
    return vistos[:MAX_TOPICOS]


def _bloco(c: Conteudo) -> str:
    texto = (c.texto or "").strip()
    corpo = f"Título: {c.titulo}\nTipo: {c.tipo}\nTexto: {truncar(texto)}"
    return f"### Conteúdo id={c.id_conteudo}\n{como_dado(corpo)}"


def _lote(conteudos: list[Conteudo], gerar: GeradorLote) -> tuple[dict[str, ItemTema], str | None]:
    """Uma chamada ao modelo. Devolve (itens por id enviado, erro ou None)."""
    enviados = {c.id_conteudo for c in conteudos}
    try:
        saida = gerar(PROMPT, "\n\n".join(_bloco(c) for c in conteudos))
    except Exception as e:  # falha do modelo num lote não derruba os outros
        logger.warning("tema em lote falhou (%d conteúdos): %s", len(conteudos), type(e).__name__)
        return {}, type(e).__name__
    return {i.id_conteudo: i for i in saida.temas if i.id_conteudo in enviados}, None


def extrair_temas(
    conteudos: list[Conteudo],
    gerar: GeradorLote,
    tamanho_lote: int = TAMANHO_LOTE,
    max_paralelo: int = MAX_PARALELO,
) -> ResultadoTemas:
    """Tema de cada conteúdo (todos da mesma empresa). Falhas ficam em `falhas`; nunca inventa tema."""
    if len({c.id_empresa for c in conteudos}) > 1:
        raise ValueError("extrair_temas: conteúdos de mais de uma empresa na mesma chamada")

    r = ResultadoTemas()
    por_id = {c.id_conteudo: c for c in conteudos}  # duplicados contam uma vez
    a_enviar: list[Conteudo] = []
    curtos = invalidos = 0
    for c in por_id.values():
        if not ID_VALIDO.match(c.id_conteudo):
            r.falhas.append(c.id_conteudo)
            invalidos += 1
        elif len(c.titulo.strip()) + len((c.texto or "").strip()) < MIN_CARACTERES:
            r.temas[c.id_conteudo] = _tema(c)
            curtos += 1
        else:
            a_enviar.append(c)

    lotes = [a_enviar[i : i + tamanho_lote] for i in range(0, len(a_enviar), tamanho_lote)]
    if lotes:
        with ThreadPoolExecutor(max_workers=max(1, min(max_paralelo, len(lotes)))) as pool:
            resultados = list(pool.map(lambda lote: _lote(lote, gerar), lotes))
    else:
        resultados = []

    erros: dict[str, int] = {}
    sem_resposta = 0
    for lote, (itens, erro) in zip(lotes, resultados):
        for c in lote:
            item = itens.get(c.id_conteudo)
            if item is None:
                r.falhas.append(c.id_conteudo)
                if erro:
                    erros[erro] = erros.get(erro, 0) + 1
                else:
                    sem_resposta += 1
                continue
            avisos = ["texto truncado antes de analisar"] if len((c.texto or "").strip()) > MAX_CARACTERES else []
            r.temas[c.id_conteudo] = _tema(c, _limpar(item.topicos), item, avisos)

    if curtos:
        r.avisos.append(f"{curtos} conteúdo(s) sem texto suficiente para extrair tema")
    if invalidos:
        r.avisos.append(f"{invalidos} conteúdo(s) com id fora do padrão aceito, ignorados")
    for erro, n in erros.items():
        r.avisos.append(f"tema indisponível para {n} conteúdo(s) ({erro})")
    if sem_resposta:
        r.avisos.append(f"o modelo não devolveu tema para {sem_resposta} conteúdo(s)")
    return r


def gerador_bedrock() -> GeradorLote:
    """Gerador real: Haiku 5.5 com saída estruturada do Strands.

    Sem `temperature`: o Haiku 5.5 a recusa. A estabilidade vem do schema e do prompt, e a avaliação (T13) mede.
    """
    from strands import Agent

    from model.load import load_model

    def gerar(system_prompt: str, entrada: str) -> SaidaTemaLote:
        agente = Agent(model=load_model(), system_prompt=system_prompt, tools=[], callback_handler=None)
        return agente.structured_output(SaidaTemaLote, entrada)

    return gerar
