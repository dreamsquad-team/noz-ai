resource "aws_cloudwatch_log_group" "build" {
  # Pré-criado para que o log tenha retenção definida. Se deixássemos o
  # CodeBuild criar sozinho, a retenção seria "nunca expira".
  name              = "/aws/codebuild/${var.name_prefix}-agent-builder"
  retention_in_days = 30

  tags = var.tags
}

resource "aws_codebuild_project" "builder" {
  name          = "${var.name_prefix}-agent-builder"
  description   = "Constrói a imagem do AgentCore Runtime de ${var.name_prefix}"
  service_role  = aws_iam_role.builder.arn
  build_timeout = var.build_timeout_minutes

  artifacts {
    # A imagem vai direto para o ECR pelo buildspec; não há artefato a guardar.
    type = "NO_ARTIFACTS"
  }

  environment {
    # ARM_CONTAINER + imagem aarch64: o AgentCore Runtime só executa arm64.
    type            = "ARM_CONTAINER"
    compute_type    = var.build_compute_type
    image           = var.build_image
    privileged_mode = true # necessário para rodar o daemon do Docker

    # O que varia entra por aqui, mantendo o buildspec.yml estático.
    environment_variable {
      name  = "ECR_REPOSITORY_URI"
      value = aws_ecr_repository.this.repository_url
    }

    environment_variable {
      name  = "IMAGE_TAG"
      value = local.image_tag
    }
  }

  source {
    type      = "S3"
    location  = "${aws_s3_bucket.source.id}/${aws_s3_object.source.key}"
    buildspec = file("${path.module}/buildspec.yml")
  }

  logs_config {
    cloudwatch_logs {
      group_name = aws_cloudwatch_log_group.build.name
    }
  }

  tags = var.tags
}
