# ---------------------------------------------------------------------------
# Disparo do build
# ---------------------------------------------------------------------------
# Terraform não constrói imagens, mas o aws_bedrockagentcore_agent_runtime exige
# que a imagem JÁ esteja no ECR no momento do apply.
#
# A ordenação NÃO é feita com depends_on: o `input` deste recurso vira o
# `output`, e o container_uri do módulo é montado a partir desse output. Assim o
# URI é literalmente impossível de calcular antes do build terminar — a ordem
# fica garantida por dependência de dados, que o Terraform respeita sempre.
#
# Limitação consciente: local-exec exige AWS CLI, bash e credencial na máquina
# do apply. Em execução remota (Terraform Cloud, runner sem CLI) use
# build_on_apply = false e construa a imagem no pipeline.

# O IAM tem consistência eventual: sem esta espera, o start-build logo após a
# criação da role falha com InvalidInputException. O toolkit dormia 10s no mesmo
# ponto; aqui a espera é explícita e ajustável.
resource "time_sleep" "iam_propagation" {
  count = var.build_on_apply ? 1 : 0

  depends_on      = [aws_iam_role_policy.builder]
  create_duration = "${var.iam_propagation_seconds}s"
}

resource "terraform_data" "build" {
  count = var.build_on_apply ? 1 : 0

  # input -> output: é isto que cria a dependência de dados (ver outputs.tf).
  input = local.source_tag

  triggers_replace = {
    source    = data.archive_file.source.output_sha256
    buildspec = filesha256("${path.module}/buildspec.yml")
    project   = aws_codebuild_project.builder.arn
  }

  provisioner "local-exec" {
    # O shell interativo do dev pode ser fish; forçamos bash.
    interpreter = ["/bin/bash", "-c"]

    environment = merge(
      {
        PROJECT    = aws_codebuild_project.builder.name
        AWS_REGION = var.aws_region
        MAX_POLLS  = tostring(var.build_timeout_minutes * 12)
      },
      var.aws_profile == null ? {} : { AWS_PROFILE = var.aws_profile },
    )

    # CUIDADO ao editar: dentro deste heredoc, ${...} é interpolação do
    # TERRAFORM. Variável de shell tem que ser $VAR ou $(...) — nunca ${VAR}.
    command = <<-BASH
      set -euo pipefail

      ID=$(aws codebuild start-build --project-name "$PROJECT" \
             --region "$AWS_REGION" --query 'build.id' --output text)
      echo "CodeBuild iniciado: $ID"

      # A API do CodeBuild não tem waiter no botocore, então `aws codebuild wait`
      # não existe. Polling explícito, a cada 5s.
      for _ in $(seq 1 "$MAX_POLLS"); do
        S=$(aws codebuild batch-get-builds --ids "$ID" --region "$AWS_REGION" \
              --query 'builds[0].buildStatus' --output text)

        if [ "$S" != "IN_PROGRESS" ]; then
          echo "status=$S"
          [ "$S" = "SUCCEEDED" ] && exit 0
          echo "Build falhou. Logs:" >&2
          echo "  aws logs tail /aws/codebuild/$PROJECT --region $AWS_REGION" >&2
          exit 1
        fi
        sleep 5
      done

      echo "Timeout aguardando o build ($MAX_POLLS polls)." >&2
      exit 1
    BASH
  }

  depends_on = [
    aws_s3_object.source,
    time_sleep.iam_propagation,
  ]
}
