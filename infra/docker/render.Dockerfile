# Light single-container image for a 512 MB free host (Render). BM25 retrieval, no PyTorch, no embedding model, no reranker.
# One container: GigSim (127.0.0.1:8081) + the API, which also serves the built web app on $PORT. Tools run in-process (GIGBID_TOOLS=local).
FROM node:22-alpine AS web
WORKDIR /web
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONPATH=/app
WORKDIR /app
COPY requirements-light.txt ./
RUN pip install -r requirements-light.txt
COPY . .
COPY --from=web /web/dist /app/apps/web/dist
RUN python -m data.build.gen_data
ENV GIGBID_STATIC_DIR=/app/apps/web/dist MODEL_PROFILE=open RAG_VARIANT=v6_bm25 GIGBID_TOOLS=local MARKETPLACE_MODE=gigsim \
    GIGSIM_BASE_URL=http://127.0.0.1:8081 MCP_LEDGER_PATH=/tmp/mcp_ledger.sqlite REDIS_URL=
EXPOSE 10000
CMD ["bash", "scripts/render_start.sh"]
