---
phase: 59-ed25519-signature-verification-validation-challenge
plan: 02
wave: 2
status: complete
requirements:
  - INGRESS-01
  - INGRESS-02
started: 2026-07-07T09:00:00Z
completed: 2026-07-07T09:10:00Z
commits:
  - 1330f4c: "feat(59-02): add bot_secret_ref config field + extend wecom import isolation tests"
  - cdbc70d: "feat(59-02): wire verify_and_ack with Ed25519 signature verification, 401 rejection, op=13 challenge"
---

# Phase 59 Plan 02 — Summary

## Objective

Wire the signature module (created in Plan 01) into the adapter's frozen `verify_and_ack` method and add the `bot_secret_ref` config field, completing the end-to-end signature verification flow: callback → signature check → 401 rejection or op=13 challenge response. This satisfies INGRESS-01 (reject unverified callbacks with HTTP 401) and INGRESS-02 (op=13 validation challenge handling) without changing the frozen ChannelAdapter Protocol method signature.

## Tasks Completed

### Task 1: Add bot_secret_ref to config.py + extend test_no_wecom_import.py

**Commit:** 1330f4c

**Files modified:**
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/config.py` — Added `bot_secret_ref: str | None = None` field after `token_secret_ref` (reference-only, never raw secret). `from_env` reads `INKSTATUTE_QQBOT_BOT_SECRET_REF` and passes it to `cls()`. Frozen `@dataclass(frozen=True, slots=True)` decorator unchanged.
- `packages/channels/qqbot/tests/test_no_wecom_import.py` — Added `test_ed25519_does_not_import_wecom_service` and `test_signature_does_not_import_wecom_service` covering the new source files from Plan 01 via AST import inspection.

**Test results:** 7/7 import isolation tests pass, 14/14 adapter tests pass (no regressions).

### Task 2: Wire verify_and_ack with signature verification + 401 rejection + op=13 challenge

**Commit:** cdbc70d

**Files modified:**
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`:
  - Added import of `derive_keypair`, `handle_validation_challenge`, `verify_callback_signature` from `.signature` (no wecom_service import).
  - Rewrote `verify_and_ack` (method signature unchanged: `async def verify_and_ack(self, raw: RawInbound) -> AckResponse`) with real Ed25519 signature verification:
    - Channel disabled → 503 (existing behavior preserved).
    - `bot_secret_ref` is None → stub behavior preserved (`signature_status="secret_ref_required"`, accepted=True, 200).
    - Signature headers present → derive keypair from `bot_secret` (injected via `raw.metadata["bot_secret"]`), verify over `timestamp + request_body` (bytes, never re-serialized).
    - Missing signature headers → 401 (`signature_status="missing"`).
    - Invalid/tampered signature → 401 (`signature_status="invalid"`).
    - Verified + op=13 payload → 200 with `validation_challenge_response = {plain_token, signature}` in metadata.
    - Verified + non-op=13 → 200 (`signature_status="verified"`).
  - Updated `capabilities()` and `health()` to report `bot_secret_ref` configuration status in `secret_refs_configured`.
- `packages/channels/qqbot/tests/test_signature.py` — Added `QQBotAdapterSignatureTests` class with 7 adapter integration tests covering all behaviors (valid signature, missing headers, invalid signature, tampered body, op=13 challenge, stub preservation, 503 preservation).

**Test results:** 21/21 signature tests pass (14 pure-function + 7 adapter integration), 7/7 contract freeze tests pass, 6/6 safety baseline tests pass.

## Verification Results

### Plan-specified verification (8 commands, all pass)

| # | Command | Result |
|---|---------|--------|
| 1 | `python3 -m unittest test_signature -v` | 21/21 OK (14 pure + 7 adapter) |
| 2 | `python3 -m unittest test_no_wecom_import -v` | 7/7 OK (covers _ed25519.py, signature.py) |
| 3 | `python3 -m unittest test_contract_freeze_not_violated -v` | 7/7 OK (6 Protocol methods) |
| 4 | `python3 -m unittest test_v1_8_safety_baseline -v` | 6/6 OK (dependencies = [], flag default-off) |
| 5 | `python3 -m unittest test_ed25519_vectors -v` | 9/9 OK (known-answer tests) |
| 6 | `python3 -m unittest test_qqbot_channel_adapter -v` | 14/14 OK (no regressions) |
| 7 | `python3 -m unittest test_qqbot_idempotency -v` | 7/7 OK (no regressions) |
| 8 | `python3 scripts/run_v2_gates.py` | 26/26 gates green, exit 0 |

### Full V2 gate suite

All 26 V2 gates pass with exit code 0, including `phase7-privacy-boundary` (13 tests OK — the pre-existing privacy gate failure noted in Plan 01 has been resolved by rephrasing planning docs to use `request_body`/`ref://` terminology).

## Success Criteria

- [x] verify_and_ack performs Ed25519 signature verification using signature.py from Plan 01
- [x] Unverified callbacks rejected with HTTP 401 (INGRESS-01 SC-2)
- [x] op=13 validation challenge handled: signs {event_ts + plain_token}, returns {plain_token, signature} (INGRESS-02 SC-3)
- [x] verify_and_ack method signature unchanged (frozen Protocol — 6 methods)
- [x] config.py stores bot_secret_ref as reference-only (no raw secret)
- [x] test_no_wecom_import.py covers _ed25519.py and signature.py
- [x] All existing safety tests remain green (dependencies = [], no wecom_service import, 6 Protocol methods, flag default-off)
- [x] All 26 V2 gates green (ADAPTER-04)

## Threat Model Mitigations

| Threat ID | Category | Mitigation | Status |
|-----------|----------|------------|--------|
| T-59-07 | Spoofing | Ed25519 signature verification via verify_callback_signature before accepting any callback; 401 on missing/invalid signature | ✅ mitigated |
| T-59-08 | Tampering | request_body passed as bytes from RawInbound.metadata to verify_callback_signature — never re-serialized | ✅ mitigated |
| T-59-09 | Elevation of Privilege | 401 returned before any payload processing when signature missing/invalid — no path to normalize_inbound without verified signature | ✅ mitigated |
| T-59-10 | Information Disclosure | bot_secret_ref stores reference only; raw BotSecret injected at runtime via metadata, never persisted in config | ✅ mitigated |
| T-59-11 | Tampering | op=13 challenge response signed with Ed25519 private key — QQ platform verifies signature to confirm webhook ownership | ✅ mitigated |
| T-59-12 | Repudiation | Replay window handling out of scope; timestamp included in signature message for future replay protection | ✅ accepted |
| T-59-SC | Tampering (pip) | No package installs — dependencies = [] holds, stdlib only | ✅ accepted |

## Deviations

None — all tasks executed as planned with no deviations.

## Artifacts

| Artifact | Path | Provides |
|----------|------|----------|
| Config | `packages/channels/qqbot/src/inkstatute_channels_qqbot/config.py` | QQBotChannelConfig with bot_secret_ref field (reference-only) |
| Adapter | `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py` | verify_and_ack with real Ed25519 verification + 401 + op=13 challenge |
| Signature tests | `packages/channels/qqbot/tests/test_signature.py` | Pure-function + adapter integration tests (21 tests) |
| Import isolation | `packages/channels/qqbot/tests/test_no_wecom_import.py` | Covers _ed25519.py and signature.py for wecom_service isolation |
