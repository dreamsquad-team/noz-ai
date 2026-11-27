import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent import contract as c

PASTA = Path(__file__).parent.parent / "contracts"
EXEMPLOS = PASTA / "exemplos"

# exemplo -> modelo
EXEMPLO_MODELO = {
    "entrada_empresa.json": c.ConhecimentoEntrada,
    "entrada_todas.json": c.ConhecimentoEntrada,
    "saida_ok.json": c.ConhecimentoSaida,
    "perfil_usuario.json": c.PerfilUsuario,
    "perfil_empresa.json": c.PerfilEmpresa,
    "tema_conteudo.json": c.TemaConteudo,
    "consulta_perfil_usuario.json": c.ConsultaPerfilUsuario,
    "consulta_tema_conteudo.json": c.ConsultaTemaConteudo,
    "consulta_perfil_grupo.json": c.ConsultaPerfilGrupo,
}


def carregar(caminho):
    return json.loads(caminho.read_text(encoding="utf-8"))


@pytest.mark.parametrize("nome, modelo", list(c.CONTRATOS.items()))
def test_schema_salvo_esta_atualizado(nome, modelo):
    salvo = carregar(PASTA / f"{nome}.schema.json")
    assert salvo == modelo.model_json_schema(), (
        f"{nome}.schema.json desatualizado. Rode: uv run python -m contracts.gerar_schemas"
    )


@pytest.mark.parametrize("arquivo, modelo", list(EXEMPLO_MODELO.items()))
def test_exemplo_e_valido(arquivo, modelo):
    modelo.model_validate(carregar(EXEMPLOS / arquivo))


def test_todo_exemplo_tem_modelo():
    assert {p.name for p in EXEMPLOS.glob("*.json")} == set(EXEMPLO_MODELO)


# --- isolamento: nenhum contrato aceita ausência de empresa ---

@pytest.mark.parametrize(
    "modelo, extra",
    [
        (c.ConhecimentoEntrada, {}),
        (c.ConsultaPerfilUsuario, {"id_usuario": "u1"}),
        (c.ConsultaTemaConteudo, {"id_conteudo": "c1"}),
        (c.ConsultaPerfilGrupo, {"tag": "pintor"}),
    ],
)
@pytest.mark.parametrize("empresa", [None, ""])
def test_id_empresa_e_obrigatorio(modelo, extra, empresa):
    dados = dict(extra)
    if empresa is not None:
        dados["id_empresa"] = empresa
    with pytest.raises(ValidationError):
        modelo.model_validate(dados)


def test_janela_invertida_e_rejeitada():
    with pytest.raises(ValidationError):
        c.ConhecimentoEntrada(id_empresa="e", desde="2026-11-27T00:00:00Z", ate="2026-11-26T00:00:00Z")


def test_modo_invalido_e_rejeitado():
    with pytest.raises(ValidationError):
        c.ConhecimentoEntrada(id_empresa="e", modo="outro")


def test_modo_padrao_e_real():
    assert c.ConhecimentoEntrada(id_empresa="e").modo == "real"


# --- interesses: sem evidência, sem interesse ---

def test_interesse_sem_evidencia_e_rejeitado():
    with pytest.raises(ValidationError):
        c.Interesse(topico="pintura", peso=0.5, evidencias=[])


@pytest.mark.parametrize("peso", [-0.1, 1.1])
def test_peso_fora_do_intervalo_e_rejeitado(peso):
    with pytest.raises(ValidationError):
        c.Interesse(topico="pintura", peso=peso, evidencias=["e1"])


def test_peso_e_arredondado_em_duas_casas():
    assert c.Interesse(topico="pintura", peso=0.8249, evidencias=["e1"]).peso == 0.82
