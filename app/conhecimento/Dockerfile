# Imagem do agente de Conhecimento para o AgentCore Runtime (arm64, Graviton).
# Construída pelo CodeBuild (terraform/modules/container-build) com esta pasta como contexto.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    # o SDK do AgentCore só escuta em 0.0.0.0 dentro de contêiner
    DOCKER_CONTAINER=1

WORKDIR /app

RUN pip install --no-cache-dir uv==0.7.19

# Dependências primeiro: esta camada só se refaz quando pyproject.toml ou uv.lock mudam.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

# O agente só lê o código e o .venv (ambos de root, legíveis); não escreve em /app.
RUN useradd --create-home --uid 1000 agente
USER agente

# O AgentCore Runtime espera o servidor HTTP na 8080 (/invocations e /ping).
EXPOSE 8080

CMD ["opentelemetry-instrument", "python", "-m", "main"]
