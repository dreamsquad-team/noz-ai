provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.aws_account_id]

  default_tags {
    tags = var.tags
  }
}

# O agente de Conhecimento não guarda nada (decisão de 27/11): só imagem, runtime e as permissões do runtime.
# O Gateway com o MCP real entra na ATHENA-988, quando o Gustavo entregar o contrato. Enquanto isso, o
# modo "mock" do agente roda dentro do próprio runtime, sem Gateway.
locals {
  # ECR, S3 e IAM com hífen; o nome do runtime não aceita hífen.
  name_prefix  = "noz-conhecimento-prod"
  runtime_name = "noz_conhecimento"
}

module "build" {
  source = "../../../modules/container-build"

  name_prefix = local.name_prefix
  # a pasta do agente (tem o Dockerfile); os excludes padrão do módulo já deixam de fora testes e scripts
  source_dir  = "${path.module}/../../../../app/conhecimento"
  aws_region  = var.aws_region
  aws_profile = var.aws_profile
  tags        = var.tags
}

module "runtime" {
  source = "../../../modules/agent-runtime"

  name               = local.runtime_name
  role_name          = "${local.name_prefix}-runtime"
  image_uri          = module.build.image_uri
  ecr_repository_arn = module.build.ecr_repository_arn
  aws_region         = var.aws_region
  tags               = var.tags

  # sem memória (memory_arn = null) e sem gateway por enquanto (gateway_arns = [])
  # AWS_REGION não entra aqui: o ambiente gerenciado do runtime já a define
  environment_variables = {
    LOG_LEVEL = var.log_level
  }
}
