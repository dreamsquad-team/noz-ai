output "perfis_tabela_nome" {
  description = "Nome da tabela de perfis do Conhecimento"
  value       = module.perfis.nome
}

output "perfis_tabela_arn" {
  description = "ARN da tabela de perfis do Conhecimento"
  value       = module.perfis.arn
}
