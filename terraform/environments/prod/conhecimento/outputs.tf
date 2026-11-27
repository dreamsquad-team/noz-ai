output "runtime_arn" {
  description = "ARN do runtime do Conhecimento. Recomendação e Moderação invocam por ele (bedrock-agentcore:InvokeAgentRuntime)"
  value       = module.runtime.agent_runtime_arn
}

output "runtime_id" {
  description = "ID do runtime"
  value       = module.runtime.agent_runtime_id
}

output "runtime_role_arn" {
  description = "Execution role do runtime"
  value       = module.runtime.execution_role_arn
}

output "image_uri" {
  description = "Imagem em uso (tag = hash do código)"
  value       = module.build.image_uri
}

output "ecr_repository_url" {
  description = "Repositório ECR da imagem"
  value       = module.build.ecr_repository_url
}

output "codebuild_project_name" {
  description = "Projeto CodeBuild. Logs: aws logs tail /aws/codebuild/<nome>"
  value       = module.build.codebuild_project_name
}

output "source_size_bytes" {
  description = "Tamanho do zip enviado ao CodeBuild. Centenas de KB = ok; dezenas de MB = .venv ou .git vazando"
  value       = module.build.source_size_bytes
}
