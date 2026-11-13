# One image for every Python service (api, worker, gigsim, MCP servers); the command is chosen in docker-compose.yml.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 UV_SYSTEM_PYTHON=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl && rm -rf /var/lib/apt/lists/* && pip install uv
WORKDIR /app
COPY pyproject.toml ./
# CPU-only PyTorch first (the default aarch64/x86 wheels drag in several GB of CUDA libraries we never use)
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
RUN mkdir -p agent rag evals gigsim mcp_servers apps worker data && for d in agent rag evals gigsim mcp_servers apps worker data; do touch $d/__init__.py; done \
 && uv pip install --system -e ".[dev]" langchain-openai langgraph-supervisor arize-phoenix-otel openinference-instrumentation-openai openinference-instrumentation-langchain
COPY . .
# Deterministic synthetic data (personas, clients, job pool, dev sets) is generated at build time; real Kaggle rows are NOT shipped
RUN python -m data.build.gen_data
# Pre-download the open embedding + reranker models so the first request is fast (CPU inference)
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; SentenceTransformer('BAAI/bge-small-en-v1.5'); CrossEncoder('BAAI/bge-reranker-base')"
EXPOSE 8000 8081 8082
