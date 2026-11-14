#!/usr/bin/env bash
# One-shot deploy on a fresh Ubuntu 22.04/24.04 VM (>= 4 GB RAM, 2 vCPU, 25 GB disk). Run as a sudo-capable user.
#   DOMAIN=gigbid.example.com GROQ_API_KEY=... REPO=https://github.com/<you>/gigbid.git bash scripts/deploy_vm.sh
# Point the domain's A record at the VM first (Caddy needs it to get a certificate). Secrets are generated on the VM and never leave it.
set -euo pipefail
: "${DOMAIN:?set DOMAIN}"; : "${GROQ_API_KEY:?set GROQ_API_KEY (paid/dev tier: the free tier cannot serve a grading run)}"; : "${REPO:?set REPO}"
command -v docker >/dev/null || { curl -fsSL https://get.docker.com | sudo sh; sudo usermod -aG docker "$USER"; }
[ -d gigbid ] || git clone "$REPO" gigbid
cd gigbid
if [ ! -f .env ]; then
  cp .env.example .env
  python3 -m venv /tmp/gs && /tmp/gs/bin/pip -q install cryptography && /tmp/gs/bin/python scripts/gen_secrets.py > /tmp/secrets.env
  TOK=$(grep '^MARKETPLACE_TOKENS=' /tmp/secrets.env | cut -d= -f2 | cut -d: -f1)
  { grep -vE '^(APP_SECRET_KEY|TOKEN_ENCRYPTION_KEY|MARKETPLACE_TOKENS|MARKETPLACE_MCP_TOKEN|REVIEWER_PASSWORD|GROQ_API_KEY|DOMAIN|PUBLIC_API_URL|PUBLIC_WEB_URL|PHOENIX_COLLECTOR_ENDPOINT)=' .env; grep -v '^#' /tmp/secrets.env
    echo "MARKETPLACE_MCP_TOKEN=$TOK"; echo "GROQ_API_KEY=$GROQ_API_KEY"; echo "DOMAIN=$DOMAIN"
    echo "PUBLIC_API_URL=https://$DOMAIN"; echo "PUBLIC_WEB_URL=https://$DOMAIN/"; } > .env.new && mv .env.new .env && chmod 600 .env && rm -f /tmp/secrets.env
fi
sg docker -c "docker compose -f infra/docker-compose.yml --profile public up -d --build postgres redis gigsim mcp-marketplace api worker web caddy"
echo "waiting for the API..."; for i in $(seq 1 60); do curl -fsS "http://localhost:8000/health" >/dev/null 2>&1 && break; sleep 5; done
set -a; . ./.env; set +a
sg docker -c "docker compose -f infra/docker-compose.yml exec -T -e REVIEWER_PASSWORD=$REVIEWER_PASSWORD api python scripts/seed_reviewer.py"
echo "DONE. https://$DOMAIN  | reviewer: ${REVIEWER_EMAIL:-reviewer@gigbid.dev} / (REVIEWER_PASSWORD in .env: put it in the Classroom PRIVATE comment, never in the repo)"
