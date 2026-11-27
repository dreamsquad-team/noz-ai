"""Contratos do agente de Conhecimento: consultas dos outros agentes e as respostas.

As respostas são uma análise factual dos dados da NOZ (contagens, tipos, datas e ids que sustentam), sem pesos nem pontuação.

Mesmo padrão da Validação (Pydantic + JSON Schema gerado em `contracts/`). O agente não guarda nada: cada consulta é de
uma pessoa, uma empresa, um conteúdo ou um grupo, lida do MCP e respondida na hora. Todo contrato leva `id_empresa`
obrigatório: o isolamento por empresa começa aqui.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

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

class InteresseUsuario(BaseModel):
    """Um assunto em que o usuário esteve envolvido na janela. Só fatos dos eventos, sem pontuação."""

    topico: str = Field(min_length=1, description="Assunto (tópico do tema dos conteúdos acessados), ex.: pintura")
    eventos: int = Field(ge=1, description="Quantos eventos do usuário, na janela, foram sobre conteúdos com este tópico")
    por_tipo: dict[str, int] = Field(description="Esses eventos por tipo: clique, acesso, comentario")
    ultimo_evento_em: datetime = Field(description="Quando foi o evento mais recente sobre este tópico")
    evidencias: list[str] = Field(
        min_length=1, description="Ids dos eventos mais recentes sobre o tópico (até 5). Sem evidência, sem interesse"
    )


class TemaEmpresa(BaseModel):
    """Um assunto sobre o qual a empresa publica."""

    topico: str = Field(min_length=1, description="Assunto, ex.: pintura")
    conteudos: int = Field(ge=1, description="Quantos conteúdos considerados da empresa têm este tópico")
    evidencias: list[str] = Field(min_length=1, description="Ids de conteúdos com o tópico (até 5)")


class InteresseGrupo(BaseModel):
    """Um assunto presente nos usuários do grupo."""

    topico: str = Field(min_length=1, description="Assunto, ex.: pintura")
    usuarios: int = Field(ge=1, description="Quantos usuários do grupo (dos considerados) têm este tópico")
    evidencias: list[str] = Field(min_length=1, description="Ids de eventos mais recentes sobre o tópico no grupo (até 5)")


class PerfilUsuario(BaseModel):
    id_empresa: str = Field(min_length=1, description="Empresa do usuário")
    id_usuario: str = Field(min_length=1, description="Usuário")
    interesses: list[InteresseUsuario] = Field(
        default_factory=list, description="Assuntos dos conteúdos acessados, do que tem mais eventos ao que tem menos"
    )
    canal_preferido: str | None = Field(default=None, description="Canal mais usado na janela")
    dispositivo_preferido: str | None = Field(default=None, description="Dispositivo mais usado na janela")
    janela_desde: datetime = Field(description="Início da janela de eventos considerada")
    janela_ate: datetime = Field(description="Fim da janela de eventos considerada")
    eventos_considerados: int = Field(ge=0, description="Quantos eventos entraram no cálculo")
    avisos: list[str] = Field(default_factory=list, description="O que limitou ou degradou a resposta (cortes, conteúdos sem tema)")


class PerfilEmpresa(BaseModel):
    id_empresa: str = Field(min_length=1, description="Empresa")
    temas: list[TemaEmpresa] = Field(
        default_factory=list, description="Temas sobre os quais a empresa publica, do mais ao menos frequente"
    )
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
    interesses: list[InteresseGrupo] = Field(
        default_factory=list, description="Assuntos presentes nos usuários do grupo, do que mais usuários têm ao que menos"
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
