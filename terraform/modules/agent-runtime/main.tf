# O Agent Runtime propriamente dito.
#
# O endpoint `DEFAULT` NÃO é modelado aqui de propósito: ele é criado
# implicitamente junto com o runtime e a AWS não permite deletá-lo. Quem invoca
# usa qualifier="DEFAULT". Declarar um
# aws_bedrockagentcore_agent_runtime_endpoint chamado "DEFAULT" só criaria
# conflito de import. Endpoints NOMEADOS (para fixar uma versão, por exemplo)
# são um caso legítimo desse recurso — mas não este.

resource "aws_bedrockagentcore_agent_runtime" "this" {
  agent_runtime_name = var.name
  description        = "AgentCore Runtime do agente ${var.name}"
  role_arn           = aws_iam_role.this.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = var.image_uri
    }
  }

  network_configuration {
    network_mode = var.network_mode
  }

  protocol_configuration {
    server_protocol = var.server_protocol
  }

  # Sobrepõem os ENV da imagem. Manter a configuração aqui (e não no Dockerfile)
  # é o que permite trocar de modelo ou de nível de log sem rebuildar a imagem.
  environment_variables = var.environment_variables

  tags = var.tags

  # A policy precisa existir antes do runtime: se o serviço validar a role no
  # momento da criação e ela ainda estiver sem permissões, a criação falha.
  depends_on = [aws_iam_role_policy.this]
}
