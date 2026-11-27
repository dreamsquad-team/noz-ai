provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.aws_account_id]

  default_tags {
    tags = var.tags
  }
}

module "perfis" {
  source = "../../../modules/perfis-dynamodb"
}
