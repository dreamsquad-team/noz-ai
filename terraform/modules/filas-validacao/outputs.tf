output "entrada_url" {
  description = "URL da fila de entrada (o backend da NOZ envia aqui)"
  value       = aws_sqs_queue.entrada.url
}

output "entrada_arn" {
  description = "ARN da fila de entrada"
  value       = aws_sqs_queue.entrada.arn
}

output "saida_url" {
  description = "URL da fila de saída (o backend da NOZ lê aqui)"
  value       = aws_sqs_queue.saida.url
}

output "saida_arn" {
  description = "ARN da fila de saída"
  value       = aws_sqs_queue.saida.arn
}

output "entrada_dlq_arn" {
  description = "ARN da DLQ da fila de entrada"
  value       = aws_sqs_queue.entrada_dlq.arn
}

output "saida_dlq_arn" {
  description = "ARN da DLQ da fila de saída"
  value       = aws_sqs_queue.saida_dlq.arn
}