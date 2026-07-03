# Hindsight Deployment Guide

This guide covers deploying the Hindsight long-term memory backend for InkStatute v1.4.

## Overview

Hindsight is the default long-term memory provider for InkStatute v1.4. It is self-hosted via Docker and provides `retain`, `recall`, and `reflect` operations. The InkStatute runtime connects to Hindsight through the `HindsightMemory` adapter.

## Required Secrets

| Variable | Required | Description |
|----------|----------|-------------|
| `HINDSIGHT_BASE_URL` | Yes | Hindsight API base URL, e.g. `http://localhost:8888` |
| `HINDSIGHT_API_KEY` | No | Bearer token if Hindsight is configured with authentication |
| `GEMINI_API_KEY` | Gemini backend only | Google Gemini API key for LLM |
| `HTTPS_PROXY` | Gemini backend only | Local proxy for reaching Google API from WSL |

These secrets are injected by the host at runtime. They are never read by the neutral `platform-runtime` package; the host (e.g., `wecom-service` or a deployment entrypoint) constructs the `hindsight_client.Hindsight` instance and passes it to `HindsightMemory`.

## Local Development Setup

### Option A: Gemini LLM + Ollama Embeddings (recommended)

Uses Google Gemini for LLM (fast, high quality) and local Ollama for embeddings (no dimension limits).

#### 1. Start Ollama (for embeddings only)

```bash
ollama pull nomic-embed-text
```

Ensure Ollama is reachable at `http://127.0.0.1:11434`.

#### 2. Start local proxy (for Gemini API access)

Ensure your local proxy (e.g. Clash) is running on port 7897.

#### 3. Run Hindsight

```bash
source ~/.config/inkstatute/hindsight.env

docker run -d --name hindsight --restart unless-stopped --network host \
  -e HINDSIGHT_API_LLM_PROVIDER=openai \
  -e HINDSIGHT_API_LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai \
  -e HINDSIGHT_API_LLM_API_KEY=$GEMINI_API_KEY \
  -e HINDSIGHT_API_LLM_MODEL=gemini-2.5-flash-lite \
  -e HINDSIGHT_API_LLM_MAX_CONCURRENT=1 \
  -e HINDSIGHT_API_ENABLE_OBSERVATIONS=false \
  -e HINDSIGHT_API_EMBEDDINGS_PROVIDER=openai \
  -e HINDSIGHT_API_EMBEDDINGS_OPENAI_BASE_URL=http://127.0.0.1:11434/v1 \
  -e HINDSIGHT_API_EMBEDDINGS_OPENAI_MODEL=nomic-embed-text \
  -e HINDSIGHT_API_EMBEDDINGS_OPENAI_API_KEY=ollama \
  -e HINDSIGHT_API_RERANKER_PROVIDER=rrf \
  -e HTTPS_PROXY=http://127.0.0.1:7897 \
  -e HTTP_PROXY=http://127.0.0.1:7897 \
  -e NO_PROXY=localhost,127.0.0.1,11434 \
  -v hindsight-data:/home/hindsight/.pg0 \
  ghcr.io/vectorize-io/hindsight:latest
```

Verify health:

```bash
curl http://localhost:8888/health
```

### Option B: Full Ollama (offline dev)

Uses Ollama for both LLM and embeddings. No proxy or external API needed.

```bash
ollama pull nomic-embed-text
ollama pull qwen2.5:3b
```

```bash
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
```

### Configure InkStatute

Set the runtime environment:

```bash
export HINDSIGHT_BASE_URL=http://localhost:8888
export HINDSIGHT_API_KEY=ollama
```

Run live memory tests:

```bash
PYTHONPATH=$(find packages services -name src -type d | tr '\n' ':') \
  python -m pytest packages/platform-runtime/tests/test_long_term_memory.py -v
```

## Gemini Model Selection

| Model | Free Tier RPM | Tool Calling | Notes |
|-------|---------------|--------------|-------|
| `gemini-2.5-flash-lite` | 15 | Yes (no thought_signature issue) | **Recommended** for free tier |
| `gemini-2.5-flash` | 5 | Yes | Better quality but tight rate limits |
| `gemini-2.0-flash-lite` | 15 | Yes | Daily quota exhausts quickly |
| `gemini-3.1-flash-lite` | 5 | **Broken** (requires thought_signature) | Not compatible with Hindsight's OpenAI adapter |

**Important:** Gemini 3.x models require `thought_signature` in function call parts, which Hindsight's OpenAI-compatible client does not provide. Use 2.x models only.

## Production Considerations

- Use a dedicated PostgreSQL instance for Hindsight data instead of the embedded store for production.
- Use a paid Gemini API key or a cloud LLM for higher rate limits.
- Configure a neural reranker instead of RRF for better recall ranking.
- Run Hindsight behind a reverse proxy with TLS.
- Keep the `GEMINI_API_KEY` and `HINDSIGHT_API_KEY` in a secrets manager (Kubernetes secret, Vault, etc.).
- Monitor the Hindsight health endpoint and memory operation events emitted by `RetryableMemory`.

## Resource Expectations

| Component | Minimum | Notes |
|-----------|---------|-------|
| Hindsight container | 2 CPU / 4 GB RAM | Embedded PostgreSQL + API server |
| Ollama host (embeddings) | 2 CPU / 2 GB RAM | For `nomic-embed-text` only |
| Network | Hindsight → Gemini API via proxy | Latency sensitive |
| Disk | 10 GB | Hindsight data volume |

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `TimeoutError` during retain | LLM is slow or unreachable | Check proxy and Gemini API key |
| `429 RateLimitError` | Free tier quota exhausted | Wait for reset or use paid key |
| `thought_signature` error | Using Gemini 3.x model | Switch to `gemini-2.5-flash-lite` |
| `openai.InternalServerError` | Ollama model does not support embeddings | Use `nomic-embed-text` for embeddings |
| Embedding dimension exceeds 2000 | Using Gemini embeddings (3072 dims) | Use Ollama `nomic-embed-text` (768 dims) instead |
| 401 from Hindsight chat | API key mismatch | Check `HINDSIGHT_API_KEY` and Hindsight auth config |
| Recall returns unrelated memories | Embedding model is weak | Use a stronger model or tune focus threshold |
