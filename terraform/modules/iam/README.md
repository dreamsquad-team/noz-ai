# Módulo iam

Cria a policy de IAM com o acesso **mínimo** do backend da NOZ às filas e ao bucket de evidências do agente de
Validação de Desafios. Opcionalmente, anexa a policy a roles do backend (na mesma conta).

## Recursos criados

| Recurso | Descrição |
|---|---|
| `aws_iam_policy.backend` | Policy `<prefixo>-backend-noz` com as permissões abaixo |
| `aws_iam_role_policy_attachment.backend` | Anexa a policy a cada role de `backend_role_names`. Nenhum, se a lista for vazia |

## Permissões concedidas

| Ação | Recurso | Para quê |
|---|---|---|
| `sqs:SendMessage` | fila de entrada | Enviar pedidos de validação |
| `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:GetQueueAttributes` | fila de saída | Ler e confirmar os resultados |
| `s3:PutObject` | objetos do bucket (`<arn>/*`) | Gravar as fotos das provas |

Não são concedidos: leitura ou exclusão no bucket, envio na fila de saída, leitura ou exclusão na fila de entrada,
`PurgeQueue`, nem qualquer ação com `*`. As filas e o bucket usam criptografia gerenciada pela AWS (SSE-SQS e SSE-S3),
então não são necessárias permissões de KMS.

Este módulo cobre apenas o **backend da NOZ**. As permissões do agente (ler da entrada, enviar na saída, ler o bucket e
invocar o modelo) dependem de onde ele roda e ainda não foram definidas.

## Uso

```hcl
module "iam_backend_noz" {
  source = "../../modules/iam"

  entrada_queue_arn  = module.filas_validacao.entrada_arn
  saida_queue_arn    = module.filas_validacao.saida_arn
  bucket_arn         = module.bucket_evidencias.arn
  backend_role_names = []
}
```

## Variáveis

| Nome | Tipo | Padrão | Descrição |
|---|---|---|---|
| `prefixo` | `string` | `noz-ai-validacao` | Prefixo do nome da policy |
| `entrada_queue_arn` | `string` | (obrigatória) | ARN da fila de entrada |
| `saida_queue_arn` | `string` | (obrigatória) | ARN da fila de saída |
| `bucket_arn` | `string` | (obrigatória) | ARN do bucket de evidências |
| `backend_role_names` | `list(string)` | `[]` | Nomes das roles do backend que receberão a policy. Vazio = só cria a policy |

## Saídas

| Nome | Descrição |
|---|---|
| `backend_policy_arn` | ARN da policy, para anexar à role do backend |

## Como a policy passa a valer

Uma policy sozinha não dá acesso a ninguém: ela só vale para quem a tem anexada. Com `backend_role_names = []`, a policy
existe na conta, mas nenhuma role a recebeu. Há duas formas de anexar:

- **A NOZ anexa** à role do backend usando o `backend_policy_arn`. Não altera nada do lado do Terraform.
- **O Terraform anexa**: coloque o nome da role em `backend_role_names` e aplique. Confirme o nome com a NOZ antes,
  porque isso altera uma role que este projeto não criou.

O anexo é aditivo: ele não remove as outras permissões da role. Para retirá-lo, tire o nome da lista.

## Como testar o mínimo necessário

O simulador do IAM avalia o documento da policy, sem precisar de uma role anexada:

```bash
POL=$(terraform output -raw backend_policy_arn)
aws iam get-policy-version --policy-arn "$POL" --version-id v1 \
  --query PolicyVersion.Document > /tmp/policy-backend.json

sim() { aws iam simulate-custom-policy --policy-input-list file:///tmp/policy-backend.json \
  --action-names "$1" --resource-arns "$2" \
  --query 'EvaluationResults[0].[EvalActionName,EvalDecision]' --output text; }
```

Resultado esperado:

| Ação | Recurso | Decisão |
|---|---|---|
| `sqs:SendMessage` | fila de entrada | `allowed` |
| `sqs:ReceiveMessage` | fila de saída | `allowed` |
| `sqs:DeleteMessage` | fila de saída | `allowed` |
| `s3:PutObject` | objeto no bucket | `allowed` |
| `sqs:SendMessage` | fila de saída | `implicitDeny` |
| `sqs:ReceiveMessage` | fila de entrada | `implicitDeny` |
| `sqs:PurgeQueue` | fila de saída | `implicitDeny` |
| `s3:GetObject` | objeto no bucket | `implicitDeny` |
| `s3:DeleteObject` | objeto no bucket | `implicitDeny` |

Depois que a policy for anexada a uma role real, repita o teste com `simulate-principal-policy` ou com a própria role.

## Cuidados

- **Usar `aws_iam_policy_attachment`** no lugar de `aws_iam_role_policy_attachment` seria um erro: o primeiro é
  exclusivo e remove a policy de qualquer outra identidade que não esteja listada.
- **Ampliar permissões** (por exemplo `s3:GetObject`) deve ser uma decisão consciente: o bucket guarda dado pessoal
  (LGPD).
- **Restringir mais** é possível limitando o `PutObject` a um prefixo de chaves, em vez de `<arn>/*`.
- **Renomear o `prefixo`** troca o nome da policy e o Terraform a recria. Quem a anexou manualmente precisará anexar a
  nova.