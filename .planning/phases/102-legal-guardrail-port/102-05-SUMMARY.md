# Plan 102-05 Summary: Turn Loop Integration + Golden Fixture Replay

## Status: COMPLETE

## What Was Done

Plan 102-05 is the final plan of Phase 102 (Legal Guardrail Port). It wires all
four guardrail modules (tool_leak, prompt_assembler, citations, guardrails) into
the turn loop and creates the golden fixture replay + success criteria mapping
test suite.

### Files Modified

1. **`packages/agent-core/src/inkstatute_agent_core/turn_loop.py`** — Already
   integrated by dependency plans (102-01 through 102-04). The integration
   includes:
   - Leak detection + retry loop (`contains_tool_leakage()` → retry up to
     `config.max_leak_retries`, then `sanitize_assistant_content()`)
   - Citation audit pipeline (`_run_citation_audit()` → `emit_citation_recorded()`)
   - De-AI polish (`de_ai_polish()`)
   - Retrieval evidence collection (`_collect_retrieval_evidence()`)
   - Citation audit summary in `message.completed` metadata

2. **`packages/agent-core/src/inkstatute_agent_core/config.py`** — Already
   has `max_leak_retries: int = 3` field with validation (`>= 0`), matching
   Rust `MAX_LEAK_RETRIES` (chat.rs:36).

### Files Created

3. **`packages/agent-core/tests/test_e2e_guardrail_pipeline.py`** — 9
   integration tests verifying the full guardrail pipeline in the turn loop:
   - Leak retry: leaked first round → clean second round (provider called twice)
   - Leak retry exhaustion: all rounds leak → sanitized output after max retries
   - Citation audit: law citation triggers `citation.recorded` event
   - Citation audit metadata: `message.completed` includes audit summary
   - No citation event when content has no citations
   - De-AI polish: AI disclaimers removed before `message.completed`
   - "Not legal advice" boilerplate removed
   - Retrieval evidence: tool result → citation labelled "retrieved"
   - Full pipeline: leak retry → citation audit → de-AI polish in sequence

4. **`packages/agent-core/tests/test_golden_fixture_replay.py`** — 21
   golden fixture replay tests (SC-6) verifying same-input same-output:
   - tool_leak: REAL_DSML_LEAK detection, sanitization, parsing, determinism
   - prompt_assembler: three modes, research-gate, citation spec, skill injection
   - citations/extract: law article, multiple articles, case numbers, determinism
   - Full pipeline: deterministic end-to-end output for fixed input

5. **`packages/agent-core/tests/test_phase102_success_criteria.py`** — 33
   success criteria mapping tests verifying all 6 SCs from ROADMAP:
   - SC-1: prompt assembly ported (7 tests)
   - SC-2: tool_leak ported with golden fixtures (5 tests)
   - SC-3: citation audit ported (4 tests)
   - SC-4: four guardrails code-level enforced (7 tests)
   - SC-5: skill_candidate.requires_human_review safety (4 tests)
   - SC-6: golden fixture comparison set (5 tests)
   - HG-1 reminder: NOT auto-closable (1 test)

## Test Results

- **New tests**: 63 passed (9 + 21 + 33)
- **Full suite**: 784 passed (721 existing + 63 new), 0 failed
- **HG-1**: Remains OPEN — not claimed as passed by any test

## Success Criteria Verification

| SC | Description | Status | Verifying Tests |
|----|-------------|--------|-----------------|
| SC-1 | router.rs prompt assembly ported | PASS | test_phase102_success_criteria.py::TestSC1* (7 tests) |
| SC-2 | tool_leak.rs ported with golden fixtures | PASS | test_phase102_success_criteria.py::TestSC2* (5 tests) |
| SC-3 | citation audit ported | PASS | test_phase102_success_criteria.py::TestSC3* (4 tests) |
| SC-4 | four guardrails code-level enforced | PASS | test_phase102_success_criteria.py::TestSC4* (7 tests) |
| SC-5 | skill_candidate.requires_human_review safety | PASS | test_phase102_success_criteria.py::TestSC5* (4 tests) |
| SC-6 | golden fixture comparison set | PASS | test_phase102_success_criteria.py::TestSC6* (5 tests) |

## Threat Model Disposition

| Threat | Severity | Disposition | Status |
|--------|----------|-------------|--------|
| T-102-18 | high | mitigate | Leak detection + retry (max 3) after every streaming round |
| T-102-19 | high | mitigate | Citation audit before message.completed + citation.recorded event |
| T-102-20 | medium | mitigate | De-AI polish after citation audit, conservative patterns only |
| T-102-21 | high | mitigate | Fixed guardrail sequence: leak → citation → polish → completed |
| T-102-22 | medium | mitigate | max_leak_retries default 3, validation prevents negative, frozen dataclass |

## Human Gates

- **HG-1 (法律质量)**: REMAINS OPEN. Requires lawyer sampling to confirm
  output quality is no worse than lawyer-desktop / Hermes. Not auto-closable.
  No test claims HG-1 as passed.
