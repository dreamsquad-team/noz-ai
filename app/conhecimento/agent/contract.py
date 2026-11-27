"""Contratos do agente de Conhecimento (entrada, saída, perfis e consultas).

Mesmo padrão da Validação (Pydantic + JSON Schema gerado em `contracts/`). Todo contrato leva `id_empresa`
obrigatório: o isolamento por empresa começa aqui.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

TODAS_AS_EMPRESAS = "todas"


class ConhecimentoEntrada(BaseModel):
    """Disparo de uma execução agendada."""

    id_empresa: str = Field(min_length=1, description="Empresa a processar, ou 'todas' para todas as empresas")
    desde: datetime | None = Field(default=None, description="Início da janela. Vazio = desde a última execução")
    ate: datetime | None = Field(default=None, description="Fim da janela. Vazio = agora")
    modo: Literal["real", "mock"] = Field(default="real", description="Fonte dos dados: MCP real ou MCP mockado")

    @model_validator(mode="after")
    def valida_janela(self):
        if self.desde and self.ate and self.ate <= self.desde:
            raise ValueError("'ate' deve ser posterior a 'desde'")
        return self


class ConhecimentoSaida(BaseModel):
    """Resumo de uma execução."""

    id_empresa: str = Field(min_length=1, description="Empresa processada, ou 'todas'")
    janela_desde: datetime | None = Field(description="Início efetivo da janela processada")
    janela_ate: datetime = Field(description="Fim efetivo da janela processada")
    usuarios_processados: int = Field(ge=0, description="Perfis de usuário atualizados")
    conteudos_processados: int = Field(ge=0, description="Conteúdos com tema gerado ou atualizado")
    eventos_processados: int = Field(ge=0, description="Eventos lidos na janela")
    erros: list[str] = Field(default_factory=list, description="Erros ocorridos, sem stack trace")


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
    canal_preferido: str | None = Field(default=None, description="Canal mais usado")
    dispositivo_preferido: str | None = Field(default=None, description="Dispositivo mais usado")
    atualizado_em: datetime = Field(description="Quando o perfil foi atualizado")
    versao: int = Field(ge=1, description="Versão do perfil, incrementada a cada atualização")


class PerfilEmpresa(BaseModel):
    id_empresa: str = Field(min_length=1, description="Empresa")
    temas: list[Interesse] = Field(default_factory=list, description="Temas sobre os quais a empresa publica")
    atualizado_em: datetime = Field(description="Quando o perfil foi atualizado")
    versao: int = Field(ge=1, description="Versão do perfil")


class TemaConteudo(BaseModel):
    id_empresa: str = Field(min_length=1, description="Empresa dona do conteúdo")
    id_conteudo: str = Field(min_length=1, description="Conteúdo")
    topicos: list[str] = Field(description="Tópicos principais. Vazio quando não há tema ('sem tema')")
    categoria: str | None = Field(default=None, description="Categoria sugerida")
    resumo: str | None = Field(default=None, description="Resumo curto, sem instruções do texto original")
    idioma: str | None = Field(default=None, description="Idioma detectado")
    atualizado_em: datetime = Field(description="Quando o tema foi gerado")
    atualizado_em_conteudo: datetime = Field(description="`atualizado_em` do conteúdo usado; evita reprocessar a mesma versão")


class ConsultaPerfilUsuario(BaseModel):
    id_empresa: str = Field(min_length=1, description="Empresa. Obrigatória")
    id_usuario: str = Field(min_length=1, description="Usuário")


class ConsultaTemaConteudo(BaseModel):
    id_empresa: str = Field(min_length=1, description="Empresa. Obrigatória")
    id_conteudo: str = Field(min_length=1, description="Conteúdo")


class ConsultaPerfilGrupo(BaseModel):
    id_empresa: str = Field(min_length=1, description="Empresa. Obrigatória")
    tag: str = Field(min_length=1, description="Tag que define o grupo, ex.: pintor")


# Contratos públicos que viram JSON Schema em `contracts/`.
CONTRATOS = {
    "entrada": ConhecimentoEntrada,
    "saida": ConhecimentoSaida,
    "perfil_usuario": PerfilUsuario,
    "perfil_empresa": PerfilEmpresa,
    "tema_conteudo": TemaConteudo,
    "consulta_perfil_usuario": ConsultaPerfilUsuario,
    "consulta_tema_conteudo": ConsultaTemaConteudo,
    "consulta_perfil_grupo": ConsultaPerfilGrupo,
}
