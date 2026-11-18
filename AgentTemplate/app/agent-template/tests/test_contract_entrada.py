from agent.contract import ProvaEntrada
from pydantic import ValidationError
import pytest


def entrada_valida(**mudancas):
    base = {
        "id_envio": "3f2b8c1e-5a4d-4b7e-9c10-2d6e8f0a1b23",
        "id_desafio": "desafio-teste",
        "id_empresa": "empresa-teste",
        "tipo": "texto",
        "conteudo": "Conteúdo de teste",
        "regras_desafio": "Regras do desafio de teste",
        "descricao": "descrição de teste",
    }
    return {**base, **mudancas}


def test_aceita_foto_no_s3():
    prova = ProvaEntrada(**entrada_valida(tipo="foto", conteudo="desafios/foto.jpg"))
    assert prova.conteudo == "desafios/foto.jpg"


def test_aceita_extensao_maiuscula():
    prova = ProvaEntrada(**entrada_valida(tipo="foto", conteudo="desafios/foto.JPG"))
    assert prova.conteudo == "desafios/foto.JPG"


def test_aceita_link_https():
    prova = ProvaEntrada(**entrada_valida(tipo="link", conteudo="https://exemplo.com"))
    assert prova.conteudo == "https://exemplo.com"


def test_aceita_texto():
    prova = ProvaEntrada(**entrada_valida(tipo="texto", conteudo="Este é um texto de teste."))
    assert prova.conteudo == "Este é um texto de teste."


def test_aceita_descricao():
    prova = ProvaEntrada(**entrada_valida(descricao="Descrição de teste"))
    assert prova.descricao == "Descrição de teste"


def test_aceita_regras_desafio():
    prova = ProvaEntrada(**entrada_valida(regras_desafio="Regras do desafio de teste"))
    assert prova.regras_desafio == "Regras do desafio de teste"


def test_aceita_id_desafio():
    prova = ProvaEntrada(**entrada_valida(id_desafio="desafio-teste"))
    assert prova.id_desafio == "desafio-teste"


def test_aceita_id_empresa():
    prova = ProvaEntrada(**entrada_valida(id_empresa="empresa-teste"))
    assert prova.id_empresa == "empresa-teste"


def test_aceita_id_envio(): 
    prova = ProvaEntrada(**entrada_valida(id_envio="3f2b8c1e-5a4d-4b7e-9c10-2d6e8f0a1b23"))
    assert str(prova.id_envio) == "3f2b8c1e-5a4d-4b7e-9c10-2d6e8f0a1b23"


def test_aceita_contexto_extra():
    prova = ProvaEntrada(**entrada_valida(contexto_extra="Informações adicionais"))
    assert prova.contexto_extra == "Informações adicionais"


def test_contexto_extra_opcional():
    prova = ProvaEntrada(**entrada_valida())
    assert prova.contexto_extra is None


def test_rejeita_tipo_invalido():
    with pytest.raises(ValidationError):
        ProvaEntrada(**entrada_valida(tipo="audio"))  # Tipo inválido


def test_rejeita_id_vazio():
    with pytest.raises(ValidationError):
        ProvaEntrada(**entrada_valida(id_envio="")) # ID vazio


def test_rejeita_id_ausente():
    dados = entrada_valida()
    del dados["id_envio"]
    with pytest.raises(ValidationError):
        ProvaEntrada(**dados)  # ID ausente


def test_rejeita_foto_sem_s3():
    with pytest.raises(ValidationError):
        ProvaEntrada(**entrada_valida(tipo="foto", conteudo="https://exemplo.com/foto.jpg"))


def test_rejeita_foto_vazia():
    with pytest.raises(ValidationError):
        ProvaEntrada(**entrada_valida(tipo="foto", conteudo=""))  # Conteúdo vazio para foto


def test_rejeita_foto_s3_sem_chave():
    with pytest.raises(ValidationError):
        ProvaEntrada(**entrada_valida(tipo="foto", conteudo="s3://bucket-teste/"))  # S3 sem chave


def test_rejeita_foto_s3_sem_extensao_imagem():
    with pytest.raises(ValidationError):
        ProvaEntrada(**entrada_valida(tipo="foto", conteudo="s3://bucket-teste/foto.pdf"))  # S3 sem extensão de imagem


def test_rejeita_s3_invalido():
    with pytest.raises(ValidationError):
        ProvaEntrada(**entrada_valida(tipo="foto", conteudo="s3://bucket"))  # S3 inválido


def test_rejeita_link_sem_http():
    with pytest.raises(ValidationError):
        ProvaEntrada(**entrada_valida(tipo="link", conteudo="www.exemplo.com"))  # Link sem http/https


def test_rejeita_texto_vazio():
    with pytest.raises(ValidationError):
        ProvaEntrada(**entrada_valida(tipo="texto", conteudo=""))  # Conteúdo vazio para texto


def test_rejeita_texto_com_espacos():
    with pytest.raises(ValidationError):
        ProvaEntrada(**entrada_valida(tipo="texto", conteudo="   "))  # Conteúdo apenas com espaços


def test_rejeita_descricao_vazia():
    with pytest.raises(ValidationError):
        ProvaEntrada(**entrada_valida(descricao=""))  # Descrição vazia


def test_rejeita_regras_desafio_vazia():
    with pytest.raises(ValidationError):
        ProvaEntrada(**entrada_valida(regras_desafio=""))  # Regras do desafio vazias


def test_rejeita_descricao_ausente():
    dados = entrada_valida()
    del dados["descricao"]
    with pytest.raises(ValidationError):
        ProvaEntrada(**dados)  # Descrição ausente


def test_rejeita_regras_desafio_ausente():
    dados = entrada_valida()
    del dados["regras_desafio"]
    with pytest.raises(ValidationError):
        ProvaEntrada(**dados)  # Regras do desafio ausentes


def test_rejeita_id_desafio_vazio():
    with pytest.raises(ValidationError):
        ProvaEntrada(**entrada_valida(id_desafio=""))  # ID do desafio vazio


def test_rejeita_id_desafio_ausente():
    dados = entrada_valida()
    del dados["id_desafio"]
    with pytest.raises(ValidationError):
        ProvaEntrada(**dados)  # ID do desafio ausente


def test_rejeita_id_empresa_vazio():
    with pytest.raises(ValidationError):
        ProvaEntrada(**entrada_valida(id_empresa=""))  # ID da empresa vazio


def test_rejeita_id_empresa_ausente():
    dados = entrada_valida()
    del dados["id_empresa"]
    with pytest.raises(ValidationError):
        ProvaEntrada(**dados)  # ID da empresa ausente
