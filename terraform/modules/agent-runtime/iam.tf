# Execution role do Agent Runtime.
#
# Esta policy é deliberadamente MENOR que a que o bedrock-agentcore-starter-toolkit
# anexava. O toolkit concedia, sempre, permissões de Code Interpreter e de
# Identity/OAuth (que este projeto não usa) e dava Memory data-plane em
# `memory/*` — todas as memórias da conta. Aqui a memória só entra se `memory_arn`
# for informado (e escopada ao ARN dela), e os blocos extras ficam atrás de flag.

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id

  model_arns = coalesce(var.model_arn_patterns, [
    "arn:aws:bedrock:${var.aws_region}::foundation-model/*",
    "arn:aws:bedrock:${var.aws_region}:${local.account_id}:inference-profile/*",
    # Modelos cross-region (prefixos us./eu./apac.) resolvem para foundation
    # models de outras regiões, por isso o wildcard de região aqui.
    "arn:aws:bedrock:*::foundation-model/*",
  ])
}

data "aws_iam_policy_document" "assume_role" {
  statement {
    sid     = "AgentCoreAssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:bedrock-agentcore:${var.aws_region}:${local.account_id}:*"]
    }
  }
}

resource "aws_iam_role" "this" {
  name               = var.role_name
  description        = "Execution role do AgentCore Runtime ${var.name}"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json

  tags = var.tags
}

data "aws_iam_policy_document" "this" {
  # --- Imagem -------------------------------------------------------------
  statement {
    sid       = "EcrAuthToken"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"] # a API não aceita escopo por recurso nesta action
  }

  # Escopado ao repositório deste agente. O toolkit usava repository/*, que
  # deixava o agente puxar qualquer imagem da conta.
  statement {
    sid    = "EcrPullImage"
    effect = "Allow"

    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]

    resources = [var.ecr_repository_arn]
  }

  # --- Logs ---------------------------------------------------------------
  statement {
    sid    = "CloudWatchLogGroups"
    effect = "Allow"

    # PutResourcePolicy: o AgentCore libera o X-Ray para gravar os spans no log
    # group do próprio agente (destino padrão dos agentes novos, com o
    # Transaction Search ligado).
    actions = [
      "logs:CreateLogGroup",
      "logs:DescribeLogStreams",
      "logs:PutResourcePolicy",
    ]

    resources = ["arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"]
  }

  statement {
    sid       = "CloudWatchDescribeLogGroups"
    effect    = "Allow"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:*"]
  }

  statement {
    sid    = "CloudWatchLogStreams"
    effect = "Allow"

    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = ["arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"]
  }

  # --- Observabilidade ----------------------------------------------------
  statement {
    sid    = "XRayTracing"
    effect = "Allow"

    actions = [
      "xray:GetSamplingRules",
      "xray:GetSamplingTargets",
      "xray:PutTelemetryRecords",
      "xray:PutTraceSegments",
    ]

    resources = ["*"] # X-Ray não suporta permissão por recurso nestas actions
  }

  statement {
    sid       = "CloudWatchMetrics"
    effect    = "Allow"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]

    # Sem esta condition o agente poderia escrever métricas em qualquer
    # namespace da conta.
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["bedrock-agentcore"]
    }
  }

  # --- Modelo -------------------------------------------------------------
  statement {
    sid    = "InvokeBedrockModel"
    effect = "Allow"

    actions = [
      "bedrock:ApplyGuardrail",
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]

    resources = local.model_arns
  }

  # --- Gateway (tools) ----------------------------------------------------
  dynamic "statement" {
    for_each = length(var.gateway_arns) > 0 ? [1] : []

    content {
      sid       = "InvokeGateway"
      effect    = "Allow"
      actions   = ["bedrock-agentcore:InvokeGateway"]
      resources = var.gateway_arns
    }
  }

  # --- Memória (opcional) -------------------------------------------------
  # Só existe se o agente tiver uma memória (memory_arn). Escopado ao ARN dela;
  # as operações de data-plane atuam em sub-recursos (actor/session/event), por
  # isso o ARN e os filhos. O Conhecimento não usa memória: sem este bloco.
  dynamic "statement" {
    for_each = var.memory_arn == null ? [] : [1]

    content {
      sid    = "MemoryDataPlane"
      effect = "Allow"

      actions = [
        "bedrock-agentcore:CreateEvent",
        "bedrock-agentcore:DeleteEvent",
        "bedrock-agentcore:DeleteMemoryRecord",
        "bedrock-agentcore:GetEvent",
        "bedrock-agentcore:GetMemory",
        "bedrock-agentcore:GetMemoryRecord",
        "bedrock-agentcore:ListActors",
        "bedrock-agentcore:ListEvents",
        "bedrock-agentcore:ListMemoryRecords",
        "bedrock-agentcore:ListSessions",
        "bedrock-agentcore:RetrieveMemoryRecords",
      ]

      resources = [
        var.memory_arn,
        "${var.memory_arn}/*",
      ]
    }
  }

  # --- Opcionais ----------------------------------------------------------
  dynamic "statement" {
    for_each = var.allow_invoke_other_runtimes ? [1] : []

    content {
      sid       = "InvokeOtherAgentRuntimes"
      effect    = "Allow"
      actions   = ["bedrock-agentcore:InvokeAgentRuntime"]
      resources = ["arn:aws:bedrock-agentcore:${var.aws_region}:${local.account_id}:runtime/*"]
    }
  }

  dynamic "statement" {
    for_each = var.enable_code_interpreter ? [1] : []

    content {
      sid    = "CodeInterpreter"
      effect = "Allow"

      actions = [
        "bedrock-agentcore:CreateCodeInterpreter",
        "bedrock-agentcore:DeleteCodeInterpreter",
        "bedrock-agentcore:GetCodeInterpreter",
        "bedrock-agentcore:GetCodeInterpreterSession",
        "bedrock-agentcore:InvokeCodeInterpreter",
        "bedrock-agentcore:ListCodeInterpreterSessions",
        "bedrock-agentcore:ListCodeInterpreters",
        "bedrock-agentcore:StartCodeInterpreterSession",
        "bedrock-agentcore:StopCodeInterpreterSession",
      ]

      resources = ["arn:aws:bedrock-agentcore:${var.aws_region}:${local.account_id}:*"]
    }
  }

  dynamic "statement" {
    for_each = var.enable_identity ? [1] : []

    content {
      sid    = "AgentCoreIdentity"
      effect = "Allow"

      actions = [
        "bedrock-agentcore:GetResourceApiKey",
        "bedrock-agentcore:GetResourceOauth2Token",
        "bedrock-agentcore:GetWorkloadAccessToken",
      ]

      resources = [
        "arn:aws:bedrock-agentcore:${var.aws_region}:${local.account_id}:token-vault/*",
        "arn:aws:bedrock-agentcore:${var.aws_region}:${local.account_id}:workload-identity-directory/*",
      ]
    }
  }
}

resource "aws_iam_role_policy" "this" {
  name   = var.role_name
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.this.json

  lifecycle {
    # Guarda de graça, em tempo de plan: inline policy do IAM tem teto de 10 KB.
    # Ligar várias flags de uma vez pode estourar, e o erro da AWS é obscuro.
    precondition {
      condition     = length(data.aws_iam_policy_document.this.json) < 10240
      error_message = "A inline policy passou de 10.240 bytes (limite do IAM). Desligue flags opcionais ou migre para managed policy."
    }
  }
}
