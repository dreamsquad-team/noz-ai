variable "nome" {
  description = "Nome da tabela de perfis"
  type        = string
  default     = "noz-conhecimento-perfis"
}

variable "habilitar_pitr" {
  description = "Recuperação ponto no tempo (backup contínuo)"
  type        = bool
  default     = true
}

variable "ttl_atributo" {
  description = "Atributo com o epoch de expiração (retenção). null = sem TTL até a NOZ definir a retenção (LGPD)"
  type        = string
  default     = null
}
