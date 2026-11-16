from agent.contract import ProvaSaida
from pydantic import ValidationError
import pytest


def saida_valida(**mudancas):
    base = {
        "id": "1",
        "status": "aprovado",
        "confianca": 85,
    }
    return {**base, **mudancas}


def test_aceita_saida_valida():
    prova = ProvaSaida(**saida_valida())
    assert prova.id == "1"
    assert prova.status == "aprovado"
    assert prova.confianca == 85


def test_rejeita_status_invalido():
    with pytest.raises(ValidationError):
        ProvaSaida(**saida_valida(status="pendente"))  # Status inválido


def test_rejeita_confianca_menor_que_zero():
    with pytest.raises(ValidationError):
        ProvaSaida(**saida_valida(confianca=-1))  # Confianca menor que zero


def test_rejeita_confianca_maior_que_cem():
    with pytest.raises(ValidationError):
        ProvaSaida(**saida_valida(confianca=101))  # Confianca maior que cem


def test_rejeita_id_vazio():
    with pytest.raises(ValidationError):
        ProvaSaida(**saida_valida(id=""))  # ID vazio


def test_rejeita_id_ausente():
    dados = saida_valida()
    del dados["id"]
    with pytest.raises(ValidationError):
        ProvaSaida(**dados)  # ID ausente


def test_rejeita_confianca_ausente():
    dados = saida_valida()
    del dados["confianca"]
    with pytest.raises(ValidationError):
        ProvaSaida(**dados)  # Confianca ausente


def test_rejeita_status_ausente():
    dados = saida_valida()
    del dados["status"]
    with pytest.raises(ValidationError):
        ProvaSaida(**dados)  # Status ausente


def test_rejeita_confianca_nao_inteiro():
    with pytest.raises(ValidationError):
        ProvaSaida(**saida_valida(confianca=50.5))  # Confianca não é inteiro


def test_rejeita_confianca_nao_numero():
    with pytest.raises(ValidationError):
        ProvaSaida(**saida_valida(confianca="cinquenta"))  # Confianca não é número


def test_rejeita_status_nao_string():
    with pytest.raises(ValidationError):
        ProvaSaida(**saida_valida(status=123))  # Status não é string


