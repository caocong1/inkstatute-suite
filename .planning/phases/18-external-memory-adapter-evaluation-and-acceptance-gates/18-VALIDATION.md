---
phase: 18-external-memory-adapter-evaluation-and-acceptance-gates
status: passed
test_environment: local-stdlib
verified_at: 2026-07-02
---

# Phase 18 Validation

## Environment

No external service, API key, SDK, Docker service, database, WeCom credential, or Hermes runtime is required.

Use local source roots only:

```bash
PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src
```

For contract-suite checks:

```bash
PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src
```

For full contract-suite checks:

```bash
PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src:packages/platform-runtime/src:packages/backends/hermes/src:packages/solution-loader/src:solutions/lawfirm/src:solutions/demo_non_legal/src:packages/channels/wecom/src:packages/channels/web_sse/src:services/wecom-service/src:services/feedback-service/src:services/conversation-read-view/src
```

## Planned Checks

| Plan | Requirement | Check |
|---|---|---|
| 18-01 | EXT-02 | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_adapter_contract.py` |
| 18-01 | EXT-02 | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests` |
| 18-02 | EXT-03 | `python -m json.tool packages/contract-test-suite/fixtures/phase18_external_memory_adapter_acceptance.json >/dev/null` |
| 18-02 | EXT-03 | `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase18_external_memory_adapter_acceptance.py'` |
| 18-02 | EXT-03 | `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py'` |
| 18-03 | EXT-04 | `rg -n "platform-native|Mem0|Zep|Hindsight|OpenViking|ReMe|accepted_for_sanitized_spike|deferred_for_legal_production|live legal memory" docs/architecture/memory/external-memory-adapter-recommendation.md` |
| 18-03 | EXT-04 | Full contract-suite command from above. |

## Actual Results

| Check | Result |
|---|---|
| `python -m json.tool packages/contract-test-suite/fixtures/phase18_external_memory_adapter_acceptance.json >/dev/null` | Passed |
| `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_adapter_contract.py` | Passed, 9 tests |
| `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests` | Passed, 99 tests |
| `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase18_external_memory_adapter_acceptance.py'` | Passed, 9 tests |
| `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py'` | Passed, 9 tests |
| Full contract-suite command from above | Passed, 180 tests |
| `rg -n "platform-native|Mem0|Zep|Hindsight|OpenViking|ReMe|accepted_for_sanitized_spike|deferred_for_legal_production|live legal memory" docs/architecture/memory/external-memory-adapter-recommendation.md` | Passed |

## Acceptance Gate

Phase 18 can pass only if:

- Adapter manifests are dependency-free, provider-neutral, and do not alter RunRuntime or channel contracts.
- Mem0/Zep-style evidence is synthetic/sanitized only.
- Privacy tests reject raw payloads, secret-like values, and attempts to make an external provider the default legal path.
- Final docs recommend a production path and list live legal-memory gates.
