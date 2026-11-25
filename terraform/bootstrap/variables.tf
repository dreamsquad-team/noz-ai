variable "aws_region" {
  description = "Região da AWS onde o bucket de state será criado"
  type        = string
  default     = "us-east-1"
}

variable "aws_account_id" {
  description = "ID da conta da NOZ. Protege contra aplicar na conta errada"
  type        = string
}

variable "state_bucket_name" {
  description = "Nome do bucket do state. Precisa ser único no mundo"
  type        = string
}

variable "tags" {
  description = "Tags aplicadas a todos os recursos"
  type        = map(string)
  default     = {}
}