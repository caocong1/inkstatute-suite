# Pitfalls Research: v1.9 QQBot Host Composition

**Domain:** Adding a thin production QQBot webhook host, runtime channel registration, full-path smoke Protocol hardening, and controlled live QQ integration on top of the shipped v1.8 package-level QQBot loop.
**Researched:** 2026-07-09
**Confidence:** HIGH

This research covers common mistakes when **composing host-level production paths around existing packages** — not re-implementing Ed25519, normalization, sender, or session logic. v1.8 already shipped those as composable modules (`packages/channels/qqbot`, 321 unit tests, `dependencies=[]`, ADAPTER-04 no-wecom, Protocol freeze, flag default OFF) with audit status `gaps_found`: no production webhook host, no `DefaultRunRuntime.channels` registration / flag→config mapping, and smoke `--dry-run` that exercises leaf helpers only. v1.9 must close those gaps without unfreezing Protocols, without leaking WeCom into qqbot, without deleting Phase 08 lawyer-trial artifacts, and without auto-claiming live QQ acceptance.

Suggested phase themes (roadmap may renumber): **HOST** (thin webhook composition), **REG** (runtime registration + dual-knob mapping), **SMOKE** (Protocol-path dry-run), **LIVE** (controlled `--live` human gate), **SAFETY** (freeze / secrets / Phase-08 preservation).

---

## Critical Pitfalls

### Pitfall 1: Building a fat host that reimplements package logic

**What goes wrong:**
The host re-copies signature verification, normalization, token refresh, sender envelopes, or session resolution instead of calling `QQBotChannelAdapter.verify_and_ack` / `normalize_inbound` / `deliver`, `QQBotRuntimeIngress.handle_callback`, and `handle_feedback_callback`. Two divergent code paths appear: unit tests stay green on the package while production webhook behavior drifts. Bugs fixed in v1.8 modules never reach the live host.

**Why it happens:**
v1.8 modules look “library-only” and hosts feel incomplete without local logic. WeCom’s `services/wecom-service` is a large reference, so developers clone its shape instead of a thin compose layer over already-complete qqbot packages.

**How to avoid:**
- Keep the host as orchestration only: HTTP raw body + headers → `RawInbound` → `verify_and_ack` → (message) ingress/session → `deliver`; (interaction) `handle_feedback_callback` → optional interaction ACK.
- Do not duplicate Ed25519, envelope builders, or `SessionScope` construction in the host.
- Place the host under `services/` (or a thin `scripts`/entry module that imports packages), never thicken `packages/channels/qqbot` with a server framework.

**Warning signs:**
- Host file contains `derive_keypair`, `normalize_message_event`, or copy-pasted SHA/Ed25519 helpers.
- Host tests mock QQ OpenAPI instead of composing Fake transports through the adapter.
- Package README still says “host maps flag→config” but no host code does that mapping.

**Phase to address:**
HOST — first composition plan must wire existing public APIs only.

---

### Pitfall 2: Treating package-green as “deployed webhook host complete”

**What goes wrong:**
Teams ship v1.9 claiming production QQBot readiness because 321 package tests and leaf smoke pass. Operators still have no single HTTPS callback that joins ACK → ingress/session/feedback → deliver. The v1.8 audit gap is papered over with “modules exist.”

**Why it happens:**
v1.8 phase success criteria were package-scoped by design. Habit is to treat unittest green as product-complete.

**How to avoid:**
- Define done as: one host entrypoint that composes the full path under default-OFF flags, plus a dry-run that calls adapter + session Protocol surfaces.
- Keep “live QQ acceptance” out of done; require operator evidence for LIVE.
- Re-run the v1.8 audit gap checklist as v1.9 exit criteria.

**Warning signs:**
- ROADMAP/REQUIREMENTS mark HOST-* complete without a webhook handler module.
- Smoke evidence steps still only list `signature` / `send_text` / `send_keyboard` / `callback` leaf helpers.
- No process binds an HTTPS path QQ can call for `op=13` and `op=0`/`12`.

**Phase to address:**
HOST + milestone verification — explicit “host composition present” gate.

---

### Pitfall 3: Dual-knob desync (`RuntimeFeatureFlags` vs `QQBotChannelConfig`)

**What goes wrong:**
Host enables `RuntimeFeatureFlags.qqbot_channel_enabled=True` but constructs `QQBotChannelAdapter(QQBotChannelConfig())` (still `enabled=False`), or the reverse. ACK/delivery stay refused (`503`) while operators believe the platform flag is on. Or config is enabled without injecting `token_manager` + `transport`, so `_live_io_ready()` stays false and the adapter remains fixture-only.

**Why it happens:**
README already documents that the adapter gates solely on `QQBotChannelConfig.enabled` (+ injected transports) and does **not** import `RuntimeFeatureFlags`. Host authors forget the mapping. Dual defaults both `False` hide the bug until someone opts in one knob only.

**How to avoid:**
- Host construction must be: `QQBotChannelConfig(enabled=flags.qqbot_channel_enabled, …refs…)` plus injected Fake/Urllib transports when live IO is intended.
- Add a REG-phase test: flag True → config.enabled True → with transports, `capabilities().metadata["network_io"]` is True; flag False → ACK refused.
- Never teach the adapter to import `RuntimeFeatureFlags` (keeps package embeddable and freeze-safe).

**Warning signs:**
- Host reads only `INKSTATUTE_QQBOT_CHANNEL_ENABLED` into flags but not into `QQBotChannelConfig`.
- Health reports `fixture_only=True` after “enabling” the channel in ops docs.
- Registration inserts an adapter into `channels=` that cannot deliver.

**Phase to address:**
REG — flag→config mapping + transport injection tests.

---

### Pitfall 4: Registering into `DefaultRunRuntime.channels` without a real host path

**What goes wrong:**
Someone adds `QQBotChannelAdapter` to `DefaultRunRuntime(..., channels=(adapter,))` in a unit test or factory and calls that “runtime registration.” Outbound `deliver` may be reachable from the runtime, but inbound QQ webhooks never hit `verify_and_ack` → ingress. Operators still cannot register a callback URL.

**Why it happens:**
`DefaultRunRuntime` already accepts `channels=()`; it is the most visible “registration” hook. Inbound webhook ownership is easy to forget because WeCom also separates ingress service from runtime.

**How to avoid:**
- Treat REG as two deliverables: (1) flag→config factory that builds a live-ready adapter, (2) HOST webhook that uses that factory and calls ingress after ACK.
- Document that `channels=` enables runtime-mediated delivery, not QQ platform callback receipt.
- Integration test: simulated HTTP callback → adapter ACK → `QQBotRuntimeIngress.handle_callback` → (fake) deliver.

**Warning signs:**
- Only constructor/unit changes under `platform-runtime` with no HTTP/webhook module.
- Ingress tests remain package-only; no host-level composition test.

**Phase to address:**
REG after or with HOST — registration without webhook is incomplete.

---

### Pitfall 5: HTTP host breaks Ed25519 by consuming/re-serializing the body

**What goes wrong:**
Framework middleware parses JSON first; the host verifies signature over `json.dumps(parsed)` or a second read of an empty body. Validation (`op=13`) or event verify fails intermittently. Worse: host skips verify “temporarily” to get URL registration working — forging risk (seen in other QQ webhook products that only sign the challenge and never verify pushes).

**Why it happens:**
Package tests pass raw bytes/fixtures into `verify_and_ack`. Real ASGI/WSGI stacks make raw-body access awkward. Pressure to pass QQ console URL validation encourages verify bypass.

**How to avoid:**
- Read **raw body bytes once**; pass the same bytes into signature verify; parse JSON only after.
- Map `X-Signature-Ed25519` / `X-Signature-Timestamp` into `RawInbound` metadata exactly as the adapter expects.
- Fail closed on missing/invalid signature for non-challenge traffic; never ship `VERIFY_SIGNATURE=false` as default.
- Host tests: official demo vector through the HTTP handler, not only through `signature.py`.

**Warning signs:**
- Host calls `await request.json()` before verify.
- Logs show verify failures only in production, never in unit tests.
- Feature flag or env to disable signature verification defaults on.

**Phase to address:**
HOST — raw-body contract in the first webhook plan.

---

### Pitfall 6: Host ACK path too slow or wrong shape for `op=13` / two-tier ACK

**What goes wrong:**
Host awaits full Hermes/agent work inside the webhook request before returning. QQ retries or drops the callback. Or host always returns generic `{"op":12}` for validation challenges, so callback URL registration never succeeds. Or interaction events get webhook ACK but never `PUT /interactions/{id}` when live IO is on.

**Why it happens:**
Package adapter already encodes challenge + two-tier ACK, but the host must return the adapter’s response body/status promptly and must not block on agent completion. Long legal tasks tempt synchronous handling.

**How to avoid:**
- Webhook handler: verify_and_ack → return ACK/challenge body immediately; schedule ingress/agent/deliver asynchronously (same pattern as WeCom quick-ACK + control plane).
- Assert `op=13` responses contain `plain_token` + hex signature from adapter metadata/body.
- Live path: preserve adapter’s `op12_plus_interaction_put` behavior; dry-run must not perform real PUT (existing smoke invariant).

**Warning signs:**
- Single request spans agent `submit_run` before HTTP response.
- QQ console validation fails while package `handle_validation_challenge` tests pass.
- Smoke live evidence shows interaction without ack step.

**Phase to address:**
HOST (fast ACK) + LIVE (two-tier ACK evidence).

---

### Pitfall 7: Smoke “hardening” that still only hits leaf helpers — or hits the network in CI

**What goes wrong:**
Dry-run is extended with more sender/token assertions but still never calls `QQBotChannelAdapter` Protocol methods or `QQBotRuntimeIngress` / session runtime. False confidence returns. Alternatively, “full path” smoke accidentally constructs `Urllib*` transports in default CI, flaking or leaking credentials.

**Why it happens:**
Current `scripts/smoke_test.py` is explicitly leaf-oriented (signature, Fake egress, feedback helper). Extending steps is easier than composing adapter+ingress. Live env vars in developer shells leak into CI.

**How to avoid:**
- SMOKE dry-run must invoke: `verify_and_ack` + `normalize_inbound` (or ingress `handle_callback`) + `deliver` with Fake transports, and record Protocol-path steps in sanitized evidence.
- Keep `--live` fail-closed: missing env → non-zero exit before Urllib construction (existing pattern).
- CI runs only `--dry-run`; never auto-run `--live`.
- Evidence must keep `not_live_acceptance: true` for dry-run; forbid secret substrings (existing allowlist).

**Warning signs:**
- Evidence `steps` keys unchanged from v1.8 leaf set.
- Import graph of dry-run still avoids `QQBotChannelAdapter` / `QQBotRuntimeIngress`.
- CI job passes `INKSTATUTE_QQBOT_*` value secrets.

**Phase to address:**
SMOKE — Protocol-path dry-run as explicit requirement.

---

### Pitfall 8: Auto-claiming live QQ acceptance from `--live` exit 0

**What goes wrong:**
A green `scripts/smoke_test.py --live` (or a single successful C2C send) is written into VERIFICATION/UAT as “QQBot production accepted.” Milestone done definition absorbs a human gate. Parallel Phase 05/08 WeCom gates get confused with QQ live.

**Why it happens:**
Operators want a checkbox; smoke toolkit looks like acceptance. v1.8 already deferred live as HUMAN GATE; pressure returns in v1.9.

**How to avoid:**
- LIVE phase delivers capability + runbook + sanitized evidence schema only.
- Acceptance requires human-signed evidence (operator, timestamp, bot app id ref, scenario list); automation may only produce candidate evidence with `not_live_acceptance` / explicit human-gate markers unless an operator flips a documented acceptance artifact.
- Do not mark Phase 08 lawyer-trial or Phase 05 WeCom UAT complete from QQ smoke.

**Warning signs:**
- REQUIREMENTS traceability shows LIVE-* “Complete” from CI alone.
- Evidence JSON lacks operator attestation fields but STATUS says accepted.
- Phase 08 directory cleared or “superseded by QQ.”

**Phase to address:**
LIVE — human gate protocol; SAFETY — preserve Phase 08 artifacts.

---

### Pitfall 9: Unfreezing ChannelAdapter / BackendAdapter to “make the host fit”

**What goes wrong:**
Host needs a new hook (e.g. `handle_webhook`, `register`, streaming QQ events), so someone adds a 7th `ChannelAdapter` method or mutates BackendAdapter. `test_contract_freeze_not_violated.py` and contract-test-suite baselines fail or are weakened. Every channel/backend implementer pays the tax.

**Why it happens:**
Composition friction feels like a Protocol gap. Extending the Protocol seems cleaner than adapting HTTP↔existing six methods.

**How to avoid:**
- Keep Protocol at exactly 6 channel methods / 9 backend methods unless a phase explicitly changes scope and updates freeze tests + all implementers.
- Put HTTP/webhook specifics in the host; keep adapter methods as the only channel boundary.
- If a new host-facing helper is needed, add a plain function/class in qqbot or the service — not a Protocol method.

**Warning signs:**
- PR touches `packages/platform-runtime/src/platform_runtime/protocols.py` method set.
- Freeze tests rewritten to expect 7 methods “temporarily.”
- WeCom/web_sse adapters forced to stub new methods.

**Phase to address:**
SAFETY (baseline) — reaffirm freeze before HOST/REG work.

---

### Pitfall 10: WeCom import leakage into `packages/channels/qqbot` (ADAPTER-04)

**What goes wrong:**
Host author “reuses” WeCom ingress/session/output helpers by importing `wecom_service` from qqbot package modules, or moves host code into the qqbot package and pulls WeCom types. ADAPTER-04 and `test_no_wecom_import.py` fail — or worse, tests are narrowed so only old modules are scanned.

**Why it happens:**
WeCom is the only full service reference. Shared need (output policy, session patterns) already lives in `channel-core` / `platform-runtime`; people still reach for `wecom_service`.

**How to avoid:**
- Host may depend on qqbot + platform-runtime + channel-core + feedback-service; qqbot package must not import `wecom_service`.
- Reuse `channel_core.output_policy` / `owned_notices`, not WeCom-only modules.
- Extend `test_no_wecom_import.py` to any new qqbot production modules; keep `dependencies=[]` unless a phase explicitly adds optional extras outside the frozen package invariant.

**Warning signs:**
- `wecom_service` string in new qqbot `.py` files.
- pyproject `dependencies` no longer `[]`.
- Host logic merged into `packages/channels/qqbot/src` with HTTP framework deps.

**Phase to address:**
SAFETY + HOST — isolation tests on every new module.

---

### Pitfall 11: Hermes meta/gateway notices leak on the new QQ deliver path

**What goes wrong:**
Host wires backend results straight to `deliver` without `apply_output_policy` / owned notices. Ordinary QQ users see Hermes update/command/help/status text. WeCom path stays clean; QQ becomes the leak channel.

**Why it happens:**
Adapter already applies policy in some deliver branches; host-level “shortcut deliver” or raw backend stdout bypasses it. New composition forgets the boundary that WeCom learned the hard way.

**How to avoid:**
- Every user-visible QQ egress goes through the same output-boundary rules as WeCom (`channel_core.apply_output_policy`).
- Host must not send backend meta strings via a side channel (raw OpenAPI call outside adapter.deliver).
- Add a host/SMOKE fixture where backend yields a gateway-like notice and assert deliver content is owned-notice or blocked, not raw meta.

**Warning signs:**
- Host calls `send_message` directly with backend stdout.
- Deliver tests only cover happy-path legal text.
- Capability docs claim “parity with WeCom output boundary” without a failing-meta fixture.

**Phase to address:**
HOST (boundary on compose) + SMOKE (meta fixture).

---

### Pitfall 12: Deleting or “archiving away” Phase 08 lawyer-trial directory

**What goes wrong:**
Milestone cleanup treats `.planning/phases/08-lawyer-trial-acceptance/` as stale V2 noise and removes it while adding QQ host work. Carried human-gate evidence and templates disappear; STATE.md continuity breaks.

**Why it happens:**
v1.9 focus is QQ; Phase 08 is WeCom lawyer trial and looks unrelated. Aggressive `.planning` hygiene.

**How to avoid:**
- Explicit SAFETY constraint: do not delete Phase 08 directory; QQ live does not replace it.
- Milestone scripts/checklists list Phase 08 as carry-forward, not in-scope delete.
- If moving artifacts, copy+link — never unlink without human approval.

**Warning signs:**
- Git status shows deleted `08-*` UAT/evidence templates.
- STATE.md “Parallel Human Gate” section removed “to simplify.”

**Phase to address:**
SAFETY — continuous; verify at milestone open/close.

---

### Pitfall 13: Committing secrets, tokens, runtime DBs, or raw payloads via host/smoke

**What goes wrong:**
Host `.env.example` gets real values; smoke evidence includes `Authorization`, openids, message bodies, or callback payloads; runbooks paste bot secrets. Repo and CI logs become secret stores.

**Why it happens:**
Live debugging needs real credentials; evidence “helpfulness” fights sanitization. v1.8 smoke already bans many keys — host logs are a new surface.

**How to avoid:**
- Secrets only via external env/secret manager; config carries `*_ref` only.
- Reuse smoke sanitizer allowlists for host debug evidence; hash openids; drop raw bodies.
- Pre-commit / tests: refuse forbidden evidence keys; scan for `DEMO_BOT_SECRET` only as public vector in tests, never as production secret.

**Warning signs:**
- `INKSTATUTE_QQBOT_CLIENT_SECRET` value in repo files.
- Evidence JSON contains `http://` or `access_token`.
- Host writes callback JSONL with full `raw_payload`.

**Phase to address:**
HOST + SMOKE + LIVE — sanitization as exit criterion.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Leaf-only smoke | Fast green CI | False production confidence | Never as HOST/SMOKE done |
| Flag on without transport injection | Looks “enabled” | Silent fixture-only mode | Never in production host |
| Sync agent inside webhook | Simpler code | QQ retries, timeouts, duplicate turns | Never for legal long tasks |
| Disable signature verify to pass URL check | Unblocks console setup | Forged inbound turns | Never |
| Import WeCom helpers into qqbot | Faster copy | ADAPTER-04 break, channel coupling | Never |
| Claim live from `--live` exit 0 | Instant “done” | Fake acceptance, safety bypass | Never |
| Add Protocol method for webhook | Feels clean | Freeze break across channels | Only if explicit unfreeze phase |
| In-process wakeup store only | No deps | Multi-worker recall wrong | Dev-only; document durable store for multi-instance |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| QQ HTTPS callback | Host returns HTML/framework 200 without challenge body | Return adapter challenge JSON for `op=13`; fast ACK for events |
| QQ webhook vs WebSocket | Enable both or wrong mode | Webhook XOR WebSocket on QQ side; InkStatute v1.9 is webhook host |
| Raw body signature | Verify parsed JSON | Verify `timestamp + raw_body` bytes ([QQ sign docs](https://bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/sign.html)) |
| `DefaultRunRuntime.channels` | Treat as inbound webhook registration | Use for delivery registration; pair with HOST ingress |
| Dual enable knobs | Flip only platform flag | Map flag → `QQBotChannelConfig.enabled` + inject transports |
| Feedback INTERACTION | Message path only in host | Compose `handle_feedback_callback` + live interaction ACK |
| Output boundary | Direct OpenAPI send from host | Only `adapter.deliver` / policy-wrapped content |
| Smoke `--live` | Run in CI / mark UAT complete | Operator-only; human gate evidence |
| Phase 08 carry | Delete trial dir during QQ milestone | Preserve `.planning/phases/08-lawyer-trial-acceptance/` |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Blocking webhook on Hermes | QQ retries, duplicate AgentTurns | ACK first, async run | First long legal answer |
| Token fetch on every deliver | Latency spikes, 401 bursts | Reuse `TokenManager` cache in host-scoped singleton | Moderate traffic |
| In-memory idempotency only | Duplicate turns after restart/multi-worker | Durable idempotency key store at host | >1 worker or restart mid-retry |
| Passive reply after window | `MSG_EXPIRE` / silent fail | Respect scene windows; owned notice / active strategy | Group >5m, C2C >60m |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Skip Ed25519 on pushes | Forged lawyer turns / feedback ([prior art](https://github.com/lobehub/lobehub/issues/16538)) | Mandatory verify; no default bypass |
| Commit bot/client secrets | Credential theft, impersonation | Refs only; env outside repo |
| Raw legal text in host logs | Privacy / compliance breach | `raw_payload_ref`, hash, allowlisted evidence |
| Host enables channel by default | Accidental production exposure | Flags/config default OFF |
| Meta notice leak on QQ | Users see Hermes operator UI | `apply_output_policy` on all egress |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Validation fails, bot never receives | “QQ bot is dead” with no events | Correct `op=13` host response + runbook |
| Slow ACK then silence | User retries, duplicate asks | Fast ACK + owned progress notice |
| Live smoke marked accepted, bot still OFF | Operators think done; users blocked | Human gate checklist separate from enablement |
| Feedback buttons no ACK | Keyboard clicks feel broken | Two-tier interaction ACK on live path |

## "Looks Done But Isn't" Checklist

- [ ] **Production webhook host:** Exists and composes `verify_and_ack` → ingress/session/feedback → `deliver` — verify one module path, not only package unit tests.
- [ ] **Flag→config mapping:** `qqbot_channel_enabled` True constructs `QQBotChannelConfig(enabled=True)` — verify REG test.
- [ ] **Transport injection:** Live-ready adapter has `token_manager` + `transport` so `_live_io_ready()` is True — verify capabilities `network_io`.
- [ ] **Raw-body verify:** HTTP handler verifies demo vector without re-serialization — verify host-level test.
- [ ] **op=13 through host:** Challenge response returned on webhook — verify console registration or fixture HTTP test.
- [ ] **Smoke Protocol path:** Dry-run evidence includes adapter/session steps — verify step keys / import calls.
- [ ] **Dry-run non-acceptance:** Evidence has `not_live_acceptance: true` — verify sanitizer.
- [ ] **Live is human gate:** No REQUIREMENT marked accepted from CI `--live` alone — verify traceability notes.
- [ ] **Protocol freeze:** Still 6 ChannelAdapter methods — verify `test_contract_freeze_not_violated.py`.
- [ ] **No wecom in qqbot:** New modules pass `test_no_wecom_import.py` — verify AST scan scope includes them.
- [ ] **Output boundary:** Meta fixture blocked on QQ deliver path — verify policy test.
- [ ] **Phase 08 preserved:** `.planning/phases/08-lawyer-trial-acceptance/` still present — verify tree.
- [ ] **Secrets:** No value secrets in repo/evidence — verify smoke forbidden keys + git scan.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Fat host drift | HIGH | Delete duplicated logic; rewire to package APIs; add composition tests |
| Dual-knob desync | LOW | Fix factory mapping; add REG regression test |
| Body/signature break | MEDIUM | Fix raw-body handling; add demo-vector HTTP test; rotate secrets if bypass was deployed |
| Smoke false confidence | MEDIUM | Extend dry-run to Protocol path; keep leaf steps as sub-checks only |
| False live acceptance | HIGH | Reopen LIVE as human gate; attach operator evidence; revert “accepted” markers |
| Protocol unfreeze | HIGH | Revert Protocol; restore freeze tests; move behavior to host/helpers |
| WeCom leak into qqbot | MEDIUM | Remove imports; move shared code to channel-core; widen no-wecom tests |
| Phase 08 deleted | HIGH | Restore from git; re-link STATE.md carry-forward |
| Secret commit | HIGH | Rotate QQ bot secrets; purge history if needed; strengthen scanners |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Fat host / reimplementation | HOST | Host imports package public APIs only; no duplicated crypto/normalize |
| Package-green ≠ host-complete | HOST + milestone gate | Webhook entrypoint exists; audit gaps closed |
| Dual-knob desync | REG | Flag True/False × config × transports matrix tests |
| channels= without webhook | REG + HOST | Composition test: HTTP→ACK→ingress→deliver |
| Raw body / verify bypass | HOST | Demo vector via HTTP handler; no default bypass |
| Slow/wrong ACK / op=13 | HOST + LIVE | Challenge fixture; ACK-before-agent; interaction PUT on live only |
| Leaf-only or networked CI smoke | SMOKE | Protocol-path dry-run; CI dry-run only |
| Auto live acceptance | LIVE | Human attestation required; CI cannot complete LIVE-* |
| Protocol unfreeze | SAFETY | Freeze tests unchanged (6 / 9 methods) |
| WeCom import leak | SAFETY + HOST | `test_no_wecom_import` covers new modules; `dependencies=[]` |
| Hermes meta leak on QQ | HOST + SMOKE | Meta fixture → owned notice / block |
| Phase 08 deletion | SAFETY | Directory present at open and close |
| Secret/payload commit | HOST + SMOKE + LIVE | Sanitizer + ref-only config |

## Sources

- In-repo: `.planning/PROJECT.md` (v1.9 goal), `.planning/milestones/v1.8-MILESTONE-AUDIT.md` (host/smoke/live gaps), `.planning/STATE.md` (carried gates, Phase 08 preserve), `AGENTS.md` (secrets, output boundary, scope).
- In-repo: `packages/channels/qqbot` (`adapter.py` `_live_io_ready`, `config.py` dual-knob, `ingress_runtime.py` host-callable boundary), `tests/test_contract_freeze_not_violated.py`, `tests/test_feature_flag.py`, `tests/test_no_wecom_import.py`, `scripts/smoke_test.py` (leaf dry-run + live human gate).
- Prior milestone pitfalls: `.planning/research/PITFALLS.md` (v1.8 package-level; superseded by this host-composition focus).
- Official QQ Bot signature / webhook validation: [安全和授权](https://bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/sign.html), [事件订阅与通知](https://bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/event-emit.html) (MEDIUM–HIGH; raw body + op=13).
- Ecosystem warning: forged QQ webhooks when verify skipped ([lobehub#16538](https://github.com/lobehub/lobehub/issues/16538)) — LOW–MEDIUM confidence as external incident, HIGH as pattern match to “challenge-only verify.”
- Community webhook host notes (ports, webhook XOR websocket): [bub-qq README](https://github.com/bubbuild/bub-contrib/blob/main/packages/bub-qq/README.md) — MEDIUM.

---
*Pitfalls research for: v1.9 QQBot Host Composition (add host/registration/smoke/live on existing v1.8 packages)*
*Researched: 2026-07-09*
