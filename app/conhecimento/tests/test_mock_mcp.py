import asyncio
import json
from datetime import datetime, timedelta

import pytest

from agent.dominio import Conteudo, Empresa, Evento, Usuario
from mock_mcp import dados, servico
from mock_mcp.servico import ErroMcp

EMPRESAS = [e["id_empresa"] for e in dados.EMPRESAS]


def tudo(funcao, *args, **kw):
    """Pagina até o fim."""
    itens, cursor = [], None
    while True:
        pag = funcao(*args, cursor=cursor, limite=kw.pop("limite", 37), **kw)
        itens += pag["itens"]
        cursor = pag["proximo_cursor"]
        if cursor is None:
            return itens


# --- volume e formato ---

def test_volume_dos_dados():
    assert len(dados.EMPRESAS) == 3
    assert 45 <= len(dados.USUARIOS) <= 55
    assert 90 <= len(dados.CONTEUDOS) <= 110
    assert 1800 <= len(dados.EVENTOS) <= 2200


def test_dados_batem_com_os_modelos_de_dominio():
    for modelo, linhas in ((Empresa, dados.EMPRESAS), (Usuario, dados.USUARIOS), (Conteudo, dados.CONTEUDOS), (Evento, dados.EVENTOS)):
        for linha in linhas:
            modelo.model_validate(linha)


def test_dados_sao_deterministicos():
    de_novo = dados._gerar()
    assert de_novo[3] == dados.EVENTOS and de_novo[2] == dados.CONTEUDOS


# --- paginação ---

@pytest.mark.parametrize("emp", EMPRESAS)
def test_paginacao_nao_duplica_nem_perde(emp):
    esperados = [e["id_evento"] for e in dados.EVENTOS if e["id_empresa"] == emp]
    lidos = [e["id_evento"] for e in tudo(servico.listar_eventos, emp)]
    assert lidos == esperados
    assert len(set(lidos)) == len(lidos)


def test_ultima_pagina_nao_tem_cursor():
    assert servico.listar_usuarios("emp-memorial", limite=100)["proximo_cursor"] is None


def test_limite_e_cursor_invalidos():
    for kw in ({"limite": 0}, {"limite": "x"}, {"cursor": "abc"}, {"cursor": "-1"}):
        with pytest.raises(ErroMcp):
            servico.listar_usuarios("emp-tintas", **kw)


def test_limite_maximo_e_respeitado():
    assert len(servico.listar_eventos("emp-tintas", limite=10_000)["itens"]) <= servico.LIMITE_MAXIMO


# --- isolamento ---

@pytest.mark.parametrize("funcao", [servico.listar_usuarios, servico.listar_conteudos, servico.listar_eventos])
@pytest.mark.parametrize("vazio", [None, "", "  "])
def test_sem_id_empresa_e_rejeitado(funcao, vazio):
    with pytest.raises(ErroMcp, match="id_empresa é obrigatório"):
        funcao(vazio)


@pytest.mark.parametrize("funcao", [servico.listar_usuarios, servico.listar_conteudos, servico.listar_eventos])
def test_empresa_inexistente_e_rejeitada(funcao):
    with pytest.raises(ErroMcp, match="não encontrada"):
        funcao("emp-nao-existe")


@pytest.mark.parametrize("emp", EMPRESAS)
@pytest.mark.parametrize("funcao", [servico.listar_usuarios, servico.listar_conteudos, servico.listar_eventos])
def test_empresa_nunca_ve_dado_de_outra(emp, funcao):
    assert all(i["id_empresa"] == emp for i in tudo(funcao, emp))


def test_mesmo_tema_em_empresas_diferentes_nao_vaza():
    tintas = {c["id_conteudo"] for c in tudo(servico.listar_conteudos, "emp-tintas") if "pintura" in c["titulo"]}
    memorial = {c["id_conteudo"] for c in tudo(servico.listar_conteudos, "emp-memorial") if "pintura" in c["titulo"]}
    assert tintas and memorial and not (tintas & memorial)


# --- leitura incremental ---

def test_conteudos_atualizado_desde():
    todos = tudo(servico.listar_conteudos, "emp-devhub")
    corte = todos[len(todos) // 2]["atualizado_em"]
    novos = tudo(servico.listar_conteudos, "emp-devhub", atualizado_desde=corte)
    assert 0 < len(novos) < len(todos)
    assert all(c["atualizado_em"] > corte for c in novos)


def test_eventos_por_periodo():
    desde, ate = "2026-11-10T00:00:00Z", "2026-11-12T00:00:00Z"
    evs = tudo(servico.listar_eventos, "emp-devhub", desde=desde, ate=ate)
    assert evs
    assert all(desde < e["ocorrido_em"] <= ate for e in evs)
    assert [e["ocorrido_em"] for e in evs] == sorted(e["ocorrido_em"] for e in evs)


def test_periodo_invertido_e_data_invalida():
    with pytest.raises(ErroMcp):
        servico.listar_eventos("emp-tintas", desde="2026-11-12T00:00:00Z", ate="2026-11-10T00:00:00Z")
    with pytest.raises(ErroMcp):
        servico.listar_eventos("emp-tintas", desde="ontem")


# --- casos embutidos ---

def test_usuario_sem_eventos():
    assert not [e for e in dados.EVENTOS if e["id_usuario"] == "u-emp-tintas-20"]
    assert "u-emp-tintas-20" in {u["id_usuario"] for u in tudo(servico.listar_usuarios, "emp-tintas")}


def test_evento_de_conteudo_inexistente():
    ids = {c["id_conteudo"] for c in dados.CONTEUDOS}
    orfaos = [e for e in dados.EVENTOS if e["id_conteudo"] and e["id_conteudo"] not in ids]
    assert len(orfaos) == 1 and orfaos[0]["id_conteudo"] == "c-inexistente"


def test_prompt_injection_em_conteudo_e_comentario():
    assert any(dados.INJECAO in (c["texto"] or "") for c in dados.CONTEUDOS)
    assert any(dados.INJECAO in (e["texto"] or "") for e in dados.EVENTOS)


# --- pelo protocolo MCP de verdade (em memória) ---

def _chamar(nome, args):
    from mcp.shared.memory import create_connected_server_and_client_session

    from mock_mcp.server import mcp

    async def run():
        async with create_connected_server_and_client_session(mcp._mcp_server) as cliente:
            tools = {t.name for t in (await cliente.list_tools()).tools}
            return tools, await cliente.call_tool(nome, args)

    return asyncio.run(run())


def test_mcp_lista_as_tools_e_responde():
    tools, res = _chamar("listar_usuarios", {"id_empresa": "emp-tintas", "limite": 5})
    assert tools == {"listar_empresas", "listar_usuarios", "listar_conteudos", "listar_eventos"}
    assert not res.isError
    corpo = json.loads(res.content[0].text)
    assert len(corpo["itens"]) == 5 and corpo["proximo_cursor"] == "5"


def test_mcp_sem_empresa_devolve_erro_claro():
    _, res = _chamar("listar_eventos", {"id_empresa": ""})
    assert res.isError and "id_empresa é obrigatório" in res.content[0].text
    assert "Traceback" not in res.content[0].text


# --- consulta dirigida (D13): por usuário, por ids e por tag ---

def test_eventos_por_usuario():
    evs = tudo(servico.listar_eventos, "emp-tintas", id_usuario="u-emp-tintas-01")
    assert evs and {e["id_usuario"] for e in evs} == {"u-emp-tintas-01"}
    assert len(evs) == len([e for e in dados.EVENTOS if e["id_usuario"] == "u-emp-tintas-01"])


def test_eventos_por_usuario_respeitam_a_janela_e_a_ordem():
    desde, ate = "2026-11-05T00:00:00Z", "2026-11-15T00:00:00Z"
    evs = tudo(servico.listar_eventos, "emp-devhub", desde=desde, ate=ate, id_usuario="u-emp-devhub-02")
    assert evs and all(desde < e["ocorrido_em"] <= ate for e in evs)
    assert [e["ocorrido_em"] for e in evs] == sorted(e["ocorrido_em"] for e in evs)


def test_usuario_sem_eventos_devolve_lista_vazia_e_nao_erro():
    assert tudo(servico.listar_eventos, "emp-tintas", id_usuario="u-emp-tintas-20") == []


def test_usuario_inexistente_ou_de_outra_empresa_e_nao_encontrado():
    for uid in ("u-nao-existe", "u-emp-devhub-01"):  # o segundo existe, mas em outra empresa
        with pytest.raises(ErroMcp, match=f"usuário não encontrado: {uid}"):
            servico.listar_eventos("emp-tintas", id_usuario=uid)
    with pytest.raises(ErroMcp):
        servico.listar_eventos("emp-tintas", id_usuario="  ")


def test_conteudos_por_ids_devolve_so_os_pedidos():
    pedidos = ["c-emp-tintas-001", "c-emp-tintas-005", "c-emp-tintas-001"]
    achados = servico.listar_conteudos("emp-tintas", ids=pedidos)["itens"]
    assert sorted(c["id_conteudo"] for c in achados) == ["c-emp-tintas-001", "c-emp-tintas-005"]


def test_conteudos_por_ids_ignoram_inexistentes_e_de_outra_empresa():
    achados = servico.listar_conteudos("emp-tintas", ids=["c-inexistente", "c-emp-devhub-001", "c-emp-tintas-002"])["itens"]
    assert [c["id_conteudo"] for c in achados] == ["c-emp-tintas-002"]
    assert servico.listar_conteudos("emp-tintas", ids=[])["itens"] == []


@pytest.mark.parametrize("ruim", ["c1", [1], [""], ["a"] * 201])
def test_ids_invalidos(ruim):
    with pytest.raises(ErroMcp):
        servico.listar_conteudos("emp-tintas", ids=ruim)


def test_usuarios_por_tag_so_da_empresa_pedida():
    pintores = tudo(servico.listar_usuarios, "emp-tintas", tag="pintor")
    assert pintores and all("pintor" in u["tags"] and u["id_empresa"] == "emp-tintas" for u in pintores)
    assert tudo(servico.listar_usuarios, "emp-devhub", tag="pintor") == []
    with pytest.raises(ErroMcp):
        servico.listar_usuarios("emp-tintas", tag="")


def test_mcp_aceita_os_filtros_pelo_protocolo():
    _, res = _chamar("listar_eventos", {"id_empresa": "emp-tintas", "id_usuario": "u-emp-tintas-01", "limite": 3})
    assert not res.isError and {e["id_usuario"] for e in json.loads(res.content[0].text)["itens"]} == {"u-emp-tintas-01"}
    _, res = _chamar("listar_conteudos", {"id_empresa": "emp-tintas", "ids": ["c-emp-tintas-001"]})
    assert [c["id_conteudo"] for c in json.loads(res.content[0].text)["itens"]] == ["c-emp-tintas-001"]
    _, res = _chamar("listar_eventos", {"id_empresa": "emp-tintas", "id_usuario": "u-emp-devhub-01"})
    assert res.isError and "usuário não encontrado" in res.content[0].text
