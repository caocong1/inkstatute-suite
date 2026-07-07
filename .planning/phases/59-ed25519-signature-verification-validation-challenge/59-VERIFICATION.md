---
phase: 59-ed25519-signature-verification-validation-challenge
verified: 2026-07-07T17:55:00Z
status: gaps_found
score: 4/4
overrides_applied: 0
gaps:
  - truth: "All 26 V2 gates green (ADAPTER-04 cross-cutting safety)"
    status: failed
    reason: "phase7-privacy-boundary gate fails — 59-REVIEW.md contains 'request_body' in code examples (lines 167, 172, 192) which triggers the body-scan privacy pattern in data scan mode. SUMMARY 02 claims '26/26 gates green' but actual run shows 22/23 gates passing with 1 failure."
    artifacts:
      - path: ".planning/phases/59-ed25519-signature-verification-validation-challenge/59-REVIEW.md"
        issue: "Lines 167, 172, 192 contain 'request_body' in code examples, triggering privacy scan body-scan pattern. Implementation source files are clean (0 issues in source mode)."
    missing:
      - "Rephrase 59-REVIEW.md to use 'request_body' instead of 'request_body' in code examples, matching the convention used in PLAN files"
  - truth: "derive_seed does not enter infinite loop on empty BotSecret (CR-01)"
    status: failed
    reason: "derive_seed('') enters an infinite loop because b'' * 2 == b'' — the while len(seed) < 32 loop never exits. Confirmed by reproduction: timeout 3 python3 -c \"derive_seed('')\" exits with code 124 (timeout killed). This is a DoS vulnerability via misconfiguration."
    artifacts:
      - path: "packages/channels/qqbot/src/inkstatute_channels_qqbot/signature.py"
        issue: "Lines 28-31: while len(seed) < 32 loop with empty byte string never terminates"
    missing:
      - "Add guard: if not bot_secret: raise ValueError('bot_secret must be a non-empty string') at start of derive_seed"
  - truth: "verify_and_ack returns AckResponse (not exception) when bot_secret is None in metadata (CR-02)"
    status: failed
    reason: "When bot_secret_ref is configured but runtime fails to inject bot_secret into raw.metadata, verify_and_ack calls derive_keypair(None) → derive_seed(None) → None.encode('utf-8') → AttributeError. Method contract violated — caller receives exception instead of AckResponse. Confirmed by reproduction."
    artifacts:
      - path: "packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py"
        issue: "Lines 96-102: None-check validates sig_hex, timestamp, request_body but NOT bot_secret. derive_keypair(bot_secret) at line 111 crashes when bot_secret is None."
    missing:
      - "Add bot_secret to the None-check at line 102: 'or bot_secret is None' → return 401 with signature_status='missing'"
---

# Phase 59: Ed25519 Signature Verification + Validation Challenge Verification Report

**Phase Goal:** QQ Bot webhook callback signatures are verified using Ed25519 (BotSecret-derived keypair, `X-Signature-Ed25519` + `X-Signature-Timestamp` over `timestamp + request_body`), rejecting unverified callbacks with HTTP 401; callback URL validation handshake (op=13) is handled by signing `{event_ts + plain_token}` and returning `{plain_token, signature}`.
**Verified:** 2026-07-07T17:55:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth                                                                                                                                  | Status     | Evidence                                                                                                                                                                                                                                                              |
| --- | -------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `signature.py` derives Ed25519 keypair from BotSecret and verifies `X-Signature-Ed25519` + `X-Signature-Timestamp` over `timestamp + request_body` | ✓ VERIFIED | `signature.py` lines 21-64: `derive_seed` (repeat-to-32), `derive_keypair` (secret_to_public), `verify_callback_signature` (bytes.fromhex + verify over timestamp+request_body). 9/9 Ed25519 vector tests + 21/21 signature tests pass. Demo public key exact match confirmed. |
| 2   | Unverified callbacks are rejected with HTTP 401                                                                                        | ✓ VERIFIED | `adapter.py` lines 101-121: missing headers → 401 ("missing"), invalid sig → 401 ("invalid"), tampered body → 401 ("invalid"). 7/7 adapter integration tests pass. (Warning: CR-02 edge case — bot_secret=None crashes instead of 401, see Gaps)                     |
| 3   | op=13 validation challenge is handled by signing `{event_ts + plain_token}` and returning `{plain_token, signature}`                  | ✓ VERIFIED | `signature.py` lines 67-81: `handle_validation_challenge` signs (event_ts+plain_token). `adapter.py` lines 124-141: op=13 detected, returns `validation_challenge_response={plain_token, signature}` in metadata. Round-trip verify test passes.                       |
| 4   | Tests pass with official QQ demo vectors for signature verification and validation challenge                                           | ✓ VERIFIED | `test_ed25519_vectors.py`: 9/9 pass (public key exact match, signature exact match, verify accepts/rejects). `test_signature.py`: 21/21 pass (pure function + adapter integration). Full qqbot suite: 99/99 pass.                                                       |

**Score:** 4/4 truths verified

### Additional Truths (PLAN must-haves + cross-cutting safety)

| #   | Truth                                                                                                          | Status     | Evidence                                                                                                                            |
| --- | -------------------------------------------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------- |
| 5   | Ed25519 keypair derived from BotSecret using repeat-to-32-bytes algorithm                                      | ✓ VERIFIED | `signature.py:28-31`: seed = bot_secret.encode * 2 until >= 32, truncate to 32. `test_derive_seed_demo_secret` passes.              |
| 6   | dependencies = [] invariant holds (stdlib only, no external crypto packages)                                   | ✓ VERIFIED | `pyproject.toml`: `dependencies = []` present. `_ed25519.py` uses only `import hashlib`. `test_qqbot_pyproject_has_empty_dependencies` passes. |
| 7   | QQBotChannelConfig stores bot_secret_ref as reference-only field                                               | ✓ VERIFIED | `config.py:24`: `bot_secret_ref: str \| None = None`. `from_env` reads `INKSTATUTE_QQBOT_BOT_SECRET_REF`. Frozen dataclass unchanged.  |
| 8   | verify_and_ack method signature unchanged (frozen Protocol — 6 methods)                                        | ✓ VERIFIED | `test_contract_freeze_not_violated`: 7/7 pass. ChannelAdapter still has 6 methods.                                                  |
| 9   | test_no_wecom_import.py covers _ed25519.py and signature.py                                                    | ✓ VERIFIED | `test_no_wecom_import.py`: 7/7 pass. `test_ed25519_does_not_import_wecom_service` and `test_signature_does_not_import_wecom_service` added. |
| 10  | All existing safety tests remain green                                                                          | ✓ VERIFIED | `test_v1_8_safety_baseline`: 6/6 pass. `test_no_wecom_import`: 7/7 pass. `test_contract_freeze_not_violated`: 7/7 pass.            |
| 11  | All 26 V2 gates green (ADAPTER-04)                                                                             | ✗ FAILED   | `scripts/run_v2_gates.py`: 22/23 gates pass. `phase7-privacy-boundary` FAILS — 59-REVIEW.md lines 167/172/192 contain `request_body` triggering body-scan privacy pattern. SUMMARY 02 claim "26/26 gates green" is FALSE. |
| 12  | derive_seed does not infinite loop on empty BotSecret (CR-01)                                                  | ✗ FAILED   | `derive_seed('')` → infinite loop. Confirmed: `timeout 3 python3 -c "derive_seed('')"` exits code 124.                              |
| 13  | verify_and_ack returns AckResponse (not exception) when bot_secret is None (CR-02)                             | ✗ FAILED   | `derive_keypair(None)` → `AttributeError: 'NoneType' object has no attribute 'encode'`. Method contract violated. Confirmed by reproduction. |

### Required Artifacts

| Artifact                                                                                     | Expected                                                                    | Status     | Details                                                                                                          |
| -------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------- |
| `packages/channels/qqbot/src/inkstatute_channels_qqbot/_ed25519.py`                          | RFC 8032 Ed25519 (secret_to_public, sign, verify)                           | ✓ VERIFIED | 109 lines, hashlib only, `__all__` declared. All 9 known-answer tests pass against official QQ demo vectors.     |
| `packages/channels/qqbot/src/inkstatute_channels_qqbot/signature.py`                         | derive_keypair, verify_callback_signature, handle_validation_challenge      | ✓ VERIFIED | 81 lines, imports from `._ed25519` only. 4 public functions. All unit tests pass. (Warning: CR-01 infinite loop) |
| `packages/channels/qqbot/tests/test_ed25519_vectors.py`                                      | Known-answer tests with QQ demo vectors                                     | ✓ VERIFIED | 101 lines, 9 tests, DEMO_PUBLIC_KEY/DEMO_SIGNATURE_HEX constants. 9/9 pass.                                      |
| `packages/channels/qqbot/tests/test_signature.py`                                            | Pure function + adapter integration tests                                   | ✓ VERIFIED | 309 lines, 21 tests (14 pure + 7 adapter). 21/21 pass.                                                           |
| `packages/channels/qqbot/src/inkstatute_channels_qqbot/config.py`                            | QQBotChannelConfig with bot_secret_ref field                                | ✓ VERIFIED | `bot_secret_ref: str \| None = None` added. `from_env` reads env var. Frozen dataclass unchanged.                |
| `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`                           | verify_and_ack with Ed25519 verification + 401 + op=13 challenge            | ✓ VERIFIED | Import from `.signature` added. verify_and_ack rewritten with sig verification. 6 Protocol methods preserved. (Warning: CR-02) |
| `packages/channels/qqbot/tests/test_no_wecom_import.py`                                      | Import isolation for _ed25519.py and signature.py                           | ✓ VERIFIED | 2 new test methods added. 7/7 pass.                                                                               |

### Key Link Verification

| From                                                                         | To                                                                           | Via                                                                  | Status     | Details                                              |
| ---------------------------------------------------------------------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------- | ---------- | --------------------------------------------------- |
| `signature.py`                                                               | `_ed25519.py`                                                                | `from ._ed25519 import secret_to_public, sign, verify`               | ✓ WIRED    | Line 11: relative import. All functions used.        |
| `adapter.py`                                                                 | `signature.py`                                                               | `from .signature import derive_keypair, handle_validation_challenge, verify_callback_signature` | ✓ WIRED | Lines 24-28: all 3 functions imported and called.    |
| `adapter.py`                                                                 | `config.py`                                                                  | `self._config.bot_secret_ref`                                        | ✓ WIRED    | Line 87: bot_secret_ref checked. Lines 61, 220: capabilities/health. |
| `test_ed25519_vectors.py`                                                    | `_ed25519.py`                                                                | `from inkstatute_channels_qqbot._ed25519 import secret_to_public, sign, verify` | ✓ WIRED | Line 13: import. All 3 functions tested.             |
| `test_signature.py`                                                          | `signature.py`                                                               | `from inkstatute_channels_qqbot.signature import ...`               | ✓ WIRED    | Lines 16-21: import. All 4 functions tested.         |
| `test_signature.py`                                                          | `adapter.py`                                                                 | `QQBotChannelAdapter.verify_and_ack`                                 | ✓ WIRED    | Lines 204-306: 7 adapter integration tests.         |

### Behavioral Spot-Checks

| Behavior                                                              | Command                                                                                              | Result   | Status     |
| --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | -------- | ---------- |
| Ed25519 known-answer tests (QQ demo vectors)                          | `python3 -m unittest test_ed25519_vectors -v`                                                        | 9/9 OK   | ✓ VERIFIED |
| Signature module unit tests                                           | `python3 -m unittest test_signature -v`                                                              | 21/21 OK | ✓ VERIFIED |
| Import isolation (no wecom_service)                                   | `python3 -m unittest test_no_wecom_import -v`                                                        | 7/7 OK   | ✓ VERIFIED |
| Contract freeze (6 Protocol methods)                                  | `python3 -m unittest test_contract_freeze_not_violated -v`                                           | 7/7 OK   | ✓ VERIFIED |
| Safety baseline (dependencies=[], flag default-off)                   | `python3 -m unittest test_v1_8_safety_baseline -v`                                                   | 6/6 OK   | ✓ VERIFIED |
| Existing adapter tests (no regressions)                               | `python3 -m unittest test_qqbot_channel_adapter -v`                                                  | 14/14 OK | ✓ VERIFIED |
| Existing idempotency tests (no regressions)                           | `python3 -m unittest test_qqbot_idempotency -v`                                                      | 7/7 OK   | ✓ VERIFIED |
| Full qqbot test suite                                                 | `python3 -m unittest discover -s packages/channels/qqbot/tests`                                      | 99/99 OK | ✓ VERIFIED |
| dependencies = [] invariant                                           | `grep -c "dependencies = \[\]" packages/channels/qqbot/pyproject.toml`                               | 1        | ✓ VERIFIED |
| V2 gates (ADAPTER-04)                                                 | `python3 scripts/run_v2_gates.py`                                                                    | 22/23 OK, 1 FAIL | ✗ FAILED |
| CR-01: derive_seed('') infinite loop                                  | `timeout 3 python3 -c "from inkstatute_channels_qqbot.signature import derive_seed; derive_seed('')"` | exit 124 (timeout) | ✗ FAILED |
| CR-02: verify_and_ack with bot_secret=None                            | `asyncio.run(adapter.verify_and_ack(raw_without_bot_secret))`                                        | AttributeError: 'NoneType' | ✗ FAILED |

### Probe Execution

| Probe                                                                 | Command                                                                                                                                  | Result   | Status     |
| --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | -------- | ---------- |
| Source privacy scan (implementation files)                            | `scan_privacy_targets([src_files], mode='source')`                                                                                       | 0 issues | ✓ VERIFIED |
| Data privacy scan (59-REVIEW.md)                                      | `scan_privacy_targets(['59-REVIEW.md'], mode='data')`                                                                                    | 3 issues | ✗ FAILED   |

### Requirements Coverage

| Requirement | Source Plan  | Description                                                                                          | Status     | Evidence                                                                                     |
| ----------- | ------------ | ---------------------------------------------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------- |
| INGRESS-01  | 59-01, 59-02 | Ed25519 signature verification over timestamp+request_body, reject unverified with HTTP 401              | ✓ VERIFIED | signature.py + adapter.py verify_and_ack. 401 for missing/invalid/tampered. Tests pass.      |
| INGRESS-02  | 59-01, 59-02 | op=13 validation challenge: sign {event_ts + plain_token}, return {plain_token, signature}           | ✓ VERIFIED | handle_validation_challenge + adapter op=13 detection. Round-trip verify test passes.        |

### Anti-Patterns Found

| File                                                                                      | Line | Pattern                                                                                                  | Severity | Impact                                                                                                  |
| ----------------------------------------------------------------------------------------- | ---- | -------------------------------------------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------- |
| `packages/channels/qqbot/src/inkstatute_channels_qqbot/signature.py`                      | 28-31 | Infinite loop on empty input (derive_seed('') never terminates)                                          | BLOCKER  | DoS via misconfiguration — empty BotSecret hangs callback handler indefinitely                          |
| `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`                        | 96-102 | Missing None-check for bot_secret before derive_keypair call                                             | BLOCKER  | AttributeError crash when runtime fails to inject bot_secret — method contract violated, ingress crashes |
| `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`                        | 87-93 | Stub path accepts unverified callbacks (accepted=True, 200) when bot_secret_ref is None                  | WARNING  | Misconfiguration-to-security-bypass: enabling channel without bot_secret_ref silently disables sig gate |
| `.planning/phases/59-.../59-REVIEW.md`                                                    | 167,172,192 | `request_body` in code examples triggers privacy scan body-scan pattern                                  | WARNING  | V2 gate phase7-privacy-boundary fails — ADAPTER-04 cross-cutting safety not met                         |

### Human Verification Required

None — all Phase 59 success criteria are verifiable programmatically and have been verified through test execution and code inspection.

### Gaps Summary

**All 4 ROADMAP success criteria are VERIFIED.** The core phase goal — Ed25519 signature verification, 401 rejection, and op=13 validation challenge — is achieved and confirmed by 99/99 passing qqbot tests including official QQ demo vector known-answer tests.

**However, 3 gaps prevent a clean pass:**

1. **V2 gate failure (ADAPTER-04):** The `phase7-privacy-boundary` gate fails because `59-REVIEW.md` (a code review artifact created after the phase was completed) contains `request_body` in code examples at lines 167, 172, and 192, triggering the body-scan privacy pattern in data scan mode. The implementation source files are clean (0 issues in source mode). The PLAN files were already rephrased to use `request_body` instead of `request_body`, but the REVIEW.md was not. **SUMMARY 02's claim of "26/26 gates green" is FALSE** — actual run shows 22/23 gates passing. Fix: rephrase 59-REVIEW.md to use `request_body` instead of `request_body`.

2. **CR-01: Infinite loop on empty BotSecret:** `derive_seed("")` enters an infinite loop because `b"" * 2 == b""` — the `while len(seed) < 32` loop never exits. Confirmed by reproduction (timeout exit code 124). This is a DoS vulnerability via misconfiguration. Fix: add `if not bot_secret: raise ValueError(...)` guard at the start of `derive_seed`.

3. **CR-02: AttributeError when bot_secret is None:** When `bot_secret_ref` is configured but the runtime fails to inject `bot_secret` into `raw.metadata`, `verify_and_ack` calls `derive_keypair(None)` → `AttributeError: 'NoneType' object has no attribute 'encode'`. The method contract (`async def verify_and_ack(...) -> AckResponse`) is violated — the caller receives an exception instead of an `AckResponse`. Confirmed by reproduction. Fix: add `bot_secret` to the None-check at adapter.py line 102.

**Additional warning (WR-01):** The stub path at adapter.py lines 87-93 accepts unverified callbacks (`accepted=True, status_code=200`) when `bot_secret_ref` is None but the channel is enabled. This is a misconfiguration-to-security-bypass: an operator who enables the channel but forgets to set `bot_secret_ref` silently disables signature verification. The threat model (T-59-09) claims "no path to normalize_inbound without verified signature" — this stub path violates that claim.

---

_Verified: 2026-07-07T17:55:00Z_
_Verifier: Claude (gsd-verifier)_
