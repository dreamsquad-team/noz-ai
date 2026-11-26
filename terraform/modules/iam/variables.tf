variable "prefixo" {
  description = "Prefixo do nome da policy"
  type        = string
  default     = "noz-ai-validacao"
}

variable "entrada_queue_arn" {
  description = "Arn da fila de entrada (o backend envia aqui)"
  type        = string
}

variable "saida_queue_arn" {
  description = "ARN da fila de saída (o backend lê daqui)"
  type        = string
}

variable "bucket_arn" {
  description = "ARN do bucket de evidências (o backend grava aqui)"
  type        = string
}

variable "backend_role_names" {
  description = "Roles do backend da NOZ que receberão a policy. Vazio = só cria a policy"
  type        = list(string)
  default     = []
}