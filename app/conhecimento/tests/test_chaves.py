import pytest

from storage import chaves
from storage.chaves import Tipo


@pytest.mark.parametrize("tipo", list(Tipo))
def test_toda_pk_comeca_com_a_empresa(tipo):
    assert chaves.pk("emp1", tipo, "x9").startswith("emp1#")


def test_formato_da_chave():
    assert chaves.chave("emp1", Tipo.USUARIO, "u7") == {"PK": "emp1#usuario#u7", "SK": "ATUAL"}
    assert chaves.sk_hist("2026-11-26T10:00:00Z") == "HIST#2026-11-26T10:00:00Z"


def test_empresas_diferentes_nunca_geram_a_mesma_pk():
    assert chaves.pk("emp1", Tipo.CONTEUDO, "c1") != chaves.pk("emp2", Tipo.CONTEUDO, "c1")


@pytest.mark.parametrize("empresa", ["", "  ", None])
def test_empresa_vazia_e_rejeitada(empresa):
    with pytest.raises(ValueError):
        chaves.pk(empresa, Tipo.USUARIO, "u1")


@pytest.mark.parametrize("valor", ["a#b", ""])
def test_id_invalido_e_rejeitado(valor):
    with pytest.raises(ValueError):
        chaves.pk("emp1", Tipo.USUARIO, valor)
    with pytest.raises(ValueError):
        chaves.pk(valor, Tipo.USUARIO, "u1")


def test_separador_na_empresa_nao_permite_colisao():
    # sem a validação, ("a#usuario", "b") colidiria com ("a", "usuario#b")
    with pytest.raises(ValueError):
        chaves.pk("a#usuario", Tipo.USUARIO, "b")


def test_tipo_desconhecido_e_rejeitado():
    with pytest.raises(ValueError):
        chaves.pk("emp1", "outro", "u1")


def test_atributos_do_indice_e_empresa_da_chave():
    assert chaves.atributos_indexados("emp1", Tipo.GRUPO, "g2") == {"empresa_id": "emp1", "tipo_id": "grupo#g2"}
    assert chaves.empresa_da_chave(chaves.pk("emp1", Tipo.GRUPO, "g2")) == "emp1"
