import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from agent import contract as c

PASTA = Path(__file__).parent.parent / "contracts"
EXEMPLOS = PASTA / "exemplos"

# exemplo -> modelo
EXEMPLO_MODELO = {
    "consulta_perfil_usuario.json": c.ConsultaPerfilUsuario,
    "consulta_perfil_empresa.json": c.ConsultaPerfilEmpresa,
    "consulta_tema_conteudo.json": c.ConsultaTemaConteudo,
    "consulta_perfil_grupo.json": c.ConsultaPerfilGrupo,
    "perfil_usuario.json": c.PerfilUsuario,
    "perfil_empresa.json": c.PerfilEmpresa,
    "tema_conteudo.json": c.TemaConteudo,
    "perfil_grupo.json": c.PerfilGrupo,
}


def carregar(caminho):
    return json.loads(caminho.read_text(encoding="utf-8"))


@pytest.mark.parametrize("nome, modelo", list(c.CONTRATOS.items()))
def test_schema_salvo_esta_atualizado(nome, modelo):
    salvo = carregar(PASTA / f"{nome}.schema.json")
    assert salvo == modelo.model_json_schema(), (
        f"{nome}.schema.json desatualizado. Rode: uv run python -m contracts.gerar_schemas"
    )


def test_nao_sobra_schema_de_contrato_removido():
    assert {p.name.removesuffix(".schema.json") for p in PASTA.glob("*.schema.json")} == set(c.CONTRATOS)


@pytest.mark.parametrize("arquivo, modelo", list(EXEMPLO_MODELO.items()))
def test_exemplo_e_valido(arquivo, modelo):
    modelo.model_validate(carregar(EXEMPLOS / arquivo))


def test_todo_exemplo_tem_modelo():
    assert {p.name for p in EXEMPLOS.glob("*.json")} == set(EXEMPLO_MODELO)


# --- consulta: o campo `tipo` escolhe o contrato ---

CONSULTA = TypeAdapter(c.Consulta)


@pytest.mark.parametrize(
    "arquivo, modelo",
    [(a, m) for a, m in EXEMPLO_MODELO.items() if a.startswith("consulta_")],
)
def test_tipo_escolhe_a_consulta(arquivo, modelo):
    assert isinstance(CONSULTA.validate_python(carregar(EXEMPLOS / arquivo)), modelo)


def test_tipo_desconhecido_ou_ausente_e_rejeitado():
    for dados in ({"tipo": "tudo", "id_empresa": "e"}, {"id_empresa": "e", "id_usuario": "u1"}):
        with pytest.raises(ValidationError):
            CONSULTA.validate_python(dados)


# --- isolamento: nenhuma consulta aceita ausência de empresa ---

@pytest.mark.parametrize(
    "dados",
    [
        {"tipo": "perfil_usuario", "id_usuario": "u1"},
        {"tipo": "perfil_empresa"},
        {"tipo": "tema_conteudo", "id_conteudo": "c1"},
        {"tipo": "perfil_grupo", "tag": "pintor"},
    ],
)
@pytest.mark.parametrize("empresa", [None, "", "x"])
def test_id_empresa_e_obrigatorio(dados, empresa):
    d = dict(dados)
    if empresa is not None:
        d["id_empresa"] = empresa
    if empresa == "x":
        CONSULTA.validate_python(d)  # com empresa, passa
        return
    with pytest.raises(ValidationError):
        CONSULTA.validate_python(d)


@pytest.mark.parametrize(
    "dados",
    [
        {"tipo": "perfil_usuario", "id_empresa": "e"},
        {"tipo": "tema_conteudo", "id_empresa": "e"},
        {"tipo": "perfil_grupo", "id_empresa": "e"},
    ],
)
def test_consulta_sem_o_alvo_e_rejeitada(dados):
    with pytest.raises(ValidationError):
        CONSULTA.validate_python(dados)


def test_janela_invertida_e_rejeitada():
    with pytest.raises(ValidationError):
        c.ConsultaPerfilUsuario(id_empresa="e", id_usuario="u", desde="2026-11-27T00:00:00Z", ate="2026-11-26T00:00:00Z")
    with pytest.raises(ValidationError):
        c.ConsultaPerfilGrupo(id_empresa="e", tag="t", desde="2026-11-27T00:00:00Z", ate="2026-11-27T00:00:00Z")


def test_modo_invalido_e_rejeitado_e_padrao_e_real():
    with pytest.raises(ValidationError):
        c.ConsultaPerfilEmpresa(id_empresa="e", modo="outro")
    assert c.ConsultaPerfilEmpresa(id_empresa="e").modo == "real"


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


def test_respostas_nao_guardam_estado():
    """Sem persistência: nenhuma resposta traz versão nem carimbo de atualização de armazenamento."""
    for modelo in (c.PerfilUsuario, c.PerfilEmpresa, c.TemaConteudo, c.PerfilGrupo):
        assert not {"versao", "atualizado_em", "atualizado_em_conteudo"} & set(modelo.model_fields)
