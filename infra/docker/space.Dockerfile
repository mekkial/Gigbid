# Single container for a free Hugging Face Docker Space: UI + API + GigSim + marketplace MCP on one port (7860). No Redis: jobs run in-process.
FROM node:22-alpine AS web
WORKDIR /web
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HOME=/home/user/.cache/huggingface
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl && rm -rf /var/lib/apt/lists/* && pip install uv \
 && useradd -m -u 1000 user && mkdir -p /app && chown user /app
USER user
ENV PATH=/home/user/.local/bin:$PATH
WORKDIR /app
COPY --chown=user pyproject.toml ./
RUN pip install --user torch --index-url https://download.pytorch.org/whl/cpu
RUN mkdir -p agent rag evals gigsim mcp_servers apps worker data && for d in agent rag evals gigsim mcp_servers apps worker data; do touch $d/__init__.py; done \
 && uv pip install --system --break-system-packages -e . 2>/dev/null || pip install --user -e . langchain-openai
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; SentenceTransformer('BAAI/bge-small-en-v1.5'); CrossEncoder('BAAI/bge-reranker-base')"
COPY --chown=user . .
COPY --chown=user --from=web /web/dist /app/apps/web/dist
RUN python -m data.build.gen_data
ENV GIGBID_STATIC_DIR=/app/apps/web/dist MODEL_PROFILE=open GIGBID_TOOLS=mcp MARKETPLACE_MODE=gigsim \
    GIGSIM_BASE_URL=http://127.0.0.1:8081 MARKETPLACE_MCP_URL=http://127.0.0.1:8082/mcp MCP_LEDGER_PATH=/tmp/mcp_ledger.sqlite
EXPOSE 7860
CMD ["bash", "scripts/space_start.sh"]
