# Tudo que existe apenas para colocar uma imagem no ECR:
# repositório, bucket de source, projeto CodeBuild, role do builder e o disparo.
#
# O único output que o resto da stack consome é `image_uri`.

data "aws_caller_identity" "current" {}

locals {
  # A imagem é tagueada com o HASH DO SOURCE, não "latest".
  # Consequência: quando o código muda, o container_uri do agent runtime muda,
  # o Terraform enxerga a diferença e atualiza o Runtime. Com ":latest" fixo o
  # atributo nunca mudaria, o Terraform não veria diff, e o AgentCore
  # continuaria servindo a imagem antiga — silenciosamente.
  source_tag = "src-${substr(data.archive_file.source.output_sha256, 0, 12)}"
  image_tag  = coalesce(var.image_tag_override, local.source_tag)

  source_key = "${var.name_prefix}/source.zip"
}

# ---------------------------------------------------------------------------
# Guarda de configuração
# ---------------------------------------------------------------------------
resource "terraform_data" "validate_inputs" {
  lifecycle {
    precondition {
      condition     = var.build_on_apply || var.image_tag_override != null
      error_message = "Com build_on_apply = false é obrigatório informar image_tag_override — sem build e sem tag conhecida não há imagem para o Runtime referenciar."
    }
  }
}

# ---------------------------------------------------------------------------
# Repositório da imagem
# ---------------------------------------------------------------------------
resource "aws_ecr_repository" "this" {
  name                 = var.name_prefix
  image_tag_mutability = "MUTABLE" # a tag "latest" é reescrita a cada build

  image_scanning_configuration {
    scan_on_push = true
  }

  # Sem isso, `terraform destroy` falha enquanto houver imagem no repositório.
  force_delete = true

  tags = var.tags
}

resource "aws_ecr_lifecycle_policy" "this" {
  repository = aws_ecr_repository.this.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Mantém apenas as ${var.ecr_keep_last_n_images} imagens mais recentes"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = var.ecr_keep_last_n_images
      }
      action = { type = "expire" }
    }]
  })
}

# ---------------------------------------------------------------------------
# Source enviado ao CodeBuild
# ---------------------------------------------------------------------------
data "archive_file" "source" {
  type        = "zip"
  source_dir  = var.source_dir
  output_path = "${path.module}/.build/${var.name_prefix}-source.zip"
  excludes    = var.source_excludes

  # Normaliza a permissão dos arquivos dentro do zip. Sem isto, o MESMO código
  # zipado em Linux e em macOS produz hashes diferentes, e cada dev dispara um
  # rebuild inútil da imagem.
  output_file_mode = "0666"
}

resource "aws_s3_bucket" "source" {
  # Por stack, NÃO compartilhado da conta. O toolkit usava um único
  # "bedrock-agentcore-codebuild-sources-{account}-{region}" para todos os
  # agentes: o segundo stack falhava com BucketAlreadyOwnedByYou e um destroy
  # apagava o source de todos.
  bucket        = "${var.name_prefix}-build-source-${data.aws_caller_identity.current.account_id}"
  force_destroy = true # o conteúdo é descartável: só zips de source

  tags = var.tags
}

resource "aws_s3_bucket_versioning" "source" {
  bucket = aws_s3_bucket.source.id

  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "source" {
  bucket = aws_s3_bucket.source.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "source" {
  bucket = aws_s3_bucket.source.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Zips antigos não têm valor depois que a imagem foi construída.
resource "aws_s3_bucket_lifecycle_configuration" "source" {
  bucket = aws_s3_bucket.source.id

  rule {
    id     = "expire-old-sources"
    status = "Enabled"

    filter {}

    expiration {
      days = 30
    }
  }
}

resource "aws_s3_object" "source" {
  bucket = aws_s3_bucket.source.id
  key    = local.source_key
  source = data.archive_file.source.output_path
  etag   = data.archive_file.source.output_md5
}
