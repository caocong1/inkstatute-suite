# Plan 54-03 Summary: Cost Tracking with Budget Ceilings + Integration Tests + V2 Gate Integration

## Objective

Add per-tenant/matter cost tracking with budget ceilings to the `ModelProviderGateway`. Token usage from provider responses is accumulated per tenant per matter, and when a budget ceiling is exceeded, further requests are rejected with a clear `model_gateway_budget_exceeded` error. Add comprehensive integration tests and integrate the new package into the V2 gate script.

## Tasks Completed

### Task 1: CostTracker — per-tenant/matter cost tracking with budget ceilings

**Files created:**
- `packages/model-gateway/src/inkstatute_model_gateway/cost_tracker.py` — `PricingRate` (input_token_cost, output_token_cost), `BudgetCeiling` (max_cost, scope), `CostTracker` class with:
  - `check_budget(tenant_id, matter_id)` → (within_budget, accumulated, ceiling)
  - `record_usage(tenant_id, matter_id, provider_id, usage)` → cost added
  - `get_accumulated(tenant_id, matter_id)` → accumulated cost
  - `_extract_tokens(usage)` handles input_tokens/prompt_tokens and output_tokens/completion_tokens
  - `asyncio.Lock` for safe concurrent access
  - No budget configured → always within_budget=True
  - No pricing configured → cost is 0.0
- `packages/model-gateway/tests/test_cost_tracker.py` — 12 tests covering cost calculation, accumulated persistence, budget within/exceeded, no-config, tenant_matter scope isolation, tenant_global scope, reset

### Task 2: Integrate cost tracking into ModelProviderGateway submit_run

**Files modified:**
- `packages/model-gateway/src/inkstatute_model_gateway/config.py` — Added `pricing` and `budgets` fields to `ModelProviderGatewayConfig`
- `packages/model-gateway/src/inkstatute_model_gateway/gateway.py` — Added budget check at the start of `_submit_run_enabled()`:
  1. Check budget before attempting any provider
  2. If budget exceeded → return failed RunHandle with `model_gateway_budget_exceeded` error immediately
  3. After successful submit_run → extract `provider_usage` from run metadata and call `cost_tracker.record_usage()`
  4. Budget check uses `tenant_id` from `req.tenant_id` and `matter_id` from `req.metadata.get("matter_id")`
- `packages/model-gateway/src/inkstatute_model_gateway/__init__.py` — Added exports for CostTracker, PricingRate, BudgetCeiling

### Task 3: Integration tests + V2 gate script integration

**Files created:**
- `packages/model-gateway/tests/test_integration.py` — 7 integration tests:
  - `test_full_flow_with_rate_limiting_fallback_and_cost_tracking` — two providers, A fails, B succeeds, cost recorded, tried_providers tracked
  - `test_budget_exceeded_rejects_request` — low budget, first request succeeds, second rejected with budget_exceeded
  - `test_disabled_gateway_fully_transparent` — enabled=False, no rate limiting/circuit breaking/cost tracking/fallback
  - `test_circuit_breaker_isolation` — provider A breaker open, B works independently
  - `test_concurrent_requests_thread_safe` — 5 concurrent requests don't corrupt state
  - `test_all_features_combined` — rate limiting + circuit breaker + fallback + cost tracking + budget ceiling
  - `test_budget_exceeded_no_fallback_attempted` — budget check before any provider tried

**Files modified:**
- `scripts/run_v2_gates.py` — Added `model_gateway_src` path variable, `model-gateway` test gate, `packages/model-gateway/src` to compileall gate, `model_gateway_src` to contract-test-suite PYTHONPATH
- `packages/contract-test-suite/tests/test_audit_v2_requirements.py` — Updated gate count assertion from 22 to 23, added `model-gateway` to gate name assertions

**Commit:** `2f2e084` — `feat(54-03): cost tracking with budget ceilings, integration tests, V2 gate integration`

## Test Results

- **model-gateway tests:** 80 tests pass (18 gateway + 17 rate limiter + 16 circuit breaker + 12 fallback + 12 cost tracker + 7 integration)
  - `python3 -m unittest discover -s packages/model-gateway/tests -v` — OK
- **V2 gates:** All 23 gates pass (exit 0)
  - `python3 scripts/run_v2_gates.py` — exit 0

## Key Design Decisions

1. **Budget check before provider attempt** — The budget is checked before any provider is tried, preventing wasted API calls when the budget is already exceeded. The `tried_providers` list is empty in this case.
2. **Cost from run metadata** — `_extract_usage_from_run(run)` extracts `provider_usage` from `run.metadata`, which is populated by the sub-adapter from the provider response.
3. **Budget key scoping** — `"{tenant_id}:{matter_id}"` for tenant_matter scope, `"{tenant_id}"` for tenant_global scope (matter_id=None).
4. **V2 gate integration** — Added `model-gateway` as a new test gate and `packages/model-gateway/src` to the compileall gate, ensuring the package is covered by CI.
5. **Gate count update** — Updated `test_v2_gates_includes_traceability_gate` from 22 to 23 gates, added `model-gateway` to the gate name assertions.
