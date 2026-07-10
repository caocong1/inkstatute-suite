# Stack Research

**Domain:** Operator Config Console (writable channel / provider / vision routing config)
**Researched:** 2026-07-10
**Confidence:** HIGH

## Scope Boundary

This research covers **only** stack additions/changes for v1.10 Operator Config Console. The following are **already validated** and must not be re-selected as greenfield:

| Already shipped (reuse) | Do not re-research |
|-------------------------|--------------------|
| `packages/platform-contract` schemas + validators | Contract redesign |
| WeCom / QQ channel packages + `qqbot-service` host | Channel crypto / OpenAPI clients |
| `platform-runtime` feature flags (default OFF) | Flag framework redesign |
| `admin-web-ui` (SSR stdlib, read-only) + `admin-console-api` (read-only) | New SPA / new mega-API service |
| `provider_model` (incl. Ollama OpenAI-compatible runner) + `model-gateway` | Hermes model gateway rebuild |
| Hermes as first agent backend | Configuring Hermes `~/.hermes` from this project |

**Milestone goal:** InkStatute-owned writable operator UI/API for QQ+WeCom channels, provider catalog (vendors + custom OpenAI-compatible), built-in model lists, and vision/image-routing — secrets as refs only.

---

## Architectural Constraints (Carried Forward)

1. **`dependencies = []`** on every package/service `pyproject.toml` — verified across admin-web-ui, admin-console-api, provider_model, model-gateway, qqbot-service, channels. New config work must preserve empty hard deps unless an optional extra is explicitly justified.
2. **Python-first** — Python 3.11+ (CI floor); stdlib preferred. TypeScript clients are out of scope for this console.
3. **No new DB / queue** unless the active plan justifies it (AGENTS.md). Config persistence must be file- or env-backed.
4. **Secrets as refs only** — config objects store `*_ref` / `api_key_ref`; values resolve at process edge via injected env mapping (qqbot-service `resolve_secret_ref` pattern). Never commit tokens; never plant raw secrets in config JSON or API responses.
5. **Feature flags default OFF** — writable config surface needs an explicit opt-in flag (recommend `operator_config_enabled=False`).
6. **Do not treat Hermes `~/.hermes` as source of truth** — InkStatute env / config store owns channel + provider_model settings; Hermes remains agent-backend only.

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Extend `services/admin-console-api` | 0.1.0 (in-repo) | Writable config API (`GET`/`PUT`/`PATCH` for channels, providers, vision) | Already owns auth, RBAC, health allowlists, and read views. Adding mutation handlers here avoids a new mega-service and keeps one operator API surface. |
| Extend `services/admin-web-ui` | 0.1.0 (in-repo) | SSR config forms (channels, providers, models, vision routing) | Existing stdlib `http.server` + HTML-escaped templates + CSP. Forms POST to admin-console-api; no React/Vite needed for operator CRUD. |
| Python 3.11+ stdlib (`dataclasses`, `json`, `pathlib`, `html`, `http.server`, `tomllib`, `secrets`, `os`) | 3.11+ | Config models, atomic JSON file store, SSR forms, CSRF tokens | Matches zero-deps monorepo convention. `tomllib` (3.11+) covers optional TOML overlays without PyYAML. |
| Existing channel configs (`QQBotChannelConfig`, `WeComChannelConfig`) | in-repo | Channel enable flags + secret refs | Already define `enabled` + `*_ref` fields and `from_env`. Console reads/writes the same shape; hosts keep resolving refs at process edge. |
| Existing `ProviderModelBackendConfig` + runners | in-repo | Provider endpoint + `api_key_ref` + model name | Extend with vision fields (`vision_api_base_url`, `vision_api_key_ref`, `vision_model`, `vision_routing`, `supports_vision`) rather than a parallel config type. Lazy `openai` import stays optional. |
| Existing `rbac` (`RbacGuard`, `Role.ADMIN` / `Role.OPERATOR`) | in-repo | Authorize config writes | Matrix is default-deny; add `/config/*` prefixes for admin/operator only. Lawyers/viewers must not mutate channel or provider secrets refs. |
| Existing `RuntimeFeatureFlags` | in-repo | Gate writable console | Add `operator_config_enabled: bool = False` (and keep `admin_api_enabled` / `admin_web_ui_enabled` as prerequisites). |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Built-in provider/model catalog (static JSON under e.g. `packages/backends/provider_model/catalog/` or `services/admin-console-api/data/`) | in-repo artifact | Vendor presets + selectable model IDs + `supports_vision` flags | Ship as versioned JSON loaded by stdlib `json`. Do **not** scrape Hermes or live vendor APIs for the catalog SoT. |
| Generalized secret-ref resolver (lift/adapt `qqbot_service.secrets.resolve_secret_ref`) | in-repo | Process-edge ref → value | Console API validates ref **shape** only; hosts/runtime resolve values. Prefer a small shared helper (channel-core or platform-runtime) over duplicating QQ-only maps. |
| `openai` (optional runtime, lazy import) | **2.45.0** (PyPI current 2026-07-09) | Optional connectivity / model-list probe for OpenAI-compatible endpoints | Keep as **optional** host/runtime install — never add to `dependencies = []`. Probe must not run in CI without fakes; never log API keys. |
| Atomic JSON config store (`pathlib` + write-temp-rename) | stdlib | Persist operator config outside git | Path via env e.g. `INKSTATUTE_OPERATOR_CONFIG_PATH` (default under runtime data dir, gitignored). Single-file JSON is enough for channel + provider + vision docs; no Postgres/SQLite. |
| CSRF token (stdlib `secrets.token_urlsafe`) | stdlib | Protect SSR form POSTs | admin-web-ui currently GET-only; writable forms need double-submit or session cookie + token. Keep CSP `default-src 'self'`. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `unittest` (existing patterns) | API write/read, allowlist, secret-ref rejection, form CSRF | Prefer pure handlers (`handle_admin_put` / `handle_config_request`) testable without binding ports — same as admin-web-ui / qqbot-service. |
| V2 gate / gate-coverage meta-test | Ensure new modules stay gated | No new top-level service directory required if extending admin-*; if a thin `packages/operator-config/` appears, add a gate entry. |
| Fixture JSON catalogs + planted-secret negative tests | Prove refs-only + allowlist | Plant raw `sk-…` in PUT bodies and assert 400; assert responses never echo resolved secrets or `api_key` values. |

---

## Installation

```bash
# No new hard PyPI dependencies for the console itself.
# Editable installs remain empty-deps:

pip install -e services/admin-console-api
pip install -e services/admin-web-ui
pip install -e packages/backends/provider_model
pip install -e packages/channels/qqbot
pip install -e packages/channels/wecom
pip install -e packages/platform-runtime
pip install -e packages/rbac

# Optional — only on hosts that run live provider_model / connectivity probe:
pip install "openai>=2.45.0,<3"
```

Config path (example, gitignored runtime data — never commit):

```bash
export INKSTATUTE_OPERATOR_CONFIG_PATH=/var/lib/inkstatute/operator-config.json
# Values for refs still come from process env / secret store, not the JSON file.
```

---

## Integration Points (Existing Packages)

| Surface | Change | Keep unchanged |
|---------|--------|----------------|
| `admin-console-api` | Add `handle_admin_mutate` (or method-aware dispatcher) for `/config/channels`, `/config/providers`, `/config/vision`, `/config/catalog`; field allowlist on GET (refs + booleans + non-secret URLs as policy allows); refuse raw secret fields | Existing read-only `/sessions` `/tasks` `/feedback` `/health` `/gates` |
| `admin-web-ui` | New sections `/config/channels`, `/config/providers`, `/config/vision`; HTML forms → API; CSRF; `html.escape` only | Read dashboard sections; CSP; no `innerHTML` |
| `provider_model.config.ProviderModelBackendConfig` | Add vision routing fields aligned with `.env.example` (`INKSTATUTE_VISION_*`, `INKSTATUTE_VISION_ROUTING=auto\|always\|never`) | Lazy OpenAI import; `api_key_ref` semantics; runners |
| `model-gateway` | Optional consumer of persisted provider list / fallback chain later | Do not make gateway the config editor |
| Channel packages + hosts | Consume persisted enable + refs the same way as `from_env` today | Crypto, webhook, Protocol methods |
| `rbac` matrix | Register `/config` prefixes for `ADMIN` + `OPERATOR` | Default-deny elsewhere |
| Feature flags | `operator_config_enabled=False` | Do not flip existing flags' defaults |

**Data flow (recommended):**

```text
Operator browser
  → admin-web-ui (SSR form, CSRF, RBAC)
  → admin-console-api (validate schema, refs-only, allowlist)
  → operator-config.json (atomic write; refs + non-secret settings only)
  → channel hosts / provider_model factory (load config + resolve_secret_ref(env) at process edge)
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Extend admin-console-api + admin-web-ui | New `services/operator-config-service` | Only if write path forces a hard dependency conflict with read-only API packaging; prefer extend first. |
| Stdlib SSR HTML forms | React/Vite SPA admin | If multi-page interactive UX becomes primary product surface later — not justified for v1.10 CRUD. |
| Atomic JSON file store | PostgreSQL / SQLite / Redis | Multi-node shared config with HA requirements; AGENTS.md forbids new DB unless plan requires it. |
| Frozen dataclasses + hand validators | Pydantic 2.13.4 | If console later needs OpenAPI generation or complex nested coercion — would break `dependencies = []` unless optional extra; repo already validates with hand-written validators. |
| Static in-repo model catalog JSON | Live vendor `/models` listing as SoT | Use live list only as optional probe enrichment; catalog SoT stays built-in + operator custom entries. |
| InkStatute config store | Hermes `~/.hermes` / gateway config | Never — Hermes is agent backend, not channel/provider config authority for this product. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| FastAPI / Starlette / Flask as new admin stack | Introduces hard deps; diverges from stdlib hosts (`admin-web-ui`, `qqbot-service`) | Extend existing stdlib handlers |
| React / Next / Vite admin SPA | Overkill for operator forms; CSP/`innerHTML` risk; new frontend toolchain | SSR templates in `admin-web-ui` |
| New Postgres/SQLite/Redis for config | Violates AGENTS “no new DB unless justified”; secrets risk in DB dumps | Atomic JSON file + env secret values |
| Pydantic / jsonschema as **hard** package deps | Entire monorepo uses `dependencies = []`; platform-contract already hand-validates | Dataclasses + explicit validators; optional extras only if plan demands |
| `httpx` / `aiohttp` as hard deps | Rejected repeatedly for channel/host work; urllib + lazy openai suffice | Stdlib / existing lazy OpenAI transport |
| Storing raw API keys / WeCom tokens / QQ secrets in config JSON or git | AGENTS.md + SAFE-02; health allowlist already excludes secret maps | `*_ref` / `api_key_ref` only; resolve at process edge |
| Hermes `~/.hermes` as config SoT or sync target | Product boundary: InkStatute owns channels + provider_model path; Hermes owns agent logic | InkStatute operator config + env |
| Auto-writing Hermes profile / gateway files from the console | Couples product to Hermes internals; leaks meta config into wrong layer | Configure InkStatute provider_model / channels only |
| Committing `.env` or operator-config with values | Secrets in repo | `.env.example` + gitignored runtime paths |

---

## Stack Patterns by Variant

**If operator configures QQ / WeCom channels:**
- Persist `enabled` + secret **refs** matching `QQBotChannelConfig` / `WeComChannelConfig`.
- Dual-knob safety: feature flag + channel `enabled` both default OFF; UI must not imply live IO until both are on and refs resolve.
- Because hosts already implement `from_env` + `resolve_secret_ref`.

**If operator configures built-in vendor or custom OpenAI-compatible provider:**
- Persist `api_base_url`, `api_key_ref`, `model_name`, optional vendor id from catalog.
- Custom endpoints are first-class (Ollama Cloud / local OpenAI-compatible already proven).
- Because `ProviderModelBackendConfig` already uses ref-not-value.

**If main model lacks vision (e.g. text-only GLM) and inbound turn has images:**
- Persist dedicated vision provider/model + `vision_routing` ∈ `{auto, always, never}` per `.env.example`.
- Runtime: `auto` → vision model then main; multimodal main with `supports_vision=true` can skip dedicated vision.
- Because vision routing is an InkStatute provider_model concern, not Hermes gateway config.

**If multi-node deploy needs shared config later:**
- Keep file schema stable; swap store implementation behind a `ConfigStore` protocol (load/save).
- Because premature DB adds ops burden without changing the config schema.

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| Python ≥3.11 | `tomllib`, `dataclasses(slots=True)`, admin SSR hosts | CI floor; do not require 3.14-only APIs |
| `openai` 2.45.0 (optional) | OpenAI-compatible bases (Ollama `/v1`, etc.) | Lazy import inside runners/probes; pin `>=2.45.0,<3` on hosts that install it |
| `admin-console-api` 0.1.0 | `rbac`, `platform-runtime`, `conversation-read-view` | Write routes must honor same auth + tenant guard patterns |
| `provider_model` 0.1.0 | Optional `openai`; `model-gateway` composite | Vision fields additive; do not break existing `api_key_ref` |
| Operator config JSON schema (hand-versioned, e.g. `schema_version: 1`) | Channel + provider_model config dataclasses | Bump version on breaking field renames; reject unknown secret-like keys |

---

## Sources

- In-repo: `services/admin-web-ui/README.md`, `services/admin-console-api` (`handle_admin_get` read-only), `packages/backends/provider_model/config.py`, `packages/model-gateway/config.py`, `services/qqbot-service/src/qqbot_service/secrets.py`, `packages/channels/{qqbot,wecom}/config.py`, `.env.example` vision vars, `packages/platform-runtime/feature_flags.py`, AGENTS.md / PROJECT.md v1.10 — **HIGH**
- PyPI / GitHub: `openai` **2.45.0** (2026-07-09 release) — **HIGH**
- PyPI: `pydantic` 2.13.4, `httpx` 0.28.1, `jsonschema` 4.26.0 — verified current but **not recommended as hard deps** for this milestone — **HIGH** (versions), **HIGH** (avoid as hard deps given monorepo convention)
- Prior research: `.planning/research/STACK.md` (v1.9 host composition) — empty-deps + stdlib HTTP host pattern — **HIGH**

---
*Stack research for: Operator Config Console (v1.10)*
*Researched: 2026-07-10*
