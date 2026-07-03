#!/usr/bin/env bash
# Start Hindsight with Gemini LLM + Ollama embeddings.
# Usage: ./scripts/start-hindsight.sh [--ollama]
#   --ollama  Use full Ollama backend (offline mode, no Gemini/proxy needed)
#
# Secrets are loaded from ~/.config/inkstatute/hindsight.env

set -euo pipefail

ENV_FILE="${HOME}/.config/inkstatute/hindsight.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found. Create it with GEMINI_API_KEY and proxy settings." >&2
  exit 1
fi
set -a; source "$ENV_FILE"; set +a

BACKEND="${1:-gemini}"

# Stop existing container
docker stop hindsight 2>/dev/null || true
docker rm hindsight 2>/dev/null || true

if [ "$BACKEND" = "--ollama" ]; then
  echo "Starting Hindsight with full Ollama backend (offline mode)..."
  docker run -d --name hindsight --restart unless-stopped --network host \
    -e HINDSIGHT_API_LLM_PROVIDER=openai \
    -e HINDSIGHT_API_LLM_BASE_URL=http://127.0.0.1:11434/v1 \
    -e HINDSIGHT_API_LLM_API_KEY=ollama \
    -e HINDSIGHT_API_LLM_MODEL=qwen2.5:3b \
    -e HINDSIGHT_API_LLM_MAX_CONCURRENT=1 \
    -e HINDSIGHT_API_ENABLE_OBSERVATIONS=false \
    -e HINDSIGHT_API_EMBEDDINGS_PROVIDER=openai \
    -e HINDSIGHT_API_EMBEDDINGS_OPENAI_BASE_URL=http://127.0.0.1:11434/v1 \
    -e HINDSIGHT_API_EMBEDDINGS_OPENAI_MODEL=nomic-embed-text \
    -e HINDSIGHT_API_EMBEDDINGS_OPENAI_API_KEY=ollama \
    -e HINDSIGHT_API_RERANKER_PROVIDER=rrf \
    -v hindsight-data:/home/hindsight/.pg0 \
    ghcr.io/vectorize-io/hindsight:latest
else
  echo "Starting Hindsight with Gemini LLM + Ollama embeddings..."
  docker run -d --name hindsight --restart unless-stopped --network host \
    -e HINDSIGHT_API_LLM_PROVIDER=openai \
    -e HINDSIGHT_API_LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai \
    -e HINDSIGHT_API_LLM_API_KEY="${GEMINI_API_KEY}" \
    -e HINDSIGHT_API_LLM_MODEL="${GEMINI_MODEL:-gemini-2.5-flash-lite}" \
    -e HINDSIGHT_API_LLM_MAX_CONCURRENT=1 \
    -e HINDSIGHT_API_ENABLE_OBSERVATIONS=false \
    -e HINDSIGHT_API_EMBEDDINGS_PROVIDER=openai \
    -e HINDSIGHT_API_EMBEDDINGS_OPENAI_BASE_URL=http://127.0.0.1:11434/v1 \
    -e HINDSIGHT_API_EMBEDDINGS_OPENAI_MODEL=nomic-embed-text \
    -e HINDSIGHT_API_EMBEDDINGS_OPENAI_API_KEY=ollama \
    -e HINDSIGHT_API_RERANKER_PROVIDER=rrf \
    -e HTTPS_PROXY="${HTTPS_PROXY:-http://127.0.0.1:7897}" \
    -e HTTP_PROXY="${HTTP_PROXY:-http://127.0.0.1:7897}" \
    -e NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,11434}" \
    -v hindsight-data:/home/hindsight/.pg0 \
    ghcr.io/vectorize-io/hindsight:latest
fi

echo "Waiting for Hindsight to start..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8888/health >/dev/null 2>&1; then
    echo "Hindsight is healthy."
    curl -s http://localhost:8888/health
    echo
    exit 0
  fi
  sleep 1
done

echo "ERROR: Hindsight did not become healthy within 30s." >&2
docker logs hindsight --tail 20
exit 1
