variable "name_prefix" {
  description = "Prefixo dos recursos, no formato \"{projeto}-{ambiente}\" (ex.: \"noz-conhecimento-prod\")."
  type        = string
}

variable "source_dir" {
  description = "Diretório zipado e enviado ao CodeBuild. Deve ser a pasta do agente (a que tem o Dockerfile): tudo que o Dockerfile copia precisa estar dentro dela."
  type        = string
}

variable "source_excludes" {
  description = "Caminhos excluídos do zip. Espelhe o .dockerignore: o que entra aqui define o hash e, portanto, quando a imagem é reconstruída."
  type        = list(string)

  # Globs, não nomes de diretório: em archive_file, "infra" sozinho não exclui
  # o conteúdo aninhado.
  #
  # CRÍTICOS para o hash (sem eles a imagem rebuilda sem motivo):
  #   infra/** -> editar qualquer .tf mudaria o hash
  #   .git/**  -> cada commit mudaria o hash
  #   specs/**, docs/**, .github/**, tests/** e scripts/** -> documentação, testes e ferramentas de
  #                           desenvolvimento ficam fora da imagem (.dockerignore); sem
  #                           eles aqui, editar qualquer um reconstruía a imagem
  default = [
    "infra/**",
    ".git/**",
    "specs/**",
    "tests/**",
    "scripts/**",
    "docs/**",
    ".github/**",
    ".venv/**",
    "venv/**",
    "**/__pycache__/**",
    "**/*.pyc",
    ".pytest_cache/**",
    ".ruff_cache/**",
    "node_modules/**",
    ".env",
    ".bedrock_agentcore.yaml",
  ]
}

variable "aws_region" {
  description = "Região — usada no login do ECR dentro do buildspec."
  type        = string
}

variable "build_image" {
  description = "Imagem do CodeBuild. Precisa ser aarch64: o AgentCore Runtime roda em Graviton."
  type        = string
  default     = "aws/codebuild/amazonlinux2-aarch64-standard:3.0"
}

variable "build_compute_type" {
  description = "Tamanho do worker do CodeBuild."
  type        = string
  default     = "BUILD_GENERAL1_MEDIUM"
}

variable "build_timeout_minutes" {
  description = "Timeout do build."
  type        = number
  default     = 30
}

variable "build_on_apply" {
  description = <<-EOT
    true  → o apply dispara o CodeBuild e espera terminar (exige AWS CLI na
            máquina que roda o apply; é o modo de deploy em um comando).
    false → o apply NÃO builda; use quando a imagem já foi construída no CI.
            Nesse caso `image_tag_override` passa a ser obrigatório.
  EOT
  type        = bool
  default     = true
}

variable "image_tag_override" {
  description = "Tag de imagem a usar em vez do hash do source. Obrigatório quando build_on_apply = false."
  type        = string
  default     = null
}

variable "ecr_keep_last_n_images" {
  description = "Quantas imagens manter no ECR. As mais antigas são expiradas."
  type        = number
  default     = 10
}

variable "tags" {
  description = "Tags aplicadas aos recursos deste módulo."
  type        = map(string)
  default     = {}
}

variable "aws_profile" {
  description = "Profile AWS repassado ao local-exec do build. Null usa a credencial default."
  type        = string
  default     = null
}

variable "iam_propagation_seconds" {
  description = "Espera pela propagação da role do CodeBuild antes do start-build. IAM tem consistência eventual."
  type        = number
  default     = 15
}
