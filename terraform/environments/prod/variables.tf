variable "aws_region" {
  description = "Região da AWS"
  type        = string
  default     = "us-east-1"
}

variable "aws_account_id" {
  description = "ID da conta da AWS da NOZ"
  type        = string
}

variable "visibility_timeout_seconds" {
  description = "Visibility timeout da fila de entrada. Deve ser maior que o timeout da Lambda"
  type        = number
  default     = 360 # TODO: confirmar
}

variable "max_receive_count" {
  description = "Tentativas antes da mensagem ir pra DLQ"
  type        = number
  default     = 3 # TODO: confirmar
}

variable "dias_para_expirar" {
  description = "Dias até as evidências serem apagadas"
  type        = number
  default     = 90 # TODO: confirmar
}

variable "tags" {
  description = "Tags aplicadas a todos os recursos"
  type        = map(string)
  default     = {}
}