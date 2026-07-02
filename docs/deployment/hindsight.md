# Hindsight Deployment Guide

This guide covers deploying the Hindsight long-term memory backend for InkStatute v1.4.

## Overview

Hindsight is the default long-term memory provider for InkStatute v1.4. It is self-hosted via Docker and provides `retain`, `recall`, and `reflect` operations. The InkStatute runtime connects to Hindsight through the `HindsightMemory` adapter.

## Required Secrets

| Variable | Required | Description |
|----------|----------|-------------|
| `HINDSIGHT_BASE_URL` | Yes | Hindsight API base URL, e.g. `http://localhost:8888` |
| `HINDSIGHT_API_KEY` | No | Bearer token if Hindsight is configured with authentication |

These secrets are injected by the host at runtime. They are never read by the neutral `platform-runtime` package; the host (e.g., `wecom-service` or a deployment entrypoint) constructs the `hindsight_client.Hindsight` instance and passes it to `HindsightMemory`.

## Local Development Setup

### 1. Start Ollama

Hindsight can use Ollama for local LLM and embedding inference. Pull the recommended models:

```bash
ollama pull nomic-embed-text
ollama pull qwen2.5:3b
```

Ensure Ollama is reachable at `http://127.0.0.1:11434`.

### 2. Run Hindsight

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

Verify health:

```bash
curl http://localhost:8888/health
```

### 3. Configure InkStatute

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

## Production Considerations

- Use a dedicated PostgreSQL instance for Hindsight data instead of the embedded store for production.
- Use a cloud or self-managed LLM and embedding model instead of Ollama for better latency and quality.
- Configure a neural reranker instead of RRF for better recall ranking.
- Run Hindsight behind a reverse proxy with TLS.
- Keep the `HINDSIGHT_API_KEY` in a secrets manager (Kubernetes secret, Vault, etc.).
- Monitor the Hindsight health endpoint and memory operation events emitted by `RetryableMemory`.

## Resource Expectations

| Component | Minimum | Notes |
|-----------|---------|-------|
| Hindsight container | 2 CPU / 4 GB RAM | Embedded PostgreSQL + API server |
| Ollama host (dev) | 4 CPU / 8 GB RAM | For `qwen2.5:3b` + `nomic-embed-text` |
| Network | Hindsight → LLM/embedding endpoint | Latency sensitive |
| Disk | 10 GB | Hindsight data volume |

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `TimeoutError` during retain | Ollama model is slow or unreachable | Verify Ollama health and model availability |
| `openai.InternalServerError` | Ollama model does not support embeddings | Use `nomic-embed-text` for embeddings |
| 401 from Hindsight chat | API key mismatch | Check `HINDSIGHT_API_KEY` and Hindsight auth config |
| Recall returns unrelated memories | Local embedding model is weak | Use a stronger model or tune focus threshold |
