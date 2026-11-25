output "state_bucket_name" {
  description = "Nome do bucket para usar no backend dos ambientes"
  value       = aws_s3_bucket.state.id
}

output "state_bucket_arn" {
  description = "ARN do bucket do state"
  value       = aws_s3_bucket.state.arn
}