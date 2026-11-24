from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, model_validator, field_validator

EXTENSOES_IMAGEM = (".jpg", ".jpeg", ".png", ".gif", ".webp")


class RegraDesafio(BaseModel):
    nome: str = Field(min_length=1, description="Nome da ação que o participante precisa realizar")
    descricao: str | None = Field(default=None, description="Descrição da ação, com o que conta como cumprir. Pode vir vazia")
    tipo_medicao: Literal["vezes", "quantidade", "percentual_meta", "conquista_unica"] = Field(
        description="Como a ação é medida: vezes (conta ocorrências), quantidade (soma um valor com o rótulo), percentual_meta (vale o maior percentual atingido), conquista_unica (acontece uma única vez)"
    )


class ProvaEntrada(BaseModel):
    id_envio: UUID = Field(description="Identificador único do envio da prova")
    id_desafio: str = Field(min_length=1, description="Identificador da missão(desafio)")
    id_empresa: str = Field(min_length=1, description="Identificador da empresa")
    tipo: Literal["foto", "link", "texto"] = Field(description="Tipo de conteúdo enviado: foto, link ou texto")
    conteudo: str = Field(min_length=1, description="Foto: chave do objeto no S3, sem bucket, terminando em jpg, jpeg, png, gif ou webp. Link: URL http ou https. Texto: texto não vazio.")
    descricao: str = Field(min_length=1, description="Descrição escrita pelo participante ao enviar a comprovação")
    regras_desafio: RegraDesafio = Field(description="Ação do desafio: nome, descrição e tipo de medição")
    contexto_extra: str | None = Field(default=None, description="Informações adicionais sobre o contexto do desafio, se houver")

    @model_validator(mode="after")
    def valida_conteudo_por_tipo(self):
        """Valida o campo 'conteudo' com base no valor do campo 'tipo'"""
        if self.tipo == "foto":
            if self.conteudo.startswith(("s3://", "http://", "https://", "/")):
                raise ValueError("Conteúdo inválido para tipo 'foto': deve ser apenas a chave do arquivo, sem 's3://', bucket ou '/' no início.")

            if not self.conteudo.lower().endswith(EXTENSOES_IMAGEM):
                raise ValueError("Conteúdo inválido para tipo 'foto': a chave deve terminar com uma extensão de imagem válida.")
            
        elif self.tipo == "link":
            if not (self.conteudo.startswith("http://") or self.conteudo.startswith("https://")): 
                raise ValueError("Conteúdo inválido para tipo 'link': deve ser uma URL válida.")
        elif self.tipo == "texto":
            if len(self.conteudo.strip()) == 0:
                raise ValueError("Conteúdo inválido para tipo 'texto': deve ser um texto não vazio.")
        return self


class ProvaSaida(BaseModel):
    id_envio: UUID = Field(description="Identificador único do envio da prova")
    status: Literal["aprovado", "reprovado", "para_analise"] = Field(description="Decisão: aprovado, reprovado ou para análise")
    confianca: float = Field(ge=0, le=1, description="Confiança na decisão, de 0 a 1, com até duas casas decimais")
    justificativa: str = Field(min_length=1, description="Motivo ou explicação da decisão tomada pelo agente, para o revisor humano")

    @field_validator("confianca")
    @classmethod
    def arredonda_confianca(cls, valor):
        """Mantém a confiança com no máximo duas casas decimais"""
        return round(valor, 2)
    
