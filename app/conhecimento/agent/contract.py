"""Contratos do agente de Conhecimento: consultas dos outros agentes e as respostas.

Mesmo padrão da Validação (Pydantic + JSON Schema gerado em `contracts/`). O agente não guarda nada: cada consulta é de
uma pessoa, uma empresa, um conteúdo ou um grupo, lida do MCP e respondida na hora. Todo contrato leva `id_empresa`
obrigatório: o isolamento por empresa começa aqui.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Modo = Literal["real", "mock"]


# --- consultas ---

class _Consulta(BaseModel):
    id_empresa: str = Field(min_length=1, description="Empresa. Obrigatória: nenhuma consulta cruza empresas")
    modo: Modo = Field(default="real", description="Fonte dos dados: MCP real ou MCP mockado (dados fictícios)")


class _ConsultaComJanela(_Consulta):
    desde: datetime | None = Field(default=None, description="Início da janela de eventos. Vazio = janela padrão")
    ate: datetime | None = Field(default=None, description="Fim da janela de eventos. Vazio = agora")

    @model_validator(mode="after")
    def valida_janela(self):
        if self.desde and self.ate and self.ate <= self.desde:
            raise ValueError("'ate' deve ser posterior a 'desde'")
        return self


class ConsultaPerfilUsuario(_ConsultaComJanela):
    tipo: Literal["perfil_usuario"] = "perfil_usuario"
    id_usuario: str = Field(min_length=1, description="Usuário")


class ConsultaPerfilEmpresa(_Consulta):
    tipo: Literal["perfil_empresa"] = "perfil_empresa"


class ConsultaTemaConteudo(_Consulta):
    tipo: Literal["tema_conteudo"] = "tema_conteudo"
    id_conteudo: str = Field(min_length=1, description="Conteúdo")


class ConsultaPerfilGrupo(_ConsultaComJanela):
    tipo: Literal["perfil_grupo"] = "perfil_grupo"
    tag: str = Field(min_length=1, description="Tag que define o grupo, ex.: pintor")


# O campo `tipo` escolhe a consulta: {"tipo": "perfil_usuario", "id_empresa": "...", "id_usuario": "..."}
Consulta = Annotated[
    ConsultaPerfilUsuario | ConsultaPerfilEmpresa | ConsultaTemaConteudo | ConsultaPerfilGrupo,
    Field(discriminator="tipo"),
]


# --- respostas ---

class Interesse(BaseModel):
    topico: str = Field(min_length=1, description="Tópico de interesse, ex.: pintura")
    peso: float = Field(ge=0, le=1, description="Força do interesse, de 0 a 1, com até duas casas decimais")
    evidencias: list[str] = Field(
        min_length=1, description="Ids de eventos ou conteúdos que sustentam o interesse. Sem evidência, sem interesse"
    )

    @field_validator("peso")
    @classmethod
    def arredonda_peso(cls, valor):
        return round(valor, 2)


class PerfilUsuario(BaseModel):
    id_empresa: str = Field(min_length=1, description="Empresa do usuário")
    id_usuario: str = Field(min_length=1, description="Usuário")
    interesses: list[Interesse] = Field(default_factory=list, description="Interesses inferidos, do mais forte ao mais fraco")
    canal_preferido: str | None = Field(default=None, description="Canal mais usado na janela")
    dispositivo_preferido: str | None = Field(default=None, description="Dispositivo mais usado na janela")
    janela_desde: datetime = Field(description="Início da janela de eventos considerada")
    janela_ate: datetime = Field(description="Fim da janela de eventos considerada")
    eventos_considerados: int = Field(ge=0, description="Quantos eventos entraram no cálculo")
    avisos: list[str] = Field(default_factory=list, description="O que limitou ou degradou a resposta (cortes, conteúdos sem tema)")


class PerfilEmpresa(BaseModel):
    id_empresa: str = Field(min_length=1, description="Empresa")
    temas: list[Interesse] = Field(default_factory=list, description="Temas sobre os quais a empresa publica")
    conteudos_considerados: int = Field(ge=0, description="Quantos conteúdos entraram no cálculo")
    avisos: list[str] = Field(default_factory=list, description="O que limitou ou degradou a resposta")


class TemaConteudo(BaseModel):
    id_empresa: str = Field(min_length=1, description="Empresa dona do conteúdo")
    id_conteudo: str = Field(min_length=1, description="Conteúdo")
    topicos: list[str] = Field(description="Tópicos principais. Vazio quando não há tema ('sem tema')")
    categoria: str | None = Field(default=None, description="Categoria sugerida")
    resumo: str | None = Field(default=None, description="Resumo curto, sem instruções do texto original")
    idioma: str | None = Field(default=None, description="Idioma detectado")
    avisos: list[str] = Field(default_factory=list, description="Ex.: texto truncado antes de analisar")


class PerfilGrupo(BaseModel):
    id_empresa: str = Field(min_length=1, description="Empresa do grupo")
    tag: str = Field(min_length=1, description="Tag que define o grupo")
    usuarios_considerados: int = Field(ge=0, description="Usuários do grupo que entraram no cálculo")
    interesses: list[Interesse] = Field(
        default_factory=list,
        description="Interesse médio do grupo: média do peso entre os usuários considerados (quem não tem o tópico conta 0)",
    )
    janela_desde: datetime = Field(description="Início da janela de eventos considerada")
    janela_ate: datetime = Field(description="Fim da janela de eventos considerada")
    avisos: list[str] = Field(default_factory=list, description="O que limitou ou degradou a resposta")


# Contratos públicos que viram JSON Schema em `contracts/`.
CONTRATOS = {
    "consulta_perfil_usuario": ConsultaPerfilUsuario,
    "consulta_perfil_empresa": ConsultaPerfilEmpresa,
    "consulta_tema_conteudo": ConsultaTemaConteudo,
    "consulta_perfil_grupo": ConsultaPerfilGrupo,
    "perfil_usuario": PerfilUsuario,
    "perfil_empresa": PerfilEmpresa,
    "tema_conteudo": TemaConteudo,
    "perfil_grupo": PerfilGrupo,
}
