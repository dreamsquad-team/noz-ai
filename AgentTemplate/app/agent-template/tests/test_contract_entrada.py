from agent.contract import ProvaEntrada
from pydantic import ValidationError
import pytest


def entrada_valida(**mudancas):
    base = {
        "id": "1",
        "tipo": "texto",
        "conteudo": "Conteúdo de teste",
        "descricao": "descrição de teste",
    }
    return {**base, **mudancas}


def test_aceita_foto_com_referencia_s3():
    prova = ProvaEntrada(**entrada_valida(tipo="foto", conteudo="s3://bucket-teste/desafios/foto.jpg"))
    assert prova.conteudo == "s3://bucket-teste/desafios/foto.jpg"


def test_aceita_extensao_maiuscula():
    prova = ProvaEntrada(**entrada_valida(tipo="foto", conteudo="s3://bucket-teste/desafios/foto.JPG"))
    assert prova.conteudo == "s3://bucket-teste/desafios/foto.JPG"


def test_aceita_link_https():
    prova = ProvaEntrada(**entrada_valida(tipo="link", conteudo="https://exemplo.com"))
    assert prova.conteudo == "https://exemplo.com"


def test_aceita_texto():
    prova = ProvaEntrada(**entrada_valida(tipo="texto", conteudo="Este é um texto de teste."))
    assert prova.conteudo == "Este é um texto de teste."


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
        ProvaEntrada(**entrada_valida(id="")) # ID vazio


def test_rejeita_id_ausente():
    dados = entrada_valida()
    del dados["id"]
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
