# Deploy checklist (single VM, Docker Compose, public HTTPS via Caddy)

**Where to host for free (researched 2026-11-14)**
* **Hugging Face Docker Spaces: no longer free** (creating one returned "requires a PRO subscription"). `scripts/deploy_space.sh` and `infra/docker/space.Dockerfile` (single-container image, UI served by the API) are kept for anyone with PRO (about $9/month).
* **Oracle Cloud Always Free** (recommended): an Ampere A1 VM with 4 OCPU / 24 GB RAM, no charge within the free limits; a card is needed for identity verification only. Create the VM with Ubuntu 24.04, open ports 80 and 443 in the VCN security list, get a free `*.duckdns.org` name pointing at the VM, then run the steps below. `deploy_vm.sh` also opens the VM's own iptables for 80/443.
* **Not enough RAM for our models:** Fly.io, Google Cloud and other free micro VMs (about 1 GB), Render/Koyeb free (512 MB), Vercel (serverless only: it can host the web UI, not the torch-based backend).
* **Laptop + Cloudflare tunnel:** free but the assignment requires the link to stay live until grades are released and to survive the hidden test run, so use it only as a stop-gap.

**LLM quota.** The Groq free tier gives 200,000 tokens/day per model (about 13 proposals at ~15k tokens each, spread over three models by node routing). A grading run may need more: add a second free provider key in `agent/config.yaml`, or enable pay-as-you-go (about $0.005 per proposal). The deployed link **must work on the open profile** (hosted open models are allowed).

**Steps**
```bash
# on the VM (replace the values)
DOMAIN=gigbid.duckdns.org GROQ_API_KEY=<key> REPO=https://github.com/<you>/gigbid.git bash <(curl -fsSL https://raw.githubusercontent.com/<you>/gigbid/main/scripts/deploy_vm.sh)
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
