output "agent_runtime_arn" {
  description = "ARN do Agent Runtime — é o que Recomendação e Moderação usam para invocar o Conhecimento (bedrock-agentcore:InvokeAgentRuntime)."
  value       = aws_bedrockagentcore_agent_runtime.this.agent_runtime_arn
}

output "agent_runtime_id" {
  description = "ID do Agent Runtime — necessário para criar endpoints nomeados."
  value       = aws_bedrockagentcore_agent_runtime.this.agent_runtime_id
}

output "agent_runtime_version" {
  description = "Versão do Runtime. Incrementa quando a imagem ou a configuração mudam."
  value       = aws_bedrockagentcore_agent_runtime.this.agent_runtime_version
}

output "execution_role_arn" {
  description = "ARN da execution role do Runtime."
  value       = aws_iam_role.this.arn
}
