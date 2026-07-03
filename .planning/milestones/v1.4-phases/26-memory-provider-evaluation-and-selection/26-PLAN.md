# Phase 26 Plan: Memory Provider Evaluation and Selection

**Phase:** 26
**Goal:** Re-evaluate 2026 external long-term memory providers and select the one that best fits the product goal of seamless, personalized, long-horizon memory.
**Requirements:** MEM-01, MEM-02, MEM-03
**Success Criteria:**
1. A shortlist of 2026 providers is evaluated against accuracy, integration cost, self-hosting, and long-term personality retention.
2. A real API smoke test against the top candidate is performed and recorded.
3. The final selection is documented with explicit rejection rationale for the others.
4. The chosen provider can be self-hosted or deployed without adding new managed-cloud dependencies that break the single-tenant product shape.

---

## Wave 1: Finalize Provider Comparison Matrix and Selection Artifact

### Task 1.1: Create a structured comparison matrix
- Write `.planning/phases/26-memory-provider-evaluation-and-selection/26-PROVIDER-COMPARISON.md`.
- Include rows for Hindsight, Mem0, Zep, Letta, LangMem, Supermemory, Honcho.
- Columns: recall accuracy, integration cost, self-hosting, latency, API simplicity, long-term personality retention, framework lock-in, operational footprint.
- Cite sources from 26-RESEARCH.md and the web search results.

### Task 1.2: Document the final selection
- Write `26-SELECTION.md` with:
  - Selected provider: Hindsight
  - Selection rationale
  - Rejection rationale for each other candidate
  - Risk notes (newer provider, LLM extraction cost, dependency on LLM provider)
  - Smoke-test plan

### Task 1.3: Commit Wave 1 artifacts
- Commit `26-RESEARCH.md`, `26-PROVIDER-COMPARISON.md`, `26-SELECTION.md`.

---

## Wave 2: Live Smoke Test Against Hindsight

### Task 2.1: Install and run Hindsight locally
- Install `hindsight-all` in a fresh virtual environment or use Docker.
- Start `hindsight-api` with embedded Postgres on default port 8888.
- Verify health endpoint and API docs.

### Task 2.2: Run a realistic multi-turn memory scenario
- Create a synthetic user persona: name, role, preferences, active project.
- Retain the persona and project facts via the Hindsight `retain` API.
- Simulate a second conversation days later where the user references the project indirectly.
- Call `recall` with the new turn and verify the relevant persona/project facts are returned.
- Verify that unrelated memories are not recalled.

### Task 2.3: Record smoke-test evidence
- Write `26-SMOKE-TEST.md` with:
  - Setup steps
  - API requests/responses (sanitized)
  - Observed recall quality
  - Latency notes
  - Blockers or issues encountered

### Task 2.4: Commit smoke-test evidence
- Commit `26-SMOKE-TEST.md` and any helper scripts under `.planning/phases/26-memory-provider-evaluation-and-selection/scripts/`.

---

## Verification

- [ ] `26-PROVIDER-COMPARISON.md` exists and covers all required candidates and dimensions.
- [ ] `26-SELECTION.md` exists with explicit selection and rejection rationale.
- [ ] `26-SMOKE-TEST.md` exists with evidence of a real Hindsight API call.
- [ ] Hindsight API was reachable and returned memories.
- [ ] No managed-cloud dependency is required for the selected path.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Hindsight self-hosting fails or is buggy | Also run a quick Mem0 smoke test so the matrix has a second real data point. |
| LLM extraction is too slow/costly | Record latency and cost; this becomes a design input for Phase 28 retention policy. |
| Hindsight API changes | Pin version and record exact command/package versions used. |

---

## Next Phase

Phase 27 will define the unified `Memory` interface and implement the Hindsight adapter based on the selection and smoke-test findings here.
