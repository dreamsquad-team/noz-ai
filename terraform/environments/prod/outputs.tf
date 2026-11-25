output "fila_entrada_url" {
  description = "URL da fila de entrada"
  value       = module.filas_validacao.entrada_url
}

output "fila_saida_url" {
  description = "URL da fila de saída"
  value       = module.filas_validacao.saida_url
}

output "bucket_evidencias_nome" {
  description = "Nome do bucket de evidências"
  value       = module.bucket_evidencias.nome
}