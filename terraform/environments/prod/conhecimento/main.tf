provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.aws_account_id]

  default_tags {
    tags = var.tags
  }
}

# O agente de Conhecimento não guarda nada (decisão de 27/11), então não há tabela aqui.
# Os recursos da infra (container, runtime, Gateway) entram na T09, ver
# docs/specs/conhecimento/tasks/T09-terraform-infra.md.
