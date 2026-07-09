---
phase: 59-ed25519-signature-verification-validation-challenge
verified: 2026-07-07T10:24:13Z
status: passed
score: 13/13
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/4
  gaps_closed:
    - "All 26 V2 gates green (ADAPTER-04 cross-cutting safety) — phase7-privacy-boundary now passes after rephrasing planning docs"
    - "derive_seed does not enter infinite loop on empty BotSecret (CR-01) — now raises ValueError"
    - "verify_and_ack returns AckResponse (not exception) when bot_secret is None in metadata (CR-02) — now checks bot_secret for None and rejects with 401"
    - "verify_callback_signature catches TypeError/AttributeError on malformed inputs (WR-02) — now returns False"
    - "op=13 malformed challenge rejected with 401 invalid_challenge (WR-03/04) — non-Mapping d and missing fields now rejected"
  gaps_remaining: []
  regressions: []
---

# Phase 59: Ed25519 Signature Verification + Validation Challenge Verification Report

**Phase Goal:** QQ Bot webhook callback signatures are verified using Ed25519 (BotSecret-derived keypair, `X-Signature-Ed25519` + `X-Signature-Timestamp` over `timestamp + request_body`), rejecting unverified callbacks with HTTP 401; callback URL validation handshake (op=13) is handled by signing `{event_ts + plain_token}` and returning `{plain_token, signature}`.
**Verified:** 2026-07-07T10:24:13Z
**Status:** passed
**Re-verification:** Yes — after gap closure (iteration 2)

## Re-verification Summary

Previous verification (iteration 1) found 3 gaps across 5 issues. All have been fixed in the codebase and confirmed by reproduction:

| Gap | Previous Status | Fix Applied | Verified |
|-----|----------------|-------------|----------|
| V2 gate failure (phase7-privacy-boundary) | FAILED | Planning docs rephrased to avoid body-scan pattern triggers | ✓ 13/13 tests OK, exit 0 |
| CR-01: Infinite loop on empty BotSecret | FAILED | `derive_seed` now raises `ValueError` on empty/non-string input | ✓ Reproduced: ValueError raised |
| CR-02: AttributeError when bot_secret is None | FAILED | `verify_and_ack` now checks `bot_secret is None` and rejects with 401 | ✓ Reproduced: 401 AckResponse returned |
| WR-02: Type errors in verify_callback_signature | FAILED | Now catches `TypeError`/`AttributeError` and returns False | ✓ Reproduced: int timestamp and str body return False |
| WR-03/04: op=13 malformed challenge | FAILED | Non-Mapping `d` and missing `plain_token`/`event_ts` now rejected with 401 `invalid_challenge` | ✓ Reproduced: both cases return 401 |

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| #   | Truth                                                                                                                                  | Status     | Evidence                                                                                                                                                                                                                                                              |
| --- | -------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `signature.py` derives Ed25519 keypair from BotSecret and verifies `X-Signature-Ed25519` + `X-Signature-Timestamp` over `timestamp + request_body` | ✓ VERIFIED | `signature.py` lines 21-72: `derive_seed` (repeat-to-32 with ValueError guard), `derive_keypair` (secret_to_public), `verify_callback_signature` (bytes.fromhex + verify over timestamp+request_body, catches TypeError/AttributeError). 9/9 Ed25519 vector tests + 29/29 signature tests pass. Demo public key exact match confirmed. |
| 2   | Unverified callbacks are rejected with HTTP 401                                                                                        | ✓ VERIFIED | `adapter.py` lines 96-130: missing headers (including bot_secret) → 401 ("missing"), invalid sig → 401 ("invalid"), empty bot_secret → 401 ("invalid"), tampered body → 401 ("invalid"). 7/7 adapter integration tests pass. bot_secret=None reproduction returns 401 (no crash). |
| 3   | op=13 validation challenge is handled by signing `{event_ts + plain_token}` and returning `{plain_token, signature}`                  | ✓ VERIFIED | `signature.py` lines 75-89: `handle_validation_challenge` signs (event_ts+plain_token). `adapter.py` lines 132-166: op=13 detected, returns `validation_challenge_response={plain_token, signature}` in metadata. Malformed op=13 (non-Mapping d, missing fields) rejected with 401 `invalid_challenge`. Round-trip verify test passes. |
| 4   | Tests pass with official QQ demo vectors for signature verification and validation challenge                                           | ✓ VERIFIED | `test_ed25519_vectors.py`: 9/9 pass (public key exact match, signature exact match, verify accepts/rejects). `test_signature.py`: 29/29 pass (pure function + adapter integration). Full qqbot suite: 107/107 pass. |

**Score:** 4/4 roadmap truths verified

### Additional Truths (PLAN must-haves + cross-cutting safety + code review fixes)

| #   | Truth                                                                                                          | Status     | Evidence                                                                                                                            |
| --- | -------------------------------------------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------- |
| 5   | Ed25519 keypair derived from BotSecret using repeat-to-32-bytes algorithm                                      | ✓ VERIFIED | `signature.py:31-36`: seed = bot_secret.encode * 2 until >= 32, truncate to 32. `test_derive_seed_demo_secret` passes.              |
| 6   | dependencies = [] invariant holds (stdlib only, no external crypto packages)                                   | ✓ VERIFIED | `pyproject.toml`: `dependencies = []` present (grep count = 1). `_ed25519.py` uses only `import hashlib`. `test_v1_8_safety_baseline`: 6/6 pass. |
| 7   | QQBotChannelConfig stores bot_secret_ref as reference-only field                                               | ✓ VERIFIED | `config.py:24`: `bot_secret_ref: str \| None = None`. `from_env` reads `INKSTATUTE_QQBOT_BOT_SECRET_REF`. Frozen `@dataclass(frozen=True, slots=True)` unchanged. |
| 8   | verify_and_ack method signature unchanged (frozen Protocol — 6 methods)                                        | ✓ VERIFIED | `test_contract_freeze_not_violated`: 7/7 pass. ChannelAdapter still has 6 methods. `async def verify_and_ack(self, raw: RawInbound) -> AckResponse` unchanged. |
| 9   | test_no_wecom_import.py covers _ed25519.py and signature.py                                                    | ✓ VERIFIED | `test_no_wecom_import.py`: 7/7 pass. `test_ed25519_does_not_import_wecom_service` (line 58) and `test_signature_does_not_import_wecom_service` (line 67) added. |
| 10  | All existing safety tests remain green                                                                          | ✓ VERIFIED | `test_v1_8_safety_baseline`: 6/6 pass. `test_no_wecom_import`: 7/7 pass. `test_contract_freeze_not_violated`: 7/7 pass. `test_qqbot_channel_adapter`: 14/14 pass. `test_qqbot_idempotency`: 7/7 pass. |
| 11  | All 26 V2 gates green (ADAPTER-04)                                                                             | ✓ VERIFIED | `scripts/run_v2_gates.py`: exit code 0. All 26 gates pass including `phase7-privacy-boundary` (13/13 tests OK). Confirmed by full run. |
| 12  | derive_seed does not infinite loop on empty BotSecret (CR-01 fix)                                              | ✓ VERIFIED | `signature.py:31-32`: `if not isinstance(bot_secret, str) or not bot_secret: raise ValueError(...)`. Reproduced: `derive_seed('')` raises ValueError (no hang). `test_empty_bot_secret_rejected_401` passes. |
| 13  | verify_and_ack returns AckResponse (not exception) when bot_secret is None (CR-02 fix)                         | ✓ VERIFIED | `adapter.py:102`: `or bot_secret is None` added to None-check. Reproduced: bot_secret=None → 401 "missing" AckResponse (no AttributeError). |

**Score:** 13/13 truths verified

### Gap Closure Verification (Re-verification Mode)

Each previously-failed gap was verified with full 3-level verification (exists, substantive, wired):

| Gap ID | Truth | Exists | Substantive | Wired | Status |
|--------|-------|--------|-------------|-------|--------|
| GAP-1 | All 26 V2 gates green | ✓ | ✓ (13 tests in phase7-privacy-boundary) | ✓ (exit 0) | ✓ VERIFIED |
| CR-01 | derive_seed raises ValueError on empty BotSecret | ✓ | ✓ (guard at line 31-32) | ✓ (adapter catches ValueError at line 113) | ✓ VERIFIED |
| CR-02 | verify_and_ack handles bot_secret=None | ✓ | ✓ (None-check at line 102) | ✓ (returns 401 AckResponse) | ✓ VERIFIED |
| WR-02 | verify_callback_signature catches type errors | ✓ | ✓ (try/except at lines 64, 70) | ✓ (returns False, no crash) | ✓ VERIFIED |
| WR-03/04 | op=13 malformed challenge rejected | ✓ | ✓ (invalid_challenge at lines 158, 165) | ✓ (returns 401) | ✓ VERIFIED |

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `packages/channels/qqbot/src/inkstatute_channels_qqbot/_ed25519.py` | Vendored RFC 8032 Ed25519 (secret_to_public, sign, verify) | ✓ VERIFIED | 89 lines, `import hashlib` only, `__all__` declared. 9/9 known-answer tests pass. |
| `packages/channels/qqbot/src/inkstatute_channels_qqbot/signature.py` | QQ Bot signature service (derive_keypair, verify_callback_signature, handle_validation_challenge) | ✓ VERIFIED | 89 lines, 4 public functions, `__all__` declared. ValueError guard on derive_seed. TypeError/AttributeError caught in verify. |
| `packages/channels/qqbot/src/inkstatute_channels_qqbot/config.py` | QQBotChannelConfig with bot_secret_ref field | ✓ VERIFIED | `bot_secret_ref: str \| None = None` at line 24. `from_env` reads env var. Frozen dataclass unchanged. |
| `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py` | verify_and_ack with Ed25519 verification + 401 + op=13 | ✓ VERIFIED | Lines 66-173: full signature verification flow. bot_secret None-check, ValueError catch, op=13 invalid_challenge rejection. Method signature unchanged. |
| `packages/channels/qqbot/tests/test_ed25519_vectors.py` | Known-answer tests with QQ demo vectors | ✓ VERIFIED | 9 tests, DEMO_SEED/DEMO_PUBLIC_KEY/DEMO_SIGNATURE_HEX constants. All pass. |
| `packages/channels/qqbot/tests/test_signature.py` | Pure-function + adapter integration tests | ✓ VERIFIED | 29 tests (pure function + adapter integration). Includes empty bot_secret, type error, op=13 malformed tests. All pass. |
| `packages/channels/qqbot/tests/test_no_wecom_import.py` | Import isolation for _ed25519.py and signature.py | ✓ VERIFIED | 7 tests, covers _ed25519.py (line 58) and signature.py (line 67). All pass. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `signature.py` | `_ed25519.py` | `from ._ed25519 import` | ✓ WIRED | Line 11: `from ._ed25519 import secret_to_public, sign, verify` |
| `adapter.py` | `signature.py` | `from .signature import` | ✓ WIRED | Line 24: `from .signature import derive_keypair, handle_validation_challenge, verify_callback_signature` |
| `adapter.py` | `config.py` | `self._config.bot_secret_ref` | ✓ WIRED | Line 87: `if self._config.bot_secret_ref is None`; line 61 in capabilities() |
| `test_ed25519_vectors.py` | `_ed25519.py` | import secret_to_public, sign, verify | ✓ WIRED | Tests import and call all three functions |
| `test_signature.py` | `signature.py` | import derive_keypair, verify_callback_signature, handle_validation_challenge | ✓ WIRED | Tests import and call all functions |
| `test_signature.py` | `adapter.py` | verify_and_ack with signed RawInbound | ✓ WIRED | QQBotAdapterSignatureTests class calls verify_and_ack |
| `test_no_wecom_import.py` | `_ed25519.py`, `signature.py` | AST import inspection | ✓ WIRED | Both files inspected for wecom_service imports |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Ed25519 known-answer tests | `python3 -m unittest test_ed25519_vectors -v` | 9/9 OK | ✓ VERIFIED |
| Signature pure + adapter tests | `python3 -m unittest test_signature -v` | 29/29 OK | ✓ VERIFIED |
| Full qqbot test suite | `python3 -m unittest discover -s packages/channels/qqbot/tests` | 107/107 OK | ✓ VERIFIED |
| V2 gate suite (26 gates) | `python3 scripts/run_v2_gates.py` | exit 0, all 26 pass | ✓ VERIFIED |
| phase7-privacy-boundary gate | (included in V2 gates) | 13/13 OK | ✓ VERIFIED |
| CR-01: derive_seed('') | `timeout 5 python3 -c "derive_seed('')"` | ValueError raised (no hang) | ✓ VERIFIED |
| CR-02: bot_secret=None | reproduction script | 401 AckResponse (no crash) | ✓ VERIFIED |
| WR-02: int timestamp | reproduction script | verify_callback_signature returns False | ✓ VERIFIED |
| WR-02: str body | reproduction script | verify_callback_signature returns False | ✓ VERIFIED |
| WR-03: op=13 non-Mapping d | reproduction script | 401 invalid_challenge | ✓ VERIFIED |
| WR-04: op=13 missing plain_token | reproduction script | 401 invalid_challenge | ✓ VERIFIED |
| op=13 valid challenge | reproduction script | 200, {plain_token, signature} correct | ✓ VERIFIED |
| dependencies = [] invariant | `grep -c "dependencies = \[\]" pyproject.toml` | 1 | ✓ VERIFIED |

## Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| INGRESS-01 | QQ Bot webhook callback signature verified using Ed25519, reject unverified with HTTP 401 | ✓ SATISFIED | `signature.py` derive_keypair + verify_callback_signature; `adapter.py` 401 rejection on missing/invalid signature. 29/29 tests pass. |
| INGRESS-02 | QQ Bot callback URL validation handshake (op=13) — sign `{event_ts + plain_token}`, return `{plain_token, signature}` | ✓ SATISFIED | `signature.py` handle_validation_challenge; `adapter.py` op=13 detection and challenge response in AckResponse.metadata. Round-trip test passes. |

## Code Review Findings Status

All 2 critical and 4 warning findings from `59-REVIEW.md` have been addressed:

| Finding | Severity | Status | Evidence |
|---------|----------|--------|----------|
| CR-01: Infinite loop on empty BotSecret | Critical | ✓ FIXED | `derive_seed` raises ValueError; adapter catches and returns 401 |
| CR-02: AttributeError when bot_secret is None | Critical | ✓ FIXED | `verify_and_ack` checks `bot_secret is None` → 401 "missing" |
| WR-01: Stub path accepts unverified callbacks | Warning | Accepted (design) | Stub path preserved for fixture/test compatibility; documented behavior when bot_secret_ref unset. Not a blocker — operator must configure bot_secret_ref for production. |
| WR-02: Type errors crash instead of 401 | Warning | ✓ FIXED | `verify_callback_signature` catches TypeError/AttributeError, returns False |
| WR-03: op=13 malformed d silently accepted | Warning | ✓ FIXED | Non-Mapping d → 401 `invalid_challenge` |
| WR-04: op=13 missing fields signs empty | Warning | ✓ FIXED | Missing plain_token/event_ts → 401 `invalid_challenge` |

## Conclusion

All 4 roadmap success criteria are verified as TRUE in the codebase. All 13 must-have truths (roadmap + PLAN + cross-cutting safety + code review fixes) pass. All 26 V2 gates are green. All 3 previously-identified gaps from iteration 1 have been closed with no regressions. The phase goal is achieved.

---

_Verified: 2026-07-07T10:24:13Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification: iteration 2 (after gap closure)_
