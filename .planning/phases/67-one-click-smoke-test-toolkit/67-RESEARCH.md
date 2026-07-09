# Phase 67: One-Click Smoke-Test Toolkit - Research

**Researched:** 2026-07-09
**Domain:** Operator CLI smoke toolkit for QQBot channel (signature + egress + callback simulation + sanitized evidence)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting.

Key constraints:
- `scripts/smoke_test.py` CLI: validate signature, send text + markdown+keyboard, simulate callback, sanitized evidence
- Credentials via env-var injection only (never commit secrets)
- `--dry-run` for CI (fixture credentials, no live platform)
- `runbook/SMOKE_TEST_RUNBOOK.md` documents setup, commands, expected outputs, evidence format
- Evidence sanitized: no tokens, no raw user payloads, no attachment URLs
- Live run is a HUMAN GATE — not an autonomous deliverable
- Reuse Phase 59–66 qqbot modules; dependencies=[] for qqbot package; smoke script may use stdlib only
- No frozen Protocol/platform-contract/channel-core edits; no wecom imports

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting.

### Deferred Ideas (OUT OF SCOPE)
Live platform smoke execution remains a human gate after this phase ships the toolkit.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SMOKE-01 | One-click CLI validates signature, sends text + markdown+keyboard, simulates callback, collects sanitized evidence via env-var credentials | Compose `signature.py` + `sender.build_*` + Fake/Urllib transports + `feedback_ingress.handle_feedback_callback` / adapter `verify_and_ack` in `scripts/smoke_test.py` |
| SMOKE-02 | `--dry-run` CI mode: fixture credentials, no live QQ connection; validates envelopes, signature logic, evidence format | Default path uses official DEMO vectors + `FakeTokenTransport` / `FakeMessageTransport`; assert zero network |
| SMOKE-03 | Operator runbook `runbook/SMOKE_TEST_RUNBOOK.md` | New markdown under repo-root `runbook/` (directory does not exist yet) covering env setup, commands, expected outputs, evidence archival |
| SMOKE-04 | Evidence sanitized (no tokens, raw payloads, attachment URLs); structured for `.planning/` archival | Reuse `_rich_media_evidence` / SendError sanitization patterns; smoke-owned `sanitize_evidence()` + privacy unit tests |
</phase_requirements>

## Summary

Phases 59–66 already deliver the full QQBot production loop behind `qqbot_channel_enabled` (default OFF): Ed25519 signature + op=13 challenge, normalization, token manager, text/markdown/keyboard egress, rich media, session/ingress runtimes, adapter real-IO, and feedback/wakeup. [VERIFIED: codebase] What is missing is an **operator-facing one-click CLI** that exercises those modules end-to-end with env-injected credentials, emits a **sanitized JSON evidence artifact**, and documents the live procedure in a runbook — without making the live platform call an autonomous CI deliverable. [CITED: .planning/REQUIREMENTS.md SMOKE-01..04; .planning/research/FEATURES.md]

There is **no existing `runbook/` directory** and **no `scripts/smoke_test.py`**. Closest precedents are `scripts/run_v2_gates.py` (argparse + PYTHONPATH gate runner) and `scripts/inkstatute_wecom_live_bridge.py` (operator-run live bridge with secrets from external env — never committed). [VERIFIED: scripts/] QQBot already exposes Fake/Urllib transport twins, official DEMO signature vectors, and sanitized rich-media evidence helpers suitable for reuse. [VERIFIED: sender.py, test_ed25519_vectors.py]

**Primary recommendation:** Implement a stdlib-only `scripts/smoke_test.py` that defaults to `--dry-run` (Fake transports + official DEMO BotSecret), optionally runs `--live` only when required env vars are present (human gate), writes sanitized evidence JSON to stdout and/or `--evidence-out`, and ship `runbook/SMOKE_TEST_RUNBOOK.md`. Do not add package dependencies; do not modify frozen Protocol/platform-contract/channel-core; do not import wecom.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| CLI orchestration / argparse | Operator tooling (`scripts/smoke_test.py`) | — | Repo-root script; not a qqbot package module |
| Signature verify + op=13 challenge | API / Backend (`signature.py`) | Smoke CLI | Reuse Phase 59; dry-run uses DEMO vectors |
| Text + markdown+keyboard envelopes | API / Backend (`sender.build_*`) | Smoke CLI | Reuse Phase 62 builders; strip_for_wire before send |
| Live / fake message POST | API / Backend (`send_message` + Fake/Urllib transport) | Smoke CLI injects transport | Same twin pattern as Phase 61–65 |
| Callback simulation (INTERACTION) | API / Backend (`feedback_ingress` / `adapter.verify_and_ack`) | Smoke CLI | Dry-run: fixture envelope; live: optional recorded callback or fixture replay |
| Evidence sanitization + archival shape | Operator tooling (smoke sanitize helper) | `.planning/` human archive | SMOKE-04; never store secrets |
| Credential injection | OS env vars (operator machine) | Runbook docs | Never commit; never print |
| Live platform execution | Manual / HUMAN GATE | — | Explicitly deferred from autonomous delivery |
| Operator documentation | `runbook/SMOKE_TEST_RUNBOOK.md` | — | SMOKE-03 |

## Project Constraints (from .cursor/rules/ + AGENTS.md)

No `.cursor/rules/` directory present in this workspace. Applicable project constraints from `AGENTS.md` / v1.8 practice:

- Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads.
- Prefer `raw_payload_ref`; contract/evidence must not store sensitive full text by default.
- Do not import `wecom_service` into qqbot paths (`test_no_wecom_import.py`).
- Do not modify frozen ChannelAdapter Protocol, BackendAdapter Protocol, platform-contract enums/schemas, or channel-core modules (ADAPTER-04).
- Keep `packages/channels/qqbot` at `dependencies = []`.
- Smoke script: stdlib preferred; may import in-repo qqbot/channel-core/platform-contract via `sys.path` (mirror `scripts/inkstatute_wecom_live_bridge.py` / gate runner).
- Live promotion / live smoke remains a human gate — toolkit ships; live execution does not auto-complete.
- High-risk legal feedback stays human-reviewed; smoke must not auto-synthesize skills.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `argparse` | 3.11+ (env 3.14.6) | CLI flags (`--dry-run`, `--live`, `--evidence-out`) | Existing scripts pattern [VERIFIED: scripts/run_v2_gates.py] |
| Python stdlib `asyncio` | 3.11+ | Drive async `send_message` / `verify_and_ack` | Sender/adapter are async [VERIFIED: sender.py] |
| Python stdlib `json` / `hashlib` / `os` / `sys` / `pathlib` | — | Evidence I/O, hashing openids/ids, env injection, path bootstrap | No new deps [VERIFIED: env] |
| `inkstatute_channels_qqbot` | in-repo `0.1.0` | signature, sender, token_manager, adapter, feedback_ingress | Reuse Phases 59–66; `dependencies=[]` [VERIFIED: pyproject.toml] |
| `channel_core` / `platform_contract` / `platform_runtime` | in-repo | Output policy, RawInbound/AckResponse types if adapter path used | Already on qqbot PYTHONPATH [VERIFIED: run_v2_gates.py] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `FakeTokenTransport` / `FakeMessageTransport` | in-repo | Dry-run zero-network | Always in `--dry-run` / CI |
| `UrllibTokenTransport` / `UrllibMessageTransport` | in-repo | Live OpenAPI | Only with `--live` + env credentials |
| Official DEMO BotSecret vectors | in-repo tests | Dry-run signature known-answers | `naOC0ocQE3shWLAfffVLB1rhYPG7` (public docs, not production) [VERIFIED: test_ed25519_vectors.py] |
| Existing fixtures under `packages/channels/qqbot/fixtures/` | in-repo | Callback / C2C envelopes for simulation | Dry-run callback step |
| `unittest` (stdlib) | 3.11+ | Smoke unit tests (sanitize, dry-run steps) | Wave 0 + CI |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Repo-root `scripts/smoke_test.py` | Package entry point `python -m inkstatute_channels_qqbot.smoke` | Would expand qqbot public API; ROADMAP/REQUIREMENTS lock `scripts/smoke_test.py` |
| Compose adapter `deliver()` for sends | Call `build_*` + `send_message` directly | Adapter needs ChannelDelivery + flag/config wiring; direct sender is simpler for smoke and still reuses production builders |
| Live webhook listener in smoke | Simulate callback from fixture / operator-pasted JSON | Listening requires public HTTPS + long-running process; out of “one-click” scope; runbook can note optional paste |
| pytest as smoke runner | unittest + CLI | Repo qqbot tests use unittest; keep consistent |
| Copy WeCom live bridge patterns wholesale | QQ-specific stdlib script | WeCom bridge pulls Hermes/wecom_service — forbidden for qqbot smoke |

**Installation:** none — no new external packages.

**Version verification:** No registry packages. Python 3.14.6 available; qqbot `dependencies = []`. [VERIFIED: env + pyproject.toml]

## Package Legitimacy Audit

> No new external packages are recommended for this phase.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| — | — | — | — | — | — | N/A — no installs |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck 0.6.1 available; unused because no install candidates.* [VERIFIED: slopcheck --version]

## Architecture Patterns

### System Architecture Diagram

```
Operator / CI
    │
    ▼
scripts/smoke_test.py  (--dry-run | --live)
    │
    ├─ bootstrap sys.path → qqbot / channel-core / platform-contract / platform-runtime
    ├─ load credentials
    │     dry-run: DEMO BotSecret + fixture openids (no real secrets)
    │     live:    env INKSTATUTE_QQBOT_* (fail closed if missing)
    │
    ├─ Step A: Signature
    │     derive_keypair → sign/verify DEMO or live body
    │     optional handle_validation_challenge (op=13)
    │
    ├─ Step B: Egress text
    │     build_text_envelope → send_message
    │     transport = Fake (dry) | Urllib (live)
    │
    ├─ Step C: Egress markdown+keyboard
    │     build_feedback_keyboard_envelope → send_message
    │
    ├─ Step D: Callback simulation
    │     load fixture INTERACTION_CREATE (or --callback-json)
    │     handle_feedback_callback AND/OR adapter.verify_and_ack(RawInbound)
    │     dry-run: Fake put_json; live: optional real PUT if interaction_id real
    │
    └─ Step E: Evidence
          sanitize_evidence(steps) → stdout + optional --evidence-out PATH
          assert no tokens / Authorization / raw content / attachment URLs
```

### Recommended Project Structure

```
scripts/
└── smoke_test.py                 # NEW — CLI entry (stdlib + qqbot imports)

runbook/
└── SMOKE_TEST_RUNBOOK.md         # NEW — operator docs (SMOKE-03)

packages/channels/qqbot/tests/
└── test_smoke_toolkit.py         # NEW — dry-run + sanitize unit tests (CI)

.planning/phases/67-.../          # optional human-archived evidence copies (not auto-written by CI)
```

Do **not** add smoke modules inside `inkstatute_channels_qqbot/` unless a tiny pure helper is needed and exported — prefer keeping operator tooling in `scripts/` so the package stays a library. [ASSUMED: packaging preference aligned with ROADMAP path]

### Pattern 1: Path bootstrap like existing scripts
**What:** Insert package `src/` dirs onto `sys.path` from repo root before importing qqbot.
**When to use:** Always at top of `smoke_test.py`.
**Example:**
```python
# Source: scripts/inkstatute_wecom_live_bridge.py + scripts/run_v2_gates.py patterns
REPO_ROOT = Path(__file__).resolve().parents[1]
for rel in (
    "packages/channels/qqbot/src",
    "packages/channel-core/src",
    "packages/platform-contract/src",
    "packages/platform-runtime/src",
):
    p = REPO_ROOT / rel
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
```

### Pattern 2: Dual-mode transport injection
**What:** `--dry-run` always uses Fake transports; `--live` constructs `TokenManager(UrllibTokenTransport)` + `UrllibMessageTransport` only after env validation.
**When to use:** Every smoke invocation.
**Example:**
```python
# Source: packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py (Fake/Urllib twins)
if args.dry_run:
    token_mgr = TokenManager(app_id="fixture-app-id", client_secret="fixture-secret",
                             transport=FakeTokenTransport({"access_token": "fixture-token", "expires_in": 7200}))
    transport = FakeMessageTransport()
else:
    # --live: read env; never log values
    token_mgr = TokenManager(app_id=app_id, client_secret=client_secret,
                             transport=UrllibTokenTransport())
    transport = UrllibMessageTransport()
```

### Pattern 3: Sanitized evidence record
**What:** Collect per-step booleans, hashes, msg_type, status codes — never secrets or raw bodies.
**When to use:** After each step; final JSON artifact.
**Example:**
```python
# Source: sender._rich_media_evidence pattern [VERIFIED: sender.py:943-971]
def _hash16(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]

evidence = {
    "schema": "inkstatute.qqbot.smoke_evidence.v1",
    "mode": "dry-run",
    "not_live_acceptance": True,  # False only after human live run archival
    "steps": {
        "signature": {"ok": True, "vector": "qq_official_demo"},
        "send_text": {"ok": True, "msg_type": 0, "openid_hash": _hash16(openid)},
        "send_keyboard": {"ok": True, "msg_type": 2, "actions": list(FEEDBACK_ACTIONS)},
        "callback": {"ok": True, "category": "interaction", "idempotency_key_present": True},
    },
}
```

### Anti-Patterns to Avoid
- **Printing env secrets or Authorization headers:** Violates SMOKE-04 / AGENTS.md — redact in sanitize pass.
- **Defaulting to live network:** CI must be dry-run; require explicit `--live`.
- **Importing wecom_service or modifying Protocol:** ADAPTER-03/04 regressions.
- **Storing raw callback JSON with user content in evidence:** Use refs + hashes only.
- **Treating live smoke as phase completion:** Human gate remains open after toolkit ships.
- **Adding qqbot package dependencies for HTTP:** Urllib already in-package; smoke stays stdlib.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Ed25519 verify/sign | Custom crypto in smoke | `signature.derive_keypair` / `verify_callback_signature` / `handle_validation_challenge` | Already vector-tested Phase 59 |
| Message envelopes | Ad-hoc JSON | `build_text_envelope` / `build_feedback_keyboard_envelope` | Output policy + keyboard shape already correct |
| Token acquire/cache | Manual urllib in smoke | `TokenManager` + Fake/Urllib transports | Single-flight + sanitized TokenError |
| Send + retry | Raw POST loops | `send_message` | Backoff, 401 refresh, terminal codes |
| Feedback normalize | Re-parse INTERACTION | `handle_feedback_callback` | FEEDBACK-03 idempotency already stamped |
| Rich-media evidence hashing | New hash scheme | Mirror `_rich_media_evidence` (sha256[:16]) | Consistency with Phase 63 |

**Key insight:** Smoke is an **orchestrator**, not a second implementation of the channel. Every behavioral step should call production helpers; smoke owns only CLI, env loading, evidence sanitize, and runbook.

## Common Pitfalls

### Pitfall 1: Accidental live calls in CI
**What goes wrong:** Default path hits `api.sgroup.qq.com` or `bots.qq.com`.
**Why it happens:** `--live` as default, or constructing Urllib transports unconditionally.
**How to avoid:** Default `--dry-run=True`; `--live` mutually exclusive; unit test asserts Fake `call_count` and no urllib import side effects beyond Fake path.
**Warning signs:** CI flakes / network timeouts in gate `qqbot-channel`.

### Pitfall 2: Secret leakage in evidence JSON
**What goes wrong:** Evidence contains `access_token`, `Authorization`, BotSecret, openids, message content, attachment URLs.
**Why it happens:** Dumping transport.calls or raw envelopes into evidence.
**How to avoid:** Allowlist evidence keys; recursive redact of forbidden substrings; unittest scans serialized JSON for banned tokens.
**Warning signs:** `fixture-token` or DEMO secret appearing in archived evidence (DEMO secret is public docs value — still prefer not to echo in live evidence; dry-run may record `vector: qq_official_demo` without the secret string).

### Pitfall 3: Live send without passive-reply msg_id
**What goes wrong:** Live text/keyboard send fails QQ window / msg_id rules.
**Why it happens:** Smoke invents msg_id without a prior user message.
**How to avoid:** Runbook requires `INKSTATUTE_QQBOT_REPLY_MSG_ID` from a recent user message for live passive reply; dry-run uses fixture msg_id. Document clearly that live step B/C need an in-window `msg_id`.
**Warning signs:** QQ codes related to passive reply / invalid msg_id.

### Pitfall 4: Confusing config refs with secret values
**What goes wrong:** Reading `INKSTATUTE_QQBOT_APP_ID_REF` (secret://…) as the AppId.
**Why it happens:** `QQBotChannelConfig.from_env` uses `*_REF` names for production config.
**How to avoid:** Smoke live env uses **value** vars distinct from refs: `INKSTATUTE_QQBOT_APP_ID`, `INKSTATUTE_QQBOT_CLIENT_SECRET`, `INKSTATUTE_QQBOT_BOT_SECRET`, `INKSTATUTE_QQBOT_USER_OPENID`, `INKSTATUTE_QQBOT_REPLY_MSG_ID`. Runbook table must list these explicitly.
**Warning signs:** TokenError / empty appId on live run.

### Pitfall 5: Claiming live acceptance from dry-run
**What goes wrong:** Evidence with `not_live_acceptance: false` from CI.
**Why it happens:** Mode flag not stamped correctly.
**How to avoid:** Dry-run always sets `not_live_acceptance: true` and `mode: "dry-run"`; only `--live` success may set `mode: "live"` and still requires human archival decision for acceptance claims.
**Warning signs:** Planning docs citing CI JSON as live proof.

### Pitfall 6: Expanding scope into rich-media / wakeup / WebSocket
**What goes wrong:** Phase balloons past SMOKE-01..04.
**Why it happens:** FEATURES.md lists many QQ differentiators.
**How to avoid:** Scope fence: signature + text + markdown+keyboard + callback simulation + evidence + runbook. Rich-media/wakeup optional future flags only if explicitly added later.
**Warning signs:** New env vars for file upload in this phase.

## Code Examples

Verified patterns from in-repo sources:

### Dry-run signature known-answer
```python
# Source: packages/channels/qqbot/tests/test_ed25519_vectors.py
from inkstatute_channels_qqbot.signature import derive_keypair, verify_callback_signature
from inkstatute_channels_qqbot._ed25519 import sign

DEMO_BOT_SECRET = "naOC0ocQE3shWLAfffVLB1rhYPG7"
DEMO_SIG_TIMESTAMP = "1725442341"
DEMO_SIG_BODY = b'{\n  "op": 0,\n  "d": {},\n  "t": "GATEWAY_EVENT_NAME"\n}'

public_key, seed = derive_keypair(DEMO_BOT_SECRET)
sig_hex = sign(seed, DEMO_SIG_TIMESTAMP.encode() + DEMO_SIG_BODY).hex()
assert verify_callback_signature(public_key, sig_hex, DEMO_SIG_TIMESTAMP, DEMO_SIG_BODY)
```

### Build + send keyboard (dry-run)
```python
# Source: packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py
envelope = build_feedback_keyboard_envelope(
    title="墨律冒烟：请评价",
    feedback_target="smoke-target-001",
    msg_id="ROBOT1.0_fixture_c2c_msg_001",
    msg_seq=1,
)
result = await send_message(
    envelope=envelope,
    scene="c2c",
    token_manager=token_mgr,
    transport=transport,
    user_openid="FIXTURE_USER_OPENID_C2C_001",
)
```

### Callback simulation
```python
# Source: packages/channels/qqbot/src/inkstatute_channels_qqbot/feedback_ingress.py
from inkstatute_channels_qqbot.feedback_ingress import handle_feedback_callback

payload = json.loads(Path("packages/channels/qqbot/fixtures/qqbot_interaction_create.json").read_text())
outcome = handle_feedback_callback(
    payload["envelope"],
    received_at="2026-07-09T12:00:00+00:00",
    payload_ref="fixture://qqbot/smoke/interaction",
)
assert outcome["status"] == "normalized"
assert outcome["idempotency_key"]  # FEEDBACK-03
```

### CLI skeleton
```python
# Source: scripts/run_v2_gates.py argparse style
parser = argparse.ArgumentParser(description="InkStatute QQBot one-click smoke test")
mode = parser.add_mutually_exclusive_group()
mode.add_argument("--dry-run", action="store_true", default=True,
                  help="CI mode: fixtures + Fake transports (default)")
mode.add_argument("--live", action="store_true",
                  help="HUMAN GATE: real OpenAPI; requires env credentials")
parser.add_argument("--evidence-out", type=Path, default=None)
parser.add_argument("--callback-json", type=Path, default=None,
                    help="Optional INTERACTION envelope for callback step")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixture-only channel loop (v1.6 Phase 43) | Production qqbot modules + operator smoke toolkit | v1.8 Phase 67 | Operators can validate live without rebuilding adapters |
| WeCom live bridge as only live tool | QQ-specific smoke CLI (no wecom import) | Phase 67 | Parity tooling without cross-channel coupling |
| Ad-hoc manual curl against QQ OpenAPI | One-click script + runbook + sanitized evidence | Phase 67 | Repeatable, CI-safe dry-run + human live gate |

**Deprecated/outdated:**
- Treating Phase 43 `qqbot_channel_loop.json` alone as live acceptance — fixtures declare `not_live_acceptance: true`.
- Copying WeCom AES/signature into QQ smoke — incompatible primitives; forbidden.

## Recommended CLI Contract (Claude's Discretion → Planner Lock)

| Flag / Env | Dry-run | Live | Notes |
|------------|---------|------|-------|
| Default mode | `--dry-run` | — | CI default; no network |
| `--live` | — | required | Fail if any required env missing |
| `--evidence-out PATH` | optional | optional | Else print JSON to stdout |
| `--callback-json PATH` | optional (default fixture) | optional | Simulate INTERACTION |
| `INKSTATUTE_QQBOT_APP_ID` | unused | required | Real AppId value |
| `INKSTATUTE_QQBOT_CLIENT_SECRET` | unused | required | Token client secret |
| `INKSTATUTE_QQBOT_BOT_SECRET` | DEMO constant | required | Ed25519 BotSecret |
| `INKSTATUTE_QQBOT_USER_OPENID` | fixture openid | required | C2C target |
| `INKSTATUTE_QQBOT_REPLY_MSG_ID` | fixture msg_id | required | Passive-reply window |
| Exit code | 0 all steps ok | 0 all steps ok | Non-zero on first hard failure |

**Live human-gate rule:** Phase verification / CI must only require `--dry-run`. Runbook documents `--live` as operator-only. Do not add autonomous live smoke to `scripts/run_v2_gates.py` in this phase. [ASSUMED: gate list unchanged unless planner explicitly adds a dry-run-only gate]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Smoke stays in `scripts/` rather than qqbot package module | Architecture | Planner may prefer package entrypoint — low risk if path still `scripts/smoke_test.py` |
| A2 | Live env var names use value keys (`_APP_ID`) not `_REF` keys | Pitfall 4 / CLI Contract | Operator confusion if runbook mismatches host secret manager |
| A3 | Callback step in dry-run is fixture simulation, not a live webhook listener | Architecture | If product expects inbound listener, scope expands |
| A4 | Dry-run-only may be added to V2 gates later; not required for Phase 67 minimum | CLI Contract | CI may miss smoke regressions until gate added |
| A5 | Rich-media / wakeup / WebSocket out of Phase 67 smoke steps | Pitfall 6 | Operators may expect full EGRESS-05/06 coverage |

**If this table is empty:** N/A — assumptions listed above need planner awareness, not user re-discuss (discuss skipped).

## Open Questions

1. **Should `--live` attempt real interaction PUT, or only send + local callback normalize?**
   - What we know: Phase 65/66 already implement `ack_interaction`; live PUT needs a real `interaction_id` from a user click.
   - What's unclear: Whether operators will paste a live INTERACTION payload during smoke.
   - Recommendation: Dry-run always simulates normalize; live send steps are mandatory; live ACK PUT only if `--callback-json` contains a real interaction id and `--live` — otherwise document as optional follow-up in runbook.

2. **Should dry-run smoke be wired into `run_v2_gates.py`?**
   - What we know: REQUIREMENTS say CI-able dry-run; gates already run qqbot unittest discover.
   - What's unclear: Whether a separate gate name is desired vs unittest coverage alone.
   - Recommendation: Cover via `test_smoke_toolkit.py` under qqbot tests (picked up by existing `qqbot-channel` gate); optionally document `python3 scripts/smoke_test.py --dry-run` in runbook/CI docs without mandating a new gate entry.

3. **Where should human-archived live evidence land?**
   - What we know: SMOKE-04 says structured for archival in `.planning/` after live run.
   - What's unclear: Exact path convention.
   - Recommendation: Runbook says copy sanitized JSON to `.planning/phases/67-one-click-smoke-test-toolkit/evidence/YYYYMMDD-smoke-live.json` (gitignored or sanitized-only); do not auto-commit from the script.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | smoke CLI + tests | ✓ | 3.14.6 | — |
| qqbot package src | imports | ✓ | 0.1.0 | — |
| channel-core / platform-contract / platform-runtime | adapter/types | ✓ | in-repo | — |
| unittest | CI tests | ✓ | stdlib | — |
| pytest | optional | ✓ | 9.1.1 | Prefer unittest for consistency |
| Live QQ Bot credentials | `--live` | ✗ (operator-provided) | — | `--dry-run` only |
| Public HTTPS webhook endpoint | live inbound click | ✗ | — | Fixture/callback-json simulation |
| slopcheck | package audit | ✓ | 0.6.1 | N/A (no installs) |

**Missing dependencies with no fallback:**
- None for dry-run / phase implementation.

**Missing dependencies with fallback:**
- Live QQ credentials → dry-run Fake path; live remains human gate.
- Live webhook URL → simulate callback from fixture / pasted JSON.

Step 2.6: external live QQ not required for phase execution; CI uses dry-run.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | unittest (stdlib; asyncio for send steps) |
| Config file | `packages/channels/qqbot/pyproject.toml` (`dependencies = []`) |
| Quick run command | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_smoke_toolkit -v` |
| Full suite command | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src" python3 -m unittest discover -s packages/channels/qqbot/tests -v` |
| CLI dry-run smoke | `python3 scripts/smoke_test.py --dry-run` (exit 0; writes sanitized evidence) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SMOKE-01 | CLI steps: signature + text + keyboard + callback + evidence | unit + CLI | `test_smoke_toolkit` + `python3 scripts/smoke_test.py --dry-run` | ❌ Wave 0 |
| SMOKE-02 | Dry-run uses Fake transports; no live host URLs required | unit | `test_smoke_toolkit.TestDryRunNoNetwork` | ❌ Wave 0 |
| SMOKE-03 | Runbook file exists with required sections | unit/file | `test -f runbook/SMOKE_TEST_RUNBOOK.md` + content assertions | ❌ Wave 0 |
| SMOKE-04 | Evidence JSON has no tokens/payloads/URLs | unit | `test_smoke_toolkit.TestEvidenceSanitized` | ❌ Wave 0 |
| ADAPTER-04 | No Protocol/contract/channel-core edits; no wecom import | unit | existing `test_no_wecom_import` + `test_contract_freeze_not_violated` | ✅ |

### Sampling Rate
- **Per task commit:** narrowed unittest for touched smoke/sanitize helpers
- **Per wave merge:** full qqbot discover + `scripts/smoke_test.py --dry-run`
- **Phase gate:** Full suite green; live `--live` not required

### Wave 0 Gaps
- [ ] `packages/channels/qqbot/tests/test_smoke_toolkit.py` — dry-run orchestration + sanitize assertions
- [ ] `scripts/smoke_test.py` — CLI implementation (created in implementation wave; Wave 0 may stub RED import/CLI tests)
- [ ] `runbook/SMOKE_TEST_RUNBOOK.md` — operator docs
- [ ] Privacy assertions: banned substrings (`Authorization`, `access_token`, `http`, attachment url keys, raw `content` fields in evidence)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (live token) | `TokenManager` + env injection; never commit secrets |
| V3 Session Management | no | Smoke is one-shot CLI |
| V4 Access Control | partial | Live openids only from operator env; hash in evidence |
| V5 Input Validation | yes | Validate `--callback-json` is object; openid charset via sender helpers |
| V6 Cryptography | yes | Reuse vendored Ed25519; never hand-roll |
| V7 Error Handling / Logging | yes | Sanitized errors; no secret in stderr |
| V8 Data Protection | yes | SMOKE-04 evidence allowlist + redact |

### Known Threat Patterns for smoke CLI

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secret exfiltration via evidence/stdout | Information Disclosure | Allowlist evidence; unittest ban-list; never print env values |
| Accidental live send in CI | Elevation / Abuse | Default dry-run; Fake transports; no gate live step |
| Path injection via `--evidence-out` / `--callback-json` | Tampering | Resolve paths; read only files; write only under operator-chosen path |
| SSRF via crafted callback URLs in evidence dump | Information Disclosure | Do not persist attachment URLs; strip `url` keys |
| Using production BotSecret in committed fixtures | Information Disclosure | Dry-run uses public DEMO vector only |
| WeCom credential mix-up | Spoofing | QQ-only env names; no wecom imports |

## Sources

### Primary (HIGH confidence)
- `.planning/REQUIREMENTS.md` — SMOKE-01..04 text
- `.planning/ROADMAP.md` — Phase 67 success criteria
- `.planning/phases/67-one-click-smoke-test-toolkit/67-CONTEXT.md` — locked constraints
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/{signature,sender,token_manager,adapter,feedback_ingress,config}.py` — APIs to reuse
- `packages/channels/qqbot/tests/test_ed25519_vectors.py` — DEMO vectors
- `packages/channels/qqbot/fixtures/*.json` — callback/C2C fixtures
- `scripts/run_v2_gates.py`, `scripts/inkstatute_wecom_live_bridge.py` — CLI/path patterns
- `packages/channels/qqbot/pyproject.toml` — `dependencies = []`
- Environment probes — Python 3.14.6, slopcheck 0.6.1

### Secondary (MEDIUM confidence)
- `.planning/research/FEATURES.md` — smoke toolkit product intent (env-injected CLI + sanitized JSON)
- Prior phase RESEARCH (65/66) — live smoke deferred to Phase 67 human gate

### Tertiary (LOW confidence)
- Exact live archival path under `.planning/` — recommended convention, not yet locked [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — stdlib + in-repo qqbot only; no new packages
- Architecture: HIGH — clear compose-over-reimplement path verified in codebase
- Pitfalls: HIGH — secret leak / accidental live / msg_id window are well-known from Phases 62–65

**Research date:** 2026-07-09
**Valid until:** 2026-08-08 (30 days; stack stable)
