output "nome" {
  description = "Nome da tabela de perfis"
  value       = aws_dynamodb_table.perfis.name
}

output "arn" {
  description = "ARN da tabela de perfis"
  value       = aws_dynamodb_table.perfis.arn
}

output "policy_json_runtime" {
  description = "Policy IAM mínima para o runtime acessar a tabela"
  value       = data.aws_iam_policy_document.acesso_runtime.json
}
