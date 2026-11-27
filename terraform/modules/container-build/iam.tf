# Role assumida pelo CodeBuild. Fica neste módulo, junto do projeto que a usa —
# permissões e consumidor no mesmo arquivo é mais legível que um módulo iam/
# central que precisaria devolver ARNs para cá.

data "aws_iam_policy_document" "builder_assume_role" {
  statement {
    sid     = "CodeBuildAssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["codebuild.amazonaws.com"]
    }

    # Impede que a role seja assumida por um CodeBuild de outra conta
    # (problema do "confused deputy").
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "builder" {
  name               = "${var.name_prefix}-agent-builder-exec"
  description        = "Execução do CodeBuild que constrói a imagem do agente ${var.name_prefix}"
  assume_role_policy = data.aws_iam_policy_document.builder_assume_role.json

  tags = var.tags
}

data "aws_iam_policy_document" "builder" {
  # O token de login do ECR não é escopável por recurso — a própria API exige "*".
  statement {
    sid       = "EcrAuthToken"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  # Push escopado ao repositório deste projeto, não a todos os repos da conta.
  statement {
    sid    = "EcrPushToThisRepository"
    effect = "Allow"

    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]

    resources = [aws_ecr_repository.this.arn]
  }

  statement {
    sid    = "CloudWatchLogs"
    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/codebuild/${var.name_prefix}*",
      "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/codebuild/${var.name_prefix}*:*",
    ]
  }

  statement {
    sid    = "ReadBuildSource"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
      "s3:ListBucket",
    ]

    resources = [
      aws_s3_bucket.source.arn,
      "${aws_s3_bucket.source.arn}/*",
    ]

    condition {
      test     = "StringEquals"
      variable = "s3:ResourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role_policy" "builder" {
  name   = "${var.name_prefix}-agent-builder-exec"
  role   = aws_iam_role.builder.id
  policy = data.aws_iam_policy_document.builder.json
}
