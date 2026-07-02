---
phase: 18-external-memory-adapter-evaluation-and-acceptance-gates
status: passed
verified_at: 2026-07-02
score: 4/4
human_verification: []
review_status: local_self_review
---

# Phase 18 Verification

## Goal

The team knows whether to use platform-native memory, Mem0, Zep, or another adapter later, based on contract evidence and privacy gates.

## Must-Haves

1. A `MemoryStore` adapter contract and capability manifest can represent external memory stores without changing RunRuntime or channel contracts.
2. Mem0/Zep-style adapter spikes use only synthetic or sanitized fixtures.
3. Privacy tests fail if raw legal payloads, secrets, or unreviewed high-risk legal conclusions are stored as reusable memory.
4. The milestone ends with a documented production recommendation and acceptance gate for live legal memory use.

## Evidence

- `packages/platform-runtime/src/platform_runtime/memory_adapters.py` defines the provider-neutral adapter protocol, capability manifest, decision labels, and evaluation helper.
- `packages/platform-runtime/tests/test_memory_adapter_contract.py` proves platform-native memory can remain the current default while Mem0, Zep, Hindsight, OpenViking, and ReMe remain sanitized-spike candidates.
- `packages/contract-test-suite/fixtures/phase18_external_memory_adapter_acceptance.json` contains schema-valid, synthetic, reference-first adapter evidence.
- `packages/contract-test-suite/tests/test_phase18_external_memory_adapter_acceptance.py` validates provider non-default decisions, live legal gates, candidate roles, human review, and recursive privacy scans.
- `docs/architecture/memory/external-memory-adapter-recommendation.md` documents the final recommendation: platform-native memory now; Zep/Hindsight, OpenViking/ReMe, and Mem0 only behind future gates.
- `.planning/phases/18-external-memory-adapter-evaluation-and-acceptance-gates/18-RESEARCH.md` records the Mem0/Zep official-doc findings and the expanded lawyer-assistant component study.

## Automated Checks

- `python -m json.tool packages/contract-test-suite/fixtures/phase18_external_memory_adapter_acceptance.json >/dev/null` - passed.
- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_adapter_contract.py` - passed, 9 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests` - passed, 99 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase18_external_memory_adapter_acceptance.py'` - passed, 9 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py'` - passed, 9 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src:packages/platform-runtime/src:packages/backends/hermes/src:packages/solution-loader/src:solutions/lawfirm/src:solutions/demo_non_legal/src:packages/channels/wecom/src:packages/channels/web_sse/src:services/wecom-service/src:services/feedback-service/src:services/conversation-read-view/src python -m unittest discover -s packages/contract-test-suite/tests` - passed, 180 tests.
- `rg -n "platform-native|Mem0|Zep|Hindsight|OpenViking|ReMe|accepted_for_sanitized_spike|deferred_for_legal_production|live legal memory" docs/architecture/memory/external-memory-adapter-recommendation.md` - passed.

## Notes

- This is local synthetic acceptance, not live WeCom/legal production approval.
- No external memory SDK, service, API key, Docker service, database, network call, or runtime secret was added.
- External providers remain future candidates until privacy, tenant isolation, deletion/export, data residency, security, human-review, latency/relevance, runbook, and license/procurement gates pass.

## Result

Phase 18 passed. EXT-02, EXT-03, and EXT-04 are satisfied for v1.2: external memory stores are representable behind a neutral adapter contract, evaluated with sanitized evidence only, and governed by a documented recommendation that keeps platform-native memory as the current lawyer-assistant default.
