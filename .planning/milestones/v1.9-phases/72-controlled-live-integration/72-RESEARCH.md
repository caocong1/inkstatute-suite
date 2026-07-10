# Phase 72: Controlled Live Integration - Research

**Researched:** 2026-07-10
**Domain:** QQBot controlled `--live` smoke path, fail-closed env gates, operator runbook / HUMAN GATE semantics
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
All implementation choices are at the agent's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, Phase 71 smoke hardening, and existing live smoke fail-closed patterns to guide decisions.

CRITICAL: Do NOT mark live acceptance as complete. Do NOT redefine Phase 5/8 human gates as done. Autonomous phase completion must not require live evidence.

### Claude's Discretion
All implementation choices are at the agent's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, Phase 71 smoke hardening, and existing live smoke fail-closed patterns to guide decisions.

CRITICAL: Do NOT mark live acceptance as complete. Do NOT redefine Phase 5/8 human gates as done. Autonomous phase completion must not require live evidence.

### Deferred Ideas (OUT OF SCOPE)
None — discuss phase skipped. Actual live QQ operator runs remain HUMAN GATE outside autonomous completion.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LIVE-01 | Controlled `--live` path remains available with fail-closed env checks and is explicitly a HUMAN GATE (CI/phase complete must not auto-claim live acceptance) | Preserve `_run_smoke_live` + `load_live_credentials`; keep `not_live_acceptance=true` on script output; extend/assert HUMAN GATE markers in CLI help, runbook, tests, and VERIFICATION; never add live to CI/`run_v2_gates` |
| LIVE-02 | Operator runbook documents host enablement, dual-knob mapping, dry-run vs live, and interaction ACK safety windows | Close runbook gaps: dual-knob / host enablement (today only in `services/qqbot-service/README.md`); expand ACK/passive-reply safety windows; keep dry-run vs live table; add runbook content asserts |
</phase_requirements>

## Summary

Phase 72 is a **documentation + fail-closed preservation** phase, not a live-network delivery phase. The controlled `--live` path already exists from Phase 67 (`scripts/smoke_test.py` → `_run_smoke_live`, `load_live_credentials`, Urllib transports) and was intentionally left untouched by Phase 71 Protocol-path dry-run work. [VERIFIED: scripts/smoke_test.py; packages/channels/qqbot/tests/test_smoke_toolkit.py; 71-VERIFICATION.md]

What remains for LIVE-01/LIVE-02 is to (1) **preserve and explicitly mark** the live path as a HUMAN GATE so CI/phase complete cannot auto-claim acceptance, (2) **close operator-runbook gaps** for host enablement and dual-knob mapping (documented in host README but missing from `runbook/SMOKE_TEST_RUNBOOK.md`), and (3) **document interaction ACK / passive-reply safety windows** with the same constants the package already enforces. Live evidence, when an operator collects it, stays sanitized/reference-first and is never required for autonomous phase completion. Phase 5 live WeCom UAT and Phase 8 lawyer trial remain carried human gates — not redefined as v1.9 done. [CITED: .planning/REQUIREMENTS.md Out of Scope; .planning/ROADMAP.md Phase 72 SC-4]

**Primary recommendation:** Treat Phase 72 as runbook + assertion hardening over the existing `--live` fail-closed path — do not rewrite smoke live IO, do not require network runs for phase complete, and do not touch Phase 05/08 gate status.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Fail-closed live credential gate | API / Backend (CLI process edge) | — | `load_live_credentials` exits before Urllib construction; values never logged |
| Controlled `--live` OpenAPI Steps A–C | API / Backend (smoke CLI) | CDN / Static — | Leaf live path uses Urllib token/message transports; operator-only |
| Evidence sanitization / `not_live_acceptance` | API / Backend | — | `sanitize_evidence` allowlist + ban-list; script stamps `not_live_acceptance=true` even on live success |
| Host enablement / dual-knob mapping docs | API / Backend (host package) | — | `build_qqbot_channel_config` AND of platform flag + host config; document in operator runbook |
| Interaction ACK safety (fixture vs real id) | API / Backend (smoke + package sender) | — | Live PUT only with real non-fixture `interaction_id`; package `ack_interaction` |
| Passive-reply `msg_id` window | API / Backend (package sender) | — | `check_passive_reply_window` C2C 3600s/4, group 300s/5 |
| CI / phase-complete honesty | API / Backend (tests + VERIFICATION) | — | Dry-run only; HUMAN GATE markers; no live gate in `run_v2_gates` |
| Phase 5/8 carried human gates | Manual / HUMAN GATE | — | Preserve artifacts; never mark done from Phase 72 |

## Project Constraints (from .cursor/rules/)

No `.cursor/rules/` directory present in this workspace. [VERIFIED: filesystem]

Applicable project constraints from `AGENTS.md` (always applied):

- Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads.
- Contract logs / evidence prefer references (`raw_payload_ref`); no sensitive full text by default.
- Keep changes scoped to the active GSD phase and its plan.
- Do not introduce a new service, database, queue, or runtime dependency unless the V2 PRD or active GSD plan requires it.
- Update docs and GSD artifacts when implementation decisions change.
- High-risk legal feedback remains human-reviewed (`skill_candidate` only).

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python 3 stdlib (`argparse`, `os`, `json`, `urllib`) | 3.14.6 local [VERIFIED: `python3 --version`] | Smoke CLI + fail-closed env | Already used by `scripts/smoke_test.py`; no new deps |
| `inkstatute_channels_qqbot` | in-repo package | Signature, sender, feedback, Urllib transports, passive-reply windows | Owns channel IO; host/smoke compose only |
| `qqbot_service` | in-repo host | Dual-knob wiring, webhook composition, secret refs | Source of truth for host enablement docs |
| `unittest` + existing `test_smoke_toolkit.py` | stdlib / in-repo | Fail-closed + runbook content asserts | Already on `qqbot-channel` discover gate |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | 9.1.1 available [VERIFIED: `pytest --version`] | Optional local runner | Prefer existing `unittest discover` for qqbot-channel consistency |
| Markdown runbook | N/A | Operator enablement docs | `runbook/SMOKE_TEST_RUNBOOK.md` is the LIVE-02 surface |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Preserve leaf `--live` Steps A–C | Extend `--live` to full host Protocol path with Urllib | Out of scope / higher risk; Phase 72 is documentation + fail-closed preservation, not live host UAT |
| Document dual-knob only in host README | Duplicate into smoke runbook | LIVE-02 explicitly requires operator runbook coverage — cross-link + concise mapping table in runbook |
| Require live evidence for phase complete | Keep HUMAN GATE optional archive | Violates CRITICAL constraint and REQUIREMENTS Out of Scope |

**Installation:** None — no new packages. [VERIFIED: phase scope]

**Version verification:** N/A for new packages. Existing runtime: Python 3.14.6, pytest 9.1.1 present on research host.

## Package Legitimacy Audit

> No external packages are installed by this phase.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| — | — | — | — | — | — | N/A — no installs |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck not required — zero new package recommendations.*

## Architecture Patterns

### System Architecture Diagram

```text
Operator (HUMAN GATE)
    │
    ├─(A) Host enablement (production webhook)──────────────┐
    │     INKSTATUTE_QQBOT_CHANNEL_ENABLED                  │
    │     + RuntimeFeatureFlags.qqbot_channel_enabled       │
    │     + QQBotHostConfig.enabled  ──AND──► channel ON    │
    │     *_REF → resolve_secret_ref at process edge        │
    │     build_qqbot_wired_runtime → webhook /qqbot/callback
    │                                                       │
    └─(B) Controlled smoke --live (CLI)─────────────────────┤
          Export 5 VALUE env vars (not *_REF)               │
          Fresh REPLY_MSG_ID (passive-reply window)         │
          python3 scripts/smoke_test.py --live              │
                    │                                       │
                    ▼                                       │
          load_live_credentials() ──missing?──► SystemExit  │
                    │ (key names only)                      │
                    ▼                                       │
          UrllibTokenTransport + UrllibMessageTransport     │
          Steps: signature → send_text → send_keyboard      │
                 → callback normalize                       │
                 → optional ACK PUT iff real interaction_id │
                    │                                       │
                    ▼                                       │
          sanitize_evidence → mode=live                     │
          not_live_acceptance=true (script default)         │
          optional --evidence-out /tmp/...                  │
                    │                                       │
                    ▼                                       │
          Human may manually archive sanitized JSON         │
          (never required for CI / phase complete)          │
                                                            │
CI / autonomous phase gate ──► --dry-run ONLY ──────────────┘
                               Fake transports
                               not_live_acceptance=true
                               NEVER claims live acceptance
```

### Recommended Project Structure

```text
scripts/smoke_test.py                 # Preserve --live fail-closed path; HUMAN GATE help text
runbook/SMOKE_TEST_RUNBOOK.md         # LIVE-02: add host enablement + dual-knob + ACK windows
services/qqbot-service/README.md      # Canonical dual-knob detail (cross-link from runbook)
packages/channels/qqbot/tests/
  test_smoke_toolkit.py               # Extend runbook/HUMAN GATE asserts; keep fail-closed tests
.planning/phases/72-controlled-live-integration/
  72-VERIFICATION.md                  # Explicit: live NOT RUN; Phase 5/8 still carried
.planning/phases/08-lawyer-trial-acceptance/  # PRESERVE — do not delete or mark done
```

### Pattern 1: Fail-closed live env before any network

**What:** Validate all five `LIVE_ENV_KEYS` before constructing Urllib transports; exit with key **names** only.
**When to use:** Any `--live` entrypoint.
**Example:**

```python
# Source: scripts/smoke_test.py [VERIFIED: codebase]
LIVE_ENV_KEYS = (
    "INKSTATUTE_QQBOT_APP_ID",
    "INKSTATUTE_QQBOT_CLIENT_SECRET",
    "INKSTATUTE_QQBOT_BOT_SECRET",
    "INKSTATUTE_QQBOT_USER_OPENID",
    "INKSTATUTE_QQBOT_REPLY_MSG_ID",
)

def load_live_credentials() -> dict[str, str]:
    missing = [k for k in LIVE_ENV_KEYS if not os.environ.get(k)]
    if missing:
        raise SystemExit(
            "live mode requires env vars (values not shown): " + ", ".join(missing)
        )
    # ... return values; never log them
```

### Pattern 2: Dual-knob AND for host enablement

**What:** Channel enablement is `flags.qqbot_channel_enabled and host_config.enabled` (both default OFF).
**When to use:** Documenting production host enablement vs smoke CLI value-env injection.
**Example:**

```python
# Source: services/qqbot-service/src/qqbot_service/wiring.py [VERIFIED: codebase]
return QQBotChannelConfig(
    enabled=bool(flags.qqbot_channel_enabled and host_config.enabled),
    ...
)
```

### Pattern 3: Live evidence never auto-claims acceptance

**What:** Even successful `--live` stamps `not_live_acceptance=true`; human archival may relabel outside the script.
**When to use:** All smoke evidence writers and VERIFICATION reports.
**Example:**

```python
# Source: scripts/smoke_test.py _run_smoke_live [VERIFIED: codebase]
evidence = {
    "schema": EVIDENCE_SCHEMA,
    "mode": "live",
    "not_live_acceptance": True,  # Prefer keep true; human may relabel archive
    "steps": {...},
}
```

### Anti-Patterns to Avoid

- **Auto-claim live acceptance from dry-run or phase VERIFICATION:** Violates LIVE-01 and CRITICAL constraint.
- **Require live network for phase complete / CI:** Out of scope; PLAT-F03 deferred; REQUIREMENTS forbid auto-claim.
- **Document `*_REF` as smoke live env:** Smoke uses value vars; host uses refs — conflating them causes operator failure. [VERIFIED: runbook Credential section]
- **Invent interaction ids for live ACK PUT:** Fixture/demo ids must skip PUT (`_is_fixture_interaction_id`). [VERIFIED: smoke_test.py]
- **Mark Phase 5/8 complete:** Carried human gates; preserve `.planning/phases/08-lawyer-trial-acceptance/`. [CITED: REQUIREMENTS.md Out of Scope]
- **Rewrite `--live` into full Protocol host path this phase:** Scope creep; Phase 72 preserves controlled leaf live + documents enablement.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Live credential validation | Ad hoc per-step env checks after network | `load_live_credentials` before Urllib | Fail-closed + no secret echo already proven |
| Dual-knob enablement logic | New flag parser in smoke CLI | Document `build_qqbot_channel_config` AND | Host owns mapping; smoke is value-env CLI |
| Passive-reply window math | Re-document invented timeouts | Cite `sender.py` constants (C2C 3600/4, group 300/5) | Single source of truth in package |
| Evidence sanitization | New schema | Existing `sanitize_evidence` / allowlist | SMOKE-02 already hardened in Phase 71 |
| Live acceptance gate in CI | New `run_v2_gates` live entry | Keep `qqbot-channel` dry-run discover only | Auto-claim forbidden |

**Key insight:** The live path is already implemented; Phase 72's value is making HUMAN GATE / enablement / ACK-window semantics operator-visible and verification-honest without requiring live IO.

## Common Pitfalls

### Pitfall 1: Treating Phase 72 complete as live QQ acceptance

**What goes wrong:** VERIFICATION or SUMMARY claims “live integration done” because fail-closed tests pass.
**Why it happens:** Naming (“Controlled Live Integration”) sounds like live UAT.
**How to avoid:** VERIFICATION must state `Live QQ --live: NOT RUN (HUMAN GATE)` and `not_live_acceptance` remains true unless a human archives separately. Phase complete = docs + fail-closed asserts only.
**Warning signs:** Checklists requiring `/tmp/qqbot-smoke-live.json` or network evidence.

### Pitfall 2: Runbook documents smoke env but omits host dual-knob

**What goes wrong:** Operators enable only one knob or set smoke value vars on the host and expect webhook live IO.
**Why it happens:** Dual-knob lives in `services/qqbot-service/README.md`; smoke runbook only lists five value env vars. [VERIFIED: runbook vs host README gap]
**How to avoid:** Add a “Host enablement / dual-knob” section to `SMOKE_TEST_RUNBOOK.md` with AND table + cross-link to host README; assert cues in `test_smoke_toolkit.py`.
**Warning signs:** Runbook mentions `--live` but not `qqbot_channel_enabled` / `QQBotHostConfig.enabled`.

### Pitfall 3: Stale `msg_id` / fixture interaction ACK

**What goes wrong:** Live send fails outside passive-reply window; or ACK PUT uses fixture id and hits OpenAPI errors / no-ops incorrectly.
**Why it happens:** QQ C2C window is 3600s / max 4 replies; group 300s / max 5; smoke skips fixture ids but operators may paste stale envelopes. [VERIFIED: sender.py constants; `_is_fixture_interaction_id`]
**How to avoid:** Runbook “ACK safety windows” section: fresh `REPLY_MSG_ID`; ACK only with recent real `interaction_id`; treat ACK as optional follow-up.
**Warning signs:** Live exit non-zero with QQ passive-reply / invalid msg_id codes; `ack_status=sent` with fixture payloads.

### Pitfall 4: Redefining Phase 5/8 as v1.9 done

**What goes wrong:** Closing v1.9 milestone language implies WeCom UAT / lawyer trial complete.
**Why it happens:** Success criterion 4 is easy to skip in SUMMARY boilerplate.
**How to avoid:** Explicit VERIFICATION / SUMMARY bullets: Phase 05 live WeCom UAT and Phase 08 lawyer trial remain carried; `.planning/phases/08-lawyer-trial-acceptance/` preserved.
**Warning signs:** REQUIREMENTS checkboxes for Phase 5/8 flipped; deletion of Phase 08 artifacts.

### Pitfall 5: Secret echo in fail-closed messages

**What goes wrong:** Partial env prints planted secret values.
**Why it happens:** Error formatting includes `os.environ` values.
**How to avoid:** Keep existing key-name-only `SystemExit`; retain `TestLiveEnvFailClosed` planted-secret asserts. [VERIFIED: test_smoke_toolkit.py]
**Warning signs:** Test failures on `assertNotIn(planted, combined)`.

## Code Examples

### Fail-closed CLI proof (no network)

```bash
# Source: research host verification 2026-07-10 [VERIFIED: shell]
python3 scripts/smoke_test.py --live
# → exit 1
# → "live mode requires env vars (values not shown): INKSTATUTE_QQBOT_APP_ID, ..."
```

### Dry-run remains CI gate

```bash
# Source: research host verification 2026-07-10 [VERIFIED: shell]
python3 scripts/smoke_test.py --dry-run
# → exit 0; mode=dry-run; not_live_acceptance=true
# → steps include adapter_ack, session_ingress, adapter_deliver
```

### Recommended runbook cues to assert (LIVE-02)

```python
# Planner should extend TestRunbookExists / new TestLiveRunbookHumanGate
REQUIRED_LIVE_CUES = (
    "human gate",
    "dual-knob",           # or "dual knob" / "qqbot_channel_enabled"
    "host enable",         # host enablement section
    "dry-run",
    "ack",                 # interaction ACK safety
    "passive-reply",       # or "msg_id" window
    "not_live_acceptance",
)
# Do NOT assert presence of live evidence files under .planning/
```

### Passive-reply window constants (document, don't reimplement)

```python
# Source: packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py [VERIFIED: codebase]
_C2C_MAX_AGE_SECONDS = 3600
_C2C_MAX_REPLIES = 4
_GROUP_MAX_AGE_SECONDS = 300
_GROUP_MAX_REPLIES = 5
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Leaf-only dry-run claimed host-complete | Protocol-path dry-run via host webhook helpers | Phase 71 (2026-07-10) | CI proves composition; live still Phase 72 |
| Live path undocumented relative to dual-knob | Runbook must map smoke value-env vs host REF + dual-knob | Phase 72 (this phase) | Operators can enable safely without auto-claim |
| Auto live acceptance from CI | Explicit HUMAN GATE; `not_live_acceptance=true` | Phase 67+ policy | False production readiness prevented |

**Deprecated/outdated:**

- Treating Phase 67 evidence archive path as mandatory CI artifact — optional human archival only. [VERIFIED: runbook Evidence section]
- Inventing a new V2 live gate in `run_v2_gates.py` — intentionally not added in Phase 71; keep that decision. [CITED: 71-VERIFICATION.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Exact QQ OpenAPI interaction-ACK wall-clock SLA beyond package passive-reply constants is not separately codified in-repo; runbook should cite package windows + “recent INTERACTION_CREATE” rather than inventing a new timeout number | Pitfalls / LIVE-02 | Operators may still hit vendor-side ACK expiry; document as “use fresh payload” without claiming an unverified second timeout |
| A2 | Two–three fine-grained plans (preserve asserts / runbook / verification honesty) is sufficient granularity for this docs-heavy phase | Open Questions | Planner may prefer a single plan — low risk |

**If this table is empty:** N/A — two assumptions logged.

## Open Questions

1. **Should `--live` also exercise host Protocol path with Urllib?**
   - What we know: Current `--live` is leaf Steps A–C (signature/send/callback); dry-run owns Protocol path with Fakes. [VERIFIED: smoke_test.py]
   - What's unclear: Whether operators need live host webhook UAT in v1.9.
   - Recommendation: **No for Phase 72.** Preserve leaf `--live`; document host enablement separately. Live host Protocol UAT would be a future HUMAN GATE, not autonomous scope.

2. **Where should optional live evidence be archived if collected?**
   - What we know: Runbook still points at `.planning/phases/67-one-click-smoke-test-toolkit/evidence/`. [VERIFIED: runbook]
   - What's unclear: Whether Phase 72 should add `72-.../evidence/` template.
   - Recommendation: Keep Phase 67 path or add optional `72-.../evidence/` note — either is fine; **never require** the file for phase complete. Prefer not inventing a second mandatory path.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | smoke CLI + unittest | ✓ | 3.14.6 | — |
| pytest | optional runner | ✓ | 9.1.1 | use `python3 -m unittest` |
| `scripts/smoke_test.py --dry-run` | CI honesty | ✓ | exit 0 verified | — |
| `scripts/smoke_test.py --live` fail-closed | LIVE-01 | ✓ | exit 1 without env | — |
| Live QQ network / real credentials | Operator HUMAN GATE only | ✗ / not required | — | Do not block phase; document only |
| Graphify knowledge graph | research enrichment | ✗ disabled | — | Codebase grep / prior phase artifacts |

**Missing dependencies with no fallback:**
- None for autonomous Phase 72 completion.

**Missing dependencies with fallback:**
- Live QQ credentials / network — HUMAN GATE only; phase uses fail-closed + docs.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | unittest (stdlib) via `qqbot-channel` discover gate |
| Config file | none — discover under `packages/channels/qqbot/tests/` |
| Quick run command | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:services/qqbot-service/src:services/feedback-service/src" python3 -m unittest packages.channels.qqbot.tests.test_smoke_toolkit -v` |
| Full suite command | Same module + `python3 scripts/smoke_test.py --dry-run` |

*(Exact PYTHONPATH may match existing test harness / `run_v2_gates.py` qqbot-channel entry — reuse gate; do not add live gate.)*

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LIVE-01 | `--live` without full env exits non-zero; no secret echo | unit/CLI | `TestLiveEnvFailClosed` | ✅ |
| LIVE-01 | `load_live_credentials` exists; Urllib only behind live | unit | `test_load_live_credentials_helper_and_urllib_wiring` | ✅ |
| LIVE-01 | Live success evidence keeps `not_live_acceptance=true` (script) | unit / source assert | Extend if missing explicit live-mode sanitize assert | ❌ Wave 0 — add assert on `_run_smoke_live` / sanitize live branch |
| LIVE-01 | CI/phase docs mark HUMAN GATE; dry-run never claims live | unit + VERIFICATION | Extend runbook/CI honesty tests; VERIFICATION template | ❌ Wave 0 — extend cues |
| LIVE-02 | Runbook documents host enablement + dual-knob | unit (content) | Extend `TestRunbookExists` / new class | ❌ Wave 0 — headings/cues missing today |
| LIVE-02 | Runbook documents dry-run vs live | unit (content) | Existing headings include dry-run/live | ✅ partial |
| LIVE-02 | Runbook documents ACK safety windows + passive-reply | unit (content) | Extend asserts for ack/window cues | ❌ Wave 0 — expand section |
| SAFE carry | Phase 08 dir preserved; Phase 5/8 not marked done | verification / path assert | VERIFICATION checklist + optional `test_phase08_dir_present` if desired | ✅ dir present; assert optional |

### Sampling Rate

- **Per task commit:** `python3 -m unittest … test_smoke_toolkit -v` (fail-closed + runbook asserts)
- **Per wave merge:** same + `python3 scripts/smoke_test.py --dry-run`
- **Phase gate:** Full toolkit green; VERIFICATION explicitly records live NOT RUN; Phase 5/8 still carried

### Wave 0 Gaps

- [ ] Extend `test_smoke_toolkit.py` runbook cues for dual-knob / host enablement / ACK safety / HUMAN GATE (LIVE-02)
- [ ] Optional explicit assert that `_run_smoke_live` evidence dict sets `not_live_acceptance=True` (LIVE-01)
- [ ] VERIFICATION template language: live NOT RUN; Phase 05/08 carried — not a test file, but required phase gate artifact
- [ ] Do **not** add live network integration tests
- [ ] Framework install: none

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (token/app credentials) | Value env at process edge; never commit; fail-closed missing keys |
| V3 Session Management | no (smoke CLI ephemeral) | — |
| V4 Access Control | yes | Dual-knob default OFF; `--live` HUMAN GATE; CI dry-run only |
| V5 Input Validation | yes | Env key presence; fixture interaction id rejection; sanitize allowlist |
| V6 Cryptography | yes (Ed25519 BotSecret) | Package signature helpers; never log BotSecret |

### Known Threat Patterns for QQBot live smoke

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secret echo in CLI errors | Information Disclosure | Key-name-only SystemExit; planted-secret tests |
| Accidental live IO from CI | Elevation / Spoofing readiness | Default `--dry-run`; no live gate; HUMAN GATE markers |
| Dual-knob desync / single-knob enable | Elevation of Privilege | Document AND mapping; host strips transports when OFF |
| Raw payload / URL in evidence | Information Disclosure | `sanitize_evidence` ban-list; reference-first archival |
| Stale msg_id / forged interaction ACK | Tampering / Denial | Passive-reply window; fixture id skip; optional ACK only |
| False live acceptance claim | Repudiation | `not_live_acceptance=true` from script; human archive decision |

## Sources

### Primary (HIGH confidence)

- `scripts/smoke_test.py` — `LIVE_ENV_KEYS`, `load_live_credentials`, `_run_smoke_live`, `_step_callback_live`, sanitize stamps [VERIFIED: codebase]
- `runbook/SMOKE_TEST_RUNBOOK.md` — dry-run/live/evidence sections; gap on dual-knob/host enablement [VERIFIED: codebase]
- `services/qqbot-service/README.md` + `wiring.py` — dual-knob AND + live injection [VERIFIED: codebase]
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py` — passive-reply constants [VERIFIED: codebase]
- `packages/channels/qqbot/tests/test_smoke_toolkit.py` — fail-closed + runbook heading tests [VERIFIED: codebase]
- `.planning/REQUIREMENTS.md` LIVE-01/02 + Out of Scope Phase 5/8 [CITED]
- `.planning/ROADMAP.md` Phase 72 success criteria [CITED]
- `.planning/phases/71-smoke-protocol-path-hardening/71-VERIFICATION.md` — live deferred to Phase 72 [CITED]
- `.planning/phases/72-controlled-live-integration/72-CONTEXT.md` — CRITICAL constraints [CITED]
- Shell probes 2026-07-10: `--live` exit 1 without env; `--dry-run` exit 0 with Protocol steps [VERIFIED: shell]

### Secondary (MEDIUM confidence)

- `.planning/milestones/v1.8-phases/67-one-click-smoke-test-toolkit/67-RESEARCH.md` — original HUMAN GATE / OQ-1 ACK optional follow-up [CITED]
- `.planning/research/FEATURES.md` — controlled live HUMAN GATE feature intent [CITED]

### Tertiary (LOW confidence)

- Exact vendor-side interaction ACK expiry beyond package windows — not separately documented in-repo [ASSUMED: A1]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; existing smoke/host stack verified on disk
- Architecture: HIGH — live path, dual-knob, evidence stamps, and CI boundary verified in code
- Pitfalls: HIGH — drawn from Phase 67/71 research + confirmed runbook gap + REQUIREMENTS Out of Scope

**Research date:** 2026-07-10
**Valid until:** 2026-08-09 (30 days — stable docs/preservation phase)
