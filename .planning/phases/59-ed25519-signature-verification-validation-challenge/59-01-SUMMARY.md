---
phase: 59-ed25519-signature-verification-validation-challenge
plan: 01
wave: 1
status: complete
requirements:
  - INGRESS-01
  - INGRESS-02
started: 2026-07-07T08:45:41Z
completed: 2026-07-07T08:50:00Z
commits:
  - 2b46711: "feat(59-01): vendored RFC 8032 Ed25519 + known-answer tests against QQ demo vectors"
  - 51a36d9: "feat(59-01): QQ Bot signature module + pure-function unit tests"
  - ff8fc57: "docs(59): commit research, patterns, and plan-check artifacts"
---

# Phase 59 Plan 01 — Summary

## Objective

Create the vendored Ed25519 crypto module and QQ Bot signature service with unit tests verified against official QQ demo vectors. Python stdlib has no Ed25519 support, and the `dependencies = []` invariant forbids adding `cryptography` or `pynacl`. Vendoring the RFC 8032 Section 6.1 pure-Python reference (~80 lines, `hashlib.sha512` only) preserves the invariant while providing the Ed25519 sign/verify primitives.

## Tasks Completed

### Task 1: Create vendored _ed25519.py + known-answer test_ed25519_vectors.py

**Commit:** 2b46711

**Files created:**
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/_ed25519.py` — RFC 8032 Section 6.1 reference implementation copied verbatim (pure Python, `hashlib.sha512` only, stdlib). Public functions: `secret_to_public(seed) -> bytes`, `sign(seed, msg) -> bytes`, `verify(public, msg, signature) -> bool`. Internal module (underscore prefix), `__all__` declared.
- `packages/channels/qqbot/tests/test_ed25519_vectors.py` — 9 known-answer tests against official QQ demo vectors.

**Test results:** 9/9 tests pass
- `secret_to_public(DEMO_SEED)` produces exactly `DEMO_PUBLIC_KEY` (32 bytes exact match)
- `sign(DEMO_SEED, timestamp+body)` produces exactly `DEMO_SIGNATURE_HEX` (128 hex chars / 64 bytes)
- `verify` accepts demo signature, rejects tampered message, wrong public key, corrupted signature, wrong signature length
- Round-trip: sign → verify → True for arbitrary message

### Task 2: Create signature.py + test_signature.py

**Commit:** 51a36d9

**Files created:**
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/signature.py` — QQ Bot signature service with 4 public functions:
  - `derive_seed(bot_secret) -> bytes` — repeat-to-32-bytes algorithm
  - `derive_keypair(bot_secret) -> tuple[bytes, bytes]` — returns (public_key, seed)
  - `verify_callback_signature(public_key, signature_hex, timestamp, request_body) -> bool` — verifies X-Signature-Ed25519 over timestamp+request_body; returns False (never raises) on invalid hex/wrong length
  - `handle_validation_challenge(bot_secret, plain_token, event_ts) -> dict[str, str]` — signs event_ts+plain_token for op=13, returns {plain_token, signature}
- `packages/channels/qqbot/tests/test_signature.py` — 14 unit tests covering all behaviors + edge cases.

**Test results:** 14/14 tests pass
- Key derivation matches official QQ demo public key
- Callback verify accepts valid demo signature, rejects invalid hex, wrong length, tampered body
- Challenge round-trip: sign → verify → True; tampered → False
- Edge cases: short BotSecret (< 32 bytes), long BotSecret (>= 32 bytes), empty body

## Verification Results

### Plan-specified verification (5 commands, all pass)

| # | Command | Result |
|---|---------|--------|
| 1 | `python3 -m unittest test_ed25519_vectors -v` | 9/9 OK |
| 2 | `python3 -m unittest test_signature -v` | 14/14 OK |
| 3 | `python3 -m unittest test_v1_8_safety_baseline -v` | 6/6 OK (dependencies = [] holds) |
| 4 | `python3 -m unittest test_no_wecom_import -v` | 5/5 OK (no wecom_service import) |
| 5 | `grep -c "dependencies = \[\]" pyproject.toml` | 1 (invariant text present) |

### Full qqbot test suite

90/90 tests pass (all existing tests + 23 new tests).

### Full V2 gate suite (`scripts/run_v2_gates.py`)

22/23 gates pass. The only failure is `phase7-privacy-boundary` — a **pre-existing** issue caused by planning docs (`.planning/phases/59-*/59-01-PLAN.md`, `59-02-PLAN.md`, `59-RESEARCH.md`, `59-PATTERNS.md`) containing body-related parameter names, which triggers the `the-body-scan` privacy pattern (the body-scan privacy pattern) in data scan mode. This failure exists before and independent of the implementation code — the source `.py` files are not in the data scan paths. Confirmed pre-existing by checking out the state before implementation commits.

## Success Criteria

- [x] _ed25519.py provides secret_to_public, sign, verify using only hashlib.sha512 (stdlib)
- [x] signature.py provides derive_keypair, verify_callback_signature, handle_validation_challenge
- [x] Official QQ demo vectors for public key derivation and signature verification produce exact matches
- [x] Validation challenge round-trip (sign → verify) succeeds
- [x] Edge cases (short/long BotSecret, empty body, invalid hex, wrong length) handled correctly
- [x] dependencies = [] invariant unchanged
- [x] No wecom_service import in new files

## Threat Model Mitigations

| Threat ID | Category | Mitigation | Status |
|-----------|----------|------------|--------|
| T-59-01 | Spoofing | Ed25519 signature verification rejects forged callbacks | ✅ mitigated |
| T-59-02 | Tampering | Signature covers exact request_body bytes; request_body passed as bytes | ✅ mitigated |
| T-59-03 | Tampering | RFC 8032 reference copied verbatim; demo vector tests detect modifications | ✅ mitigated |
| T-59-04 | Info Disclosure | BotSecret passed as parameter, never stored in module-level state | ✅ mitigated |
| T-59-05 | Elevation of Privilege | verify_callback_signature returns False (not exception) on invalid input | ✅ mitigated |
| T-59-SC | Tampering (pip) | No package installs — dependencies = [] holds, stdlib only | ✅ accepted |

## Deviations

### [Rule 3 - Pre-existing] Privacy gate failure from planning docs

The `phase7-privacy-boundary` gate fails due to planning docs containing `request_body` as a parameter name, which triggers the `the-body-scan` privacy pattern in data scan mode. This is a pre-existing issue from the planning phase (committed in 5031f62), not caused by the implementation code. The source `.py` files are scanned in "source" mode (which doesn't check the-body-scan patterns) and are not in the data scan paths. No fix applied — this requires either updating the privacy scan to exclude `.planning/` docs or rephrasing the planning docs to avoid the `request_body` term.

## Artifacts

| Artifact | Path | Provides |
|----------|------|----------|
| Vendored Ed25519 | `packages/channels/qqbot/src/inkstatute_channels_qqbot/_ed25519.py` | RFC 8032 Section 6.1 reference (secret_to_public, sign, verify) |
| Signature module | `packages/channels/qqbot/src/inkstatute_channels_qqbot/signature.py` | QQ Bot signature service (derive_keypair, verify_callback_signature, handle_validation_challenge) |
| Ed25519 tests | `packages/channels/qqbot/tests/test_ed25519_vectors.py` | Known-answer tests against official QQ demo vectors |
| Signature tests | `packages/channels/qqbot/tests/test_signature.py` | Pure-function unit tests for signature module |
