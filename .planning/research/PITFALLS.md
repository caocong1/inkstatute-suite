# Pitfalls Research

**Domain:** Adding a writable Operator Config Console + provider catalogs + vision/main hybrid routing to InkStatute (channel+adapter platform with existing default-OFF flags, secret refs, read-only admin UI, QQ dual-knob, WeCom output boundary, Hermes as separate agent backend)
**Researched:** 2026-07-10
**Confidence:** HIGH

This research covers common mistakes when **adding writable operator configuration and vision routing on top of an already-shipped platform** — not greenfield admin UIs. InkStatute already has: `admin-console-api` / `admin-web-ui` (strictly read-only, field allowlist), `RuntimeFeatureFlags` (all default OFF), QQ dual-knob (`RuntimeFeatureFlags.qqbot_channel_enabled` AND `QQBotHostConfig.enabled`), process-edge `*_REF` / `secret://` resolution, WeCom output boundary, and Hermes as an agent backend that must **not** be configured from this project. Phases continue from **73**.

Suggested phase themes (roadmap may renumber): **73 SAFETY** (config schema + secret-ref contract + flag defaults), **74 CHANNEL-CFG** (QQ/WeCom writable config without dual-knob collapse), **75 PROVIDER-CFG** (vendor + custom OpenAI-compatible catalogs), **76 MODEL-CATALOG** (built-in selectable models + capability metadata), **77 VISION-ROUTE** (auto/always/never hybrid), **78 PERSIST-AUDIT** (persistence, process-edge resolve, audit log), **79 DOCS-GATES** (operator docs + smoke honesty + carried human gates).

---

## Critical Pitfalls

### Pitfall 1: Configuring Hermes from the InkStatute console

**What goes wrong:**
The config console writes Hermes profile fields, `~/.hermes` paths, gateway adapters, model lists, or WeCom/QQ credentials into Hermes runtime. Operators “fix” channel/provider settings by editing the agent backend. Hermes gateway/meta notices re-enter the user path; InkStatute stops owning channel ingress/egress; AGENTS.md / V2 PRD boundary collapses.

**Why it happens:**
Hermes is the first production agent backend and historically owned channels. Operators and implementers conflate “configure the lawyer bot” with “configure Hermes.” Existing Hermes WeCom/QQ connections look like the natural place to put new knobs.

**How to avoid:**
- Hard rule: console mutates **InkStatute-owned** config only (channel hosts, provider_model / model-gateway lanes, vision routing). Never write Hermes core, gateway, profile secrets, or `~/.hermes`.
- Persist config under InkStatute services/packages; resolve secrets at InkStatute process edge.
- Document explicitly: Hermes remains agent logic only; channel + provider UI is InkStatute-owned.
- Gate tests: no Hermes filesystem/profile write APIs; no import of Hermes config writers from the console package.

**Warning signs:**
- API fields named `hermes_*`, `profile_path`, `gateway_*` in writable schemas.
- README says “edit Hermes model” or points operators at `~/.hermes`.
- Enabling QQ/WeCom in the console also toggles Hermes gateway adapters.

**Phase to address:**
Phase 73 SAFETY + Phase 74 CHANNEL-CFG — schema allowlist and boundary tests first.

---

### Pitfall 2: Planting raw secrets in writable config objects or API responses

**What goes wrong:**
UI/API accepts or echoes API keys, WeCom tokens, QQ BotSecrets, or provider keys as plaintext fields. Values land in config JSON, contract logs, admin responses, browser localStorage, or git. Breaks SAFE-02 / AGENTS.md and the existing health allowlist that already excludes secret refs and `api_base_url` from read views.

**Why it happens:**
Writable UIs default to “value in, value out.” Smoke `--live` already uses value env vars; developers copy that shape into production config. Read-only admin never needed write-path redaction discipline.

**How to avoid:**
- Config schema stores **refs only** (`secret://…`, `env:VAR`, or named `*_REF`). Values resolve once at process edge (same pattern as `QQBotHostConfig` + `resolve_secret_ref`).
- GET responses return ref shapes / “configured: true|false”, never secret values. Mask on write-ack.
- Reject payloads that look like raw tokens in `*_REF` fields (fail closed).
- Ban-list tests: no `Authorization`, BotSecret, corp secret, or key material in config persistence, audit events, or evidence JSON.

**Warning signs:**
- Form fields labeled “API Key” without “reference” wording.
- Config dump includes `sk-…`, AES keys, or BotSecret hex.
- `.env.example` and console schema diverge (one refs, one values).

**Phase to address:**
Phase 73 SAFETY + Phase 78 PERSIST-AUDIT.

---

### Pitfall 3: Collapsing QQ dual-knob into a single UI toggle

**What goes wrong:**
Console exposes one “Enable QQBot” switch that sets only `RuntimeFeatureFlags.qqbot_channel_enabled` **or** only `QQBotHostConfig.enabled`. Live injection stays stripped; ACK returns refuse; operators believe the channel is on. Or the UI sets both True while skipping transport/token injection, leaving `_live_io_ready()` false.

**Why it happens:**
Dual-knob AND semantics are easy to oversimplify in UX. v1.9 already documented the pitfall; a writable UI reintroduces it by “making enablement simple.”

**How to avoid:**
- Model enablement as two explicit knobs (platform flag + host config), both default OFF, AND-gated in wiring — do not invent a third shadow flag that bypasses either.
- UI copy must state: both must be ON; smoke `--live` value env ≠ host `*_REF` enablement.
- Regression tests from Phase 69: flag-alone / host-alone / both-on with and without transports.

**Warning signs:**
- Single boolean `qqbot_enabled` in the writable schema with no dual mapping.
- Health shows `fixture_only=True` after “enable” in UI.
- Docs claim console enablement replaces dual-knob.

**Phase to address:**
Phase 74 CHANNEL-CFG.

---

### Pitfall 4: Mutating the read-only admin console in place

**What goes wrong:**
Teams add POST/PUT to `admin-console-api` or flip `metadata.read_only` false on existing session/task/feedback views. Field allowlists weaken; RBAC/TenantGuard assumptions break; “ops read views” and “config writes” share one blast radius. Existing `test_read_only.py` (no post/put/delete handlers) becomes a silent casualty.

**Why it happens:**
Admin Web UI already exists; extending it feels cheaper than a separate config surface. M2/M3 treated admin as read-only by design — that constraint is easy to forget under milestone pressure.

**How to avoid:**
- Prefer a **separate** config API/service (or clearly versioned `/config` write surface) with its own flag (default OFF), authz, and audit trail.
- Keep existing admin GET views read-only and allowlisted; do not reuse their serializers for secret-bearing config.
- If sharing the admin-web-ui shell, isolate write routes behind a distinct flag and backend enforcement (UI hide ≠ authz).

**Warning signs:**
- `handle_admin_post` appears next to `handle_admin_get`.
- Config endpoints return the same envelopes as `/sessions` without write audit fields.
- Flag freeze tests break because write paths piggyback `admin_api_enabled` alone.

**Phase to address:**
Phase 73 SAFETY (surface split) before any write handlers.

---

### Pitfall 5: Logging or persisting raw legal image payloads on vision turns

**What goes wrong:**
Inbound WeCom/QQ images (contracts, IDs, case materials) are base64-logged, written into contract events, stored in config audit, or forwarded to providers with full retention. Violates `raw_payload_ref` privacy baseline and legal work-product expectations. Vision “debug” dumps become the highest-risk leak surface in the product.

**Why it happens:**
Multimodal debugging wants the bytes. Provider SDKs accept `image_url` / base64 inline. Teams treat images like text prompts and forget AGENTS.md: prefer refs; never commit/store raw legal payloads by default.

**How to avoid:**
- Ingress stores media as refs (`raw_payload_ref` / object-store keys); vision runner resolves bytes ephemerally at process edge.
- Contract/audit events record: media ref, content-type, size hash, provider/model id, routing decision — **not** image bytes or OCR full text by default.
- Provider calls: prefer zero-retention / non-training endpoints where policy requires; never commit fixtures with real client scans.
- Privacy gate tests: vision path fixtures must fail if raw base64 or `data:image` appears in JSONL/evidence.

**Warning signs:**
- Vision request builders concatenate base64 into logged dicts.
- Evidence JSON grows megabytes on image turns.
- “Temporary” debug flag dumps images to `/tmp` inside the repo tree.

**Phase to address:**
Phase 77 VISION-ROUTE + Phase 78 PERSIST-AUDIT.

---

### Pitfall 6: Wrong or missing vision capability metadata → silent mis-route

**What goes wrong:**
Catalog marks a text-only model (e.g. GLM-class) as vision-capable, or leaves capability unknown. `INKSTATUTE_VISION_ROUTING=auto` either skips the vision model (images ignored / errors) or always double-calls vision+main (cost/latency + inconsistent answers). Custom OpenAI-compatible endpoints inherit “supports vision” from the vendor template incorrectly.

**Why it happens:**
OpenAI-compatible APIs look identical for chat and vision until runtime. Catalogs copy marketing names without a capability probe. `.env.example` documents `auto|always|never` but code treats unknown as “assume multimodal.”

**How to avoid:**
- Model catalog entries require explicit `supports_vision: true|false` (no silent default true).
- `auto`: if inbound has image AND main `supports_vision=false` → vision then main; if main true → main only; if capability unknown → fail closed or force explicit operator choice.
- Probe/custom endpoint registration must set capability from operator declaration + optional non-mutating probe — never infer solely from URL path.
- Fixture matrix: text-only main + image inbound; multimodal main + image; no-image turn (must not call vision).

**Warning signs:**
- Catalog rows without capability fields.
- Production traces show vision calls on every turn including pure text.
- Operator sets vision model empty but routing=`auto` and images “disappear” without error.

**Phase to address:**
Phase 76 MODEL-CATALOG + Phase 77 VISION-ROUTE.

---

### Pitfall 7: Vision→main handoff leaks provider/gateway meta past the output boundary

**What goes wrong:**
Vision stage errors (“rate limit”, “model xyz unavailable”, provider stack traces) or intermediate captions are delivered raw to WeCom/QQ. Hermes/gateway-style notices reappear via a new path. Legal conclusions get mixed with routing debug. Dual-model turns bypass the assistant output boundary because they are “not Hermes.”

**Why it happens:**
Output boundary was built for Hermes meta/gateway/update/command. New provider_model / vision paths feel “already InkStatute-owned” so filtering is skipped. Error strings from SDKs are user-facing by accident.

**How to avoid:**
- Every channel deliver path (WeCom + QQ host) runs the same output policy on vision errors, provider failures, and intermediate vision text.
- User-visible failures use InkStatute service copy only; provider/model ids stay in operator logs/refs.
- Do not stream raw vision captions to users unless product policy explicitly allows sanitized summaries.
- Contract tests: vision failure fixtures must assert boundary `rewrite|block`, not `allow` of provider text.

**Warning signs:**
- User messages contain `openai`, `ollama`, `404 model`, or API base URLs.
- Vision errors skip `boundary_action` in smoke/Protocol evidence.
- Separate “vision deliver” helper that does not call output policy.

**Phase to address:**
Phase 77 VISION-ROUTE (wire through existing boundary; do not fork a second egress).

---

### Pitfall 8: Auto-claiming live acceptance from config-console smoke

**What goes wrong:**
CI or autonomous phase complete marks WeCom UAT, lawyer trial, or QQ `--live` acceptance done because the config UI saved settings and a dry-run passed. `not_live_acceptance=true` discipline from v1.9 is lost. Carried human gates are closed without operator judgment.

**Why it happens:**
Writable config feels like “production readiness.” Prior milestones already fought this for QQ smoke; a new console reopens the claim path.

**How to avoid:**
- Config smoke/dry-run always stamps non-acceptance; never flip carried Phase 5 / Phase 8 / QQ live gates from console evidence.
- Separate “config schema valid” from “live channel/provider accepted.”
- Runbook: enabling knobs in UI ≠ live OpenAPI/WeCom UAT.

**Warning signs:**
- SUMMARY/VERIFICATION cites console screenshot as live acceptance.
- Evidence sets `not_live_acceptance=false`.
- ROADMAP checks off human gates in the same phase as config CRUD.

**Phase to address:**
Phase 79 DOCS-GATES (and every phase’s verification wording).

---

### Pitfall 9: Rebuilding Hermes model gateway / treating provider catalog as Hermes config

**What goes wrong:**
Milestone scope expands into forking Hermes model gateway, skill registry, or MCP registry “so the console can manage models.” Provider catalog becomes a second source of truth that fights Hermes lawfirm runtime. Violates AGENTS.md: do not rebuild Hermes core systems unless a phase explicitly changes scope.

**Why it happens:**
v1.7 already has `model_gateway` / `hybrid_routing` flags and provider_model multi-provider runners. Implementers either ignore them and rebuild, or wire the console straight into Hermes internals for “one model list.”

**How to avoid:**
- Console configures **InkStatute** provider_model / model-gateway **lanes** and catalogs; Hermes mode continues to use existing adapter bootstrap — not Hermes file edits.
- Reuse `ProviderModelBackendConfig.api_key_ref` patterns; do not invent parallel secret fields inside Hermes profiles.
- Scope check in Phase 73: no new Hermes core packages; no writes under Hermes profile bundles from console code.

**Warning signs:**
- PRs touch Hermes upstream trees or copy gateway routers into `services/`.
- Single “models” table claimed to drive both Hermes and provider_model without an adapter boundary.
- Flag `model_gateway_enabled` flipped default True to “make the console work.”

**Phase to address:**
Phase 73 SAFETY + Phase 75 PROVIDER-CFG.

---

### Pitfall 10: Writable config bypasses default-OFF flags / backend enforcement

**What goes wrong:**
Saving `enabled=true` in config immediately opens live IO even when `RuntimeFeatureFlags` are False, or the Web UI hides controls but write APIs accept unauthenticated/flag-off mutations. Mirrors the classic “frontend flag only” failure mode.

**Why it happens:**
Config persistence is treated as source of truth above feature flags. Dual systems (flags vs stored config) race; the write path forgets `require_enabled`.

**How to avoid:**
- New console flag(s) default False; write and read-config routes call `require_enabled`.
- Channel/provider activation remains fail-closed: stored config AND runtime flags AND secret resolution success.
- Authz on server: static token / RBAC — never “UI disabled ⇒ secure.”
- Tests: flag off → 403/disabled even with valid config body; flag on + config off → still fail closed for live IO.

**Warning signs:**
- Config service starts with writes enabled whenever `ADMIN_API_TOKEN` is set.
- No `operator_config_enabled` (or equivalent) in `RuntimeFeatureFlags`.
- Browser can PUT config while API flag is off.

**Phase to address:**
Phase 73 SAFETY + Phase 74/75 write routes.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Extend read-only admin with POST | Fast UI reuse | Breaks read-only contract, allowlist, audit story | Never for secret-bearing config |
| Single “enable channel” boolean | Simpler UX | Dual-knob desync, false “live” belief | Never for QQ; WeCom must keep fail-closed parity |
| Store API keys in config JSON “for MVP” | Faster demo | Secret sprawl, git/log leaks | Never — refs only from day one |
| Infer vision support from model name | Less catalog work | Silent mis-route, legal image mishandling | Never — explicit capability field |
| Log base64 images “temporarily” | Easier debug | Legal privacy incident | Never in contract logs / evidence |
| Wire console to Hermes `~/.hermes` | Familiar ops path | Destroys channel ownership boundary | Never |
| Share smoke value-env with host `*_REF` | One credential story | Operators plant values in REF fields | Never — document two lanes |
| Default new flags to True so UI “works” | Demo green | Accidental live IO | Never |

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| QQBot host | UI enable ≠ dual-knob + transport injection | Map both knobs; inject transports only when live IO intended; keep `*_REF` |
| WeCom service | Console writes Hermes WeCom gateway creds | Write InkStatute wecom-service refs only; output boundary stays on egress |
| Provider OpenAI-compatible | Assume `/v1` means vision + tools identical | Explicit capability + probe; normalize errors before user delivery |
| Vision provider | Send client scans with training-on retention | Prefer policy-approved endpoints; ref-first; no raw bytes in logs |
| Hermes agent backend | Console “syncs” model/provider into Hermes | Do not configure Hermes from this project; adapter consumes InkStatute run inputs only |
| Admin token auth | Reuse `ADMIN_API_TOKEN` without write-scope separation | Separate flag + tighter authz/audit for mutations |
| Model gateway (v1.7) | Rebuild gateway instead of configuring existing lane | Configure behind `model_gateway_enabled` default OFF; no Hermes fork |
| Smoke `--live` | Treat successful live leaf send as host+console acceptance | Keep `not_live_acceptance=true`; human archival only |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Vision+main on every text turn | 2× latency/cost | Gate vision on inbound image + routing mode | First busy lawyer day |
| Inline base64 in hot path logs | Disk/CPU spikes, PII risk | Ref-only logging | Dozens of image messages |
| Catalog fetch on every request | UI/API latency | Cache catalog; version stamp | Multi-operator editing |
| Unbounded custom provider list | Slow validation, confused routing | Cap + validation + health probe | Tens of custom endpoints |
| Synchronous vision then main without timeout budget | Channel ACK/reply timeouts | Per-stage timeouts; fail closed with service notice | Large scans / slow vision APIs |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Secrets in writable config / GET bodies | Credential theft, git commit | Refs only; allowlist; mask; ban-list tests |
| UI-only disable of config writes | Unauthorized channel/provider enable | Backend `require_enabled` + authz |
| Image bytes in contract JSONL | Legal privilege / privacy breach | `raw_payload_ref`; privacy gates |
| Custom provider URL without SSRF controls | Internal network pivot | Allowlist schemes/hosts; block link-local/metadata IPs |
| Config audit without actor identity | No forensics after bad enable | Audit who/when/what-ref (never what-secret) |
| Mixing smoke value env into production REF fields | Secrets in wrong store | Schema validation of ref shapes |
| Weakening health allowlist to “show config” | Leak refs/paths/base URLs | Keep allowlist; separate operator config view with redaction |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| One Enable toggle for QQ | Operators think live works; it doesn’t | Show dual-knob status + “live IO ready” explicitly |
| “API Key” free-text without ref hint | Secrets pasted into config | Label as secret reference; link to `.env.example` / runbook |
| Vision routing jargon only | Mis-set `auto/always/never` | Short examples: text-only main + image → vision then main |
| Error text from providers to lawyers | Confusing / non-legal UX; possible meta leak | InkStatute service notices only |
| Catalog of 100 models unsorted | Wrong model selected | Built-in curated catalog + capability badges (vision yes/no) |
| Saving config implies “accepted live” | False confidence | Banner: dry-run/config ≠ live UAT / human gates |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Secret refs:** Writable schema rejects raw secrets; GET never returns values — verify ban-list tests green
- [ ] **Dual-knob:** QQ enable in UI maps to **both** flag and host config; transports injected only when intended — verify Phase-69-style matrix
- [ ] **Hermes boundary:** No console code writes Hermes profile/gateway — verify import/allowlist gate
- [ ] **Read-only admin preserved:** Existing `/sessions|/tasks|/feedback` still `read_only: true` with no POST — verify `test_read_only.py`
- [ ] **Vision capability:** Every catalog model has explicit `supports_vision` — verify unknown ≠ multimodal
- [ ] **Vision privacy:** Image turns log refs only — verify privacy scan on vision fixtures
- [ ] **Output boundary:** Vision/provider errors rewritten/blocked on WeCom and QQ deliver — verify boundary fixtures
- [ ] **Flags default OFF:** New console/provider/vision flags False — verify feature_flags introspection test
- [ ] **Live honesty:** Evidence/docs still `not_live_acceptance`; carried human gates untouched — verify Phase 79 wording
- [ ] **Docs parity:** README + `.env.example` + runbook match console fields (refs vs smoke values)

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Raw secrets in config store | HIGH | Rotate all exposed keys; scrub store/logs; force ref-only migration; audit git history |
| Hermes configured from console | HIGH | Revert Hermes writes; restore InkStatute-owned channel path; reaffirm output boundary; delete console→Hermes APIs |
| Dual-knob collapse | MEDIUM | Restore AND mapping; add UI status for both knobs; regression tests |
| Image bytes in contract logs | HIGH | Purge/redact logs; rotate storage; tighten privacy gate; notify per legal policy |
| Mis-routed vision | MEDIUM | Fix catalog capabilities; set routing fail-closed; replay fixtures |
| Live acceptance auto-claimed | LOW–MEDIUM | Reopen human gates in STATE/ROADMAP; stamp evidence non-acceptance; do not delete Phase 08 artifacts |
| Admin read-only broken | MEDIUM | Split write surface; restore GET-only handlers; re-freeze allowlist tests |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls. Phases continue from 73.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Hermes configured from console | 73 SAFETY, 74 CHANNEL-CFG | No Hermes write APIs; boundary/import tests |
| Raw secrets in config/API | 73 SAFETY, 78 PERSIST-AUDIT | Ref-shape validation + ban-list on GET/persist/audit |
| QQ dual-knob collapse | 74 CHANNEL-CFG | Flag-alone / host-alone / both-on matrix |
| Mutating read-only admin in place | 73 SAFETY | `test_read_only.py` still green; separate write surface |
| Raw legal image persistence | 77 VISION-ROUTE, 78 PERSIST-AUDIT | Privacy scan on vision fixtures/evidence |
| Wrong vision capability / mis-route | 76 MODEL-CATALOG, 77 VISION-ROUTE | Explicit capability + auto/always/never fixture matrix |
| Vision errors bypass output boundary | 77 VISION-ROUTE | Boundary fixtures on vision/provider failures |
| Auto-claim live acceptance | 79 DOCS-GATES | `not_live_acceptance`; carried gates unchanged |
| Rebuild Hermes gateway / wrong catalog authority | 73 SAFETY, 75 PROVIDER-CFG | Scope gate; reuse provider_model/model-gateway lanes |
| Config writes bypass default-OFF | 73 SAFETY, 74–75 | `require_enabled` on write routes; flags default False |
| Custom endpoint SSRF / capability lie | 75 PROVIDER-CFG, 76 MODEL-CATALOG | URL allowlist + declared capability |
| Smoke value-env vs host REF confusion | 74 CHANNEL-CFG, 79 DOCS-GATES | Docs + schema reject values in REF fields |
| Vision+main cost on text turns | 77 VISION-ROUTE | No vision call without inbound image (unless `always`) |
| Provider meta in lawyer-facing text | 77 VISION-ROUTE | Output policy on all provider paths |

## Sources

- Repo: `.planning/PROJECT.md` (v1.10 goals, secret-ref + vision decisions, Hermes-not-configured)
- Repo: `AGENTS.md` (no Hermes rebuild; no secrets in git; output boundary; `raw_payload_ref`)
- Repo: `runbook/SMOKE_TEST_RUNBOOK.md` (dual-knob, `*_REF` vs smoke value env, `not_live_acceptance`)
- Repo: `.env.example` (provider/vision routing knobs; InkStatute path — not Hermes)
- Repo: `services/admin-console-api` read-only contract + field allowlist (`test_read_only.py`, README)
- Repo: `packages/backends/provider_model/.../config.py` (`api_key_ref` not raw key)
- Repo: `packages/platform-runtime/.../feature_flags.py` (all default OFF, including `model_gateway_enabled` / `hybrid_routing_enabled`)
- ConfigCat: feature-flag mistakes — frontend-only flags; secrets in flags ([configcat.com/blog/feature-flag-best-practices](https://configcat.com/blog/feature-flag-best-practices/)) — MEDIUM
- Multi-provider routing: dialect/schema breakage on fallback; capability-specific vision differences ([tianpan.co JSON-mode fallback](https://tianpan.co/blog/2026-04-27-json-mode-dialect-fallback-router-breakage), LiteLLM/multi-provider guides) — MEDIUM
- Legal/vision privacy: raw document images to cloud LLMs; ZDR and logging risks ([vaquill.ai legal AI data path](https://www.vaquill.ai/blog/where-your-legal-ai-data-actually-goes), GDPR document-processing patterns) — MEDIUM
- Secret-ref operator patterns: plaintext in CR/config specs vs `secretKeyRef` (OpenFeature / Superset operator security docs) — MEDIUM

**Confidence notes:** InkStatute-specific pitfalls (Hermes boundary, dual-knob, read-only admin, live-acceptance honesty) are HIGH confidence from repo evidence. Generic multi-provider dialect and legal-image residency claims are MEDIUM (ecosystem sources; validate per chosen providers in Phase 75–77).

---
*Pitfalls research for: InkStatute v1.10 Operator Config Console + vision routing*
*Researched: 2026-07-10*
