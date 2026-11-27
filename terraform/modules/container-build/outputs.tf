output "image_uri" {
  description = "URI da imagem para o agent runtime consumir, com tag."

  # Quando build_on_apply = true, a tag vem do OUTPUT do terraform_data.build.
  # Isso não é cosmético: é o que impede o Terraform de criar o Agent Runtime
  # em paralelo ao build, apontando para uma tag que ainda não existe no ECR.
  value = var.build_on_apply ? (
    "${aws_ecr_repository.this.repository_url}:${one(terraform_data.build[*].output)}"
    ) : (
    "${aws_ecr_repository.this.repository_url}:${var.image_tag_override}"
  )
}

output "image_tag" {
  description = "Tag da imagem: hash do source, ou o override informado."
  value       = local.image_tag
}

output "ecr_repository_url" {
  description = "URL do repositório ECR."
  value       = aws_ecr_repository.this.repository_url
}

output "ecr_repository_arn" {
  description = "ARN do repositório — usado para escopar a policy de pull do runtime."
  value       = aws_ecr_repository.this.arn
}

output "codebuild_project_name" {
  description = "Nome do projeto CodeBuild — útil para `aws logs tail`."
  value       = aws_codebuild_project.builder.name
}

output "source_size_bytes" {
  description = <<-EOT
    Tamanho do zip enviado ao CodeBuild. Métrica de sanidade: centenas de KB
    significa que os excludes funcionaram; dezenas de MB significa que .venv/
    ou .git/ estão vazando para o zip (e rebuildando a imagem sem motivo).
  EOT
  value       = data.archive_file.source.output_size
}

output "source_sha256" {
  description = "Hash do source. Compare entre máquinas: se divergir, o zip não é determinístico."
  value       = data.archive_file.source.output_sha256
}
