# Módulo bucket-evidencias

Cria o bucket S3 onde ficam as evidências (fotos) enviadas pelos participantes para validação dos desafios. O agente
lê o objeto pela chave (key) informada no pedido de validação.

## Recursos criados

| Recurso | Descrição |
|---|---|
| `aws_s3_bucket.evidencias` | Bucket `<prefixo>-<id da conta>`, com `prevent_destroy` |
| `aws_s3_bucket_public_access_block.evidencias` | Bloqueia todo acesso público (os 4 itens) |
| `aws_s3_bucket_server_side_encryption_configuration.evidencias` | Criptografia em repouso AES256 (SSE-S3) |
| `aws_s3_bucket_lifecycle_configuration.evidencias` | Expiração dos objetos e limpeza de uploads incompletos |
| `aws_s3_bucket_policy.evidencias` | Nega qualquer acesso que não use HTTPS |

Características:

- **Nome previsível e único:** o ID da conta é acrescentado ao prefixo, o que garante a unicidade global exigida pelo
  S3. Ele é lido de `aws_caller_identity`, então sempre corresponde à conta em que o Terraform está rodando.
- **Expiração:** os objetos são apagados depois de `dias_para_expirar` dias, e uploads multipart incompletos, depois de
  7 dias. A regra vale para o bucket inteiro.
- **`prevent_destroy`:** o bucket guarda dado pessoal (LGPD). O Terraform recusa apagá-lo.
- **Sem versionamento:** não há necessidade de recuperar versões antigas das evidências, e o versionamento complicaria
  a expiração.

## Uso

```hcl
module "bucket_evidencias" {
  source = "../../modules/bucket-evidencias"

  dias_para_expirar = 90
}
```

O provider AWS (região, conta e tags) é configurado por quem chama o módulo.

## Variáveis

| Nome | Tipo | Padrão | Descrição |
|---|---|---|---|
| `prefixo` | `string` | `noz-ai-evidencias` | Prefixo do nome do bucket. O ID da conta é acrescentado ao final |
| `dias_para_expirar` | `number` | `90` | Dias até as evidências serem apagadas. Mínimo 1 |

O padrão de `dias_para_expirar` é provisório e deve ser definido com a NOZ, considerando a LGPD.

## Saídas

| Nome | Descrição |
|---|---|
| `nome` | Nome do bucket de evidências |
| `arn` | ARN do bucket de evidências |

O ARN é a base das policies de IAM de quem grava as fotos (backend da NOZ) e de quem as lê (agente). Para objetos, use
`<arn>/*`.

## Cuidados

- **Renomear o `prefixo`** muda o nome do bucket e faz o Terraform tentar destruí-lo e recriá-lo. Como há
  `prevent_destroy`, o `plan` falhará, e isso é intencional.
- **Reduzir `dias_para_expirar`** apaga evidências já existentes na próxima execução da regra. Confirme com a NOZ antes
  de diminuir.
- **Remover o bucket de propósito** exige retirar o `prevent_destroy` do código e esvaziar o bucket antes (o
  `force_destroy` é `false`).
- Este módulo não cria permissões de leitura ou escrita. Elas ficam nas policies de IAM de cada serviço.