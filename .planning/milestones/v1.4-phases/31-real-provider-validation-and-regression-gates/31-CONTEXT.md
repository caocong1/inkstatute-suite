# Phase 31 Context: Real-Provider Validation and Regression Gates

**Date:** 2026-07-03
**Phase goal:** Validate the integration against a live self-hosted Hindsight instance, add automated tests, and keep the existing V2 gate suite green.

---

## Current State

- Phase 30 shipped retry + observability for memory operations.
- `HindsightMemoryContractTest` in `test_long_term_memory.py` already validates a single retain/recall/reflect cycle against a live Hindsight.
- V2 gates are currently green.
- No deployment documentation for Hindsight exists yet.

## What Needs to Change

1. Add a comprehensive live-provider test that proves multi-turn memory, cross-task recall, and preference retention.
2. Ensure CI can run without a live provider (skip tests when Hindsight is unavailable).
3. Add deployment documentation for Hindsight with environment variables, secrets, and resource expectations.
4. Run a final V2 gate regression.

## Key Decisions Already Made

- Hindsight is self-hosted via Docker.
- Ollama can serve local LLM + embeddings for dev/testing.
- `HINDSIGHT_BASE_URL` and `HINDSIGHT_API_KEY` are injected by the host.
- Tests skip when Hindsight is unavailable.

---

## Suggested Minimal Shippable Scope

- Extend `test_long_term_memory.py` with a multi-turn Hindsight validation test.
- Add `docs/deployment/hindsight.md` with setup, env vars, secrets, and resource notes.
- Add a live Hindsight test that runs only when `HINDSIGHT_BASE_URL` is reachable.
- Run `scripts/run_v2_gates.py` one final time.
- Mark v1.4 milestone complete.
