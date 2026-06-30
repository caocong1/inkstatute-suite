---
phase: 12-channel-interface-wecom-wrapper-web-sse-client-sdk
status: ready
nyquist_compliant: true
created: 2026-06-29
---

# Phase 12 Validation Plan

## Framework

Use stdlib Python `unittest` and source/fixture scans. Do not add runtime services or network dependencies unless a later plan explicitly changes scope.

## Quick Checks

- `python -m compileall packages/channels apps/platform_api packages/contract-test-suite/tests`
- `PYTHONPATH=packages/platform-runtime/src:packages/platform-contract/src:services/wecom-service/src:packages/channels/wecom/src python -m unittest packages/channels/wecom/tests/test_wecom_channel_adapter.py`
- `PYTHONPATH=packages/platform-runtime/src:packages/platform-contract/src:packages/channels/web_sse/src python -m unittest packages/channels/web_sse/tests/test_web_sse_channel.py`
- `PYTHONPATH=apps/platform_api/src:packages/platform-runtime/src:packages/platform-contract/src:packages/platform-sdk-ts python -m unittest apps/platform_api/tests/test_platform_api.py`

## Full Checks

- `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src:packages/channels/wecom/src:packages/channels/web_sse/src:apps/platform_api/src python packages/contract-test-suite/scripts/run_contract_tests.py`
- `python - <<'PY'` boundary scans for channel packages not importing `inkstatute_backends_hermes`, `BackendAdapter`, or concrete backend modules.
- Privacy scan of Phase 12 fixtures.

## Acceptance Mapping

| Plan | Primary checks |
|---|---|
| 12-01 | WeCom wrapper unit tests, existing WeCom service tests, channel/backend boundary scan |
| 12-02 | Web/SSE channel unit tests, multichannel fixture/privacy tests |
| 12-03 | Platform API handler tests, OpenAPI validity, SDK deterministic generation |
| 12-04 | Web chat render tests, contract-suite Phase 12 fixture test, full runner |

