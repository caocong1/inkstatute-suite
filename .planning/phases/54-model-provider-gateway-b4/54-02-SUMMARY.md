# Plan 54-02 Summary: Rate Limiting + Circuit Breakers + Fallback Chains + Tried-Provider Tracking

## Objective

Add per-tenant/provider rate limiting (RPM, TPM, concurrency), circuit breakers (CLOSED/OPEN/HALF_OPEN), and fallback chains with `tried_providers` tracking to the `ModelProviderGateway`. When a provider fails or its circuit breaker is open, the gateway falls back to the next provider in the configured fallback chain, tracking all tried providers in run metadata.

## Tasks Completed

### Task 1: RateLimiter — RPM/TPM/concurrency per tenant per provider

**Files created:**
- `packages/model-gateway/src/inkstatute_model_gateway/rate_limiter.py` — `RateLimitConfig` (rpm, tpm, max_concurrency) and `RateLimiter` class with:
  - Sliding-window RPM tracking via `collections.deque` of timestamps
  - Sliding-window TPM tracking via `collections.deque` of (timestamp, token_count) tuples
  - Concurrency limiting via `asyncio.Semaphore`
  - `asyncio.Lock` for safe concurrent state updates
  - 60-second window eviction on each check
  - No config → no limit (returns True)
- `packages/model-gateway/tests/test_rate_limiter.py` — 17 tests covering RPM under/over limit, window eviction, per-tenant/provider isolation, TPM under/over limit, concurrency, no-config skip, record_request

### Task 2: CircuitBreaker — CLOSED/OPEN/HALF_OPEN with cooldown

**Files created:**
- `packages/model-gateway/src/inkstatute_model_gateway/circuit_breaker.py` — `CircuitState` StrEnum (CLOSED, OPEN, HALF_OPEN), `CircuitBreakerConfig` (failure_threshold, cooldown_seconds), `CircuitBreaker` class with state transitions, `CircuitBreakerRegistry` for per-provider isolation
- `packages/model-gateway/tests/test_circuit_breaker.py` — 16 tests covering all state transitions, threshold tripping, cooldown, half-open success/failure, registry isolation

### Task 3: Integrate rate limiting, circuit breakers, and fallback chains into gateway

**Files modified:**
- `packages/model-gateway/src/inkstatute_model_gateway/config.py` — Added `rate_limit_configs` and `circuit_breaker_config` fields to `ModelProviderGatewayConfig`
- `packages/model-gateway/src/inkstatute_model_gateway/gateway.py` — Added `_submit_run_enabled()` method implementing the fallback chain:
  1. Build provider order: primary first, then fallback chain
  2. For each provider: check circuit breaker → check RPM → acquire concurrency → delegate → check result
  3. On success: record_success, record_request, return handle with `tried_providers` in metadata
  4. On failure: record_failure, continue to next provider
  5. All providers exhausted: return failed RunHandle with `model_gateway_all_providers_failed` error
- `packages/model-gateway/src/inkstatute_model_gateway/__init__.py` — Added exports for RateLimiter, RateLimitConfig, CircuitBreaker, CircuitBreakerConfig, CircuitBreakerRegistry, CircuitState
- `packages/model-gateway/tests/test_fallback.py` — 12 tests covering fallback on failure/circuit-open/exception, all-providers-fail, circuit breaker tripping and half-open recovery, rate limit skipping, disabled gateway no-fallback, tried_providers metadata

**Commit:** `955a06f` — `feat(54-02): rate limiting (RPM/TPM/concurrency), circuit breakers, fallback chains with tried_providers tracking`

## Test Results

- **model-gateway tests:** 61 tests pass (18 from Plan 01 + 17 rate limiter + 16 circuit breaker + 12 fallback)
  - `python3 -m unittest discover -s packages/model-gateway/tests -v` — OK

## Key Design Decisions

1. **Sliding-window deque** for RPM/TPM — entries older than 60 seconds are evicted on each check, providing accurate per-minute rate limiting without external dependencies.
2. **Circuit breaker states** — CLOSED (normal) → OPEN (tripped after N failures) → HALF_OPEN (after cooldown) → CLOSED (on success) or OPEN (on failure). Per-provider isolation via `CircuitBreakerRegistry`.
3. **Fallback chain** — Provider order is `[primary] + fallback_chain` (deduplicated). Each provider is tried in order; if circuit breaker is open or rate limit is exceeded, the provider is skipped (added to `tried_providers`) and the next is tried.
4. **tried_providers tracking** — List of `backend_id` strings stored in `RunHandle.metadata["tried_providers"]`, showing all providers attempted (including skipped ones).
5. **Disabled gateway bypass** — When `config.enabled` is `False`, `_submit_run_passthrough()` delegates directly with no rate limiting, circuit breaking, or fallback.
