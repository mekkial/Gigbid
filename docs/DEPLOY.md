# Deploy checklist (single VM, Docker Compose, public HTTPS via Caddy)

**Decisions you must make first**
1. **LLM quota.** The Groq free tier (200,000 tokens/day per model) cannot serve a reviewer plus the hidden test run. Upgrade the Groq account to the pay-as-you-go **Dev tier** (the list-price cost of one proposal is about $0.005, so a few dollars covers a grading run) and use that key; or point `agent/config.yaml` at another OpenAI-compatible provider. The deployed link **must work on the open profile** (hosted open models are allowed).
2. **Host.** Any Ubuntu VM with >= 4 GB RAM (the image is ~5 GB; embeddings and the reranker run on CPU), for example a small Hetzner, DigitalOcean or Oracle instance. Cost: a few dollars a month. Keep it up until grades are released.
3. **Domain.** A subdomain with an A record pointing at the VM's IP (Caddy obtains the certificate automatically).

**Steps**
```bash
# on the VM (replace the values)
DOMAIN=gigbid.example.com GROQ_API_KEY=<dev-tier key> REPO=https://github.com/<you>/gigbid.git bash <(curl -fsSL https://raw.githubusercontent.com/<you>/gigbid/main/scripts/deploy_vm.sh)
```
The script installs Docker, clones the repo, generates secrets **on the VM** (`scripts/gen_secrets.py`), builds, starts `postgres redis gigsim mcp-marketplace api worker web caddy`, and seeds the reviewer account.
Then open `https://<domain>`, sign in as the reviewer, run one job end to end, and **put the reviewer login in the Classroom private comment** (never in the repo).

**After deploy, verify (10 minutes)**
- `curl https://<domain>/api/health` returns ok; sign in; Scout produces a draft that reaches "awaiting approval"; approve and a pipeline card appears.
- `docker compose -f infra/docker-compose.yml kill -s SIGKILL api worker`, then `docker compose -f infra/docker-compose.yml up -d api worker`; confirm a pending approval is still listed (the drill recorded in `docs/evidence/`).
- Optional: start `phoenix` and set `PHOENIX_COLLECTOR_ENDPOINT` so traces are collected.

**Known caveats**
- The Python image is large (about 5 GB) and the first request loads the embedding models (about 20 s).
- The compose file's `phoenix` and `ollama` services and the Caddy profile have not been exercised end to end by the author.
- x86 hosts are untested: the author built on arm64 (the CPU-only PyTorch wheel index supports both architectures).
