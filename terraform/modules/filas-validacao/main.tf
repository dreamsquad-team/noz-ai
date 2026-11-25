locals {
  quatorze_dias = 14 * 24 * 60 * 60

  filas = {
    entrada     = aws_sqs_queue.entrada
    entrada_dlq = aws_sqs_queue.entrada_dlq
    saida       = aws_sqs_queue.saida
    saida_dlq   = aws_sqs_queue.saida_dlq
  }
}

# As DLQs vêm primeiro: as filas principais referenciam os ARN delas
resource "aws_sqs_queue" "entrada_dlq" {
  name                      = "${var.prefixo}-entrada-dlq"
  message_retention_seconds = local.quatorze_dias
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "saida_dlq" {
  name                      = "${var.prefixo}-saida-dlq"
  message_retention_seconds = local.quatorze_dias
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "entrada" {
  name                       = "${var.prefixo}-entrada"
  visibility_timeout_seconds = var.visibility_timeout_seconds
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.entrada_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })
}

resource "aws_sqs_queue" "saida" {
  name                    = "${var.prefixo}-saida"
  sqs_managed_sse_enabled = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.saida_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })
}

# Nega qualquer acesso que não use HTTPS (equivale ao enforceSSL do CDK).
data "aws_iam_policy_document" "somente_https" {
  for_each = local.filas

  statement {
    sid       = "NegarHttpSemTls"
    effect    = "Deny"
    actions   = ["sqs:*"]
    resources = [each.value.arn]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_sqs_queue_policy" "somente_https" {
  for_each = local.filas

  queue_url = each.value.url
  policy    = data.aws_iam_policy_document.somente_https[each.key].json
}