---
phase: "26-memory-provider-evaluation-and-selection"
title: "Phase 26 Memory Provider Evaluation and Selection"
status: complete
completed: "2026-07-03"
requirements: [MEM-01, MEM-02, MEM-03]
---

# Phase 26 Summary: Memory Provider Evaluation and Selection

## What Was Done

### Evaluation artifacts
- `26-RESEARCH.md` — surveyed 7 external long-term memory providers (Hindsight, Mem0, Zep, Letta, LangMem, Supermemory, Honcho) against the product goal of seamless, long-horizon, personalized memory.
- `26-PROVIDER-COMPARISON.md` — structured comparison matrix covering recall accuracy, integration cost, self-hosting, latency, API simplicity, long-term personality retention, framework lock-in, and operational footprint.
- `26-SELECTION.md` — final selection of **Hindsight** with explicit rejection rationale for each other candidate and risk notes (newer provider, LLM extraction cost, LLM-provider dependency).

### Live smoke test
- `26-SMOKE-TEST.md` — real Hindsight API smoke test against a local Hindsight v0.8.4 Docker instance with embedded PostgreSQL and Ollama (`qwen2.5:3b` + `nomic-embed-text`).
- Verified `retain`, `recall`, and `reflect` end-to-end with a synthetic user persona and cross-day recall scenario.
- Latency: retain ~3.3s, recall ~0.15s, reflect ~5.4s (local inference).

### Decision
- Hindsight selected as the single productized long-term memory backend.
- No managed-cloud dependency required; single-tenant self-hosted shape preserved.

## Test Results

- Smoke test: Hindsight API reachable; retain/recall/reflect returned expected results.
- No automated unit tests in this phase (evaluation/selection phase).

## Known Limitations

- Local embedding model (`nomic-embed-text`) is less precise than cloud providers; semantic thresholds to be tuned in Phase 28.
- RRF reranker used instead of a neural reranker under the local-only setup.
- Negative recall returns the closest available facts rather than nothing without a configured focus threshold.

## Requirements Closed

- MEM-01, MEM-02, MEM-03 — satisfied.

## Next Phase

Phase 27: Unified Memory Interface and Hindsight Adapter.
