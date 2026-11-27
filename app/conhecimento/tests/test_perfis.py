from datetime import datetime, timedelta, timezone

import pytest

from agent import perfis
from agent.contract import Interesse, PerfilUsuario, TemaConteudo
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

def test_pintor_abre_post_de_tinta_gera_interesse_em_pintura_com_evidencia():
    p = perfil([evento(1)], [tema("c1", "pintura")])
    assert [i.topico for i in p.interesses] == ["pintura"]
    assert p.interesses[0].evidencias == ["e1"] and 0 < p.interesses[0].peso < 1
    assert (p.id_empresa, p.id_usuario, p.eventos_considerados) == (EMP, "u1", 1)
    assert (p.janela_desde, p.janela_ate) == (DESDE, ATE)


def test_sem_tema_nao_gera_interesse_mas_conta_canal_e_dispositivo():
    p = perfil([evento(1, conteudo="c1"), evento(2, conteudo="c-inexistente"), evento(3, conteudo=None)], [tema("c1")])
    assert p.interesses == [] and p.canal_preferido == "app" and p.dispositivo_preferido == "android"
    assert p.eventos_considerados == 3


def test_usuario_sem_eventos_tem_perfil_vazio():
    p = perfil([], [])
    assert p.interesses == [] and p.canal_preferido is None and p.eventos_considerados == 0


def test_todo_interesse_tem_evidencia_e_peso_valido():
    evs = [evento(n, conteudo=f"c{n % 3}", dias_antes=n) for n in range(1, 40)]
    p = perfil(evs, [tema("c0", "a"), tema("c1", "b"), tema("c2", "c", "d")])
    assert p.interesses and all(i.evidencias and 0 <= i.peso <= 1 for i in p.interesses)


def test_mesmos_dados_mesmo_perfil():
    evs = [evento(n, conteudo=f"c{n % 3}", dias_antes=n) for n in range(1, 40)]
    ts = [tema("c0", "a"), tema("c1", "b"), tema("c2", "c", "d")]
    assert perfil(evs, ts) == perfil(list(reversed(evs)), ts)


def test_avisos_vao_para_a_resposta():
    assert perfil([evento(1)], [tema("c1", "x")], avisos=["leu só os 5 eventos mais recentes"]).avisos == [
        "leu só os 5 eventos mais recentes"
    ]


# --- pesos ---

def test_mais_eventos_mais_peso_e_nunca_passa_de_um():
    pesos = [perfil([evento(n) for n in range(k)], [tema("c1", "pintura")]).interesses[0].peso for k in (1, 3, 10, 200)]
    assert pesos == sorted(pesos) and pesos[0] < pesos[-1] <= 1


def test_comentario_vale_mais_que_clique():
    clique = perfil([evento(1, tipo="clique")], [tema("c1", "x")]).interesses[0].peso
    comentario = perfil([evento(1, tipo="comentario")], [tema("c1", "x")]).interesses[0].peso
    assert comentario > clique


def test_evento_recente_vale_mais_que_antigo():
    recente = perfil([evento(n, dias_antes=1) for n in range(5)], [tema("c1", "x")]).interesses[0].peso
    antigo = perfil([evento(n, dias_antes=90) for n in range(5)], [tema("c1", "x")]).interesses[0].peso
    assert recente > antigo


def test_um_unico_evento_muito_antigo_nao_vira_interesse():
    assert perfil([evento(1, dias_antes=90)], [tema("c1", "x")]).interesses == []


def test_interesses_ordenados_do_mais_forte_ao_mais_fraco_e_limitados():
    evs = [evento(n, conteudo=f"c{n}") for n in range(1, 30)] + [evento(100 + n, conteudo="c1") for n in range(5)]
    p = perfil(evs, [tema(f"c{n}", f"t{n}") for n in range(1, 30)])
    pesos = [i.peso for i in p.interesses]
    assert pesos == sorted(pesos, reverse=True) and len(p.interesses) <= perfis.MAX_INTERESSES
    assert p.interesses[0].topico == "t1"


def test_evidencias_limitadas_e_mais_recentes_primeiro():
    evs = [evento(n, dias_antes=n) for n in range(1, 30)]
    ev = perfil(evs, [tema("c1", "x")]).interesses[0].evidencias
    assert len(ev) == perfis.MAX_EVIDENCIAS and ev[0] == "e1"


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

def test_perfil_da_empresa_resume_os_temas_publicados():
    p = construir_perfil_empresa(EMP, [tema("c1", "pintura"), tema("c2", "pintura", "alvenaria"), tema("c3")])
    assert [t.topico for t in p.temas] == ["pintura", "alvenaria"]
    assert p.temas[0].evidencias == ["c1", "c2"] and p.temas[0].peso > p.temas[1].peso and p.conteudos_considerados == 3


def test_perfil_da_empresa_recusa_tema_de_outra():
    with pytest.raises(ValueError):
        construir_perfil_empresa(EMP, [tema("c1", "x", empresa="emp-devhub")])


def test_perfil_da_empresa_nao_depende_da_ordem_dos_temas():
    a = [tema("c1", "x"), tema("c2", "x", "y")]
    assert construir_perfil_empresa(EMP, a) == construir_perfil_empresa(EMP, a[::-1])


# --- perfil do grupo ---

def usuario(uid, **topicos):
    return PerfilUsuario(
        id_empresa=EMP,
        id_usuario=uid,
        interesses=[Interesse(topico=t, peso=p, evidencias=[f"{uid}-{t}"]) for t, p in topicos.items()],
        janela_desde=DESDE,
        janela_ate=ATE,
        eventos_considerados=5,
    )


def test_grupo_usa_a_media_do_peso_entre_os_usuarios():
    g = construir_perfil_grupo(EMP, "pintor", [usuario("a", pintura=0.8), usuario("b", pintura=0.4, luto=0.2)], DESDE, ATE)
    pesos = {i.topico: i.peso for i in g.interesses}
    assert pesos == {"pintura": 0.6, "luto": 0.1} and g.usuarios_considerados == 2 and g.tag == "pintor"
    assert g.interesses[0].topico == "pintura" and g.interesses[0].evidencias[0] == "a-pintura"  # do mais forte


def test_grupo_vazio_nao_divide_por_zero():
    g = construir_perfil_grupo(EMP, "pintor", [], DESDE, ATE, ["nenhum usuário com a tag"])
    assert g.interesses == [] and g.usuarios_considerados == 0 and g.avisos == ["nenhum usuário com a tag"]


def test_grupo_recusa_perfil_de_outra_empresa():
    intruso = usuario("x", pintura=0.9).model_copy(update={"id_empresa": "emp-devhub"})
    with pytest.raises(ValueError):
        construir_perfil_grupo(EMP, "pintor", [usuario("a", pintura=0.5), intruso], DESDE, ATE)


def test_grupo_nao_depende_da_ordem_dos_usuarios():
    us = [usuario("a", pintura=0.8), usuario("b", pintura=0.4, luto=0.2), usuario("c", luto=0.9)]
    assert construir_perfil_grupo(EMP, "t", us, DESDE, ATE) == construir_perfil_grupo(EMP, "t", us[::-1], DESDE, ATE)
