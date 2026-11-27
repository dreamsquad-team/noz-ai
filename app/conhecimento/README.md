# Agente de Conhecimento

Lê empresa, usuário, conteúdo e eventos da NOZ **somente via MCP** (AgentCore Gateway) e grava perfis de interesse e
temas de conteúdo numa tabela DynamoDB própria, isolados por `empresa_id`. Execução agendada. Os agentes de
Recomendação e Moderação consultam esses perfis.

Specs e decisões: `docs/specs/conhecimento/` (fora deste repositório, na pasta de documentação da squad).

## Estrutura

```
app/conhecimento/
├── config/       # Settings e log (vindos do agent-template)
├── model/        # Modelo do Bedrock
├── mcp_client/   # Cliente MCP do Gateway (SigV4)
├── prompts/      # System prompts versionados
├── agent/        # Agente (T08)
├── tools/        # Tools de leitura via MCP (T05)
├── mock_mcp/     # MCP mockado, contrato provisório (T04)
├── contracts/    # Contratos e JSON Schemas (T03)
├── avaliacao/    # Avaliação (T13)
└── tests/
```

Sem AgentCore Memory e sem Knowledge Base por enquanto.

## Testes

```bash
cd app/conhecimento && uv run pytest
```
