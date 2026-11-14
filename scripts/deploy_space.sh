#!/usr/bin/env bash
# Publish the current commit to a Hugging Face Docker Space (free CPU). Usage: scripts/deploy_space.sh <user>/<space>   (needs `hf auth login`)
set -euo pipefail
SPACE=${1:?usage: deploy_space.sh user/space}
cd "$(dirname "$0")/.."
HF=.venv/bin/hf; [ -x "$HF" ] || HF=hf
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
git archive HEAD | tar -x -C "$T"
cp infra/docker/space.Dockerfile "$T/Dockerfile"
{ printf -- '---\ntitle: GigBid\nemoji: 🧭\ncolorFrom: indigo\ncolorTo: blue\nsdk: docker\napp_port: 7860\npinned: false\n---\n\n'; cat README.md; } > "$T/README.md"
$HF repo create "$SPACE" --repo-type space --space-sdk docker --exist-ok >/dev/null
$HF upload "$SPACE" "$T" . --repo-type space --commit-message "Deploy $(git rev-parse --short HEAD)"
echo "https://huggingface.co/spaces/$SPACE"
