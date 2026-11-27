import asyncio
import json
import re
import threading
from datetime import datetime, timezone

import pytest

import agent.consulta as consulta_mod
from agent.consulta import ErroConsulta, Limites, responder
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
from agent.fonte import _chamador_mock_em_processo
from config.settings import settings
from mock_mcp import dados
from tools.leitura import ErroLeitura, Leitor
from tools.tema import ItemTema, SaidaTemaLote

AGORA = datetime(2026, 12, 1, tzinfo=timezone.utc)
LIM = Limites(max_eventos=2000, max_conteudos=100, max_usuarios_grupo=50, janela_padrao_dias=90, timeout_s=60)
EMPRESAS = [e["id_empresa"] for e in dados.EMPRESAS]


class Gerador:
    """Tema falso em lote: a palavra depois de 'sobre' no bloco de cada conteúdo. Registra o que recebeu."""

    def __init__(self):
        self.chamadas: list[str] = []
        self.ids_enviados: list[str] = []
        self._trava = threading.Lock()

    def __call__(self, system, entrada):
        itens = []
        for bloco in entrada.split("### Conteúdo id=")[1:]:
            cid = bloco.split("\n", 1)[0]
            achou = re.search(r"sobre (\w+)", bloco)
            itens.append(ItemTema(id_conteudo=cid, topicos=[achou.group(1)] if achou else [], idioma="pt-BR"))
        with self._trava:
            self.chamadas.append(entrada)
            self.ids_enviados += [i.id_conteudo for i in itens]
        return SaidaTemaLote(temas=itens)


class EspiaMcp:
    """Chama o mock em processo e registra cada chamada, para provar que a consulta só pede o necessário."""

    def __init__(self):
        self.chamadas: list[tuple[str, dict]] = []

    def __call__(self, nome, args):
        self.chamadas.append((nome, dict(args)))
        return _chamador_mock_em_processo(nome, args)

    def de(self, tool):
        return [a for n, a in self.chamadas if n == tool]


def rodar(consulta, gerar=None, mcp=None, limites=LIM, agora=AGORA):
    return responder(consulta, Leitor(mcp or _chamador_mock_em_processo), gerar or Gerador(), agora=agora, limites=limites)


def perfil_usuario(emp="emp-tintas", uid="u-emp-tintas-01", **kw):
    return ConsultaPerfilUsuario(id_empresa=emp, id_usuario=uid, modo="mock", **kw)


# --- perfil do usuário ---

def test_perfil_do_pintor_tem_interesse_em_pintura_com_evidencia():
    p = rodar(perfil_usuario())
    assert isinstance(p, PerfilUsuario) and (p.id_empresa, p.id_usuario) == ("emp-tintas", "u-emp-tintas-01")
    assert p.interesses[0].topico == "pintura" and p.interesses[0].evidencias
    assert p.canal_preferido and p.dispositivo_preferido
    assert p.eventos_considerados == len([e for e in dados.EVENTOS if e["id_usuario"] == "u-emp-tintas-01"])
    assert (p.janela_desde, p.janela_ate) == (datetime(2026, 9, 2, tzinfo=timezone.utc), AGORA)


def test_conteudo_citado_que_nao_existe_vira_aviso_e_nao_erro():
    p = rodar(perfil_usuario())  # u-emp-tintas-01 tem o evento órfão (c-inexistente)
    assert p.avisos == ["1 conteúdo(s) citado(s) nos eventos não foram encontrados"]


def test_so_pede_ao_mcp_o_necessario():
    mcp = EspiaMcp()
    rodar(perfil_usuario(), mcp=mcp)
    assert {n for n, _ in mcp.chamadas} == {"listar_eventos", "listar_conteudos"}  # nem empresas, nem usuários
    assert all(a["id_empresa"] == "emp-tintas" for _, a in mcp.chamadas)
    assert all(a["id_usuario"] == "u-emp-tintas-01" for a in mcp.de("listar_eventos"))
    assert all("ids" in a for a in mcp.de("listar_conteudos"))  # nunca "todos os conteúdos da empresa"


def test_mesma_consulta_mesmos_dados_mesma_resposta():
    assert rodar(perfil_usuario()) == rodar(perfil_usuario())


def test_usuario_sem_eventos_responde_perfil_vazio_sem_chamar_o_modelo():
    g = Gerador()
    p = rodar(perfil_usuario(uid="u-emp-tintas-20"), gerar=g)
    assert p.interesses == [] and p.eventos_considerados == 0 and g.chamadas == []


def test_usuario_de_outra_empresa_ou_inexistente_nao_e_encontrado():
    g = Gerador()
    for uid in ("u-emp-devhub-01", "u-nao-existe"):
        with pytest.raises(ErroConsulta, match=f"usuário não encontrado: {uid}"):
            rodar(perfil_usuario(uid=uid), gerar=g)
    assert g.chamadas == []


def test_empresa_inexistente_e_erro_claro():
    with pytest.raises(ErroConsulta, match="empresa não encontrada: emp-x"):
        rodar(perfil_usuario(emp="emp-x"))


def test_janela_padrao_e_janela_pedida():
    longe = datetime(2027, 3, 1, tzinfo=timezone.utc)  # 90 dias antes: já passou de todos os eventos
    assert rodar(perfil_usuario(), agora=longe).eventos_considerados == 0
    estreita = rodar(perfil_usuario(desde="2026-11-10T00:00:00Z", ate="2026-11-12T00:00:00Z"))
    assert 0 < estreita.eventos_considerados < rodar(perfil_usuario()).eventos_considerados
    assert estreita.janela_ate == datetime(2026, 11, 12, tzinfo=timezone.utc)


def test_teto_de_eventos_usa_os_mais_recentes_e_avisa():
    total = len([e for e in dados.EVENTOS if e["id_usuario"] == "u-emp-tintas-01"])
    p = rodar(perfil_usuario(), limites=Limites(10, 100, 50, 90, 60))
    assert p.eventos_considerados == 10
    assert f"considerados só os 10 eventos mais recentes, de {total} na janela" in p.avisos


def test_teto_de_conteudos_limita_o_tema_e_avisa():
    mcp, g = EspiaMcp(), Gerador()
    p = rodar(perfil_usuario(), gerar=g, mcp=mcp, limites=Limites(2000, 3, 50, 90, 60))
    assert len(set(g.ids_enviados)) <= 3 and any("só dos 3 conteúdos mais recentes" in a for a in p.avisos)
    assert sum(len(a["ids"]) for a in mcp.de("listar_conteudos")) <= 3


def test_falha_do_modelo_degrada_com_aviso_e_nao_inventa_interesse():
    def quebrado(system, entrada):
        raise RuntimeError("bedrock fora")

    p = rodar(perfil_usuario(), gerar=quebrado)
    assert p.interesses == [] and p.eventos_considerados > 0
    assert any("tema indisponível" in a and "RuntimeError" in a for a in p.avisos)
    assert "bedrock fora" not in " ".join(p.avisos)


def test_falha_do_mcp_vira_erro_claro():
    def fora(nome, args):
        raise ErroLeitura(f"{nome}: MCP indisponível")

    with pytest.raises(ErroConsulta, match="MCP indisponível"):
        rodar(perfil_usuario(), mcp=fora)


# --- tema do conteúdo ---

def test_tema_do_conteudo():
    t = rodar(ConsultaTemaConteudo(id_empresa="emp-tintas", id_conteudo="c-emp-tintas-001", modo="mock"))
    assert isinstance(t, TemaConteudo) and t.topicos == ["pintura"] and t.id_conteudo == "c-emp-tintas-001"


def test_conteudo_inexistente_ou_de_outra_empresa_tem_a_mesma_resposta():
    for cid in ("c-nao-existe", "c-emp-devhub-001"):
        with pytest.raises(ErroConsulta, match=f"conteúdo não encontrado: {cid}"):
            rodar(ConsultaTemaConteudo(id_empresa="emp-tintas", id_conteudo=cid, modo="mock"))


def test_falha_do_modelo_no_tema_e_erro_e_nao_tema_inventado():
    def quebrado(system, entrada):
        raise RuntimeError("bedrock fora")

    with pytest.raises(ErroConsulta, match="não foi possível extrair o tema"):
        rodar(ConsultaTemaConteudo(id_empresa="emp-tintas", id_conteudo="c-emp-tintas-001", modo="mock"), gerar=quebrado)


def test_prompt_injection_no_conteudo_nao_vaza_nem_muda_o_formato(caplog):
    g = Gerador()
    with caplog.at_level("DEBUG"):
        t = rodar(ConsultaTemaConteudo(id_empresa="emp-tintas", id_conteudo="c-emp-tintas-005", modo="mock"), gerar=g)
    assert t.topicos == ["alvenaria"] and t.id_empresa == "emp-tintas"
    assert dados.INJECAO in g.chamadas[0] and g.chamadas[0].count("<dado_nao_confiavel>") == 1
    assert dados.INJECAO not in caplog.text  # logs sem texto de conteúdo


# --- perfil da empresa ---

def test_perfil_da_empresa():
    p = rodar(ConsultaPerfilEmpresa(id_empresa="emp-tintas", modo="mock"))
    assert isinstance(p, PerfilEmpresa) and p.conteudos_considerados == 40
    assert {t.topico for t in p.temas} == {"pintura", "alvenaria", "eletrica"} and p.avisos == []


def test_perfil_da_empresa_com_teto_avisa():
    p = rodar(ConsultaPerfilEmpresa(id_empresa="emp-tintas", modo="mock"), limites=Limites(2000, 5, 50, 90, 60))
    assert p.conteudos_considerados == 5 and p.avisos == ["considerados só os 5 conteúdos mais recentes, de 40"]


def test_perfil_da_empresa_sem_modelo_e_erro():
    def quebrado(system, entrada):
        raise RuntimeError("fora")

    with pytest.raises(ErroConsulta, match="não foi possível extrair os temas"):
        rodar(ConsultaPerfilEmpresa(id_empresa="emp-tintas", modo="mock"), gerar=quebrado)


def test_mesmo_tema_em_duas_empresas_nao_vaza():
    tintas = rodar(ConsultaPerfilEmpresa(id_empresa="emp-tintas", modo="mock"))
    memorial = rodar(ConsultaPerfilEmpresa(id_empresa="emp-memorial", modo="mock"))
    ev_tintas = {e for t in tintas.temas for e in t.evidencias}
    ev_memorial = {e for t in memorial.temas for e in t.evidencias}
    assert ev_tintas and ev_memorial and not ev_tintas & ev_memorial
    assert all("emp-memorial" in e for e in ev_memorial) and all("emp-tintas" in e for e in ev_tintas)


# --- perfil do grupo ---

def grupo(emp="emp-tintas", tag="pintor"):
    return ConsultaPerfilGrupo(id_empresa=emp, tag=tag, modo="mock")


def test_perfil_do_grupo():
    p = rodar(grupo())
    pintores = [u for u in dados.USUARIOS if u["id_empresa"] == "emp-tintas" and "pintor" in u["tags"]]
    assert isinstance(p, PerfilGrupo) and p.usuarios_considerados == len(pintores) and p.tag == "pintor"
    assert p.interesses[0].topico == "pintura" and p.interesses[0].evidencias


def test_grupo_nao_pede_o_mesmo_conteudo_duas_vezes_ao_modelo():
    g = Gerador()
    rodar(grupo(), gerar=g)
    assert len(g.ids_enviados) == len(set(g.ids_enviados))


def test_grupo_sem_usuarios_responde_vazio_com_aviso():
    p = rodar(grupo(emp="emp-devhub", tag="pintor"))  # ninguém na DevHub tem a tag
    assert p.usuarios_considerados == 0 and p.interesses == [] and "nenhum usuário com a tag" in p.avisos[0]


def test_teto_de_usuarios_do_grupo_avisa():
    p = rodar(grupo(), limites=Limites(2000, 100, 2, 90, 60))
    assert p.usuarios_considerados == 2 and any("só 2 usuários do grupo" in a for a in p.avisos)


def test_tempo_esgotado_para_de_somar_usuarios_e_avisa(monkeypatch):
    relogio = iter([0, 0, 100, 100, 100, 100, 100, 100, 100, 100])
    monkeypatch.setattr(consulta_mod.time, "monotonic", lambda: next(relogio))
    p = rodar(grupo(), limites=Limites(2000, 100, 50, 90, 60))
    assert p.usuarios_considerados == 1 and any(a.startswith("tempo esgotado: considerados 1 de") for a in p.avisos)


def test_falha_de_um_usuario_do_grupo_nao_derruba_os_outros_mas_todos_falhando_e_erro():
    def falha_em_um(nome, args):
        if args.get("id_usuario") == "u-emp-tintas-01":
            raise ErroLeitura("listar_eventos: lento demais")
        return _chamador_mock_em_processo(nome, args)

    p = rodar(grupo(), mcp=falha_em_um)
    assert any("1 usuário(s) ignorado(s)" in a for a in p.avisos) and p.usuarios_considerados >= 1

    def tudo_falha(nome, args):
        if nome == "listar_eventos":
            raise ErroLeitura("fora")
        return _chamador_mock_em_processo(nome, args)

    with pytest.raises(ErroConsulta, match="nenhum usuário do grupo"):
        rodar(grupo(), mcp=tudo_falha)


# --- isolamento ---

def test_mcp_que_vaza_outra_empresa_aborta_a_consulta():
    def vaza(nome, args):
        r = _chamador_mock_em_processo(nome, args)
        if nome == "listar_conteudos" and r["itens"]:
            r["itens"][0] = {**r["itens"][0], "id_empresa": "emp-devhub"}
        return r

    with pytest.raises(ErroConsulta, match="outra empresa"):
        rodar(perfil_usuario(), mcp=vaza)


def test_vazamento_no_grupo_nunca_e_tratado_como_falha_de_um_usuario():
    def vaza(nome, args):
        r = _chamador_mock_em_processo(nome, args)
        if nome == "listar_eventos" and r["itens"]:
            r["itens"][0] = {**r["itens"][0], "id_empresa": "emp-devhub"}
        return r

    with pytest.raises(ErroConsulta, match="outra empresa"):
        rodar(grupo(), mcp=vaza)


@pytest.mark.parametrize("emp", EMPRESAS)
def test_nenhum_perfil_de_usuario_cita_evidencia_de_outra_empresa(emp):
    dono = {e["id_evento"]: e["id_empresa"] for e in dados.EVENTOS}
    dono.update({c["id_conteudo"]: c["id_empresa"] for c in dados.CONTEUDOS})
    g = Gerador()
    for u in [u for u in dados.USUARIOS if u["id_empresa"] == emp][:6]:
        p = rodar(perfil_usuario(emp=emp, uid=u["id_usuario"]), gerar=g)
        assert p.id_empresa == emp
        assert all(dono[ev] == emp for i in p.interesses for ev in i.evidencias)


def test_consulta_nao_suportada():
    with pytest.raises(ErroConsulta, match="não suportada"):
        rodar(object())


# --- entrypoint ---

def invocar(payload):
    import main

    return asyncio.run(main.invoke(payload))


def test_entrypoint_devolve_erro_claro_para_consulta_invalida():
    ruim = invocar({"tipo": "perfil_usuario", "id_empresa": ""})
    campos = {d["campo"] for d in ruim["detalhes"]}  # o prefixo é o tipo da consulta
    assert "consulta inválida" in ruim["erro"] and campos == {"perfil_usuario.id_empresa", "perfil_usuario.id_usuario"}
    assert "consulta inválida" in invocar({"id_empresa": "emp-tintas"})["erro"]


def test_entrypoint_em_modo_real_sem_endpoint_falha_com_mensagem_clara(monkeypatch):
    monkeypatch.setattr(settings, "gateway_url", None)
    real = invocar({"tipo": "perfil_empresa", "id_empresa": "emp-tintas", "modo": "real"})
    assert "GATEWAY_URL" in real["erro"] and "'mock'" in real["erro"]


def test_entrypoint_responde_ponta_a_ponta_no_modo_mock(monkeypatch):
    import main

    monkeypatch.setattr(main, "gerador_bedrock", lambda: Gerador())
    r = invocar({"tipo": "perfil_usuario", "id_empresa": "emp-tintas", "id_usuario": "u-emp-tintas-01", "modo": "mock"})
    PerfilUsuario.model_validate(r)
    json.dumps(r)  # serializável
    assert r["interesses"][0]["topico"] == "pintura"
    erro = invocar({"tipo": "perfil_usuario", "id_empresa": "emp-tintas", "id_usuario": "u-emp-devhub-01", "modo": "mock"})
    assert "usuário não encontrado: u-emp-devhub-01" in erro["erro"] and "Traceback" not in erro["erro"]
