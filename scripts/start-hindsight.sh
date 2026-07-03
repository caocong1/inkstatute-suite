#!/usr/bin/env bash
# Start Hindsight memory backend for InkStatute.
#
# Usage:
#   ./scripts/start-hindsight.sh              # Gemini LLM + BGE-M3 embeddings + BGE reranker (default)
#   ./scripts/start-hindsight.sh --ollama     # Full Ollama backend (offline mode)
#
# Secrets are loaded from ~/.config/inkstatute/hindsight.env
# The default profile uses:
#   LLM:        Gemini 2.5-flash-lite (via proxy, requires GEMINI_API_KEY)
#   Embeddings: BAAI/bge-m3 (local, in-process, CPU)
#   Reranker:   BAAI/bge-reranker-v2-m3 (local, in-process, CPU)
# The --ollama profile uses:
#   LLM:        qwen2.5:3b (local Ollama)
#   Embeddings: nomic-embed-text (local Ollama)
#   Reranker:   RRF (local, no model needed)

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

# Ensure HF cache directory exists with correct permissions for bind mount
HF_CACHE_DIR="${HF_CACHE_DIR:-/tmp/hf-cache}"
mkdir -p "$HF_CACHE_DIR"
chmod 777 "$HF_CACHE_DIR"

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
  echo "Starting Hindsight with Gemini LLM + BGE-M3 embeddings + BGE reranker..."
  echo "  LLM:        ${GEMINI_MODEL:-gemini-2.5-flash-lite} (via proxy)"
  echo "  Embeddings: BAAI/bge-m3 (local CPU, 1024 dims)"
  echo "  Reranker:   BAAI/bge-reranker-v2-m3 (local CPU)"
  echo "  HF cache:   $HF_CACHE_DIR"
  docker run -d --name hindsight --restart unless-stopped --network host \
    -e HINDSIGHT_API_LLM_PROVIDER=openai \
    -e HINDSIGHT_API_LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai \
    -e HINDSIGHT_API_LLM_API_KEY="${GEMINI_API_KEY}" \
    -e HINDSIGHT_API_LLM_MODEL="${GEMINI_MODEL:-gemini-2.5-flash-lite}" \
    -e HINDSIGHT_API_LLM_MAX_CONCURRENT=1 \
    -e HINDSIGHT_API_ENABLE_OBSERVATIONS=false \
    -e HINDSIGHT_API_EMBEDDINGS_PROVIDER=local \
    -e HINDSIGHT_API_EMBEDDINGS_LOCAL_MODEL=BAAI/bge-m3 \
    -e HINDSIGHT_API_EMBEDDINGS_LOCAL_FORCE_CPU=true \
    -e HINDSIGHT_API_EMBEDDINGS_LOCAL_TRUST_REMOTE_CODE=true \
    -e HINDSIGHT_API_RERANKER_PROVIDER=local \
    -e HINDSIGHT_API_RERANKER_LOCAL_MODEL=BAAI/bge-reranker-v2-m3 \
    -e HINDSIGHT_API_RERANKER_LOCAL_FORCE_CPU=true \
    -e HINDSIGHT_API_RERANKER_LOCAL_TRUST_REMOTE_CODE=true \
    -e HINDSIGHT_API_RERANKER_LOCAL_MAX_CONCURRENT=2 \
    -e HINDSIGHT_API_RERANKER_LOCAL_BATCH_SIZE=16 \
    -e HTTPS_PROXY="${HTTPS_PROXY:-http://127.0.0.1:7897}" \
    -e HTTP_PROXY="${HTTP_PROXY:-http://127.0.0.1:7897}" \
    -e NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,11434}" \
    -e HF_HOME=/home/hindsight/.hf-cache \
    -v hindsight-data:/home/hindsight/.pg0 \
    -v "$HF_CACHE_DIR":/home/hindsight/.hf-cache \
    ghcr.io/vectorize-io/hindsight:latest
fi

# Wait for health (first startup downloads BGE models, may take several minutes)
TIMEOUT="${HEALTH_TIMEOUT:-180}"
echo "Waiting for Hindsight to start (timeout: ${TIMEOUT}s, first run may download models)..."
for i in $(seq 1 "$TIMEOUT"); do
  if curl -sf http://localhost:8888/health >/dev/null 2>&1; then
    echo "Hindsight is healthy (after ${i}s)."
    curl -s http://localhost:8888/health
    echo
    exit 0
  fi
  # Print progress every 15s
  if [ $((i % 15)) -eq 0 ]; then
    echo "  ...still waiting (${i}s)"
  fi
  sleep 1
done

echo "ERROR: Hindsight did not become healthy within ${TIMEOUT}s." >&2
docker logs hindsight --tail 30
exit 1
