# Phase 26: Hindsight Smoke Test Log

**Date:** 2026-07-03
**Tester:** Devin
**Target:** Hindsight self-hosted via `ghcr.io/vectorize-io/hindsight:latest`
**Runtime:** Docker on WSL2 with host-network mode
**LLM:** Ollama `qwen2.5:3b` via OpenAI-compatible endpoint
**Embeddings:** Ollama `nomic-embed-text` via OpenAI-compatible endpoint
**Reranker:** RRF (Reciprocal Rank Fusion)

---

## Environment

| Component | Value |
|-----------|-------|
| Hindsight image | `ghcr.io/vectorize-io/hindsight:latest` (v0.8.4) |
| Database | Embedded `pg0` (PostgreSQL 18.1.0) |
| LLM provider | `openai` pointing at `http://127.0.0.1:11434/v1` |
| LLM model | `qwen2.5:3b` |
| Embeddings provider | `openai` pointing at `http://127.0.0.1:11434/v1` |
| Embeddings model | `nomic-embed-text` (768 dims) |
| Reranker | `rrf` |

---

## What Worked

1. **Docker image starts cleanly** with embedded PostgreSQL.
2. **Ollama embeddings endpoint** works: `/v1/embeddings` returns vectors for `nomic-embed-text`.
3. **Ollama chat endpoint** works: `/v1/chat/completions` returns responses for `qwen2.5:3b`.
4. **Hindsight `/health` returns** `{"status":"healthy","database":"connected"}`.
5. **Bank creation** succeeds.
6. **Retain** succeeds and extracts structured facts (3.34s).
7. **Recall** returns relevant facts (0.15s).
8. **Reflect** synthesizes a coherent answer from recalled facts (5.39s).

---

## Test Scenario

Retained content:

> User is a lawyer named Alice Chen. She specializes in commercial contract disputes. Her current active case is a breach-of-contract dispute with Acme Corporation. Alice prefers concise, direct answers and dislikes verbose explanations. She usually works late on Tuesdays and Thursdays.

### Recall: "What case is Alice currently handling?"

Returned memories:

1. `User's current active case is a breach-of-contract dispute with Acme Corporation.`
2. `User (Alice Chen) is a lawyer specializing in commercial contract disputes.`
3. `User usually works late on Tuesdays and Thursdays.`
4. `User prefers concise, direct answers and dislikes verbose explanations.`

**Result:** Relevant case fact is ranked first. PASS.

### Reflect: "Tell me about Alice's work preferences and current project."

Answer correctly synthesizes:

- Concise/direct preference
- Active breach-of-contract case with Acme Corporation
- Specialization in commercial contract disputes
- Late work schedule on Tuesdays and Thursdays

**Result:** PASS.

### Negative recall: "What does Alice like to eat for breakfast?"

Returned memories are the same four unrelated facts (no breakfast info exists). This is expected behavior when no relevant memory exists: Hindsight returns the closest available facts rather than an empty set.

**Result:** Acceptable for a local smoke test; semantic threshold tuning belongs to Phase 28 (Focus vs Retention).

---

## Observations and Limitations

- Local `qwen2.5:3b` is fast enough for retain (~3s) and reflect (~5s) but fact-extraction quality is lower than cloud LLMs.
- `nomic-embed-text` is functional but less precise than `text-embedding-3-small` or `BAAI/bge-small-en-v1.5`.
- RRF reranker replaces neural reranker, which is fine for a smoke test but not optimal for final ranking.
- The negative-recall result confirms the need for a confidence threshold / focus policy in Phase 28.

---

## Conclusion

Hindsight successfully runs with a fully local Ollama stack. The core retain/recall/reflect loop is verified end-to-end. The selection is validated for v1.4.

---

## Reproduction Command

```bash
# 1. Pull Ollama embedding model
curl -s http://localhost:11434/api/pull -d '{"name":"nomic-embed-text"}'

# 2. Run Hindsight with local Ollama
docker run -d --name hindsight-smoke --restart unless-stopped --network host \
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
