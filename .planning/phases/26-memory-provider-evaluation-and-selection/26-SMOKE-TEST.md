# Phase 26: Hindsight Smoke Test Log

**Date:** 2026-07-03
**Tester:** Devin
**Target:** Hindsight self-hosted via `ghcr.io/vectorize-io/hindsight:latest`
**Runtime:** Docker on WSL2

---

## Setup Steps Attempted

1. Pulled `ghcr.io/vectorize-io/hindsight:latest` (~9 GB full image with local embedding models).
2. Started container with embedded Postgres (`pg0`) and Ollama as the LLM provider.
3. Used `qwen3.5:9b` via Ollama's OpenAI-compatible endpoint at `http://127.0.0.1:11434/v1`.
4. Configured reranker to `rrf` (Reciprocal Rank Fusion) to avoid needing a neural reranker service.

---

## What Worked

- Docker image pulled successfully.
- Hindsight API process starts and initializes its embedded PostgreSQL database.
- Ollama connection is reachable from the Hindsight container in host-network mode.
- LLM provider `ollama` is accepted and the connection is verified.
- Reranker `rrf` initializes correctly without external dependencies.

## What Blocked

- Hindsight's `openai` embeddings provider calls Ollama's `/v1/embeddings` endpoint.
- The Ollama instance available at `localhost:11434` returns:
  ```json
  {"error":{"message":"This server does not support embeddings. Start it with `--embeddings`","type":"api_error"}}
  ```
- Without an embeddings endpoint, Hindsight cannot initialize and the API fails to start.

## Attempted Workarounds

- Tried the `latest-slim` image, which does not bundle local embedding models and requires an external embeddings provider. Same result: the Ollama instance does not expose embeddings.
- Tried using local sentence-transformer models, but the container environment cannot reach HuggingFace to download them.

---

## Required to Complete Smoke Test

A real external LLM + embeddings API key, or an Ollama server started with `--embeddings` and a compatible embedding model. Recommended options:

| Provider | Needed env vars for Hindsight |
|----------|---------------------------------|
| OpenAI | `HINDSIGHT_API_LLM_PROVIDER=openai`, `HINDSIGHT_API_LLM_API_KEY=sk-...`, `HINDSIGHT_API_EMBEDDINGS_PROVIDER=openai`, `HINDSIGHT_API_EMBEDDINGS_OPENAI_API_KEY=sk-...` |
| Anthropic | `HINDSIGHT_API_LLM_PROVIDER=anthropic`, `HINDSIGHT_API_LLM_API_KEY=sk-ant-...` (need separate OpenAI-compatible embeddings endpoint) |
| Groq | `HINDSIGHT_API_LLM_PROVIDER=groq`, `HINDSIGHT_API_LLM_API_KEY=gsk-...` (need separate embeddings endpoint) |
| Gemini | `HINDSIGHT_API_LLM_PROVIDER=gemini`, `HINDSIGHT_API_LLM_API_KEY=...` |

---

## Next Step

Re-run Hindsight with a real API key and execute the multi-turn memory scenario:
1. Create a memory bank `lawyer-assistant`.
2. Retain a synthetic persona and active project facts.
3. After a simulated gap, recall with a new turn that references the project indirectly.
4. Verify relevant memories are returned and unrelated ones are not.
5. Record latency and recall quality.

---

## Conclusion

Hindsight is operationally straightforward to start with Docker and Ollama, but the local Ollama instance in this environment does not expose embeddings. The selection remains valid; a real API key is the only remaining blocker to complete the smoke test.
