variable "aws_region" {
  description = "Região da AWS"
  type        = string
  default     = "us-east-1"
}

variable "aws_account_id" {
  description = "ID da conta da AWS da NOZ. Protege contra aplicar na conta errada"
  type        = string
}

variable "tags" {
  description = "Tags aplicadas a todos os recursos"
  type        = map(string)
  default     = {}
}

variable "aws_profile" {
  description = "Perfil AWS repassado ao disparo do build (local-exec). Null usa a credencial do ambiente (AWS_PROFILE)"
  type        = string
  default     = null
}

variable "log_level" {
  description = "Nível de log do agente (LOG_LEVEL no runtime)"
  type        = string
  default     = "INFO"
}
