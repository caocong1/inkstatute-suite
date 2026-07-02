---
phase: 20
slug: durable-native-memory-store
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-02
---

# Phase 20 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python stdlib `unittest` |
| **Config file** | none - tests run with explicit `PYTHONPATH` |
| **Quick run command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_store.py packages/platform-runtime/tests/test_sqlite_memory_store.py` |
| **Full suite command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase20_durable_native_memory_store.py' && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py'` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_sqlite_memory_store.py`
- **After every plan wave:** Run `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 20-01-01 | 01 | 1 | MEM-01 | T-20-01 | Durable store reloads `MemoryRecord`, `MemoryCandidate`, and `MemoryUse` after restart | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_sqlite_memory_store.py` | No - W0 | pending |
| 20-01-02 | 01 | 1 | MEM-02 | T-20-02 | Persisted data remains refs, hashes, lengths, scopes, TTL/deletion metadata, sensitivity, confidence, review state, and safe summaries only | unit + contract | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_sqlite_memory_store.py` | No - W0 | pending |
| 20-02-01 | 02 | 1 | MEM-03 | T-20-03 | Recursive privacy guard rejects raw payload, full-text, callback/document text, and secret-like metadata before SQLite write/export | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_sqlite_memory_store.py` | No - W0 | pending |
| 20-02-02 | 02 | 2 | MEM-04, MEM-05 | T-20-04, T-20-05, T-20-06, T-20-07 | Queries enforce tenant/workspace/user/session/label/source-ref/sensitivity/confidence/TTL/deletion filters, deterministic ranking, tombstones, expiry, and export | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_sqlite_memory_store.py packages/platform-runtime/tests/test_memory_store.py` | No - W0 | pending |
| 20-02-03 | 02 | 2 | MEM-01 | T-20-08 | SQLiteMemoryStore conforms to MemoryStoreAdapter without runtime/channel constructor coupling | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_adapter_contract.py` | Existing | pending |
| 20-03-01 | 03 | 3 | MEM-02, MEM-05 | T-20-09, T-20-10 | Synthetic fixture represents active, deleted/tombstoned, candidate, memory-use, export, and deletion evidence using refs only | json | `python -m json.tool packages/contract-test-suite/fixtures/phase20_durable_native_memory_store.json >/dev/null` | No - W0 | pending |
| 20-03-02 | 03 | 3 | MEM-02, MEM-03, MEM-05 | T-20-09, T-20-10, T-20-11 | Contract tests validate fixture schema, recursive privacy, safe source refs, tombstones, export refs, and schema discovery | contract | `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase20_durable_native_memory_store.py' && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py'` | No - W0 | pending |
| 20-03-03 | 03 | 3 | MEM-01, MEM-02, MEM-03, MEM-04, MEM-05 | T-20-12 | Full phase validation passes and Nyquist sign-off records every actual Phase 20 task row as green | validation | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase20_durable_native_memory_store.py' && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py'` | This file | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `packages/platform-runtime/tests/test_sqlite_memory_store.py` - covers MEM-01 through MEM-05.
- [ ] `packages/contract-test-suite/fixtures/phase20_durable_native_memory_store.json` - synthetic durable memory fixture.
- [ ] `packages/contract-test-suite/tests/test_phase20_durable_native_memory_store.py` - privacy, relationship, export, delete, and tombstone fixture checks.
- [ ] `packages/contract-test-suite/tests/test_schema_validation.py` - include `phase20-durable-native-memory-store-001` in expected fixture IDs.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | MEM-01..MEM-05 | All phase behaviors have automated verification paths | N/A |

---

## Validation Sign-Off

- [ ] All tasks have automated verify commands or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all missing references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30 seconds
- [ ] `nyquist_compliant: true` set in frontmatter before phase verification

**Approval:** pending
