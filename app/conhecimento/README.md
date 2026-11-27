# Agente de Conhecimento

Responde, **sob demanda**, a consultas dos agentes de Recomendação e Moderação sobre uma pessoa, uma empresa, um conteúdo
ou um grupo (perfil de interesse, tema do conteúdo). Lê empresa, usuário, conteúdo e eventos da NOZ **somente via MCP**
(AgentCore Gateway), calcula na hora e responde só o que foi pedido, sempre isolado por `id_empresa`.

**O agente não guarda nada** (sem banco, sem cache, sem agendador): decisão de 27/11, D13 e D14 na spec.

Specs e decisões: `docs/specs/conhecimento/` (fora deste repositório, na pasta de documentação da squad).

## Estrutura

```
app/conhecimento/
├── main.py       # Entrypoint (AgentCore Runtime): uma consulta por invocação
├── config/       # Settings e log (vindos do agent-template)
├── model/        # Modelo do Bedrock (Haiku 5.5; não aceita `temperature`)
├── mcp_client/   # Cliente MCP do Gateway (SigV4; MCP_SIGV4=false só para MCP local)
├── prompts/      # Prompts versionados (tema em lote)
├── agent/        # consulta.py (o fluxo), perfis.py (cálculo), fonte.py (mock/real), contract.py (contratos)
├── tools/        # leitura.py (MCP), tema.py (tema em lote), seguranca.py (dado não confiável)
├── mock_mcp/     # MCP mockado, contrato provisório (dados fictícios)
├── contracts/    # JSON Schemas e exemplos das consultas e respostas
├── scripts/      # testar.py: consultar, ler o mock, extrair tema, sem escrever código
├── avaliacao/    # Avaliação (a fazer)
└── tests/
```

## Como o agente responde

1. Valida a consulta (`id_empresa` obrigatório) e a janela (padrão: últimos 90 dias).
2. Lê do MCP só o necessário: eventos **de um usuário**, conteúdos **por ids**, usuários **de uma tag**.
3. Extrai o tema dos conteúdos envolvidos (modelo, em lote); o perfil é calculado em **código**.
4. Responde com a janela usada e `avisos` de tudo que limitou ou degradou a resposta (tetos, conteúdos sem tema).

Limites por consulta (variáveis de ambiente): `MAX_EVENTOS` (2000), `MAX_CONTEUDOS` (100), `MAX_USUARIOS_GRUPO` (50),
`JANELA_PADRAO_DIAS` (90), `TIMEOUT_CONSULTA_S` (60). Passou do limite, usa os itens mais recentes e avisa.

## Consultas

O campo `tipo` escolhe a consulta (contratos em `contracts/`):

```json
{"tipo": "perfil_usuario", "id_empresa": "emp-tintas", "id_usuario": "u-emp-tintas-01", "modo": "mock"}
{"tipo": "perfil_empresa", "id_empresa": "emp-tintas", "modo": "mock"}
{"tipo": "tema_conteudo",  "id_empresa": "emp-tintas", "id_conteudo": "c-emp-tintas-001", "modo": "mock"}
{"tipo": "perfil_grupo",   "id_empresa": "emp-tintas", "tag": "pintor", "modo": "mock"}
```

`modo: "real"` lê o MCP da NOZ (exige `GATEWAY_URL`); `modo: "mock"` usa dados fictícios. Um nunca vira o outro.

## Testar sem escrever código

```bash
cd app/conhecimento
uv run python scripts/testar.py consultar --tipo usuario --empresa emp-tintas --usuario u-emp-tintas-01 --simular-tema
uv run python scripts/testar.py --help
```

`--simular-tema` troca o Haiku por um tema de mentira (sem custo e sem AWS). Sem ele, use `AWS_PROFILE=noz`.

## Testes

```bash
cd app/conhecimento && uv run pytest
```

Sem AgentCore Memory e sem Knowledge Base por enquanto.
