# Phase 71: Smoke Protocol-Path Hardening - Research

**Researched:** 2026-07-10
**Domain:** CI dry-run Protocol-path smoke over host/package QQBot composition (Fake transports + sanitized evidence)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None — discuss phase was skipped. All implementation choices are at the agent's discretion.

### Claude's Discretion
All implementation choices are at the agent's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, Phase 70 webhook composition helpers, and existing smoke_test.py patterns to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
None — discuss phase skipped. Live path remains Phase 72 HUMAN GATE.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SMOKE-01 | `scripts/smoke_test.py --dry-run` exercises the full adapter/session Protocol path (verify_and_ack → ingress/session → deliver) using Fake transports — not leaf helpers only | Call Phase 70 host helpers (`build_qqbot_wired_runtime` + `handle_qqbot_webhook_request` / `run_post_ack_composition`) with Fake transports + FakeBackend; signed C2C fixture → ACK → post-ACK ingress → boundary → deliver; keep leaf steps as secondary only |
| SMOKE-02 | Protocol-path dry-run emits sanitized evidence under the existing allowlist schema (`not_live_acceptance=true`; no secrets/raw bodies) | Extend `_STEP_KEY_ALLOW` for Protocol steps; reuse `sanitize_evidence` / `EVIDENCE_SCHEMA=inkstatute.qqbot.smoke_evidence.v1`; force `not_live_acceptance=true` on dry-run; ban tokens/URLs/raw bodies/`calls` |
</phase_requirements>

## Summary

v1.8 shipped a one-click smoke CLI whose `--dry-run` path is **leaf-only**: DEMO signature vectors, `build_*` + `send_message` via Fake transports, and `handle_feedback_callback` — never `QQBotChannelAdapter` Protocol methods, never `QQBotRuntimeIngress` / session, never the Phase 70 host composition edge. [VERIFIED: scripts/smoke_test.py; packages/channels/qqbot/tests/test_smoke_toolkit.py] That leaf path still exits 0 in CI and is valuable as a sub-check, but claiming it as host-complete is the accepted v1.8 false-confidence gap. [CITED: .planning/research/FEATURES.md; .planning/research/PITFALLS.md Pitfall on leaf-only smoke]

Phase 70 closed the production composition gap: `build_qqbot_wired_runtime` + pure `handle_qqbot_webhook_request` + `run_post_ack_composition` already prove `verify_and_ack` → ingress/feedback → output boundary → `deliver` with Fake transports in `services/qqbot-service/tests/test_webhook_composition.py`. [VERIFIED: webhook.py; wiring.py; test_webhook_composition.py] Phase 71 must **wire that same host/package path into `scripts/smoke_test.py --dry-run`**, extend the existing evidence allowlist for Protocol steps, and keep dry-run free of Urllib/network. Live `--live` / HUMAN GATE remains Phase 72. [CITED: .planning/ROADMAP.md Phase 71; 71-CONTEXT.md]

**Primary recommendation:** Extend `scripts/smoke_test.py` dry-run to compose Protocol steps through Phase 70 host helpers (`build_qqbot_wired_runtime` → signed fixture → `handle_qqbot_webhook_request` + recording scheduler → run post-ACK thunks), emit allowlisted Protocol evidence with `not_live_acceptance=true`, add `services/qqbot-service/src` to the smoke PYTHONPATH bootstrap, and extend `test_smoke_toolkit.py` — do **not** invent a parallel adapter-only smoke path claimed as host-complete.

## Project Constraints (from AGENTS.md / repo norms)

No `.cursor/rules/` directory present in this workspace. Enforce AGENTS.md + milestone research:

- Keep changes scoped to Phase 71 (smoke Protocol-path + evidence); do not start Phase 72 live acceptance.
- Never commit secrets, tokens, raw legal payloads, or dump Fake transport `calls` into evidence.
- Do not import `wecom_service` into qqbot smoke/host path (ADAPTER-04).
- Do not unfreeze `ChannelAdapter` / edit platform-runtime Protocols.
- Do not introduce new services, DBs, queues, or third-party deps (`qqbot-service` stays `dependencies=[]`).
- Prefer structured validators / allowlists over ad hoc string parsing for evidence.
- Backend/gateway/system notices are not user-facing output — Protocol deliver path must still go through `output_boundary` (already in host composition).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Smoke CLI orchestration (`--dry-run` / `--live`) | `scripts/smoke_test.py` | unittest harness | Operator one-click + CI entrypoint [VERIFIED: smoke_test.py] |
| Host composition (verify→ingress→deliver) | `qqbot_service.webhook` / `wiring` | smoke calls only | Success criterion 4: same helpers webhook uses [VERIFIED: webhook.py] |
| Protocol IO (`verify_and_ack`, `normalize_inbound`, `deliver`) | `QQBotChannelAdapter` | host invokes | Package owns crypto/IO [VERIFIED: adapter.py] |
| Session / create_run | `QQBotRuntimeIngress` + `DefaultRunRuntime` | FakeBackend in dry-run | Package owns session; smoke injects FakeBackend [VERIFIED: ingress_runtime.py; fakes.py] |
| Feedback INTERACTION normalize | `handle_feedback_callback` via host post-ACK branch | leaf callback step optional | Host already branches feedback [VERIFIED: webhook.run_post_ack_composition] |
| Fake network isolation | `FakeMessageTransport` / `FakeTokenTransport` | — | Dry-run must never construct Urllib* [CITED: PITFALLS] |
| Evidence sanitize / allowlist | `sanitize_evidence` + `_STEP_KEY_ALLOW` | — | Existing v1 schema; extend keys only [VERIFIED: smoke_test.py] |
| Live Urllib / HUMAN GATE | Deferred → Phase 72 | keep existing `--live` fail-closed | Out of Phase 71 scope |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib (`argparse`, `asyncio`, `json`, `hashlib`, `unittest`, `subprocess`) | 3.11+ (env: 3.14.6) | Smoke CLI + tests | Empty-deps culture; matches Phase 67/70 [VERIFIED: python3 --version] |
| `qqbot_service.wiring.build_qqbot_wired_runtime` | in-repo | Dual-knob DI + Fake live-ready injection | Same factory webhook uses [VERIFIED: wiring.py] |
| `qqbot_service.webhook.handle_qqbot_webhook_request` / `run_post_ack_composition` | in-repo | ACK-first Protocol composition | Success criterion 4 [VERIFIED: webhook.py] |
| `FakeMessageTransport` / `FakeTokenTransport` / `TokenManager` | in-repo qqbot | Network-free IO | Existing dry-run + host tests [VERIFIED: sender.py; token_manager.py] |
| `FakeBackendAdapter` | `platform_runtime.fakes` | Fake agent/run path | Host composition tests already use it [VERIFIED: test_webhook_composition.py] |
| `RuntimeFeatureFlags` + `QQBotHostConfig` | in-repo | Enable knobs only inside smoke fixture | Defaults stay OFF outside smoke [VERIFIED: wiring.py] |
| Package fixtures under `packages/channels/qqbot/fixtures/` | in-repo | Signed C2C / INTERACTION / op=13 envelopes | Reuse DEMO signing pattern [VERIFIED: fixtures/; test_webhook_composition.py] |

### Supporting

| Library | Purpose | When to Use |
|---------|---------|-------------|
| `RecordingScheduler` pattern (copy from host tests) | Prove ACK returns before post-ACK work; then run thunks | Dry-run Protocol message + feedback paths |
| `reply_text` / `reply_resolver` on host handler | Supply deliver content without live backend stream | Dry-run deliver step (already plumbed for Phase 71) [VERIFIED: http_server.py docstring; webhook.py] |
| Existing leaf helpers (`signature`, `build_text_envelope`, `send_message`, `handle_feedback_callback`) | Keep as secondary sub-checks | Do not claim as host-complete alone |
| `scripts/run_v2_gates.py` gate `qqbot-channel` | CI discover includes `test_smoke_toolkit.py` | Extend tests; no new gate required unless smoke moves |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Host helpers in smoke (`handle_qqbot_webhook_request`) | Call adapter Protocol methods directly in smoke | **Rejected for primary claim** — violates success criterion 4 (parallel leaf/adapter-only path). Adapter-direct calls may appear only as internal assertions if host helpers already invoked them |
| New pytest-only Protocol suite without CLI | Unit tests alone | **Rejected as sole deliverable** — ROADMAP/SMOKE-01 require `scripts/smoke_test.py --dry-run` [CITED: REQUIREMENTS.md] |
| New evidence schema v2 | Keep `inkstatute.qqbot.smoke_evidence.v1` + extend allowlist | Prefer extend; schema rename is churn [CITED: STACK.md] |
| Drop leaf steps entirely | Keep leaf as secondary | Keep — STACK says keep leaf; Protocol is the new primary claim [CITED: STACK.md] |
| Bind `QQBotWebhookServer` + real port in CI dry-run | Pure handler + Fake | **Rejected** — port bind adds flake; pure handler is the host-testable surface [VERIFIED: test_webhook_composition.py] |

**Installation:** No new third-party packages.

**Version verification:** No registry packages to install. In-repo modules verified by import + existing unittest green (2026-07-10).

## Package Legitimacy Audit

> Phase 71 installs **no** external packages.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| — | — | — | — | — | N/A | No installs |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck not required — zero new installs.*

## Architecture Patterns

### System Architecture Diagram

```text
CI / operator
  │
  ▼
scripts/smoke_test.py --dry-run
  │
  ├─ [KEEP] leaf signature DEMO vector
  ├─ [KEEP] leaf Fake send_text / send_keyboard   (secondary)
  ├─ [KEEP] leaf feedback normalize              (secondary)
  │
  └─ [NEW PRIMARY] Protocol-path dry-run
        │
        ├─ bootstrap PYTHONPATH:
        │     packages/channels/qqbot/src
        │     packages/platform-runtime/src
        │     … + services/qqbot-service/src   ← REQUIRED (missing today)
        │
        ├─ build_qqbot_wired_runtime(
        │     backend=FakeBackendAdapter(),
        │     flags=RuntimeFeatureFlags(qqbot_channel_enabled=True, run_runtime_enabled=True),
        │     host_config=QQBotHostConfig(enabled=True, …refs…),
        │     env=fixture SECRET_ENV,
        │     token_manager=TokenManager(FakeTokenTransport),
        │     transport=FakeMessageTransport,
        │     token_transport=FakeTokenTransport,
        │   )
        │
        ├─ sign fixture envelope (C2C / INTERACTION) with DEMO_BOT_SECRET
        │     body_bytes = exact JSON bytes (never re-serialize after sign)
        │
        ├─ handle_qqbot_webhook_request(
        │     POST /qqbot/callback, headers, body_bytes,
        │     wired=…, post_ack_scheduler=RecordingScheduler,
        │     received_at=FIXED_NOW (~now-30s),
        │     reply_text=FIXTURE_REPLY,   # message path only
        │     feedback_sink=[…],         # interaction path
        │   )
        │     → await adapter.verify_and_ack  → HTTP ACK evidence
        │     → schedule post-ACK (do not claim complete until thunks run)
        │
        ├─ RecordingScheduler.run_all()
        │     → run_post_ack_composition
        │          ├─ normalize_inbound
        │          ├─ message: QQBotRuntimeIngress.handle_callback → FakeBackend
        │          │            → output_boundary → adapter.deliver(Fake)
        │          └─ feedback: handle_feedback_callback → sink (no message ingress)
        │
        └─ sanitize_evidence({
              schema, mode=dry-run, not_live_acceptance=true,
              steps: { …leaf…, adapter_ack, session_ingress, adapter_deliver, … }
            })
              → stdout / --evidence-out
              → exit 0
```

### Recommended Project Structure (touch set)

```text
scripts/smoke_test.py                          # MODIFY: Protocol-path dry-run + allowlist + PYTHONPATH
packages/channels/qqbot/tests/test_smoke_toolkit.py  # MODIFY: Protocol-path assertions
runbook/SMOKE_TEST_RUNBOOK.md                  # OPTIONAL small note: Protocol dry-run vs leaf (Phase 72 owns full live docs)
services/qqbot-service/…                       # REUSE only — no HOST feature work
```

### Pattern 1: Host-helper Protocol dry-run (required)

**What:** Smoke constructs the same wired runtime + webhook handler the host tests use, with Fake transports and a recording scheduler.
**When to use:** Always for SMOKE-01 primary claim.
**Example:**

```python
# Source: services/qqbot-service/tests/test_webhook_composition.py (verified pattern)
wired, backend, transport = _enabled_wired()  # FakeToken + FakeMessage + FakeBackend
headers, body = _signed_http(_load_envelope("qqbot_c2c_message.json"))
scheduler = RecordingScheduler()
status, resp_body, _ = asyncio.run(
    handle_qqbot_webhook_request(
        "POST", "/qqbot/callback", headers, body,
        wired=wired, env=SECRET_ENV,
        post_ack_scheduler=scheduler,
        received_at=FIXED_NOW,
        reply_text=FIXTURE_REPLY,
    )
)
assert status == 200
assert json.loads(resp_body) == {"op": 12}
assert len(scheduler.thunks) == 1
scheduler.run_all()
assert backend.submitted_requests  # ingress/session fired
assert transport.call_count >= 1   # deliver via Fake
```

### Pattern 2: Evidence allowlist extension (SMOKE-02)

**What:** Keep `EVIDENCE_SCHEMA = "inkstatute.qqbot.smoke_evidence.v1"`. Extend `_STEP_KEY_ALLOW` with Protocol steps; never dump raw bodies, tokens, Authorization, openids (hash only), or `FakeMessageTransport.calls`.
**Recommended new step keys** (names aligned with STACK.md):

| Step key | Allowed fields (max) | Source |
|----------|----------------------|--------|
| `adapter_ack` | `ok`, `http_status`, `op`, `accepted` | webhook ACK mapping |
| `session_ingress` | `ok`, `ingress_action`, `run_id_present`, `branch` | post-ACK composition evidence |
| `adapter_deliver` | `ok`, `deliver_accepted`, `boundary_action` | post-ACK deliver + boundary |
| `protocol_feedback` (optional) | `ok`, `status`, `idempotency_key_present`, `idempotency_key_hash` | INTERACTION host branch |

Dry-run **must** force `not_live_acceptance=true` (existing `sanitize_evidence` already does for `mode=dry-run`). [VERIFIED: smoke_test.py]

### Pattern 3: PYTHONPATH bootstrap for host imports

**What:** Today's smoke inserts qqbot/channel-core/platform-contract/platform-runtime only — `qqbot_service` is **not** importable. [VERIFIED: ModuleNotFoundError without service path]
**When to use:** Before importing host helpers.
**Action:** Add `services/qqbot-service/src` to the smoke bootstrap list (same order style as `run_v2_gates.py`).

### Anti-Patterns to Avoid

- **Leaf-only “hardening”:** Adding more sender asserts without host Protocol calls — repeats v1.8 gap. [CITED: FEATURES.md]
- **Parallel adapter-only smoke claimed as host-complete:** Calling `adapter.verify_and_ack` without `handle_qqbot_webhook_request` / wiring factory — fails success criterion 4.
- **Urllib in dry-run:** Constructing `UrllibMessageTransport` / `UrllibTokenTransport` under `--dry-run` — CI network flake + credential risk. [CITED: PITFALLS]
- **Stale `received_at`:** Fixture timestamps outside C2C/group passive-reply windows cause deliver to fail closed — use `FIXED_NOW = now - 30s` like host tests. [VERIFIED: test_webhook_composition.py]
- **Re-serializing signed bodies:** `json.dumps(parsed)` after signing breaks Ed25519 verify — keep exact signed bytes. [CITED: 70-RESEARCH.md]
- **Dumping transport.calls / envelopes into evidence:** Forbidden keys already list `calls`, `envelope`, `body`, `payload` — keep them. [VERIFIED: smoke_test.py]
- **Auto-claiming live acceptance:** Dry-run exit 0 must never set `not_live_acceptance=false`. Phase 72 owns live. [CITED: REQUIREMENTS.md LIVE-01]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Signed callback HTTP | New crypto in smoke | Package `derive_keypair` + `_ed25519.sign` + host `handle_qqbot_webhook_request` | Host tests already encode the pattern |
| Wired Fake runtime | Ad hoc adapter construction skipping dual knobs | `build_qqbot_wired_runtime` | REG-01 mapping must match production |
| Post-ACK ingress/deliver | Copy webhook logic into smoke | `run_post_ack_composition` via scheduler thunk | Single composition path |
| Evidence redaction | New ad hoc scrubber | Existing `sanitize_evidence` + `_STEP_KEY_ALLOW` | Ban-list + allowlist already battle-tested |
| Fake network | Mock urllib globally | Inject Fake transports only | Explicit DI; no monkeypatch games |
| Reply text for deliver | Fake Hermes stream in dry-run | `reply_text=` fixture string | Host already supports smoke/Fake reply [VERIFIED: webhook.py] |

**Key insight:** Phase 70 already solved composition. Phase 71 is an **orchestration + evidence** problem, not a new Protocol implementation.

## Common Pitfalls

### Pitfall 1: Claiming leaf dry-run as Protocol-complete
**What goes wrong:** SMOKE-01 marked done while evidence only has `signature` / `send_text` / `callback`.
**Why it happens:** Leaf path already exits 0; easiest PR.
**How to avoid:** Require Protocol step keys present and assert host modules imported/called; assert `FakeBackend.submitted_requests` and Fake deliver call_count after scheduler.run_all().
**Warning signs:** Evidence steps unchanged from Phase 67 schema only.

### Pitfall 2: Missing `qqbot-service` on smoke PYTHONPATH
**What goes wrong:** ImportError in CI for `qqbot_service`, or silent fallback to leaf-only.
**Why it happens:** Smoke bootstrap predates the host service.
**How to avoid:** Add `services/qqbot-service/src` next to existing path inserts; unittest covers import.
**Warning signs:** CLI fails only in clean env without editable installs.

### Pitfall 3: Passive-reply window / no reply source
**What goes wrong:** Protocol deliver never fires (`completed_no_reply` or window fail).
**Why it happens:** Fixture `timestamp` is days old relative to wall clock; or `reply_text` omitted.
**How to avoid:** Pass `received_at=FIXED_NOW` and `reply_text=FIXTURE_REPLY` on message path (copy host tests).
**Warning signs:** `adapter_deliver.ok=false` with empty Fake call_count after ingress ok.

### Pitfall 4: Secrets / raw bodies in Protocol evidence
**What goes wrong:** Evidence includes DEMO secret, fixture-token, openids, content, URLs, or transport.calls.
**Why it happens:** Composition evidence dicts are richer than leaf steps.
**How to avoid:** Map composition → allowlisted fields only before `sanitize_evidence`; hash ids; never serialize `calls`.
**Warning signs:** `TestEvidenceSanitized` fails; ban-list hits `https://` from Fake URLs.

### Pitfall 5: Nested asyncio / scheduler double-run
**What goes wrong:** Deadlocks or “Event loop is closed” when smoke wraps `asyncio.run` around a thunk that also `asyncio.run`s.
**Why it happens:** Host thunk uses `asyncio.run(run_post_ack_composition(...))`; smoke already inside `asyncio.run`.
**How to avoid:** Match host tests: call `handle_qqbot_webhook_request` via one `asyncio.run`, then `scheduler.run_all()` on the sync side (thunks own their loops). Do not nest `asyncio.run` inside an active loop.
**Warning signs:** Flaky CLI only when Protocol steps added.

### Pitfall 6: Touching `--live` / claiming Phase 72
**What goes wrong:** Scope creep into Urllib live acceptance.
**Why it happens:** Same script owns both modes.
**How to avoid:** Preserve existing `--live` fail-closed behavior; do not require live for Phase 71 verification; keep `not_live_acceptance=true` on dry-run.
**Warning signs:** Plans editing LIVE_ENV_KEYS or runbook live sections as done criteria.

## Code Examples

### Protocol-path evidence stamp (recommended shape)

```python
# Source: extend scripts/smoke_test.py sanitize_evidence allowlist (in-repo pattern)
_STEP_KEY_ALLOW = {
    # existing leaf keys …
    "adapter_ack": frozenset({"ok", "http_status", "op", "accepted"}),
    "session_ingress": frozenset(
        {"ok", "ingress_action", "run_id_present", "branch"}
    ),
    "adapter_deliver": frozenset(
        {"ok", "deliver_accepted", "boundary_action"}
    ),
}

evidence = {
    "schema": EVIDENCE_SCHEMA,
    "mode": "dry-run",
    "not_live_acceptance": True,
    "steps": {
        "signature": sig_step,
        "send_text": text_step,
        "send_keyboard": keyboard_step,
        "callback": callback_step,
        "adapter_ack": {
            "ok": status == 200 and op == 12,
            "http_status": status,
            "op": 12,
            "accepted": True,
        },
        "session_ingress": {
            "ok": True,
            "ingress_action": "...",
            "run_id_present": True,
            "branch": "message",
        },
        "adapter_deliver": {
            "ok": True,
            "deliver_accepted": True,
            "boundary_action": "allow",  # or pass/rewrite — never raw text
        },
    },
}
```

### Assert dry-run never uses Urllib

```python
# Source: packages/channels/qqbot/tests/test_smoke_toolkit.py pattern
outcome = smoke.run_smoke(mode="dry-run")
assert outcome["transport"] == "fake"
assert "Urllib" not in outcome["transport_class"]
assert "Urllib" not in outcome["token_transport_class"]
# NEW: Protocol path markers
assert outcome["evidence"]["steps"]["adapter_ack"]["ok"]
assert outcome["evidence"]["not_live_acceptance"] is True
```

## State of the Art

| Old Approach (v1.8 / Phase 67) | Current Approach (v1.9 Phase 71) | When Changed | Impact |
|--------------------------------|----------------------------------|--------------|--------|
| Leaf smoke: signature + sender + feedback helper | Host Protocol-path smoke via Phase 70 helpers | Phase 71 | CI proves adapter/session/deliver wiring |
| No production webhook | Host composition shipped | Phase 70 | Smoke can call real host surface |
| Evidence steps: signature/send_*/callback only | + adapter_ack / session_ingress / adapter_deliver | Phase 71 | Allowlist must grow or Protocol fields are dropped |

**Deprecated/outdated:**
- Treating Phase 67 dry-run green as “host Protocol covered” — explicitly false for v1.9 SMOKE-01.
- Pre-Phase-70 STACK suggestion to build adapter+runtime only inside smoke without host helpers — superseded by success criterion 4 after Phase 70 landed.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Keeping Phase 67 leaf steps alongside Protocol steps is desired (STACK “Keep”) rather than replacing them | Standard Stack / Patterns | Planner may over-scope CLI; if user wants Protocol-only dry-run, leaf can be demoted to optional flag — confirm only if product pushes back |
| A2 | Optional runbook one-liner for Protocol dry-run is enough; full live docs stay Phase 72 | Touch set | Operators may be briefly confused until Phase 72 |

**If empty of blocking assumptions:** A1–A2 are non-blocking product preferences; implementation can keep leaf steps without user confirmation.

## Open Questions

1. **Should INTERACTION Protocol feedback be a required dry-run step or optional?**
   - What we know: Host composition tests cover both message and feedback branches; leaf `callback` already covers normalize-only.
   - What's unclear: Whether SMOKE-01 “ingress/session → deliver” implies message path only, or also host feedback branch.
   - Recommendation: **Require C2C message Protocol path** (ack→ingress→deliver). Add host feedback Protocol step as a cheap second fixture call in the same dry-run (reuses RecordingScheduler) — strengthens “same helpers webhook uses” without expanding scope to live ACK PUT.

2. **Where should new unittest classes live?**
   - What we know: `test_smoke_toolkit.py` is under qqbot package discover (`qqbot-channel` gate).
   - What's unclear: Whether host-gate should also assert smoke CLI.
   - Recommendation: Extend `test_smoke_toolkit.py` (CLI + importable `run_smoke`). Do not duplicate full Protocol matrix into `services/qqbot-service/tests` — host already has composition proofs; smoke tests prove CLI wiring.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | smoke CLI + unittest | ✓ | 3.14.6 | — |
| `pytest` (optional) | local runs | ✓ | present | Prefer `python3 -m unittest` (gate uses unittest) |
| In-repo `qqbot_service` | Protocol-path imports | ✓ (on disk) | 0.1.0 | Must add to smoke PYTHONPATH |
| In-repo Fake transports / FakeBackend | dry-run | ✓ | — | — |
| Network / live QQ | dry-run | ✗ not required | — | Must remain unused |
| New pip packages | — | N/A | — | Do not install |

**Missing dependencies with no fallback:** none

**Missing dependencies with fallback:** none (PYTHONPATH fix is a code change, not an external install)

Step 2.6 note: Phase needs no external services; only stdlib + in-repo packages.

## Validation Architecture

> `workflow.nyquist_validation` is enabled in `.planning/config.json`.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | stdlib `unittest` (gate) + optional pytest |
| Config file | none — discover-based |
| Quick run command | `python3 -m unittest packages.channels.qqbot.tests.test_smoke_toolkit -v` |
| Full suite command | `python3 scripts/smoke_test.py --dry-run` && `python3 -m unittest discover -s packages/channels/qqbot/tests -p 'test_smoke*.py'` && `python3 -m unittest discover -s services/qqbot-service/tests` (host still green) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SMOKE-01 | Dry-run CLI exits 0 | CLI | `python3 scripts/smoke_test.py --dry-run` | ✅ (leaf today; must still pass after Protocol) |
| SMOKE-01 | Protocol path uses Fake only (no Urllib) | unit | `…TestDryRunNoNetwork` + new Protocol class | ✅ partial / ❌ Wave 0 Protocol asserts |
| SMOKE-01 | Evidence includes adapter_ack → session_ingress → adapter_deliver ok | unit | new `TestProtocolPathDryRun` | ❌ Wave 0 |
| SMOKE-01 | Smoke calls host helpers (import qqbot_service / wired path) | unit | assert import + backend.submitted_requests / deliver | ❌ Wave 0 |
| SMOKE-02 | `not_live_acceptance=true`; schema v1 | unit | `TestEvidenceSchema` extended | ✅ partial |
| SMOKE-02 | Ban-list: no secrets/raw bodies/URLs/calls | unit | `TestEvidenceSanitized` + Protocol dirty payload | ✅ extend |
| SAFE cross | no wecom import via smoke path | unit | existing `test_no_wecom_import` host scan | ✅ (do not regress) |

### Sampling Rate

- **Per task commit:** `python3 scripts/smoke_test.py --dry-run` + `python3 -m unittest packages.channels.qqbot.tests.test_smoke_toolkit -v`
- **Per wave merge:** above + `python3 -m unittest discover -s services/qqbot-service/tests`
- **Phase gate:** Full suite green before `/gsd-verify-work`; never run `--live` in CI

### Wave 0 Gaps

- [ ] `TestProtocolPathDryRun` in `test_smoke_toolkit.py` — SMOKE-01 host Protocol steps present + Fake-only
- [ ] `TestEvidenceSchema` updated — Protocol step keys required under dry-run evidence
- [ ] `TestEvidenceSanitized` extended — Protocol composition dirty fields stripped
- [ ] Smoke PYTHONPATH includes `services/qqbot-service/src` (implementation prerequisite; assert via import in tests)

*(Existing leaf tests remain; they are not sufficient alone for Phase 71.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (dry-run fixtures only) | — |
| V3 Session Management | no | — |
| V4 Access Control | partial | Dual default-OFF knobs; smoke enables only inside fixture flags |
| V5 Input Validation | yes | Signed fixture bytes; allowlisted evidence schema; JSON fixture load |
| V6 Cryptography | yes (verify only) | Package Ed25519 via `verify_and_ack` — never hand-roll in smoke |

### Known Threat Patterns for smoke Protocol-path

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secret leakage in evidence/stdout | Information Disclosure | `_FORBIDDEN_EVIDENCE_KEYS` + `_BANNED_SUBSTRINGS` + allowlist |
| Accidental live network in CI | Spoofing / Abuse | Fake transports only; assert no Urllib class names |
| Raw legal payload in artifacts | Information Disclosure | Never record `content` / `body` / `payload` / envelopes |
| WeCom import coupling | Elevation of Privilege (boundary) | ADAPTER-04 / no-wecom tests; smoke imports qqbot_service only |
| False live acceptance | Repudiation | `not_live_acceptance=true` forced on dry-run |

## Sources

### Primary (HIGH confidence)
- `scripts/smoke_test.py` — current leaf dry-run + evidence allowlist (read 2026-07-10)
- `services/qqbot-service/src/qqbot_service/webhook.py` / `wiring.py` / `http_server.py` — Phase 70 composition surface
- `services/qqbot-service/tests/test_webhook_composition.py` — Fake Protocol-path pattern to reuse
- `packages/channels/qqbot/tests/test_smoke_toolkit.py` — existing SMOKE unittest map
- `.planning/REQUIREMENTS.md` — SMOKE-01 / SMOKE-02 text
- `.planning/ROADMAP.md` — Phase 71 success criteria
- `.planning/phases/71-smoke-protocol-path-hardening/71-CONTEXT.md` — discretion + defer live
- `.planning/research/STACK.md` / `FEATURES.md` / `PITFALLS.md` / `ARCHITECTURE.md` / `SUMMARY.md` — v1.9 smoke Protocol-path guidance
- `.planning/phases/70-webhook-composition-path/70-RESEARCH.md` / `70-VERIFICATION.md` — host helpers ready; smoke deferred

### Secondary (MEDIUM confidence)
- Phase 70 REVIEW note on `reply_text` / `reply_resolver` for smoke — already implemented in http_server/webhook

### Tertiary (LOW confidence)
- None material; graphify disabled (`graphify.enabled` false) — no graph cross-links used

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — reuse in-repo host + Fake stack; zero new packages
- Architecture: HIGH — Phase 70 helpers + success criterion 4 dictate host-helper path
- Pitfalls: HIGH — leaf-only / PYTHONPATH / reply window / evidence leakage verified in code + prior research

**Research date:** 2026-07-10
**Valid until:** 2026-08-09 (30 days — stable in-repo APIs)
