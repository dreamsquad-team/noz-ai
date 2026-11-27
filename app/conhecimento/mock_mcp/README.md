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
| `listar_usuarios` | `id_empresa`, `cursor?`, `limite?` | `Usuario` |
| `listar_conteudos` | `id_empresa`, `atualizado_desde?`, `cursor?`, `limite?` | `Conteudo` |
| `listar_eventos` | `id_empresa`, `desde?`, `ate?`, `cursor?`, `limite?` | `Evento` |

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
- Paginação e leitura incremental existem (cursor, `atualizado_desde`, período)? Qual o limite por página?
- Como o MCP autentica (OAuth, chave) e como aplica o escopo por empresa (token, parâmetro)?
- Existe listagem de empresas para o agente descobrir os tenants?

## Dados e casos embutidos

3 empresas (construção, tecnologia, luto), ~50 usuários, ~100 conteúdos, ~2000 eventos, determinísticos (mesma
semente, mesmos dados). Casos de teste: o tema `pintura` existe em duas empresas (isolamento); um conteúdo e um
comentário com prompt injection; um usuário sem eventos (`u-emp-tintas-20`); um evento que aponta para conteúdo
inexistente (`c-inexistente`).
