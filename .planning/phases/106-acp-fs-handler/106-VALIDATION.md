---
phase: 106
slug: acp-fs-handler
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-08
---

# Phase 106 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| Test framework | unittest (stdlib) |
| Test runner | `python -m unittest discover` |
| Gate runner | `python scripts/run_v2_gates.py` |
| Coverage tool | n/a (gate-based verification) |
| TDD mode | false |

---

## Requirement → Test Mapping

| Requirement | Test File | Test Class/Method | Gate |
|-------------|-----------|-------------------|------|
| FS-01 | test_client_capabilities.py | ClientCapabilitiesTests | acp-client |
| FS-02 | test_fs_handler.py | FSHandlerDispatchTests | acp-client |
| FS-03 | test_fs_sandbox.py | FSSandboxEscapeTests (5 vectors) | fs-sandbox-escape (NEW GATE-04) |
| FS-04 | test_client_capabilities.py | BackwardCompatTests | acp-client |
| SAFE-05 | test_fs_handler.py | ReferenceSanitizerTests | acp-client |
| GATE-04 | test_fs_sandbox.py | FSSandboxEscapeTests | fs-sandbox-escape (NEW) |

---

## Validation Waves

### Wave 0 (Pre-execution)
- [ ] Research complete (106-RESEARCH.md)
- [ ] Context complete (106-CONTEXT.md)
- [ ] Validation strategy complete (106-VALIDATION.md)

### Wave 1 (Core sandbox + handler)
- [ ] FSSandbox with 5 protections (test_fs_sandbox.py — 5 attack vectors)
- [ ] ReferenceSanitizer (delimiter + pattern detection + logging)
- [ ] fs/read_text_file handler (test_fs_handler.py)

### Wave 2 (Client integration + gate)
- [ ] ACPClient client_capabilities support (test_client_capabilities.py)
- [ ] Request handler registration + dispatch
- [ ] Gateway backward compatibility (no client_capabilities = no fs)
- [ ] GATE-04 added to run_v2_gates.py
- [ ] Gate count baseline updated

---

## Acceptance Criteria

1. **All 5 sandbox attack vectors tested:** path traversal, symlink escape, absolute path, bad extension, oversized file
2. **All 34 existing gates remain green** (no regressions)
3. **New GATE-04 (fs-sandbox-escape) passes**
4. **Gateway path unchanged** — no `client_capabilities` passed → no fs capability advertised
5. **Sanitizer wraps content in delimiters** and logs detected injection patterns
6. **Unregistered handler returns JSON-RPC error** (not crash)

---

## Nyquist Sampling

- Every task has automated verify (unittest command)
- No 3 consecutive tasks without automated verify
- Feedback latency: < 30s per test run (acp-client tests are fast)
