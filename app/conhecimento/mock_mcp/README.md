# MCP mockado da NOZ (contrato provisório)

Servidor MCP falso com **dados fictícios** para desenvolver o agente de Conhecimento enquanto o contrato real da NOZ
não chega. Este documento é o **contrato provisório**: serve para o Gustavo comparar com o MCP real e dizer o que
difere. Os modelos estão em `agent/dominio.py`.

## Como rodar

```bash
cd app/conhecimento
uv run python -m mock_mcp.server                # stdio
uv run python -m mock_mcp.server --http 8765    # http://127.0.0.1:8765/mcp
```

## Regras do contrato

1. **Toda consulta, exceto `listar_empresas`, exige `id_empresa`** e nunca devolve dado de outra empresa. Sem ele, ou
   com empresa inexistente, devolve erro claro (`id_empresa é obrigatório`, `empresa não encontrada: ...`).
2. **Listas paginadas por cursor opaco:** `{"itens": [...], "proximo_cursor": "<str>" | null}`. `limite` padrão 50,
   máximo 200.
3. **Leitura incremental:** `atualizado_desde` nos conteúdos e `desde`/`ate` nos eventos (ISO 8601; intervalo
   `(desde, ate]`, em ordem cronológica).
4. Erros viram erro de tool do MCP, sem stack trace.

## Tools

| Tool | Parâmetros | Devolve |
|---|---|---|
| `listar_empresas` | `cursor?`, `limite?` | `Empresa` |
| `listar_usuarios` | `id_empresa`, `tag?`, `cursor?`, `limite?` | `Usuario` |
| `listar_conteudos` | `id_empresa`, `ids?`, `atualizado_desde?`, `cursor?`, `limite?` | `Conteudo` |
| `listar_eventos` | `id_empresa`, `id_usuario?`, `desde?`, `ate?`, `cursor?`, `limite?` | `Evento` |

**Consulta dirigida.** O agente não guarda nada: cada consulta é de uma pessoa, empresa, conteúdo ou grupo, então ele
precisa pedir só o necessário. `id_usuario` (eventos), `ids` (conteúdos) e `tag` (usuários) existem para isso.
- `id_usuario` precisa ser da empresa pedida; senão, `usuário não encontrado` (a mesma mensagem para "não existe" e
  "é de outra empresa"). Usuário sem eventos devolve lista vazia, não erro.
- `ids` (máx. 200): os que não existem, ou são de outra empresa, simplesmente não vêm.

## Campos (provisórios)

- **Empresa:** `id_empresa`, `nome`, `setor?`, `descricao?`, `categorias[]`.
- **Usuario:** `id_usuario`, `id_empresa`, `tags[]`.
- **Conteudo:** `id_conteudo`, `id_empresa`, `tipo` (`post|curso|desafio`), `titulo`, `texto?`, `idioma?`,
  `atualizado_em`.
- **Evento:** `id_evento`, `id_empresa`, `id_usuario`, `id_conteudo?`, `tipo` (`clique|acesso|comentario`),
  `ocorrido_em`, `canal?`, `dispositivo?`, `navegador?`, `texto?` (comentário).

## Perguntas para o Gustavo (o que o contrato real pode mudar)

- Os nomes e campos acima batem com os do MCP real? Quais faltam, sobram ou têm outro nome?
- O MCP cobre **dados básicos e eventos**? A leitura de eventos é pelo MCP ou por endpoint dedicado do DynamoDB?
- **O MCP filtra eventos por usuário (`id_usuario`) e devolve conteúdos por lista de ids?** Sem isso, cada consulta teria
  de ler a empresa inteira. É a pergunta mais importante.
- Paginação existe (cursor)? Qual o limite por página e por chamada? Há limite de requisições e qual o tempo de resposta?
- Os eventos mais recentes aparecem na hora ou com atraso?
- Como o MCP autentica (OAuth, chave) e como aplica o escopo por empresa (token, parâmetro)?
- Existe listagem de empresas para o agente descobrir os tenants?

## Dados e casos embutidos

3 empresas (construção, tecnologia, luto), ~50 usuários, ~100 conteúdos, ~2000 eventos, determinísticos (mesma
semente, mesmos dados). Casos de teste: o tema `pintura` existe em duas empresas (isolamento); um conteúdo e um
comentário com prompt injection; um usuário sem eventos (`u-emp-tintas-20`); um evento que aponta para conteúdo
inexistente (`c-inexistente`).
