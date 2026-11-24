# NozAI — Agente Strands no Amazon Bedrock AgentCore Runtime

Boilerplate de agente de IA (Strands Agents) publicado no AgentCore Runtime da conta AWS da NOZ. É o ponto de partida
dos agentes do projeto (Validação, Curadoria, Conhecimento, Recomendação e Moderação).


## Informações do deploy

| Item | Valor |
|---|---|
| Conta AWS | `862558960374` (NOZ) |
| Região | `us-east-1` |
| Target | `NozAI` |
| Stack | `AgentCore-NozAI-NozAI` |
| Runtime | `noz_ai_runtime` |
| ARN do runtime | `arn:aws:bedrock-agentcore:us-east-1:862558960374:runtime/NozAI_noz_ai_runtime-oQ23lC9WVZ` |
| Memória | `noz_ai` (`NozAI_noz_ai-Y3OiPd6lk2`) |
| Modelo | `us.anthropic.claude-haiku-5-5` |


## Escopo

O deploy do `agentcore` publica apenas o runtime e a memória de curto prazo. Gateway, Lambda e policy engine do
boilerplate foram removidos do `agentcore.json` e entram em outra task. A pasta `lambda/` continua no repositório, sem
ser publicada.

As filas SQS (entrada e saída, cada uma com DLQ) e o bucket S3 de evidências **não** fazem parte do `agentcore deploy`.
Eles são gerenciados por Terraform em `infra/terraform/`.

## Estrutura

```
noz-ai/
├── agentcore/
│   ├── agentcore.json      # Recursos: runtime e memória
│   ├── aws-targets.json    # Conta e região do deploy
│   ├── .cli/               # Estado do deploy (deployed-state.json)
│   └── cdk/                # Infraestrutura gerada pelo CLI (não editar)
├── app/agent-template/     # Código do agente (Python)
│   ├── main.py             # Entrypoint (invoke)
│   ├── agent/
│   │   ├── factory.py      # Monta o Agent
│   │   └── contract.py     # Contratos de entrada e saída (Pydantic)
│   ├── contracts/          # JSON Schemas e exemplos dos contratos
│   ├── model/load.py       # Modelo do Bedrock
│   ├── prompts/v1.txt      # System prompt
│   └── tests/
├── infra/terraform/        # Filas SQS e bucket S3 de evidências (Terraform)
└── lambda/my-tool/         # Lambda de exemplo (ainda não publicada)
```

## Pré-requisitos

- Node.js 20+ e o CLI: `npm install -g @aws/agentcore` (testado com a versão 1.0.2)
- Python 3.10+ e [uv](https://docs.astral.sh/uv/getting-started/installation/)
- AWS CLI com sessão ativa na conta da NOZ (`aws login`), com permissão para CloudFormation, IAM, Lambda e AgentCore

Confirme a conta antes de qualquer deploy. O campo `Account` deve ser o de `agentcore/aws-targets.json`:

```bash
aws sts get-caller-identity
```

## Testes

```bash
(cd app/agent-template && uv run pytest)
(cd lambda && uv run pytest)
```

O teste do alias do gateway em `tests/test_settings.py` está ignorado (`skip`) porque o gateway foi removido. Reative-o
quando o gateway voltar.

## Deploy

Use sempre `--target NozAI`. Sem ele, o CLI usa o target `default` e pode publicar na conta da sessão atual.

```bash
cd agentcore
agentcore deploy --target NozAI
agentcore status --target NozAI
```

No primeiro deploy em uma conta nova, o CLI exige o bootstrap do CDK (stack `CDKToolkit`: bucket S3 e roles de IAM).
Para autorizá-lo, use `--yes`:

```bash
agentcore deploy --target NozAI --yes
```

O projeto foi gerado pelo CLI v0 e roda em modo de compatibilidade no CLI v1. Nesse modo, os comandos
`agentcore validate` e `agentcore build` não existem. O próprio `deploy` valida o projeto. A cada deploy, o CLI pode
atualizar `@aws/agentcore-cdk` em `agentcore/cdk/package.json`.

## Invocação

O agente espera o campo `prompt` no payload:

```bash
agentcore invoke --runtime noz_ai_runtime --target NozAI \
  --payload '{"prompt": "Olá, o que você sabe fazer?"}'
```

Para receber a resposta completa em vez de streaming, envie `"stream": false`:

```bash
agentcore invoke --runtime noz_ai_runtime --target NozAI \
  --payload '{"prompt": "Olá", "stream": false}'
```

Logs do runtime: `agentcore logs runtime`.

## Contratos de entrada e saída

Os contratos do agente de Validação estão em `app/agent-template/agent/contract.py`. Os JSON Schemas são gerados a partir
dos modelos e ficam em `app/agent-template/contracts/`, junto com exemplos. Depois de alterar um modelo, regenere:

```bash
cd app/agent-template
uv run python -m contracts.gerar_schemas
```

Os testes comparam o schema salvo com o do modelo e validam os exemplos, então um schema desatualizado quebra a suíte.

## Infraestrutura (Terraform)

Filas SQS e bucket S3 de evidências, em `infra/terraform/`.

| Recurso | Descrição |
|---|---|
| Fila de entrada + DLQ | Pedidos de validação enviados pelo backend da NOZ |
| Fila de saída + DLQ | Resultados lidos pelo backend da NOZ |
| Bucket de evidências | Privado, criptografado, com expiração por lifecycle |

```bash
cd infra/terraform/environments/noz
terraform init
terraform plan
```

Leia o `plan` antes de qualquer `apply`. O state fica em bucket S3 remoto e nunca vai para o git.

## Notas

- O `name` de cada recurso em `agentcore.json` define sua identidade. Renomear depois do deploy destrói e recria o
  recurso (e apaga a memória das conversas).
- O nome da memória está ligado ao alias em `app/agent-template/config/settings.py`, e os testes em
  `tests/test_settings.py` detectam se ficarem fora de sincronia.
- Referência do CLI e dos tipos do `agentcore.json`: `AGENTS.md` e `agentcore/.llm-context/`.
