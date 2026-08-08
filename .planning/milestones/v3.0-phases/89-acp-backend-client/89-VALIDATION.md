---
phase: 89
slug: acp-backend-client
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-07
---

# Phase 89 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (Python) |
| **Config file** | `packages/acp-client/pyproject.toml` |
| **Quick run command** | `python -m pytest packages/acp-client/tests/ -x` |
| **Full suite command** | `python scripts/run_v2_gates.py` |
| **Estimated runtime** | ~30 seconds |

## Sampling Rate

- **After every task commit:** Run `python -m pytest packages/acp-client/tests/ -x`
- **After every plan wave:** Run `python scripts/run_v2_gates.py`
- **Before phase complete:** All 29 gates green (28 existing + 1 new acp-client)
- **Max feedback latency:** 30 seconds

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 89-01-01 | 01 | 1 | ACP-01 | unit | `python -m pytest packages/acp-client/tests/test_acp_client.py -x` | ❌ W0 | ⬜ pending |
| 89-01-02 | 01 | 1 | ACP-01 | unit | `python -m pytest packages/acp-client/tests/test_capability_negotiation.py -x` | ❌ W0 | ⬜ pending |
| 89-01-03 | 01 | 1 | ACP-01 | unit | `python -m pytest packages/acp-client/tests/test_event_mapping.py -x` | ❌ W0 | ⬜ pending |
| 89-02-01 | 02 | 2 | ACP-02 | integration | `python -m pytest packages/acp-client/tests/test_adapter.py -x` | ❌ W0 | ⬜ pending |
| 89-03-01 | 03 | 2 | ACP-06 | integration | `python -m pytest packages/acp-client/tests/test_lifecycle.py -x` | ❌ W0 | ⬜ pending |
| 89-04-01 | 04 | 3 | ACP-03 | integration | `python -m pytest packages/acp-client/tests/test_second_backend.py -x` | ❌ W0 | ⬜ pending |
| 89-05-01 | 05 | 3 | ACP-06 | gate | `python scripts/run_v2_gates.py` | ✅ | ⬜ pending |

## Wave 0 Requirements

- [ ] `packages/acp-client/tests/test_acp_client.py` — stubs for ACP client
- [ ] `packages/acp-client/tests/test_capability_negotiation.py` — stubs for capability negotiation
- [ ] `packages/acp-client/tests/test_event_mapping.py` — stubs for event mapping
- [ ] `packages/acp-client/tests/test_adapter.py` — stubs for BackendAdapter
- [ ] `packages/acp-client/tests/test_lifecycle.py` — stubs for subprocess lifecycle
- [ ] `packages/acp-client/tests/fixtures/echo_agent.py` — in-repo fixture agent

## Validation Sign-Off

- [ ] All tasks have automated verify
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter
