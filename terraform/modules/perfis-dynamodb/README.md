# perfis-dynamodb

Tabela de perfis de interesse (usuário, empresa, grupo) e temas de conteúdo do agente de Conhecimento. Fica entre as
execuções agendadas (escrita) e as consultas da Recomendação e da Moderação (leitura). Os dados de origem da NOZ
**não** ficam aqui: são lidos via MCP.

## Modelo

| Campo | Valor |
|---|---|
| `PK` | `<empresa_id>#<tipo>#<id>`, com `tipo` = `usuario`, `empresa`, `conteudo` ou `grupo` |
| `SK` | `ATUAL` (versão vigente) ou `HIST#<iso8601>` (histórico, opcional) |
| `empresa_id` | id da empresa (atributo do índice) |
| `tipo_id` | `<tipo>#<id>` (atributo do índice) |
| demais | interesses `{topico, peso, evidencias[]}`, `atualizado_em`, `versao`, cursor da última janela |

Toda chave começa com `empresa_id`. As chaves são montadas só por `app/conhecimento/storage/chaves.py`, que rejeita
`empresa_id` vazio e ids com `#`; os testes garantem a regra. Nunca montar chave à mão.

Índice `por-empresa` (GSI): `empresa_id` (hash) + `tipo_id` (range). Todo item precisa gravar esses dois atributos
(`chaves.atributos_indexados`).

## Padrões de acesso (nenhum usa Scan)

| Consulta | Operação |
|---|---|
| Perfil atual de um usuário/empresa/grupo/conteúdo | `GetItem` com `chaves.chave(empresa, tipo, id)` |
| Vários perfis conhecidos (ex.: usuários de um grupo) | `BatchGetItem` com as chaves |
| Histórico de um perfil | `Query` na `PK`, `SK begins_with HIST#` |
| Todos os usuários (ou conteúdos) de uma empresa | `Query` no índice `por-empresa`: `empresa_id = X` e `tipo_id begins_with usuario#` |
| Atualizar perfil na execução agendada | `UpdateItem`/`PutItem` na chave atual; `BatchWriteItem` em lote |
| Cursor/janela da última execução | item `empresa#<empresa_id>` (tipo `empresa`), atributo `cursor` |

Depois de ler, conferir `chaves.empresa_da_chave(item["PK"]) == empresa_pedida` antes de devolver o dado.

## Saídas
`nome`, `arn` e `policy_json_runtime` (somente esta tabela e o índice; sem `Scan`).

## Cuidados
- `deletion_protection` ligado: para destruir a tabela de propósito, desligue primeiro.
- TTL desligado até a NOZ definir a retenção (LGPD); basta informar `ttl_atributo`.
- Renomear a tabela (`nome`) destrói e recria. Confira o `plan`.
