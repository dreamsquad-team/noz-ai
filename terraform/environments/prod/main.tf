provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.aws_account_id]

  default_tags {
    tags = var.tags
  }
}

module "filas_validacao" {
  source = "../../modules/filas-validacao"

  visibility_timeout_seconds = var.visibility_timeout_seconds
  max_receive_count          = var.max_receive_count
}

module "bucket_evidencias" {
  source = "../../modules/bucket-evidencias"

  dias_para_expirar = var.dias_para_expirar
}
