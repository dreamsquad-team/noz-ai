data "aws_iam_policy_document" "backend" {
  statement {
    sid       = "EnviarPedidosDeValidacao"
    effect    = "Allow"
    actions   = ["sqs:SendMessage"]
    resources = [var.entrada_queue_arn]
  }

  statement {
    sid    = "LerResultados"
    effect = "Allow"
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
    ]
    resources = [var.saida_queue_arn]
  }

  statement {
    sid       = "GravarEvidencias"
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${var.bucket_arn}/*"]
  }
}

resource "aws_iam_policy" "backend" {
  name        = "${var.prefixo}-backend-noz"
  description = "Acesso mínimo do backend da NOZ as filas e ao bucket de evidências"
  policy      = data.aws_iam_policy_document.backend.json
}

resource "aws_iam_role_policy_attachment" "backend" {
  for_each = toset(var.backend_role_names)

  role       = each.value
  policy_arn = aws_iam_policy.backend.arn
}