from agent.contract import ProvaSaida
from pydantic import ValidationError
import pytest


def saida_valida(**mudancas):
    base = {
        "id_envio": "3f2b8c1e-5a4d-4b7e-9c10-2d6e8f0a1b23",
        "status": "aprovado",
        "confianca": 0.75,
        "justificativa": "A prova cumpre as regras do desafio.",
    }
    return {**base, **mudancas}


def test_aceita_saida_valida():
    prova = ProvaSaida(**saida_valida())
    assert str(prova.id_envio) == "3f2b8c1e-5a4d-4b7e-9c10-2d6e8f0a1b23"
    assert prova.status == "aprovado"
    assert prova.confianca == 0.75
    assert prova.justificativa == "A prova cumpre as regras do desafio."


def test_aceita_status_reprovado():
    prova = ProvaSaida(**saida_valida(status="reprovado"))
    assert prova.status == "reprovado"


def test_aceita_status_para_analise():
    prova = ProvaSaida(**saida_valida(status="para_analise"))
    assert prova.status == "para_analise"


def test_aceita_confianca_maxima():
    prova = ProvaSaida(**saida_valida(confianca=1.0))
    assert prova.confianca == 1.0


def test_aceita_confianca_minima():
    prova = ProvaSaida(**saida_valida(confianca=0.0))
    assert prova.confianca == 0.0


def test_aceita_confianca_decimal():
    prova = ProvaSaida(**saida_valida(confianca=0.5))
    assert prova.confianca == 0.5


def test_rejeita_status_invalido():
    with pytest.raises(ValidationError):
        ProvaSaida(**saida_valida(status="pendente"))  # Status inválido


def test_rejeita_confianca_menor_que_zero():
    with pytest.raises(ValidationError):
        ProvaSaida(**saida_valida(confianca=-1.0))  # Confianca menor que zero


def test_rejeita_confianca_maior_que_cem():
    with pytest.raises(ValidationError):
        ProvaSaida(**saida_valida(confianca=101.0))  # Confianca maior que cem


def test_rejeita_id_vazio():
    with pytest.raises(ValidationError):
        ProvaSaida(**saida_valida(id_envio=""))  # ID vazio


def test_rejeita_id_ausente():
    dados = saida_valida()
    del dados["id_envio"]
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


def test_rejeita_confianca_nao_numero():
    with pytest.raises(ValidationError):
        ProvaSaida(**saida_valida(confianca="cinquenta"))  # Confianca não é número


def test_rejeita_status_nao_string():
    with pytest.raises(ValidationError):
        ProvaSaida(**saida_valida(status=123))  # Status não é string


