---
phase: 69-runtime-registration-wiring
reviewed: 2026-07-10T04:45:22Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - services/qqbot-service/src/qqbot_service/wiring.py
  - services/qqbot-service/src/qqbot_service/__init__.py
  - services/qqbot-service/README.md
  - services/qqbot-service/tests/test_wiring_flag_config.py
  - services/qqbot-service/tests/test_runtime_registration.py
  - services/qqbot-service/tests/test_wiring_disabled_refuse.py
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
fix_recommended: true
---

# Phase 69: Code Review Report

**Reviewed:** 2026-07-10T04:45:22Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Phase 69 host wiring correctly implements the REG-01 flag→`QQBotChannelConfig.enabled` map, REG-02 explicit `channels=(adapter,)` DI (no platform-runtime qqbot imports), and HOST-03 disabled refuse (503 / deliver refused / Fake `call_count==0`). All Phase 69 suites pass with `FakeBackendAdapter` and Fake transports. Remaining issues are robustness gaps: the env auto-build path silently constructs `TokenManager` with the Urllib default, and `QQBotHostConfig.enabled` is decorative despite dual-knob documentation / ARCHITECTURE AND guidance.

`--fix` recommended for the two warnings before Phase 70 webhook composition hardens this factory as the production edge.

## Warnings

### WR-01: Env auto-build constructs TokenManager with Urllib default

**File:** `services/qqbot-service/src/qqbot_service/wiring.py:86-100`
**Issue:** When `qqbot_channel_enabled` is True, `transport` is provided, `token_manager` is omitted, and `env` resolves `app_id`/`app_secret`, the factory builds `TokenManager(app_id=..., client_secret=...)` without a `transport=` argument. `TokenManager.__init__` then defaults to `UrllibTokenTransport()` (`token_manager.py:128`). A caller that injects a Fake *message* transport for tests/dry-run while relying on env secret resolution will still open live token HTTP on first `get_token()`. There is no optional `token_transport` override on the factory (RESEARCH sketch had one). No unit test covers this branch.
**Fix:** Accept an optional `token_transport` and pass it explicitly; never rely on the Urllib default unless production intends live token IO. Prefer fail-closed when no token transport is supplied in non-production paths:

```python
# In build_qqbot_wired_runtime signature:
token_transport: object | None = None,
# ...
resolved_token_manager = TokenManager(
    app_id=app_id,
    client_secret=client_secret,
    transport=token_transport,  # require caller override; or:
    # transport=token_transport or UrllibTokenTransport(),  # only if documented production default
)
```

Also add a unit test that builds via `env=` + Fake message transport and asserts the token transport type (Fake when injected; never accidental Urllib in the Fake path).

### WR-02: Dual-knob incomplete — `host_config.enabled` cannot disable the channel

**File:** `services/qqbot-service/src/qqbot_service/wiring.py:52-53`
**Issue:** `build_qqbot_channel_config` sets `enabled=flags.qqbot_channel_enabled` only. `QQBotHostConfig.enabled=False` with platform flag True still yields `channel_config.enabled=True` and can become `live_io_ready` when transports are injected. README / CONTEXT describe “dual default-OFF knobs,” and `.planning/research/ARCHITECTURE.md` / RESEARCH Pattern 1 recommend fail-closed `flags and host.enabled`. Plan 01 accepted flag-only as the REG-01 minimum, so this is not a requirement miss — but `host_config.enabled` is now decorative and will confuse Phase 70 env loading (both knobs read the same env key today, but can diverge if constructed independently).
**Fix:** AND the knobs (and lock with a test):

```python
return QQBotChannelConfig(
    enabled=bool(flags.qqbot_channel_enabled and host_config.enabled),
    app_id_ref=host_config.app_id_ref,
    # ...
)
```

Update README to state the AND rule, and add `test_host_enabled_false_keeps_channel_disabled_even_if_flag_true`.

## Info

### IN-01: Misleading comment on TokenManager Urllib default

**File:** `services/qqbot-service/src/qqbot_service/wiring.py:95-96`
**Issue:** Comment says TokenManager “defaults to UrllibTokenTransport only when live secrets resolve.” The Urllib default is unconditional whenever `transport` is omitted; the host merely *constructs* TokenManager only after secrets resolve.
**Fix:** Rephrase to: “Construct TokenManager only after secrets resolve; omit `transport=` only for intentional production Urllib default.”

### IN-02: Enabled Fake deliver contrast does not assert transport invocation

**File:** `services/qqbot-service/tests/test_wiring_disabled_refuse.py:112-136`
**Issue:** Plan 03 intentionally allows accepted-or-gated refusal. The test asserts Fake type names but does not require `message_transport.call_count >= 1` when the passive window allows send. Today `received_at=2026-07-10T11:59:00Z` is still inside the 1h C2C window (verified live), so deliver succeeds — but a clock/fixture drift could leave the test green without exercising Fake send.
**Fix:** Freeze/inject a clock or set `received_at` relative to now; when `result.accepted`, assert `message_transport.call_count >= 1` (and optionally `token_transport.call_count >= 1`).

### IN-03: No unit coverage for env-based TokenManager construction

**File:** `services/qqbot-service/tests/test_wiring_flag_config.py` (missing case)
**Issue:** Live-ready tests always inject a pre-built `TokenManager`. The `env` + `resolve_secret_ref` branch in `wiring.py:87-100` is untested.
**Fix:** Add a test with Fake token transport override (after WR-01) or, until then, assert that env-built managers are live-ready only when both deps exist and document Urllib as production-only.

## What looks solid

- Flag OFF strips caller-supplied transports; HOST-03 proves 503 ACK, refused deliver, and zero Fake call counts.
- Explicit `channels=(adapter,)` + platform-runtime AST scan — no auto-discovery.
- Adapter never imports `RuntimeFeatureFlags` (AST proof).
- Secrets stay as refs on config; values resolve only into TokenManager locals.
- All reviewed suites use `FakeBackendAdapter`; no network classes in unit Fake paths that inject both deps.

---

_Reviewed: 2026-07-10T04:45:22Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
