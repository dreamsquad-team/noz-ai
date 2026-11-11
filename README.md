# AgentCore Template

Template para agentes de IA sobre Amazon Bedrock AgentCore. Gerado com o `agentcore` CLI (deploy via CDK, runtime
`CodeZip`, Strands). Copie `AgentTemplate/`, siga o checklist abaixo e faça o deploy.

> **Começando um projeto novo?** Vá direto para [Iniciando um projeto novo](#iniciando-um-projeto-novo).
> A referência do CLI e dos tipos do `agentcore.json` está em [`AgentTemplate/README.md`](AgentTemplate/README.md) e
> [`AgentTemplate/AGENTS.md`](AgentTemplate/AGENTS.md).

## O que vem pronto

- **Runtime** Strands + `BedrockAgentCoreApp`, com streaming e fallback não-streaming (`stream: false`).
- **Memória** de curto prazo por `(session_id, user_id)` (AgentCore Memory).
- **Gateway MCP** com um target Lambda esqueleto (`AgentTemplate/lambda/my-tool`), autenticado por IAM.
- **Cliente MCP com SigV4** (`mcp_client/`): assina para a região do próprio gateway e, se o gateway estiver ausente,
  mal configurado ou fora do ar, o agente sobe sem as tools dele em vez de falhar.
- **Testes** do agente (67) e da Lambda (18), mais duas guardas contra deriva de nome e contra resíduo de cliente
  (ver [Guardas](#guardas-que-protegem-o-template)).

## Estrutura

```
AgentTemplate/                  # raiz do projeto AgentCore (é isto que se copia)
├── agentcore/
│   ├── agentcore.json          # fonte da verdade: runtime, memória, gateway, KB, policy engine
│   ├── aws-targets.json        # conta + região do deploy
│   └── cdk/                    # CDK gerado pelo CLI — não edite
├── app/agent-template/         # código do agente (codeLocation do runtime)
│   ├── main.py                 # entrypoint, registro das tools
│   ├── agent/factory.py        # monta o Agent
│   ├── mcp_client/             # cliente do Gateway (client.py) + SigV4 (sigv4.py)
│   ├── config/settings.py      # variáveis de ambiente
│   ├── model/load.py           # modelo
│   ├── prompts/v1.txt          # system prompt
│   ├── global-policy.json      # IAM extra da execution role
│   └── tests/
└── lambda/                     # código das Lambdas dos targets do gateway
    └── my-tool/handler.py
```

## Iniciando um projeto novo

Faça nesta ordem. A etapa 1 vem **antes de qualquer deploy**: renomear um recurso depois destrói e recria o recurso
(`AGENTS.md`, invariante 2), e isso apaga a memória de conversas.

### 1. Renomear

O mesmo nome aparece em vários arquivos, e esquecer um deles costuma falhar **em silêncio** (o agente sobe sem
memória ou sem as tools). Duas dessas ligações têm teste que falha se divergirem.

| O quê | Onde mudar | Se esquecer |
|---|---|---|
| Nome do projeto | `agentcore.json` → `name` e `tags` | Prefixa a stack e o nome do runtime (`<projeto>_<runtime>`) |
| Nome do runtime | `agentcore.json` → `runtimes[0].name` | O ARN de workload identity em `global-policy.json` (`<Projeto>_<Runtime>-*`) deixa de bater |
| Diretório do código | renomear `app/agent-template/` **e** `runtimes[0].codeLocation` | O deploy não acha o código |
| Memória | `agentcore.json` → `memories[0].name` **e** o alias `MEMORY_<NOME>_ID` em `config/settings.py` | Agente sobe sem memória, sem erro. **Coberto por teste** |
| Gateway | `agentcore.json` → `agentCoreGateways[0].name` **e** o alias `AGENTCORE_GATEWAY_<NOME>_URL` em `config/settings.py` (`-` vira `_`) | Agente sobe sem as tools do gateway, sem erro. **Coberto por teste** |
| Tool | `toolDefinitions[0].name` **e** `TOOL` em `lambda/my-tool/handler.py` | A Lambda responde "tool desconhecida" a toda chamada. **Sem teste** |
| Pacotes Python | `name` em `app/agent-template/pyproject.toml` e `lambda/*/pyproject.toml` | Só cosmético |

### 2. Substituir placeholders e valores de conta

O `agentcore validate` **não** pega placeholders dentro de `global-policy.json` nem de `iamPolicy`: eles chegam
literais ao IAM (conferido com `cdk synth`). Ache todos com:

```sh
grep -rnE "TROCAR POR PROJETO|<ACCOUNT_ID>|<PROMPT_ID>|<PATH>|replace-with-your-kb-bucket|000000000000" AgentTemplate \
  --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=cdk.out --exclude-dir=dist --exclude-dir=.cache \
  --exclude-dir=.llm-context --exclude-dir=.cli --exclude=uv.lock --exclude=package-lock.json
```

| Onde | O que colocar |
|---|---|
| `agentcore/aws-targets.json` | `account` (12 dígitos) e `region` |
| `app/agent-template/global-policy.json` | `<ACCOUNT_ID>` e a região nos ARNs. `<PROMPT_ID>` só importa quando houver Prompt Management (hoje nada chama `GetPrompt`) |
| `agentcore.json` → `iamPolicy` da Lambda | `<ACCOUNT_ID>` e `<PATH>` do parâmetro SSM — ou apague o statement se a Lambda não lê SSM |
| `agentcore.json` → `knowledgeBases` | bucket em `replace-with-your-kb-bucket` — ou remova o bloco (ver etapa 4) |

Nos dois campos que o `agentcore validate` confere o formato (conta de 12 dígitos e nome de bucket S3), o placeholder é
um valor **válido** (`000000000000`, `replace-with-your-kb-bucket`), porque `<...>` seria recusado.

A região `us-east-1` está fixa em `aws-targets.json`, `global-policy.json` e no ARN do SSM. No código não há região
fixa que importe: o cliente do gateway assina para a região que está na URL do próprio gateway.

### 3. Conteúdo do agente

| Onde | O que fazer |
|---|---|
| `app/agent-template/prompts/v1.txt` | Escrever o system prompt. Hoje é neutro (regras anti-invenção e formato). **O arquivo inteiro vai para o modelo**: não deixe comentário nem marcador dentro dele |
| `app/agent-template/model/load.py` | Trocar o modelo. A role do runtime já pode invocar qualquer modelo/inference profile da conta; só um modelo de **Marketplace** exige statement extra em `global-policy.json` (`aws-marketplace:ViewSubscriptions`, `Subscribe`) |
| `app/agent-template/main.py` | Apagar `add_numbers` (tool de exemplo) e registrar as tools do cliente em `build_tools(...)` |
| `lambda/my-tool/handler.py` | Implementar `run()` e `validate_input()`. Manter a forma do retorno igual ao `outputSchema` do `agentcore.json` |
| `agentcore.json` → `toolDefinitions` | Nome, descrição, `inputSchema` e `outputSchema` da tool. A descrição é o que o modelo lê para decidir quando chamar |

### 4. Decidir o que remover

Cada bloco abaixo vem ligado e provisiona recursos na conta. Se o projeto não usa, remova **antes** do primeiro deploy.

- **`knowledgeBases`**: cria uma Knowledge Base e precisa de um bucket com os documentos.
- **`agentCoreGateways` + `lambda/`**: se o agente não usa tools remotas, remova os dois e o `get_gateway_mcp_client` em
  `main.py`.
- **`policyEngines`**: o gateway está com `policyEngineConfiguration.mode: "ENFORCE"` e `policies: []`. **Não verifiquei
  em deploy** o que acontece com as chamadas de tool nesse estado; faça um deploy de teste e confirme que a tool é
  chamada antes de considerar pronto.
- **`memories`**: `strategies: []` guarda só o histórico de curto prazo. Memória de longo prazo exige estratégias.

### 5. Verificar e fazer deploy

```sh
(cd AgentTemplate/app/agent-template && uv run pytest)   # agente
(cd AgentTemplate/lambda && uv run pytest)               # Lambda
(cd AgentTemplate/agentcore && agentcore validate)       # schema do agentcore.json
(cd AgentTemplate/agentcore && agentcore deploy)
```

Não há segundo deploy: a URL do gateway é injetada pelo CDK já resolvida (ver [Decisões](#decisões-de-design)).
Para rodar local (`agentcore dev`), defina `GATEWAY_URL` e `MEMORY_ID` como variáveis de ambiente (ou num `.env`: o
`settings.py` o lê relativo ao diretório de onde o agente é executado). O cliente do gateway assina com as suas
credenciais AWS.

## Guardas que protegem o template

- `tests/test_settings.py` lê o `agentcore.json` e falha se o alias de memória ou de gateway em `settings.py` não
  casar com o nome do recurso. É o que pega a renomeação esquecida da etapa 1.
- `tests/test_template_is_agnostic.py` varre `agentcore.json`, `aws-targets.json`, `app/` e `lambda/` atrás de
  rastros de clientes anteriores (nome, conta, bucket, modelo). Ao reaproveitar o template, **não** acrescente o novo
  cliente à lista: acrescente os que passaram por aqui e deixaram resíduo.

## Decisões de design

- **Gateway sem `connection`.** Para um gateway declarado no mesmo `agentcore.json`, o CDK já injeta
  `AGENTCORE_GATEWAY_<NOME>_URL` (resolvida no deploy) e já concede `bedrock-agentcore:InvokeGateway` à role.
  Conferido comparando a saída de `cdk synth` com e sem `connection`. A `connection` só serve para gateway de **outro
  projeto**; nesse caso o `id` dela vira o nome da variável (`GATEWAY_<ID>_URL`), o alias em `settings.py` muda e o
  ARN real é obrigatório.
- **Sem context manager de sessão para o gateway.** Desde o Strands 1.53 o `MCPClient` é um `ToolProvider` com
  `continue_on_error`: entregue em `tools=[...]`, o Agent abre a sessão e, se o handshake falhar, segue com `[]`.
  Por isso o piso é `strands-agents >= 1.53.0`. Em versão anterior seria preciso gerenciar a sessão à mão.
- **`global-policy.json` só tem o que o CDK não concede.** A role já recebe `bedrock:InvokeModel*` (qualquer
  modelo e inference profile da conta) e X-Ray de escrita. Ficam amostragem do X-Ray, métricas do AgentCore e
  workload identity.

## Observações

- Este projeto não usa Terraform nem container: o deploy é `agentcore deploy` com runtime `CodeZip`.
- `.python-version` diz 3.13 (é o que o CI e os testes usam); o runtime na AWS é `PYTHON_3_14` (`agentcore.json`).
- Ao copiar o template, **não** leve junto o `agentcore/.cli/` de um projeto já deployado: o `deployed-state.json`
  guarda ids dos recursos dele. O versionado aqui está vazio (`{"targets": {}}`) e deve começar assim.
- O README e a documentação da arquitetura antiga (FastAPI + Terraform + container) estão no histórico do git, antes
  do commit `4083872`.
