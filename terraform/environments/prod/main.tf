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

module "iam_backend_noz" {
  source = "../../modules/iam"

  entrada_queue_arn  = module.filas_validacao.entrada_arn
  saida_queue_arn    = module.filas_validacao.saida_arn
  bucket_arn         = module.bucket_evidencias.arn
  backend_role_names = [] # Preencher quando informarem a role
}