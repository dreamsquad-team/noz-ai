output "backend_policy_arn" {
  description = "ARN da policy do backend da NOZ"
  value       = aws_iam_policy.backend.arn
}