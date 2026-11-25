variable "prefixo" {
  description = "Prefixo dos nomes das filas"
  type        = string
  default     = "noz-ai-validacao"
}

variable "visibility_timeout_seconds" {
  description = "Tempo que a mensagem fica invisível enquanto é processada. Deve ser maior que o timeout da Lambda"
  type        = number
  default     = 360 # TODO: confirmar (6 minutos)

  validation {
    condition     = var.visibility_timeout_seconds >= 0 && var.visibility_timeout_seconds <= 43200
    error_message = "O visibility timeout deve estar entre 0 e 43200 segundos (12 horas)."
  }
}

variable "max_receive_count" {
  description = "Quantas vezes a mensagem é entregue antes de ir para a DLQ"
  type        = number
  default     = 3 # TODO: confirmar

  validation {
    condition     = var.max_receive_count >= 1
    error_message = "max_receive_count defe ser pelo menos 1"
  }
}