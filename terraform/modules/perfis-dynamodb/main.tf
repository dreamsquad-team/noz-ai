# Perfis de interesse e temas de conteúdo do agente de Conhecimento.
# Chaves: PK = "<empresa_id>#<tipo>#<id>" (tipo: usuario | empresa | conteudo | grupo), SK = atributo/versão.
# Toda chave começa com o id da empresa: é o que garante o isolamento por tenant no armazenamento.
resource "aws_dynamodb_table" "perfis" {
  name         = var.nome
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  attribute {
    name = "empresa_id"
    type = "S"
  }

  attribute {
    name = "tipo_id"
    type = "S"
  }

  # Listar perfis de uma empresa (ex.: todos os usuários) sem Scan.
  global_secondary_index {
    name            = "por-empresa"
    hash_key        = "empresa_id"
    range_key       = "tipo_id"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = var.habilitar_pitr
  }

  server_side_encryption {
    enabled = true
  }

  dynamic "ttl" {
    for_each = var.ttl_atributo == null ? [] : [var.ttl_atributo]
    content {
      attribute_name = ttl.value
      enabled        = true
    }
  }

  deletion_protection_enabled = true
}

# Acesso mínimo do runtime: só esta tabela, sem Scan.
data "aws_iam_policy_document" "acesso_runtime" {
  statement {
    sid       = "PerfisConhecimento"
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query", "dynamodb:BatchGetItem", "dynamodb:BatchWriteItem"]
    resources = [aws_dynamodb_table.perfis.arn, "${aws_dynamodb_table.perfis.arn}/index/por-empresa"]
  }
}
