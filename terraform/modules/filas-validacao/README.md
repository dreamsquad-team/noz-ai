# Módulo filas-validacao

Cria as filas SQS do agente de Validação de Desafios: uma fila de **entrada** (o backend da NOZ envia os pedidos de
validação) e uma de **saída** (o backend lê os resultados), cada uma com sua DLQ.

## Recursos criados

| Recurso | Nome | Observação |
|---|---|---|
| `aws_sqs_queue.entrada` | `<prefixo>-entrada` | Com visibility timeout e redrive para a DLQ |
| `aws_sqs_queue.entrada_dlq` | `<prefixo>-entrada-dlq` | Retenção de 14 dias |
| `aws_sqs_queue.saida` | `<prefixo>-saida` | Com redrive para a DLQ |
| `aws_sqs_queue.saida_dlq` | `<prefixo>-saida-dlq` | Retenção de 14 dias |
| `aws_sqs_queue_policy.somente_https` | uma por fila | Nega qualquer acesso sem HTTPS |

Características:

- Filas **padrão** (não FIFO). A idempotência é responsabilidade do consumidor, usando o `id_envio` da mensagem.
- Criptografia em repouso com SSE-SQS (`sqs_managed_sse_enabled`).
- Redrive: depois de `max_receive_count` entregas sem sucesso, a mensagem vai para a DLQ da fila.
- As DLQs são criadas antes das filas principais, que referenciam o ARN delas.
- A retenção das filas principais fica no padrão da AWS (4 dias), menor que a das DLQs (14 dias). A retenção da DLQ conta
  a partir do momento em que a mensagem entrou na fila original.

## Uso

```hcl
module "filas_validacao" {
  source = "../../modules/filas-validacao"

  visibility_timeout_seconds = 360
  max_receive_count          = 3
}
```

O provider AWS (região, conta e tags) é configurado por quem chama o módulo.

## Variáveis

| Nome | Tipo | Padrão | Descrição |
|---|---|---|---|
| `prefixo` | `string` | `noz-ai-validacao` | Prefixo dos nomes das filas |
| `visibility_timeout_seconds` | `number` | `360` | Tempo que a mensagem fica invisível enquanto é processada. Entre 0 e 43200. Aplica-se só à fila de entrada e deve ser **maior que o timeout da Lambda** consumidora |
| `max_receive_count` | `number` | `3` | Entregas antes de a mensagem ir para a DLQ. Mínimo 1 |

Os padrões de `visibility_timeout_seconds` e `max_receive_count` são provisórios e devem ser confirmados.

## Saídas

| Nome | Descrição |
|---|---|
| `entrada_url` | URL da fila de entrada (o backend da NOZ envia aqui) |
| `entrada_arn` | ARN da fila de entrada |
| `saida_url` | URL da fila de saída (o backend da NOZ lê daqui) |
| `saida_arn` | ARN da fila de saída |
| `entrada_dlq_arn` | ARN da DLQ da fila de entrada |
| `saida_dlq_arn` | ARN da DLQ da fila de saída |

Os ARNs são a base das policies de IAM de quem envia e lê as mensagens.

## Cuidados

- **Renomear o `prefixo`** muda o nome das filas e faz o Terraform destruir e recriar todas. Mensagens em andamento
  são perdidas.
- **Reduzir `visibility_timeout_seconds` abaixo do tempo real de processamento** faz a mensagem reaparecer na fila
  antes de terminar e ser processada duas vezes. Se a Lambda mudar de timeout, ajuste este valor.
- As filas não têm `prevent_destroy`. Se for preciso proteger, acrescente um bloco `lifecycle` em cada recurso.
- Não há alarme nas DLQs. Uma mensagem na DLQ só é percebida se alguém olhar.