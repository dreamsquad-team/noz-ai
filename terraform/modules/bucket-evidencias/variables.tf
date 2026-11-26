variable "prefixo" {
  description = "Prefixo do nome do bucket. O ID da conta é acrescentado ao final para o nome ser único"
  type        = string
  default     = "noz-ai-evidencias"
}

variable "dias_para_expirar" {
  description = "Dias até as evidências serem apagadas automaticamente"
  type        = number
  default     = 90

  validation {
    condition     = var.dias_para_expirar >= 1
    error_message = "dias_para_expirar deve ser pelo menos 1"
  }
}