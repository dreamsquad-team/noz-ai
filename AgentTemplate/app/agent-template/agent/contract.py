from typing import Literal
from pydantic import BaseModel, Field, model_validator

EXTENSOES_IMAGEM = (".jpg", ".jpeg", ".png", ".gif", ".webp")


class ProvaEntrada(BaseModel):
    id: str = Field(min_length=1)
    tipo: Literal["foto", "link", "texto"]
    conteudo: str = Field(min_length=1)
    descricao: str = Field(min_length=1)
    contexto_extra: str | None = None

    @model_validator(mode="after")
    def valida_conteudo_por_tipo(self):
        """Valida o campo 'conteudo' com base no valor do campo 'tipo'"""
        if self.tipo == "foto":          
            if not (self.conteudo.startswith("s3://")):
                raise ValueError("Conteúdo inválido para tipo 'foto': deve ser uma URL do S3 válida.")

            bucket, _, chave = self.conteudo.removeprefix("s3://").partition("/")
            if not bucket or not chave:
                raise ValueError("Conteúdo inválido para tipo 'foto': deve ser uma URL do S3 válida com bucket e chave.")

            if not chave.lower().endswith(EXTENSOES_IMAGEM):
                raise ValueError("Conteúdo inválido para tipo 'foto': deve ser uma URL do S3 com extensão de imagem válida.")
            
        elif self.tipo == "link":
            if not (self.conteudo.startswith("http://") or self.conteudo.startswith("https://")):  # Valida se é uma URL válida
                raise ValueError("Conteúdo inválido para tipo 'link': deve ser uma URL válida.")
        elif self.tipo == "texto":
            if len(self.conteudo.strip()) == 0:
                raise ValueError("Conteúdo inválido para tipo 'texto': deve ser um texto não vazio.")
        return self


class ProvaSaida(BaseModel):
    id: str = Field(min_length=1)
    status: Literal["aprovado", "reprovado", "para_analise"]
    confianca: int = Field(ge=0, le=100)
    