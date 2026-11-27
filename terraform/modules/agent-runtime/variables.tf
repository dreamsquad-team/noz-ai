variable "name" {
  description = "Nome do Agent Runtime. Só letras, números e underscore — a API rejeita hífen."
  type        = string

  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9_]{0,47}$", var.name))
    error_message = "Comece com letra e use apenas letras, números e underscore. Hífen não é aceito pela API de Agent Runtime."
  }
}

variable "role_name" {
  description = "Nome da execution role. Aqui hífen é permitido (é IAM, não AgentCore)."
  type        = string
}

variable "image_uri" {
  description = "URI da imagem no ECR, com tag. Vem do output image_uri do módulo container-build."
  type        = string
}

variable "memory_arn" {
  description = "ARN da AgentCore Memory, quando o agente usa uma. Null = sem memória e sem permissão de memória (o Conhecimento não usa)."
  type        = string
  default     = null
}

variable "environment_variables" {
  description = "Variáveis de ambiente do container. Sobrepõem qualquer ENV da imagem. É aqui que MODEL_ID, AWS_REGION e LOG_LEVEL entram."
  type        = map(string)
  default     = {}
}

variable "aws_region" {
  description = "Região — compõe os ARNs das policies."
  type        = string
}

variable "network_mode" {
  description = "PUBLIC (o Runtime sai pela internet gerenciada pela AWS) ou VPC."
  type        = string
  default     = "PUBLIC"

  validation {
    condition     = contains(["PUBLIC", "VPC"], var.network_mode)
    error_message = "Valores aceitos: PUBLIC ou VPC."
  }
}

variable "server_protocol" {
  description = "Protocolo do contêiner. HTTP para um agente comum; MCP para servidor MCP; A2A para agent-to-agent."
  type        = string
  default     = "HTTP"

  validation {
    condition     = contains(["HTTP", "MCP", "A2A", "AGUI"], var.server_protocol)
    error_message = "Valores aceitos: HTTP, MCP, A2A, AGUI."
  }
}

variable "model_arn_patterns" {
  description = <<-EOT
    ARNs de modelo que o agente pode invocar. O default cobre foundation models
    e inference profiles da região. Restrinja ao modelo específico do cliente
    quando quiser reduzir o alcance da policy.
  EOT
  type        = list(string)
  default     = null
}

variable "enable_code_interpreter" {
  description = "Concede as permissões de Code Interpreter do AgentCore. Deixe false a menos que o agente realmente use a ferramenta."
  type        = bool
  default     = false
}

variable "enable_identity" {
  description = "Concede as permissões de AgentCore Identity (OAuth/API keys via token vault). Deixe false a menos que o agente use credential providers."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags aplicadas aos recursos deste módulo."
  type        = map(string)
  default     = {}
}

variable "ecr_repository_arn" {
  description = "ARN do repositório ECR. Escopa o pull da imagem ao repo deste agente, em vez de todos os repos da conta."
  type        = string
}

variable "allow_invoke_other_runtimes" {
  description = <<-EOT
    Concede bedrock-agentcore:InvokeAgentRuntime. Necessário só para padrões
    agent-to-agent (A2A). Deixe false: numa conta compartilhada isso permitiria
    o agente de um cliente invocar o runtime de outro.
  EOT
  type        = bool
  default     = false
}

variable "gateway_arns" {
  description = <<-EOT
    ARNs dos AgentCore Gateways que o agente pode chamar (bedrock-agentcore:InvokeGateway).
    Lista vazia = sem acesso a gateways.
  EOT
  type        = list(string)
  default     = []
}
