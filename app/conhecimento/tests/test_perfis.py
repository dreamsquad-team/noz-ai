from datetime import datetime, timedelta, timezone

import pytest

from agent import perfis
from agent.contract import InteresseUsuario, PerfilUsuario, TemaConteudo
from agent.dominio import Evento
from agent.perfis import construir_perfil_empresa, construir_perfil_grupo, construir_perfil_usuario

ATE = datetime(2026, 12, 1, tzinfo=timezone.utc)
DESDE = ATE - timedelta(days=90)
EMP = "emp-tintas"


def evento(n, conteudo="c1", tipo="clique", dias_antes=1, canal="app", dispositivo="android", usuario="u1", empresa=EMP):
    return Evento(
        id_evento=f"e{n}",
        id_empresa=empresa,
        id_usuario=usuario,
        id_conteudo=conteudo,
        tipo=tipo,
        ocorrido_em=ATE - timedelta(days=dias_antes),
        canal=canal,
        dispositivo=dispositivo,
    )


def tema(cid, *topicos, empresa=EMP):
    return TemaConteudo(id_empresa=empresa, id_conteudo=cid, topicos=list(topicos))


def perfil(eventos, temas, usuario="u1", avisos=None):
    return construir_perfil_usuario(EMP, usuario, eventos, {t.id_conteudo: t for t in temas}, DESDE, ATE, avisos)


# --- caso do aceite ---

def test_pintor_abre_post_de_tinta_gera_assunto_pintura_com_evidencia():
    p = perfil([evento(1)], [tema("c1", "pintura")])
    assert [i.topico for i in p.interesses] == ["pintura"]
    i = p.interesses[0]
    assert (i.eventos, i.por_tipo, i.evidencias) == (1, {"clique": 1}, ["e1"])
    assert i.ultimo_evento_em == ATE - timedelta(days=1)
    assert (p.id_empresa, p.id_usuario, p.eventos_considerados) == (EMP, "u1", 1)
    assert (p.janela_desde, p.janela_ate) == (DESDE, ATE)


def test_sem_tema_nao_gera_assunto_mas_conta_canal_e_dispositivo():
    p = perfil([evento(1, conteudo="c1"), evento(2, conteudo="c-inexistente"), evento(3, conteudo=None)], [tema("c1")])
    assert p.interesses == [] and p.canal_preferido == "app" and p.dispositivo_preferido == "android"
    assert p.eventos_considerados == 3


def test_usuario_sem_eventos_tem_perfil_vazio():
    p = perfil([], [])
    assert p.interesses == [] and p.canal_preferido is None and p.eventos_considerados == 0


def test_mesmos_dados_mesmo_perfil():
    evs = [evento(n, conteudo=f"c{n % 3}", dias_antes=n) for n in range(1, 40)]
    ts = [tema("c0", "a"), tema("c1", "b"), tema("c2", "c", "d")]
    assert perfil(evs, ts) == perfil(list(reversed(evs)), ts)


def test_avisos_vao_para_a_resposta():
    assert perfil([evento(1)], [tema("c1", "x")], avisos=["leu só os 5 eventos mais recentes"]).avisos == [
        "leu só os 5 eventos mais recentes"
    ]


# --- contagens: só fatos ---

def test_conta_eventos_por_tipo_e_o_ultimo():
    evs = [
        evento(1, tipo="clique", dias_antes=10),
        evento(2, tipo="clique", dias_antes=5),
        evento(3, tipo="acesso", dias_antes=3),
        evento(4, tipo="comentario", dias_antes=1),
    ]
    i = perfil(evs, [tema("c1", "pintura")]).interesses[0]
    assert i.eventos == 4 and i.por_tipo == {"acesso": 1, "clique": 2, "comentario": 1}
    assert i.ultimo_evento_em == ATE - timedelta(days=1) and i.evidencias[0] == "e4"


def test_um_evento_vale_um_evento_sem_ponderar_por_tipo_nem_por_idade():
    """Nada de peso: comentar não vale mais que clicar, e um evento antigo conta igual a um recente."""
    recente = perfil([evento(1, tipo="comentario", dias_antes=1)], [tema("c1", "x")]).interesses[0]
    antigo = perfil([evento(1, tipo="clique", dias_antes=89)], [tema("c1", "x")]).interesses[0]
    assert recente.eventos == antigo.eventos == 1


def test_evento_de_conteudo_com_varios_topicos_conta_em_cada_um():
    p = perfil([evento(1, conteudo="c1")], [tema("c1", "pintura", "alvenaria", "pintura")])
    assert sorted((i.topico, i.eventos) for i in p.interesses) == [("alvenaria", 1), ("pintura", 1)]


def test_ordem_mais_eventos_primeiro_empate_pelo_mais_recente_e_depois_pelo_nome():
    evs = [evento(1, "c1", dias_antes=5), evento(2, "c1", dias_antes=4), evento(3, "c2", dias_antes=1),
           evento(4, "c3", dias_antes=1), evento(5, "c4", dias_antes=9)]
    ts = [tema("c1", "mais"), tema("c2", "b-recente"), tema("c3", "a-recente"), tema("c4", "antigo")]
    assert [i.topico for i in perfil(evs, ts).interesses] == ["mais", "a-recente", "b-recente", "antigo"]


def test_evidencias_limitadas_e_mais_recentes_primeiro():
    evs = [evento(n, dias_antes=n) for n in range(1, 30)]
    i = perfil(evs, [tema("c1", "x")]).interesses[0]
    assert i.eventos == 29 and len(i.evidencias) == perfis.MAX_EVIDENCIAS and i.evidencias[0] == "e1"


def test_passou_do_limite_de_assuntos_lista_os_mais_frequentes_e_avisa():
    ts = [tema(f"c{n}", f"t{n:02d}") for n in range(30)]
    evs = [evento(n, conteudo=f"c{n}") for n in range(30)] + [evento(100 + n, conteudo="c7") for n in range(3)]
    p = perfil(evs, ts)
    assert len(p.interesses) == perfis.MAX_TOPICOS and p.interesses[0].topico == "t07"
    assert p.avisos == [f"listados só os {perfis.MAX_TOPICOS} assuntos mais frequentes, de 30 encontrados"]


def test_canal_e_dispositivo_preferidos_com_desempate_estavel():
    evs = [evento(1, canal="email"), evento(2, canal="app"), evento(3, canal="app"), evento(4, canal="email", dispositivo="ios")]
    p = perfil(evs, [tema("c1", "x")])
    assert p.canal_preferido == "app" and p.dispositivo_preferido == "android"


# --- isolamento ---

def test_evento_de_outra_empresa_ou_usuario_e_recusado():
    with pytest.raises(ValueError):
        perfil([evento(1, empresa="emp-devhub")], [tema("c1", "x")])
    with pytest.raises(ValueError):
        perfil([evento(1, usuario="u2")], [tema("c1", "x")])


def test_tema_de_outra_empresa_e_recusado():
    with pytest.raises(ValueError):
        perfil([evento(1)], [tema("c1", "x", empresa="emp-devhub")])


# --- perfil da empresa ---

def test_perfil_da_empresa_conta_em_quantos_conteudos_cada_assunto_aparece():
    p = construir_perfil_empresa(EMP, [tema("c1", "pintura"), tema("c2", "pintura", "alvenaria"), tema("c3")])
    assert [(t.topico, t.conteudos) for t in p.temas] == [("pintura", 2), ("alvenaria", 1)]
    assert p.temas[0].evidencias == ["c1", "c2"] and p.conteudos_considerados == 3


def test_perfil_da_empresa_recusa_tema_de_outra():
    with pytest.raises(ValueError):
        construir_perfil_empresa(EMP, [tema("c1", "x", empresa="emp-devhub")])


def test_perfil_da_empresa_nao_depende_da_ordem_dos_temas():
    a = [tema("c1", "x"), tema("c2", "x", "y")]
    assert construir_perfil_empresa(EMP, a) == construir_perfil_empresa(EMP, a[::-1])


# --- perfil do grupo ---

def usuario(uid, **topicos):
    """Perfil de usuário com `topicos` = {assunto: nº de eventos}; o evento mais recente é f'{uid}-{assunto}'."""
    return PerfilUsuario(
        id_empresa=EMP,
        id_usuario=uid,
        interesses=[
            InteresseUsuario(
                topico=t, eventos=n, por_tipo={"clique": n}, ultimo_evento_em=ATE - timedelta(days=2), evidencias=[f"{uid}-{t}"]
            )
            for t, n in topicos.items()
        ],
        janela_desde=DESDE,
        janela_ate=ATE,
        eventos_considerados=sum(topicos.values()),
    )


def test_grupo_conta_quantos_usuarios_tem_cada_assunto():
    g = construir_perfil_grupo(EMP, "pintor", [usuario("a", pintura=8), usuario("b", pintura=1, luto=2)], DESDE, ATE)
    assert [(i.topico, i.usuarios) for i in g.interesses] == [("pintura", 2), ("luto", 1)]
    assert g.usuarios_considerados == 2 and g.tag == "pintor"
    assert sorted(g.interesses[0].evidencias) == ["a-pintura", "b-pintura"]


def test_grupo_vazio_nao_quebra():
    g = construir_perfil_grupo(EMP, "pintor", [], DESDE, ATE, ["nenhum usuário com a tag"])
    assert g.interesses == [] and g.usuarios_considerados == 0 and g.avisos == ["nenhum usuário com a tag"]


def test_grupo_recusa_perfil_de_outra_empresa():
    intruso = usuario("x", pintura=3).model_copy(update={"id_empresa": "emp-devhub"})
    with pytest.raises(ValueError):
        construir_perfil_grupo(EMP, "pintor", [usuario("a", pintura=1), intruso], DESDE, ATE)


def test_grupo_nao_depende_da_ordem_dos_usuarios():
    us = [usuario("a", pintura=8), usuario("b", pintura=1, luto=2), usuario("c", luto=9)]
    assert construir_perfil_grupo(EMP, "t", us, DESDE, ATE) == construir_perfil_grupo(EMP, "t", us[::-1], DESDE, ATE)
