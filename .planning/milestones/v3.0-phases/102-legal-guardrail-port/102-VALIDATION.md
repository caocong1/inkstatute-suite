---
phase: 102
slug: legal-guardrail-port
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-08
---

# Phase 102 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x (Python 3.11+) |
| **Config file** | none — uses PYTHONPATH and default pytest discovery |
| **Quick run command** | `PYTHONPATH=packages/agent-core/src:packages/agent-core/tests:packages/platform-contract/src:packages/platform-runtime/src:packages/model-gateway/src python -m pytest packages/agent-core/tests/ -q` |
| **Full suite command** | same as quick (suite is fast, ~2s for 550 tests) |
| **Estimated runtime** | ~3 seconds (550 existing + ~126 new = ~676 tests) |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 102-01-01 | 01 | 1 | CORE-06 | — | N/A | unit | `pytest tests/test_tool_leak.py -q` | ❌ W0 | ⬜ pending |
| 102-01-02 | 01 | 1 | CORE-06 | — | N/A | unit | `pytest tests/test_tool_leak_sanitize.py -q` | ❌ W0 | ⬜ pending |
| 102-01-03 | 01 | 1 | CORE-06 | — | N/A | unit | `pytest tests/test_tool_leak_parse.py -q` | ❌ W0 | ⬜ pending |
| 102-02-01 | 02 | 1 | CORE-05 | — | N/A | unit | `pytest tests/test_prompt_assembler.py -q` | ❌ W0 | ⬜ pending |
| 102-02-02 | 02 | 1 | CORE-05 | — | N/A | unit | `pytest tests/test_retrieval_tool_mapping.py -q` | ❌ W0 | ⬜ pending |
| 102-03-01 | 03 | 2 | CORE-07 | — | N/A | unit | `pytest tests/test_citation_extract.py -q` | ❌ W0 | ⬜ pending |
| 102-03-02 | 03 | 2 | CORE-07 | — | N/A | unit | `pytest tests/test_citation_verify.py -q` | ❌ W0 | ⬜ pending |
| 102-03-03 | 03 | 2 | CORE-07 | — | N/A | unit | `pytest tests/test_citation_event.py -q` | ❌ W0 | ⬜ pending |
| 102-04-01 | 04 | 2 | SAFE-01, SAFE-04 | — | guardrails cannot be bypassed | unit | `pytest tests/test_guardrails.py -q` | ❌ W0 | ⬜ pending |
| 102-04-02 | 04 | 2 | SAFE-01 | — | skill_candidate.requires_human_review always true | unit | `pytest tests/test_skill_candidate_safety.py -q` | ❌ W0 | ⬜ pending |
| 102-04-03 | 04 | 2 | SAFE-04 | — | de-AI polish does not alter legal meaning | unit | `pytest tests/test_de_ai_polish.py -q` | ❌ W0 | ⬜ pending |
| 102-05-01 | 05 | 3 | CORE-08 | — | N/A | integration | `pytest tests/test_e2e_guardrail_pipeline.py -q` | ❌ W0 | ⬜ pending |
| 102-05-02 | 05 | 3 | CORE-05..08 | — | N/A | integration | `pytest tests/test_golden_fixture_replay.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_tool_leak.py` — stubs for CORE-06 (tool leak detection golden fixtures)
- [ ] `tests/test_prompt_assembler.py` — stubs for CORE-05 (prompt assembly golden fixtures)
- [ ] `tests/test_citation_extract.py` — stubs for CORE-07 (citation extraction golden fixtures)
- [ ] `tests/test_guardrails.py` — stubs for SAFE-01, SAFE-04 (guardrail enforcement)
- [ ] `tests/test_golden_fixture_replay.py` — stubs for CORE-08 (cross-component replay)

*Existing infrastructure (pytest, 550 tests, PYTHONPATH setup) covers framework requirements.*

---

## Manual-Only Verifications

| ID | Description | Risk if skipped | HG |
|----|-------------|-----------------|-----|
| HG-1 | Lawyer sampling: ported prompt assembly output quality ≥ existing lawyer-desktop/Hermes | Legal prompt distortion → degraded LLM output → wrong legal advice | HG-1 (not auto-closable) |

---

## Golden Fixture Comparison Set

The Rust-side test cases from `lawyer-desktop` are the golden fixture source. Each must be replicated as a Python test with equivalent behavior:

| Source File | Rust Tests | Python Target | Plan |
|-------------|-----------|---------------|------|
| `llm/tool_leak.rs` | 12 tests (detection, sanitization, parsing) | `test_tool_leak*.py` | 102-01 |
| `skills/router.rs` | 10 tests (prompt assembly, tool mapping) | `test_prompt_assembler.py` | 102-02 |
| `citations/extract.rs` | 12 tests (6 regexes, edge cases) | `test_citation_extract.py` | 102-03 |
| `citations/verify.rs` | 2 tests (verified/retrieved/unverified) | `test_citation_verify.py` | 102-03 |
| **Total** | **36 tests** | | |

---

## Guardrail Enforcement Tests

Each of the four guardrails must have tests proving code-level enforcement (no bypass path):

| Guardrail | Enforcement Point | Test Approach |
|-----------|-------------------|---------------|
| Research-gate | `prompt_assembler.build_system_prompt()` always includes research-gate text | Assert no code path produces a prompt without it |
| Ask-user-enforcement | Draft/Evidence prompts always include ask-user mandate; clarification tool terminates turn | Assert prompt contains mandate; assert turn termination |
| Citation audit | `audit()` runs after every final response; unverified citations labeled | Assert audit runs; assert three-state labeling |
| De-AI polish | Post-processing runs after citation audit; AI patterns removed | Assert polish runs; assert legal meaning preserved |
