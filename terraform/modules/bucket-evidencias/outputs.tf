output "nome" {
  description = "Nome do bucket de evidências"
  value       = aws_s3_bucket.evidencias.id
}

output "arn" {
  description = "ARN do bucket de evidências"
  value       = aws_s3_bucket.evidencias.arn
}