# Phase 75: Channel Config Apply - Research

**Researched:** 2026-07-10
**Domain:** Operator-config → QQ/WeCom host dual-knob apply, effective enablement read model, incremental SSR channel form, secret-ref no-echo
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Dual-knob channel enablement preserved (never collapse)
- Secrets as refs only; no echo of resolved values
- Extend admin-console-api + admin-web-ui stdlib SSR
- Hot-reload vs restart: MVP documents restart unless plan proves safe reload
- Carried human gates must not be auto-closed

### Claude's Discretion
All implementation choices are at the agent's discretion — discuss skipped. Use ROADMAP, success criteria, and codebase conventions.

### Deferred Ideas (OUT OF SCOPE)
Provider catalog (76), vision runtime (77), complete SSR/docs/gate honesty (78).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CHAN-01 | Operator can configure QQBot channel settings (enable knobs, credential refs, callback-related refs) via admin config API/UI | Extend Phase 74 `/config/channels` PUT; host load `QQBotChannelDoc` → `QQBotHostConfig`; SSR `/config/channels` form |
| CHAN-02 | Operator can configure WeCom channel settings (enable knobs, credential refs) via admin config API/UI | Same section PUT; map `WeComChannelDoc` → `WeComChannelConfig`; SSR WeCom fields on same page |
| CHAN-03 | Dual-knob effective enablement visible (platform flag AND host enabled) — no single bypass toggle | Effective read model on GET/PUT `/config/channels`; UI shows both knobs + AND result; QQ wiring already AND-gates; add WeCom platform flag parity |
| CHAN-04 | Credential fields accept secret refs only; GET never echoes resolved secrets | Reuse Phase 73 `normalize_config_secret_ref` + Phase 74 planted-secret 400; apply path copies refs only; never call `resolve_secret_ref` in admin API/UI |
</phase_requirements>

## Summary

Phase 74 already persists refs-only channel sections through `OperatorConfigStore` behind `operator_config_enabled`. Phase 75 closes the **ops → runtime** gap: hosts must materialize store docs into existing QQ/WeCom config shapes with **dual-knob AND** preserved, the admin API must expose an **effective enablement read model** (not just the stored section), and admin-web-ui gets an **incremental** `/config/channels` SSR form. [VERIFIED: codebase + ROADMAP]

QQ already has the dual-knob factory in `qqbot_service.wiring.build_qqbot_channel_config` (`flags.qqbot_channel_enabled AND host_config.enabled`). WeCom today has only `WeComChannelConfig.enabled` (env `INKSTATUTE_CHANNEL_WRAPPER_WECOM_ENABLED`) and **no** `RuntimeFeatureFlags.wecom_channel_enabled` — CHAN-03’s “equivalent WeCom flags” requires adding that platform knob (default OFF) plus freeze allowlist update. [VERIFIED: `feature_flags.py`, `wiring.py`, `wecom/.../config.py`, `test_contract_freeze.py`]

**Primary recommendation:** Keep store `channels.*.enabled` as the **host** knob only; never let the UI set platform flags. Enhance GET/PUT `/config/channels` with an `effective` dual-knob block + `apply_semantics: restart_required`. Wire QQ host load from store (env fallback). Add `wecom_channel_enabled` + WeCom apply helper. Ship incremental SSR form on `/config/channels` (CSRF completeness deferred to Phase 78). Document restart-to-apply; do not hot-reload live adapters in MVP.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Persist channel section (refs + host enabled) | API / Backend (`admin-console-api` + `operator-config`) | — | Phase 74 already owns section PUT |
| Effective dual-knob read model | API / Backend (`config_api`) | Frontend Server (display) | Compute from `RuntimeFeatureFlags` + store doc; never resolve secrets |
| QQ host apply / dual-knob AND | API / Backend (`qqbot-service` wiring) | — | Existing REG-01 factory; load store → `QQBotHostConfig` |
| WeCom dual-knob + apply | API / Backend (`platform-runtime` flag + wecom apply helper) | Channel package config | No WeCom host factory yet; mirror QQ AND pattern |
| Secret value resolution | Process edge (hosts only) | — | Existing `resolve_secret_ref`; admin must not resolve |
| SSR channel form | Frontend Server (`admin-web-ui`) | API proxy | Stdlib SSR; POST → `handle_admin_put` |
| Hot-reload live adapters | — (out of MVP) | — | Locked: restart-to-apply unless proven safe |
| Full CSRF / docs / gate honesty | Deferred Phase 78 | — | CONTEXT: incremental forms OK now |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `inkstatute_operator_config` | Phase 73 in-repo | Schemas, store, secret-ref normalize | Locked store authority; empty deps |
| `admin-console-api` `config_api` | Phase 74 | Section GET/PUT | Extend with effective read model — do not fork |
| `qqbot_service.wiring` | Phase 69 | Dual-knob AND + live injection | Proven REG-01 pattern; extend load source only |
| `RuntimeFeatureFlags` | in-repo | Platform knobs (`qqbot_channel_enabled`, add `wecom_channel_enabled`) | Default-OFF lane pattern |
| `admin-web-ui` stdlib SSR | Phase 57+ | HTML forms + `html.escape` + CSP | Locked: no new SPA |
| Python `unittest` | stdlib | Apply matrix + API + SSR tests | Matches V2 gates |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `QQBotHostConfig` / `from_env` | qqbot-service | Host knob + refs | Env fallback when store missing |
| `WeComChannelConfig` / `from_env` | channels/wecom | Channel config shape | Materialize from store doc |
| `qqbot_service.secrets.resolve_secret_ref` | qqbot-service | Process-edge resolve | Hosts only — never admin GET |
| `normalize_config_secret_ref` | operator-config | Shape validation | PUT path (already via validate_document) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Restart-to-apply | In-process hot-reload | Rejected for MVP — races, dual-knob desync, hard to test [CITED: FEATURES.md / CONTEXT locked] |
| Single “Enable channel” toggle | Dual-knob UI | Rejected — Pitfall 3; collapses safety [CITED: PITFALLS.md] |
| Store `enabled` sets both knobs | Host-only store knob | Rejected — would let UI bypass platform flag |
| Reuse `channel_delivery_enabled` as WeCom platform knob | Dedicated `wecom_channel_enabled` | Too broad; wrong semantics — add dedicated flag |
| New config-service | Extend admin-console-api | Rejected — locked no new service |
| Full CSRF in Phase 75 | Incremental form + Phase 78 CSRF gate | CONTEXT defers complete CSRF verification to 78 |

**Installation:** No new PyPI/npm packages.

```bash
# No npm/pip install required for Phase 75
# Gate PYTHONPATH already includes operator_config_src for admin-console-api + admin-web-ui
```

**Version verification:** In-repo packages only. Confirmed: `OperatorConfigStore`, `CONFIG_SECTIONS`, `build_qqbot_channel_config`, `QQBotChannelDoc`/`WeComChannelDoc` field parity with channel configs, admin-web-ui GET-only today. [VERIFIED: local codebase 2026-07-10]

## Package Legitimacy Audit

> Phase 75 installs **no** new external packages.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| — | — | — | — | — | — | N/A — no new installs |

**Packages removed due to slopcheck [SLOP] verdict:** none  
**Packages flagged as suspicious [SUS]:** none

*slopcheck not required — no external package installs in this phase.*

## Architecture Patterns

### System Architecture Diagram

```text
Operator browser
    │  GET/POST /config/channels (admin-web-ui SSR)
    ▼
┌──────────────────────────────────────────────────────────────┐
│ admin-web-ui                                                 │
│  • Render dual-knob form (platform read-only, host editable) │
│  • POST → handle_admin_put("/config/channels", body)         │
│  • html.escape + CSP; never resolve secrets                  │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ admin-console-api  /config/channels                          │
│  GET: store section + effective{platform,host,AND,refs_set}  │
│  PUT: validate refs → OperatorConfigStore.save (host knob)   │
│  metadata.apply_semantics = "restart_required"               │
└───────────────────────────┬──────────────────────────────────┘
                            │ persist JSON (refs only)
                            ▼
              packages/operator-config  OperatorConfigStore
                            │
          ┌─────────────────┴─────────────────┐
          ▼                                   ▼
┌─────────────────────────┐     ┌─────────────────────────────┐
│ qqbot-service (restart) │     │ WeCom apply (restart)       │
│ load store → HostConfig │     │ load store → ChannelConfig  │
│ OR env fallback         │     │                             │
│ enabled = flag AND host │     │ enabled = wecom_flag AND doc│
│ resolve_secret_ref edge │     │ resolve at process edge     │
│ strip transports if OFF │     │ adapter refuses if OFF      │
└─────────────────────────┘     └─────────────────────────────┘
```

### Recommended Project Structure

```text
packages/platform-runtime/src/platform_runtime/
└── feature_flags.py              # ADD wecom_channel_enabled: bool = False

packages/operator-config/src/inkstatute_operator_config/
└── effective.py                  # NEW: pure dual-knob effective helpers (optional)

services/admin-console-api/src/admin_console_api/
└── config_api.py                 # EXTEND: channels effective block + apply_semantics

services/qqbot-service/src/qqbot_service/
├── config.py                     # ADD from_operator_doc / load_host_config(store|env)
└── wiring.py                     # Prefer store-backed host_config at build

packages/channels/wecom/src/inkstatute_channels_wecom/
└── apply.py                      # NEW: build_wecom_channel_config(flags, doc) dual-knob
   # OR services/wecom-service thin helper if preferred — keep adapter free of flags

services/admin-web-ui/src/admin_web_ui/
├── server.py                     # ADD /config/channels GET (+ POST)
├── api_client.py                 # ADD put proxy → handle_admin_put
├── channels.py                   # NEW: form render + parse
└── dashboard.py                  # Nav link to Channels

tests:
├── services/admin-console-api/tests/test_config_channels_effective.py
├── services/qqbot-service/tests/test_store_apply.py
├── packages/channels/wecom/tests/test_apply_dual_knob.py
└── services/admin-web-ui/tests/test_channels_form.py
```

### Pattern 1: Host Knob in Store, Platform Knob Outside Store
**What:** `channels.qqbot.enabled` / `channels.wecom.enabled` map only to host/doc enablement. Platform flags stay on `RuntimeFeatureFlags` (deploy/process construction), shown read-only in UI/API effective block.
**When to use:** Always for CHAN-03.
**Example:**
```python
# Source: services/qqbot-service/src/qqbot_service/wiring.py (existing)
return QQBotChannelConfig(
    enabled=bool(flags.qqbot_channel_enabled and host_config.enabled),
    app_id_ref=host_config.app_id_ref,
    # ... refs only ...
)
```

### Pattern 2: Store-First Host Load with Env Fallback
**What:** At host process start, if operator-config store file exists (or load succeeds with non-default channel fields), materialize host config from doc; else `from_env`.
**When to use:** QQ and WeCom apply paths.
**Example:**
```python
# Recommended host load (QQ)
def load_qqbot_host_config(
    *, store: OperatorConfigStore, env: Mapping[str, str]
) -> QQBotHostConfig:
    doc = store.load()
    qq = doc.channels.qqbot
    # Store is SoT when operator config is in use; env remains bootstrap fallback
    if _store_has_channel_overrides(doc) or store.path.exists():
        return QQBotHostConfig(
            enabled=qq.enabled,
            app_id_ref=qq.app_id_ref,
            app_secret_ref=qq.app_secret_ref,
            token_secret_ref=qq.token_secret_ref,
            bot_secret_ref=qq.bot_secret_ref,
        )
    return QQBotHostConfig.from_env(env)
```

### Pattern 3: Effective Read Model on `/config/channels`
**What:** GET (and PUT response) include stored section **plus** computed effective state. Never collapse to one boolean as the only enablement field.
**When to use:** CHAN-03 API + SSR.
**Example:**
```python
# Recommended response shape (additive; keep data = section payload)
{
  "data": { "qqbot": {...}, "wecom": {...} },  # refs only, as today
  "effective": {
    "qqbot": {
      "platform_flag": False,          # RuntimeFeatureFlags.qqbot_channel_enabled
      "host_enabled": True,            # store channels.qqbot.enabled
      "effective_enabled": False,      # AND
      "refs_configured": {
        "app_id_ref": True,
        "app_secret_ref": True,
        "token_secret_ref": False,
        "bot_secret_ref": False,
      },
    },
    "wecom": {
      "platform_flag": False,          # RuntimeFeatureFlags.wecom_channel_enabled (new)
      "host_enabled": False,
      "effective_enabled": False,
      "refs_configured": {
        "token_secret_ref": True,
        "encoding_aes_key_secret_ref": False,
        "corp_id_ref": False,
      },
    },
  },
  "metadata": {
    "admin_api": True,
    "config_surface": True,
    "operator_config_enabled": True,
    "read_only": False,
    "apply_semantics": "restart_required",
  },
}
```

### Pattern 4: Incremental SSR Form (Phase 75) vs CSRF Completeness (Phase 78)
**What:** Add `/config/channels` GET form + POST that proxies `handle_admin_put`. Use `html.escape`, existing CSP, ADMIN/OPERATOR RBAC. Minimal CSRF token acceptable; Phase 78 owns complete CSRF-protected surface verification.
**When to use:** Channel page only this phase.

### Anti-Patterns to Avoid
- **Single bypass toggle:** One checkbox that sets both platform + host, or only platform. [CITED: PITFALLS.md Pitfall 3]
- **Resolving secrets in admin GET/UI:** Calling `resolve_secret_ref` to “verify” or display values. [VERIFIED: Phase 74 config_api never resolves]
- **Hot-reloading adapters mid-request:** Swapping transports while webhook threads run. [CITED: FEATURES.md deferral]
- **Auto-closing carried human gates** from config smoke. [CITED: CONTEXT / STATE.md]
- **Importing qqbot-service from operator-config:** Breaks empty-deps boundary. Keep apply mappers in hosts/channel packages. [VERIFIED: operator-config README]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dual-knob AND | New third enable flag / OR logic | Existing `build_qqbot_channel_config` + WeCom mirror | Phase 69 matrix already proven |
| Secret shape validation | Ad hoc regex in admin UI | `normalize_config_secret_ref` / `validate_document` | Planted-secret no-echo already tested |
| Config persistence | Second JSON writer in hosts | `OperatorConfigStore` | Atomic + flag-gated authority |
| SSR framework | React/SPA admin | stdlib `admin-web-ui` | Locked empty-deps / CSP patterns |
| Secret resolve in API | “Preview resolved” endpoint | Presence-only `refs_configured` | CHAN-04 |

**Key insight:** Phase 75 is mostly **composition and visibility** — persistence and dual-knob math already exist; the footguns are collapsing knobs, echoing secrets, and claiming live apply without restart.

## Common Pitfalls

### Pitfall 1: Collapsing Dual-Knob in UI/API
**What goes wrong:** Operators flip one “Enable QQ/WeCom” control; effective stays OFF or both knobs flip silently.
**Why it happens:** UX pressure to simplify. [CITED: PITFALLS.md]
**How to avoid:** Three visible fields: platform (read-only), host (editable), effective (computed). Tests assert flag-alone / host-alone / both-on matrix for API `effective` and wiring.
**Warning signs:** Schema or form with a single `enabled` as the only enablement control without platform display.

### Pitfall 2: Treating Store Save as Live Apply
**What goes wrong:** PUT returns 200; running host still uses old env/config until restart; operators file “config broken” bugs.
**Why it happens:** Assuming hot-reload. [CITED: SUMMARY.md open question]
**How to avoid:** `metadata.apply_semantics = "restart_required"`; SSR banner “Restart channel host to apply”; host README documents store load at startup only.
**Warning signs:** Docs claiming “changes take effect immediately” without a proven reload hook.

### Pitfall 3: Secret Echo / Resolve in Admin Path
**What goes wrong:** GET shows raw tokens; errors include planted `sk-…`.
**Why it happens:** Convenience debugging. [VERIFIED: Phase 74 planted-secret tests]
**How to avoid:** Apply copies `*_ref` strings only; admin never imports host `resolve_secret_ref`; extend no-echo tests to effective block JSON.
**Warning signs:** `resolve_secret_ref` import in `admin_console_api` or `admin_web_ui`.

### Pitfall 4: WeCom Dual-Knob Gap
**What goes wrong:** QQ shows dual-knob; WeCom only shows store `enabled` — CHAN-03 incomplete.
**Why it happens:** No `wecom_channel_enabled` on `RuntimeFeatureFlags` today. [VERIFIED: feature_flags.py]
**How to avoid:** Wave 0 add `wecom_channel_enabled: bool = False` + update exact-set freeze allowlist (same pattern as `operator_config_enabled` in Phase 74).
**Warning signs:** Effective WeCom block missing `platform_flag` or reusing `channel_delivery_enabled`.

### Pitfall 5: Env vs Store Desync
**What goes wrong:** Host still reads `INKSTATUTE_QQBOT_CHANNEL_ENABLED` after console save, ignoring store.
**Why it happens:** Apply path not wired; env remains sole source.
**How to avoid:** Explicit load precedence in host factory; unit test store-on / env-fallback; document that console SoT requires restart with store path set.
**Warning signs:** Wiring still only calls `QQBotHostConfig.from_env` with no store parameter.

### Pitfall 6: Breaking Admin Read-Only Operational Contract
**What goes wrong:** POST added to `/sessions` etc., or `test_read_only` regresses.
**Why it happens:** Copy-paste write handlers. [CITED: Phase 74]
**How to avoid:** Only `/config/*` mutates; SSR POST only to `/config/channels`; keep operational 405 proofs green.

## Code Examples

### QQ Dual-Knob (existing — do not rewrite)
```python
# Source: services/qqbot-service/src/qqbot_service/wiring.py
def build_qqbot_channel_config(*, flags, host_config) -> QQBotChannelConfig:
    return QQBotChannelConfig(
        enabled=bool(flags.qqbot_channel_enabled and host_config.enabled),
        app_id_ref=host_config.app_id_ref,
        app_secret_ref=host_config.app_secret_ref,
        token_secret_ref=host_config.token_secret_ref,
        bot_secret_ref=host_config.bot_secret_ref,
    )
```

### Recommended WeCom Mirror
```python
# New apply helper — adapter must NOT import RuntimeFeatureFlags
def build_wecom_channel_config(*, flags, doc: WeComChannelDoc) -> WeComChannelConfig:
    return WeComChannelConfig(
        enabled=bool(flags.wecom_channel_enabled and doc.enabled),
        token_secret_ref=doc.token_secret_ref,
        encoding_aes_key_secret_ref=doc.encoding_aes_key_secret_ref,
        corp_id_ref=doc.corp_id_ref,
        metadata=dict(doc.metadata),
    )
```

### Effective Block Helper (admin config_api)
```python
def channels_effective(doc: OperatorConfigDocument, flags: RuntimeFeatureFlags) -> dict:
    def one(platform: bool, host: bool, refs: dict[str, str | None]) -> dict:
        return {
            "platform_flag": platform,
            "host_enabled": host,
            "effective_enabled": bool(platform and host),
            "refs_configured": {k: v is not None and v != "" for k, v in refs.items()},
        }
    qq, wc = doc.channels.qqbot, doc.channels.wecom
    return {
        "qqbot": one(
            flags.qqbot_channel_enabled,
            qq.enabled,
            {
                "app_id_ref": qq.app_id_ref,
                "app_secret_ref": qq.app_secret_ref,
                "token_secret_ref": qq.token_secret_ref,
                "bot_secret_ref": qq.bot_secret_ref,
            },
        ),
        "wecom": one(
            flags.wecom_channel_enabled,  # new flag
            wc.enabled,
            {
                "token_secret_ref": wc.token_secret_ref,
                "encoding_aes_key_secret_ref": wc.encoding_aes_key_secret_ref,
                "corp_id_ref": wc.corp_id_ref,
            },
        ),
    }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Env-only host enable (`INKSTATUTE_QQBOT_CHANNEL_ENABLED`) | Store host knob + env fallback | Phase 75 | Console can set host enable without editing shell env |
| QQ dual-knob only in wiring | Dual-knob visible in API/UI effective model | Phase 75 | Operators see why channel is still OFF |
| Admin GET-only dashboard | Incremental `/config/channels` SSR form | Phase 75 | CHAN-01/02 UI path; Phase 78 completes CSRF/docs |
| Implicit “save = live” | Explicit `restart_required` | Phase 75 | Honest apply semantics |

**Deprecated/outdated:**
- Treating Phase 74 section GET as sufficient for CHAN-03 (missing effective dual-knob block)
- Assuming WeCom already has a platform feature flag equivalent to QQ

## Restart-to-Apply vs Hot-Reload (Decision)

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **Restart-to-apply** | Matches locked CONTEXT; no mid-flight transport swap; easy to test; honest ops | Brief downtime per host | **MVP choice** |
| Hot-reload on PUT | Faster iteration | Dual-knob desync, webhook race, TokenManager rebuild, hard proofs | Defer P2 / later phase |

**Recommendation:** Document and implement **restart-to-apply** only. Hosts read `OperatorConfigStore` at process start (or explicit rebuild entrypoint used only at startup). PUT persists; does not mutate in-memory adapters. Surface `apply_semantics: restart_required` on API + SSR.

## API Enhancements Beyond Phase 74 Section PUT

Phase 74 already provides GET/PUT `/config/channels` with refs-only `data`. Phase 75 must add:

1. **`effective` dual-knob object** on GET and PUT success responses (CHAN-03)
2. **`metadata.apply_semantics`: `"restart_required"`**
3. **`refs_configured` presence map** (booleans only — not values)
4. **Platform flags read from injected `RuntimeFeatureFlags`** (same object used for auth gates)
5. **No new routes required** for MVP — enhance existing `/config/channels` (avoid `/config/channels/effective` split unless planner wants isolation)
6. **Do not** add full-document GET, secret resolve, or platform-flag write via channels PUT

PUT body remains the section value (qqbot/wecom docs). Editable fields: `enabled` (host), `*_ref`, `metadata`. Platform flag is **not** a PUT field.

## SSR Form Wiring (`/config/channels`)

| Concern | Guidance |
|---------|----------|
| Route | Add `/config/channels` to admin-web-ui `_SECTION_MAP` / nav |
| GET | Proxy `handle_admin_get("/config/channels")`; render dual-knob + ref inputs |
| POST | Parse form → section JSON → `handle_admin_put`; re-render with flash/errors |
| RBAC | Reuse guard; map path to `/config` matrix (ADMIN+OPERATOR) |
| Escaping | `html.escape` all dynamic values; CSP unchanged |
| CSRF | Minimal token OK; **complete CSRF verification = Phase 78** |
| Platform knobs | Render as read-only checkmarks/text from `effective.*.platform_flag` |
| Host knobs | Editable checkboxes bound to `data.*.enabled` |
| Secrets | Text inputs for refs only; never prefill resolved values (none available) |
| Banner | “Restart QQBot/WeCom host processes to apply changes” |

`AdminApiClient` today only proxies GET — extend with `put`/`proxy_put` accepting `handle_admin_put`. [VERIFIED: `api_client.py`]

## Secret-Ref No-Echo

| Layer | Rule |
|-------|------|
| Store / validate | Shape-only; `InvalidSecretRefError` must not include raw value [VERIFIED: secrets.py + Phase 73 tests] |
| Admin PUT | Planted raw → 400 `invalid_config`; substring absent from JSON [VERIFIED: test_config_api.py] |
| Admin GET / effective | Return stored ref strings + `refs_configured` booleans; never call resolve |
| SSR | Echo submitted **ref** strings after escape; never env values |
| Host apply | Copy refs onto host/channel config; resolve only at process edge for live IO |
| Errors | Strip filesystem paths (existing `_safe_store_message`) |

## Project Constraints (from .cursor/rules/)

No `.cursor/rules/` directory present in this workspace. Follow `AGENTS.md` + GSD artifacts:

- Keep changes scoped to Phase 75; no new service/DB/queue
- Never commit secrets, runtime store JSON, or raw legal payloads
- Do not auto-close carried Phase 05 / 08 / QQ live human gates
- Prefer structured validators over ad hoc string parsing

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Adding `wecom_channel_enabled` is the correct WeCom platform knob for CHAN-03 | WeCom dual-knob | If product intended a different pair (e.g. env-only), freeze churn is wasted — confirm in plan if disputed |
| A2 | Store file existence / load is sufficient precedence over env for host apply | Pattern 2 | Ambiguous hybrid (partial env + partial store) may need explicit `source: store\|env` metadata |
| A3 | Enhancing `/config/channels` in-place is preferred over a new effective-only route | API enhancements | Clients of Phase 74 shape need additive fields only — keep `data` stable |
| A4 | Minimal CSRF in Phase 75 is acceptable | SSR | Phase 78 must not find zero CSRF if security gate expects token now — document deferral in SUMMARY |

**If this table is empty:** N/A — assumptions listed above need planner awareness, not necessarily user re-discuss (discuss skipped).

## Open Questions

1. **Store vs env precedence when both set?**
   - What we know: Today hosts use env only; store is new SoT for console.
   - What's unclear: Should store always win when file exists, or only when `operator_config_enabled`?
   - Recommendation: Store wins when the configured store path exists; else env. Document clearly. Optional `metadata.config_source` later.

2. **Where does WeCom apply helper live?**
   - What we know: No `wecom-service` dual-knob wiring factory; adapter is in `packages/channels/wecom`.
   - What's unclear: Host process entrypoint for WeCom production composition.
   - Recommendation: Put `build_wecom_channel_config` next to WeCom channel package (or thin wecom-service module); keep flag import out of adapter class.

3. **Should platform flags be env-loadable for operators?**
   - What we know: `RuntimeFeatureFlags` is constructed in code; QQ platform flag is not the same env key as host enable.
   - What's unclear: Deploy story for flipping `qqbot_channel_enabled` / `wecom_channel_enabled` without code.
   - Recommendation: Out of Phase 75 mutate scope — show as read-only; deploy/docs can document process construction. Do not write platform flags from `/config/channels` PUT.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | All packages/tests | ✓ | 3.14.6 (CI floor ≥3.11) | — |
| unittest / pytest | Validation | ✓ | unittest stdlib; pytest present | Prefer unittest for V2 gates |
| OperatorConfigStore path | Host apply | ✓ | package present | Env-only host config fallback |
| Live QQ/WeCom network | Not required | N/A | — | Fake transports / unit tests only |
| New PyPI packages | None | N/A | — | — |

**Missing dependencies with no fallback:** none  
**Missing dependencies with fallback:** Live channel IO — not needed for Phase 75 proofs

Step 2.6: External tools beyond Python stdlib + in-repo packages — none required for implementation.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Python `unittest` (V2 gates) |
| Config file | none — discover via `scripts/run_v2_gates.py` |
| Quick run command | `PYTHONPATH=… python -m unittest services.admin-console-api.tests.test_config_api -q` (plus new effective tests) |
| Full suite command | `python scripts/run_v2_gates.py` (or targeted admin-console-api + qqbot-service + admin-web-ui + operator-config + platform-runtime gates) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CHAN-01 | PUT/GET qqbot refs + host enabled roundtrip; host loads store | unit | `unittest … test_config_api` + `test_store_apply` | ⚠️ partial (API yes; apply ❌ Wave 0) |
| CHAN-02 | PUT/GET wecom refs + host enabled; WeCom apply dual-knob | unit | `unittest … test_apply_dual_knob` | ❌ Wave 0 |
| CHAN-03 | effective shows platform/host/AND; no single bypass; matrix | unit | `unittest … test_config_channels_effective` | ❌ Wave 0 |
| CHAN-04 | planted secret PUT 400 no-echo; GET effective has no resolved values | unit | extend `test_config_api` + effective JSON assert | ⚠️ partial (PUT yes; effective ❌) |
| SC apply | restart_required metadata present | unit | assert metadata key | ❌ Wave 0 |
| SC SSR | `/config/channels` renders dual-knob + posts PUT | unit | `test_channels_form` | ❌ Wave 0 |
| Freeze | `wecom_channel_enabled` in exact-set allowlist | unit | `test_contract_freeze` | ⚠️ must update |

### Sampling Rate
- **Per task commit:** targeted unittest module for touched package
- **Per wave merge:** admin-console-api + qqbot-service + admin-web-ui + platform-runtime + operator-config discovers
- **Phase gate:** Full relevant V2 gates green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `services/admin-console-api/tests/test_config_channels_effective.py` — CHAN-03 effective block + apply_semantics
- [ ] `services/qqbot-service/tests/test_store_apply.py` — store→HostConfig→dual-knob matrix + env fallback
- [ ] `packages/channels/wecom/tests/test_apply_dual_knob.py` (or wecom-service) — WeCom AND matrix
- [ ] `services/admin-web-ui/tests/test_channels_form.py` — SSR render + POST proxy
- [ ] Update `test_contract_freeze.py` expected flag set for `wecom_channel_enabled`
- [ ] Extend planted-secret no-echo asserts to cover `effective` payload

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Existing admin static token / RBAC bearer |
| V3 Session Management | partial | SSR forms; full CSRF in Phase 78 |
| V4 Access Control | yes | `/config` ADMIN+OPERATOR only; lawyer/viewer denied |
| V5 Input Validation | yes | `validate_document` + secret-ref shape normalize |
| V6 Cryptography | no new | Do not resolve/store WeCom AES/token values in admin |

### Known Threat Patterns for Channel Config Apply

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Raw secret in store/API/UI | Information Disclosure | Refs-only schema; planted-secret tests; no resolve in admin |
| UI bypass of platform flag | Elevation of Privilege | Dual-knob AND; platform read-only in channels form |
| Lawyer mutate config | Elevation of Privilege | RBAC matrix `/config` deny |
| Flag-OFF write | Tampering | `OperatorConfigDisabledError` → 403 |
| Claiming live acceptance from config smoke | Spoofing / repudiation | `not_live_acceptance`; leave human gates open |
| CSRF on SSR POST | Spoofing | Minimal token now; Phase 78 completeness |

## Sources

### Primary (HIGH confidence)
- `services/qqbot-service/src/qqbot_service/wiring.py` — dual-knob AND + live injection
- `services/admin-console-api/src/admin_console_api/config_api.py` — section GET/PUT
- `packages/operator-config/src/inkstatute_operator_config/schemas.py` — QQ/WeCom channel docs
- `packages/platform-runtime/src/platform_runtime/feature_flags.py` — flag inventory
- `services/admin-web-ui/src/admin_web_ui/server.py` — GET-only SSR today
- `.planning/REQUIREMENTS.md` CHAN-01..04; `.planning/ROADMAP.md` Phase 75
- `.planning/phases/75-channel-config-apply/75-CONTEXT.md` — locked decisions
- Phase 73–74 SUMMARYs / 74-RESEARCH.md

### Secondary (MEDIUM confidence)
- `.planning/research/ARCHITECTURE.md` — apply flow, dual-knob pattern, hot-reload open question
- `.planning/research/FEATURES.md` — restart-to-apply MVP; defer hot-reload
- `.planning/research/PITFALLS.md` — Pitfall 3 dual-knob collapse
- `runbook/SMOKE_TEST_RUNBOOK.md` — dual-knob operator docs

### Tertiary (LOW confidence)
- Exact store-vs-env precedence UX copy — product polish, not blocking

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all in-repo; no new packages
- Architecture: HIGH — QQ wiring + Phase 74 API verified; WeCom flag gap explicit
- Pitfalls: HIGH — repo PITFALLS + Phase 69 matrix + CONTEXT restart lock

**Research date:** 2026-07-10  
**Valid until:** 2026-08-09 (30 days; stable in-repo patterns)
