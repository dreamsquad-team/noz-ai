# Infraestrutura (Terraform)

Filas SQS e bucket S3 de evidências do agente de Validação de Desafios. O runtime do agente continua sendo publicado por `agentcore deploy` (ver o README da raiz). Aqui ficam só os recursos que o `agentcore.json` não
descreve.

## O que é criado

| Recurso | Nome | Descrição |
|---|---|---|
| Fila de entrada | `noz-ai-validacao-entrada` | Pedidos de validação enviados pelo backend da NOZ |
| Fila de saída | `noz-ai-validacao-saida` | Resultados lidos pelo backend da NOZ |
| DLQ de entrada e de saída | `...-entrada-dlq`, `...-saida-dlq` | Recebem a mensagem que falha `max_receive_count` vezes |
| Bucket de evidências | `noz-ai-evidencias-<id da conta>` | Fotos das provas. Privado, criptografado, com expiração |

- Filas padrão (não FIFO), com SSE-SQS e acesso apenas por HTTPS.
- DLQs com retenção de 14 dias. O visibility timeout só é definido na fila de entrada e deve ser maior que o timeout da
  Lambda que a consome.
- Bucket com bloqueio total de acesso público, criptografia AES256, acesso apenas por HTTPS e `prevent_destroy`
  (guarda dado pessoal).

## Estrutura

```
terraform/
├── bootstrap/            # Cria o bucket do state (roda uma vez, com state local)
├── environments/
│   └── prod/             # Único ambiente: chama os módulos e usa o state remoto
└── modules/
    ├── filas-validacao/  # 2 filas + 2 DLQs + policies HTTPS
    └── bucket-evidencias/
```

Cada módulo tem `main.tf`, `variables.tf`, `outputs.tf` e `versions.tf`. O provider (região, conta e tags) é
configurado no ambiente, não nos módulos.

## Pré-requisitos

- Terraform 1.10 ou superior (o lock do state usa `use_lockfile`, sem DynamoDB)
- AWS CLI com sessão ativa na conta da NOZ:

```bash
aws sso login --profile dreamsquad
export AWS_PROFILE=dreamsquad
aws sts get-caller-identity   # o campo Account deve ser 862558960374
```

O provider usa `allowed_account_ids`: o Terraform recusa rodar se as credenciais forem de outra conta.

## Primeiro uso (conta nova)

1. **Bootstrap**: cria o bucket que guarda o state.

   ```bash
   cd terraform/bootstrap
   cp terraform.tfvars.example terraform.tfvars
   terraform init
   terraform plan
   terraform apply
   ```

   O `terraform.tfstate` do bootstrap fica **local** e é a única cópia do estado desse bucket. Não apague e não
   commite.

2. **Ambiente**: aponta para o bucket do state e cria as filas e o bucket de evidências.

   ```bash
   cd terraform/environments/prod
   cp terraform.tfvars.example terraform.tfvars
   cp backend.tf.example backend.tf
   terraform init
   terraform plan
   terraform apply
   ```

Leia sempre o `plan` antes do `apply`. Para aplicar exatamente o que foi revisado:

```bash
terraform plan -out=prod.tfplan
terraform apply prod.tfplan
```

## Variáveis do ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `aws_account_id` | (obrigatória) | Conta da NOZ. Protege contra aplicar na conta errada |
| `aws_region` | `us-east-1` | Região |
| `visibility_timeout_seconds` | `360` | Fila de entrada. Deve ser maior que o timeout da Lambda |
| `max_receive_count` | `3` | Tentativas antes de a mensagem ir para a DLQ |
| `dias_para_expirar` | `90` | Dias até as evidências serem apagadas |
| `tags` | `{}` | Tags de todos os recursos |

Os valores de `visibility_timeout_seconds`, `max_receive_count` e `dias_para_expirar` são **provisórios**, marcados
com `TODO` no código, e dependem de confirmação.

## Saídas

| Output | Uso |
|---|---|
| `fila_entrada_url` | O backend da NOZ envia os pedidos de validação |
| `fila_saida_url` | O backend da NOZ lê os resultados |
| `bucket_evidencias_nome` | Destino das fotos das provas |

Veja os valores com `terraform output`.

## Segurança e cuidados

- **Nunca commitar:** `*.tfstate`, `*.tfvars`, `backend.tf`, `.terraform/` e `*.tfplan`. Todos estão no `.gitignore`.
  Só os arquivos `.example` vão para o git.
- **Commitar:** o `.terraform.lock.hcl` de `bootstrap/` e de `environments/prod/`, que fixa a versão dos providers.
- **Renomear recursos** (a primeira palavra do bloco `resource`, ou o `name`) destrói e recria o recurso. Confira o
  `plan` antes: qualquer `destroy` ou `replace` merece atenção.
- O bucket de evidências tem `prevent_destroy`: o Terraform recusa apagá-lo. Para removê-lo de propósito, é preciso
  alterar o código antes.
- O nome do ambiente (`prod`) compõe o caminho do state (`prod/terraform.tfstate`). Renomear a pasta exige mover o
  state.

