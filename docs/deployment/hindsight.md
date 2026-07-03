# Hindsight Deployment Guide

This guide covers deploying the Hindsight long-term memory backend for InkStatute v1.4.

## Overview

Hindsight is the default long-term memory provider for InkStatute v1.4. It is self-hosted via Docker and provides `retain`, `recall`, and `reflect` operations. The InkStatute runtime connects to Hindsight through the `HindsightMemory` adapter.

## Architecture

| Component | Default Backend | Model | Notes |
|-----------|----------------|-------|-------|
| LLM | Google Gemini (via proxy) | `gemini-2.5-flash-lite` | Fact extraction + reflect reasoning |
| Embeddings | Local (in-process) | `BAAI/bge-m3` | 1024 dims, multilingual, CPU |
| Reranker | Local (in-process) | `BAAI/bge-reranker-v2-m3` | Cross-encoder, CPU |
| Data store | Docker volume `hindsight-data` | Embedded PostgreSQL | pgvector for vector search |

## Required Secrets

| Variable | Required | Description |
|----------|----------|-------------|
| `HINDSIGHT_BASE_URL` | Yes | Hindsight API base URL, e.g. `http://localhost:8888` |
| `HINDSIGHT_API_KEY` | No | Bearer token if Hindsight is configured with authentication |
| `GEMINI_API_KEY` | Gemini backend only | Google Gemini API key for LLM |
| `HTTPS_PROXY` | Gemini backend only | Local proxy for reaching Google API from WSL |

Secrets are stored in `~/.config/inkstatute/hindsight.env` (outside the repo, permissions 600). They are never read by the neutral `platform-runtime` package; the host (e.g., `wecom-service` or a deployment entrypoint) constructs the `hindsight_client.Hindsight` instance and passes it to `HindsightMemory`.

## Quick Start

```bash
# 1. Create secrets file (one-time setup)
mkdir -p ~/.config/inkstatute
cat > ~/.config/inkstatute/hindsight.env <<'EOF'
GEMINI_API_KEY=<your-key>
GEMINI_MODEL=gemini-2.5-flash-lite
HTTPS_PROXY=http://127.0.0.1:7897
HTTP_PROXY=http://127.0.0.1:7897
NO_PROXY=localhost,127.0.0.1,11434
HINDSIGHT_BASE_URL=http://localhost:8888
HINDSIGHT_API_KEY=ollama
EOF
chmod 600 ~/.config/inkstatute/hindsight.env

# 2. Start Hindsight (downloads BGE models on first run, ~3 min)
./scripts/start-hindsight.sh

# 3. Verify
curl http://localhost:8888/health
```

## Configuration Profiles

### Default: Gemini LLM + BGE-M3 Embeddings + BGE Reranker

```bash
./scripts/start-hindsight.sh
```

Uses:
- **LLM**: `gemini-2.5-flash-lite` via Google Gemini API (through local proxy)
- **Embeddings**: `BAAI/bge-m3` loaded in-process via sentence-transformers (CPU, 1024 dims)
- **Reranker**: `BAAI/bge-reranker-v2-m3` loaded in-process via sentence-transformers (CPU, cross-encoder)

First startup downloads BGE-M3 (~2.3 GB) and BGE-Reranker-V2-M3 (~568 MB) from HuggingFace. Models are cached at `/tmp/hf-cache` (bind-mounted into the container). Subsequent starts load from cache.

### Offline: Full Ollama

```bash
./scripts/start-hindsight.sh --ollama
```

Uses:
- **LLM**: `qwen2.5:3b` via local Ollama
- **Embeddings**: `nomic-embed-text` via local Ollama (768 dims)
- **Reranker**: RRF (no model needed)

No proxy or external API required. Lower quality but fully offline.

## Gemini Model Selection

| Model | Free Tier RPM | Tool Calling | Notes |
|-------|---------------|--------------|-------|
| `gemini-2.5-flash-lite` | 15 | Yes | **Recommended** for free tier |
| `gemini-2.5-flash` | 5 | Yes | Better quality but tight rate limits |
| `gemini-2.0-flash-lite` | 15 | Yes | Daily quota exhausts quickly |
| `gemini-3.1-flash-lite` | 5 | **Broken** | Requires `thought_signature`, incompatible with Hindsight's OpenAI adapter |

**Important:** Gemini 3.x models require `thought_signature` in function call parts, which Hindsight's OpenAI-compatible client does not provide. Use 2.x models only.

## Why BGE-M3 + BGE-Reranker-V2-M3?

| Feature | BGE-M3 | nomic-embed-text |
|---------|--------|------------------|
| Dimensions | 1024 | 768 |
| Multilingual | Yes (100+ languages, strong CJK) | Limited |
| Max tokens | 8192 | 8192 |
| pgvector HNSW | Within 2000-dim limit | Within limit |
| License | MIT | MIT |

| Feature | BGE-Reranker-V2-M3 | RRF |
|---------|---------------------|-----|
| Type | Cross-encoder | Score fusion |
| Quality | High (neural relevance scoring) | Baseline |
| Multilingual | Yes | N/A |
| Latency | ~50ms/candidate (CPU) | ~0ms |

BGE-M3 and BGE-Reranker-V2-M3 are loaded in-process by Hindsight via `sentence-transformers` — no separate TEI container needed. Both run on CPU.

## Environment Variables

### LLM

| Variable | Default | Description |
|----------|---------|-------------|
| `HINDSIGHT_API_LLM_PROVIDER` | `openai` | LLM provider (`openai` for Gemini compat) |
| `HINDSIGHT_API_LLM_BASE_URL` | — | OpenAI-compatible endpoint |
| `HINDSIGHT_API_LLM_API_KEY` | — | API key |
| `HINDSIGHT_API_LLM_MODEL` | `gemini-2.5-flash-lite` | Model name |
| `HINDSIGHT_API_LLM_MAX_CONCURRENT` | `1` | Concurrency limit (respect free-tier RPM) |

### Embeddings

| Variable | Default | Description |
|----------|---------|-------------|
| `HINDSIGHT_API_EMBEDDINGS_PROVIDER` | `local` | `local` for sentence-transformers, `openai` for Ollama/external |
| `HINDSIGHT_API_EMBEDDINGS_LOCAL_MODEL` | `BAAI/bge-m3` | HuggingFace model ID |
| `HINDSIGHT_API_EMBEDDINGS_LOCAL_FORCE_CPU` | `true` | Force CPU mode |
| `HINDSIGHT_API_EMBEDDINGS_LOCAL_TRUST_REMOTE_CODE` | `true` | Required for BGE-M3 |

### Reranker

| Variable | Default | Description |
|----------|---------|-------------|
| `HINDSIGHT_API_RERANKER_PROVIDER` | `local` | `local` for sentence-transformers, `rrf` for fusion-only |
| `HINDSIGHT_API_RERANKER_LOCAL_MODEL` | `BAAI/bge-reranker-v2-m3` | HuggingFace model ID |
| `HINDSIGHT_API_RERANKER_LOCAL_FORCE_CPU` | `true` | Force CPU mode |
| `HINDSIGHT_API_RERANKER_LOCAL_TRUST_REMOTE_CODE` | `true` | Required for BGE reranker |
| `HINDSIGHT_API_RERANKER_LOCAL_MAX_CONCURRENT` | `2` | Concurrency limit |
| `HINDSIGHT_API_RERANKER_LOCAL_BATCH_SIZE` | `16` | Batch size for reranking |

### Proxy (for Gemini API access from WSL)

| Variable | Default | Description |
|----------|---------|-------------|
| `HTTPS_PROXY` | `http://127.0.0.1:7897` | Proxy for outbound HTTPS |
| `HTTP_PROXY` | `http://127.0.0.1:7897` | Proxy for outbound HTTP |
| `NO_PROXY` | `localhost,127.0.0.1,11434` | Exclude local services |

### Model Cache

| Variable | Default | Description |
|----------|---------|-------------|
| `HF_HOME` | `/home/hindsight/.hf-cache` | HuggingFace cache dir inside container |
| `HF_CACHE_DIR` (host) | `/tmp/hf-cache` | Host directory bind-mounted into container |

## Running Live Memory Tests

```bash
export HINDSIGHT_BASE_URL=http://localhost:8888
export HINDSIGHT_API_KEY=ollama

PYTHONPATH=$(find packages services -name src -type d | tr '\n' ':') \
  python -m pytest packages/platform-runtime/tests/test_long_term_memory.py -v
```

Tests auto-skip when Hindsight is not reachable.

## Production Considerations

- Use a dedicated PostgreSQL instance for Hindsight data instead of the embedded store.
- Use a paid Gemini API key for higher rate limits.
- Deploy BGE-M3 and BGE-Reranker-V2-M3 via TEI (Text Embeddings Inference) containers with GPU for production latency.
- Run Hindsight behind a reverse proxy with TLS.
- Keep secrets in a secrets manager (Kubernetes secret, Vault, etc.).
- Monitor the Hindsight health endpoint and memory operation events emitted by `RetryableMemory`.

## Resource Expectations

| Component | Minimum | Notes |
|-----------|---------|-------|
| Hindsight container | 4 CPU / 8 GB RAM | PostgreSQL + BGE-M3 + BGE-Reranker in-process |
| Disk (data) | 10 GB | Hindsight PostgreSQL data |
| Disk (models) | 3 GB | BGE-M3 (2.3 GB) + BGE-Reranker-V2-M3 (568 MB) |
| Network | Hindsight → Gemini API via proxy | Latency sensitive for LLM calls |

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `PermissionError: .hf-cache/hub` | HF cache dir not writable | `chmod 777 /tmp/hf-cache` |
| `TimeoutError` during retain | LLM is slow or unreachable | Check proxy and Gemini API key |
| `429 RateLimitError` | Free tier quota exhausted | Wait for reset or use paid key |
| `thought_signature` error | Using Gemini 3.x model | Switch to `gemini-2.5-flash-lite` |
| Embedding dimension exceeds 2000 | Using Gemini embeddings (3072 dims) | Use BGE-M3 (1024 dims) instead |
| Model download slow | First run downloads from HuggingFace | Wait ~3 min; cached on subsequent runs |
| 401 from Hindsight chat | API key mismatch | Check `HINDSIGHT_API_KEY` and Hindsight auth config |
| Recall returns unrelated memories | Weak embedding or reranker | Verify BGE-M3 and BGE-Reranker loaded correctly in logs |
