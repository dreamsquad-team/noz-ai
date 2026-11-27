import sys
from pathlib import Path

import pytest

from agent.dominio import Conteudo, Empresa, Evento, Usuario
from config.settings import settings
from mcp_client.client import get_gateway_mcp_client
from mock_mcp import dados, servico
from tools.leitura import ErroLeitura, Leitor, chamador_do_cliente

RAIZ = Path(__file__).resolve().parent.parent
EMPRESAS = [e["id_empresa"] for e in dados.EMPRESAS]


def chamador_mock(nome, args):
    """Chama a lógica do mock direto, traduzindo o erro como o protocolo MCP faria."""
    try:
        return getattr(servico, nome)(**args)
    except servico.ErroMcp as e:
        raise ErroLeitura(f"{nome}: {e}") from e


def leitor(**kw):
    return Leitor(chamador_mock, **kw)


def pagina(itens, proximo=None):
    return {"itens": itens, "proximo_cursor": proximo}


# --- leitura completa ---

def test_le_todas_as_empresas():
    r = leitor().ler_empresas()
    assert [e.id_empresa for e in r.itens] == EMPRESAS and r.descartados == 0
    assert all(isinstance(e, Empresa) for e in r.itens)


@pytest.mark.parametrize("emp", EMPRESAS)
def test_leitura_completa_pagina_ate_esgotar(emp):
    r = leitor().ler_eventos(emp)  # 50 por página: várias páginas
    esperados = [e["id_evento"] for e in dados.EVENTOS if e["id_empresa"] == emp]
    assert [e.id_evento for e in r.itens] == esperados
    assert all(isinstance(e, Evento) for e in r.itens)
    assert [u.id_usuario for u in leitor().ler_usuarios(emp).itens] == [
        u["id_usuario"] for u in dados.USUARIOS if u["id_empresa"] == emp
    ]


def test_evento_de_conteudo_inexistente_nao_quebra_a_leitura():
    ids = {e.id_evento for e in leitor().ler_eventos("emp-tintas").itens if e.id_conteudo == "c-inexistente"}
    assert len(ids) == 1


# --- janela de tempo e incremental ---

def test_janela_de_eventos():
    desde, ate = "2026-11-10T00:00:00Z", "2026-11-12T00:00:00Z"
    evs = leitor().ler_eventos("emp-devhub", desde=desde, ate=ate).itens
    assert evs and all(desde < e.ocorrido_em.strftime("%Y-%m-%dT%H:%M:%SZ") <= ate for e in evs)


def test_janela_aceita_datetime():
    from datetime import datetime, timezone

    desde = datetime(2026, 11, 10, tzinfo=timezone.utc)
    evs = leitor().ler_eventos("emp-devhub", desde=desde).itens
    assert evs and all(e.ocorrido_em > desde for e in evs)


# --- leitura dirigida (D13): por usuário, por ids e por tag ---

def test_eventos_de_um_usuario():
    r = leitor().ler_eventos("emp-tintas", id_usuario="u-emp-tintas-01")
    assert r.itens and {e.id_usuario for e in r.itens} == {"u-emp-tintas-01"} and not r.truncada
    assert len(r.itens) == len([e for e in dados.EVENTOS if e["id_usuario"] == "u-emp-tintas-01"])


def test_usuario_sem_eventos_le_lista_vazia():
    assert leitor().ler_eventos("emp-tintas", id_usuario="u-emp-tintas-20").itens == []


def test_usuario_de_outra_empresa_e_erro_claro():
    with pytest.raises(ErroLeitura, match="usuário não encontrado"):
        leitor().ler_eventos("emp-tintas", id_usuario="u-emp-devhub-01")


def test_mcp_que_ignora_o_filtro_de_usuario_e_barrado():
    outro = {
        "id_evento": "e1", "id_empresa": "emp-tintas", "id_usuario": "u-outro", "tipo": "clique",
        "ocorrido_em": "2026-11-01T00:00:00Z",
    }
    with pytest.raises(ErroLeitura, match="outro usuário"):
        Leitor(lambda n, a: pagina([outro])).ler_eventos("emp-tintas", id_usuario="u-emp-tintas-01")


def test_conteudos_por_ids_em_blocos_sem_perder_nem_duplicar():
    ids = [c["id_conteudo"] for c in dados.CONTEUDOS if c["id_empresa"] == "emp-tintas"]
    chamadas = []

    def espia(nome, args):
        chamadas.append(args["ids"])
        return chamador_mock(nome, args)

    from tools import leitura

    r = Leitor(espia).ler_conteudos("emp-tintas", ids=ids + ["c-inexistente", ids[0]])
    assert sorted(c.id_conteudo for c in r.itens) == sorted(ids) and all(isinstance(c, Conteudo) for c in r.itens)
    assert len(chamadas) == 1 + len(ids) // leitura.IDS_POR_CHAMADA and all(len(c) <= leitura.IDS_POR_CHAMADA for c in chamadas)


def test_conteudos_por_ids_vazio_nao_chama_o_mcp():
    chamadas = []
    r = Leitor(lambda n, a: chamadas.append(a)).ler_conteudos("emp-tintas", ids=[])
    assert r.itens == [] and chamadas == []


def test_usuarios_por_tag():
    r = leitor().ler_usuarios("emp-tintas", tag="pintor")
    assert r.itens and all("pintor" in u.tags and u.id_empresa == "emp-tintas" for u in r.itens)


def test_teto_de_itens_fica_com_os_mais_recentes_e_avisa():
    todos = leitor().ler_eventos("emp-tintas").itens
    r = leitor().ler_eventos("emp-tintas", max_itens=10)
    assert r.truncada and len(r.itens) == 10 and r.total_lido == len(todos)
    assert sorted(e.ocorrido_em for e in todos)[-10:] == [e.ocorrido_em for e in r.itens]
    assert not leitor().ler_eventos("emp-tintas", max_itens=len(todos)).truncada


def test_teto_de_conteudos_fica_com_os_mais_recentes():
    r = leitor().ler_conteudos("emp-tintas", max_itens=5)
    assert r.truncada and len(r.itens) == 5
    assert [c.id_conteudo for c in r.itens] == [f"c-emp-tintas-{n:03d}" for n in range(36, 41)]  # as 5 mais novas


# --- erros: nunca dado parcial silencioso ---

@pytest.mark.parametrize("vazio", [None, "", "  "])
def test_id_empresa_obrigatorio(vazio):
    for ler in (leitor().ler_usuarios, leitor().ler_conteudos, leitor().ler_eventos):
        with pytest.raises(ErroLeitura, match="id_empresa é obrigatório"):
            ler(vazio)


def test_erro_do_mcp_vira_erro_claro():
    with pytest.raises(ErroLeitura, match="empresa não encontrada: emp-x"):
        leitor().ler_eventos("emp-x")


def test_teto_de_paginas_e_erro_e_nao_dado_parcial():
    with pytest.raises(ErroLeitura, match="passou de 2 páginas"):
        leitor(max_paginas=2).ler_eventos("emp-tintas")


def test_cursor_repetido_nao_gira_para_sempre():
    chamadas = []

    def preso(nome, args):
        chamadas.append(args)
        return pagina([], "7")

    with pytest.raises(ErroLeitura, match="repetiu o cursor"):
        Leitor(preso).ler_usuarios("emp-tintas")
    assert len(chamadas) == 2


@pytest.mark.parametrize("resposta", [None, [], {"x": 1}, {"itens": "nao-lista"}, {"itens": [], "proximo_cursor": 3}])
def test_resposta_fora_do_formato(resposta):
    with pytest.raises(ErroLeitura, match="fora do formato|texto ou nulo"):
        Leitor(lambda n, a: resposta).ler_usuarios("emp-tintas")


# --- dado malformado ---

def test_item_malformado_e_descartado_e_contado(caplog):
    bom = {"id_usuario": "u1", "id_empresa": "emp-tintas", "tags": ["pintor"]}
    sem_id = {"id_empresa": "emp-tintas", "tags": []}
    r = Leitor(lambda n, a: pagina([bom, sem_id, "lixo", {"id_usuario": "u3", "id_empresa": "emp-tintas"}])).ler_usuarios(
        "emp-tintas"
    )
    assert [u.id_usuario for u in r.itens] == ["u1", "u3"]  # campo opcional ausente (tags) não quebra
    assert r.descartados == 2
    assert "descartado" in caplog.text


# --- isolamento ---

@pytest.mark.parametrize("emp", EMPRESAS)
def test_nenhuma_leitura_devolve_item_de_outra_empresa(emp):
    l = leitor()
    for itens in (l.ler_usuarios(emp).itens, l.ler_conteudos(emp).itens, l.ler_eventos(emp).itens):
        assert itens and all(i.id_empresa == emp for i in itens)


def test_item_de_outra_empresa_interrompe_a_leitura():
    intruso = {"id_usuario": "u9", "id_empresa": "emp-devhub", "tags": []}
    with pytest.raises(ErroLeitura, match="outra empresa"):
        Leitor(lambda n, a: pagina([intruso])).ler_usuarios("emp-tintas")


# --- pelo protocolo MCP de verdade (mock em subprocesso, via stdio) ---

def _cliente_stdio():
    from mcp import StdioServerParameters
    from mcp.client.stdio import stdio_client
    from strands.tools.mcp.mcp_client import MCPClient

    params = StdioServerParameters(command=sys.executable, args=["-m", "mock_mcp.server"], cwd=str(RAIZ))
    return MCPClient(lambda: stdio_client(params))


def test_leitura_pelo_cliente_mcp_real():
    with _cliente_stdio() as cliente:
        l = Leitor(chamador_do_cliente(cliente))
        assert [e.id_empresa for e in l.ler_empresas().itens] == EMPRESAS
        assert len(l.ler_eventos("emp-memorial").itens) == len(
            [e for e in dados.EVENTOS if e["id_empresa"] == "emp-memorial"]
        )
        with pytest.raises(ErroLeitura, match="empresa não encontrada"):
            l.ler_usuarios("emp-x")


# --- cliente MCP local, sem assinatura ---

def test_sem_assinatura_so_para_host_local(monkeypatch):
    monkeypatch.setattr(settings, "mcp_sigv4", False)
    monkeypatch.setattr(settings, "gateway_url", "http://127.0.0.1:8765/mcp")
    assert get_gateway_mcp_client() is not None
    monkeypatch.setattr(settings, "gateway_url", "https://abc.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp")
    assert get_gateway_mcp_client() is None
