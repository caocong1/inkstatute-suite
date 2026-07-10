# Phase 76: Provider Registry + Model Catalog - Research

**Researched:** 2026-07-10
**Domain:** Operator-config provider registry (built-in vendors + custom OpenAI-compatible), built-in model catalog with `supports_vision`, non-destructive connection probe, incremental SSR forms
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Secrets as refs only; never log/echo resolved secrets or probe response bodies
- No Hermes filesystem as config authority
- Extend admin-console-api + admin-web-ui
- Catalog must include supports_vision for Phase 77

### Claude's Discretion
Discuss skipped — use ROADMAP, research, and codebase conventions. All implementation choices are at the agent's discretion.

### Deferred Ideas (OUT OF SCOPE)
Vision routing runtime (Phase 77), complete SSR/docs/gate honesty (Phase 78). Live `/models` refresh for custom endpoints (PROV-F01). LiteLLM-style budgets / virtual keys (PROV-F02). Per-lawyer self-serve model switching (PROV-F03). Hot-reload without restart.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROV-01 | Operator can select a built-in vendor provider profile (base URL + key ref conventions + catalog binding) without editing Hermes | Code-defined vendor profile tuple in operator-config (vendor_id → preset `api_base_url` + key ref convention); SSR `<select>` of vendor IDs; `ProviderDoc.kind` carries the vendor id; `api_base_url` read-only when built-in |
| PROV-02 | Operator can define a custom OpenAI-compatible provider (`api_base_url` + `api_key_ref` + explicit model allowlist) | Add `model_allowlist` field to `ProviderDoc`; SSR custom card with editable `api_base_url` + `api_key_ref` + comma-separated allowlist; validate allowlist non-empty for `kind=custom` |
| PROV-03 | Operator can pick a main model from a built-in selectable catalog that includes `supports_vision` metadata | New code-defined `BuiltInCatalogEntry` tuple (provider_id, model_id, supports_vision, description) in operator-config; SSR `/config/catalog` radio list with vision badges; `CatalogSelectionDoc` persists provider_id + model_id |
| PROV-04 | Operator can run a non-destructive connection probe for main (and vision when configured) that fail-closes on missing refs and does not log response bodies/secrets | New `POST /config/providers/probe` on admin-console-api (non-mutating, fail-closed on blank `api_key_ref`, stdlib `urllib` GET `/models`, generic status only); SSR probe button per provider card; vision probe deferred to Phase 77 |
</phase_requirements>

## Summary

Phase 73 already ships the refs-only `ProviderDoc` (`provider_id`, `kind`, `enabled`, `api_base_url`, `api_key_ref`, `metadata`) and `CatalogSelectionDoc` (`provider_id`, `model_id`) schemas, and Phase 74 already persists `/config/providers` (list body) and `/config/catalog` (object body) through `OperatorConfigStore` behind `operator_config_enabled`. Phase 76 closes three gaps: (1) the **built-in vendor profiles + built-in model catalog with `supports_vision`** do not exist yet — they must be code-defined data in the `operator-config` package so the API, UI, and Phase 77 runtime share one authority; (2) `ProviderDoc` lacks a **model allowlist** field required by PROV-02 for custom providers; (3) there is **no connection probe** endpoint and no provider/catalog SSR forms. [VERIFIED: `schemas.py`, `config_api.py`, `channels.py`, ROADMAP]

The connection probe (PROV-04) is the highest-risk surface. It must resolve `api_key_ref` at the process edge (env), make a non-destructive `GET {api_base_url}/models` call, and return **generic status only** — never the response body, resolved key, or `Authorization` header. Because Phase 73 locked "no `resolve_secret_ref` and no process-environment reads in operator-config", the probe **cannot** live in `packages/operator-config`. It belongs in `admin-console-api` as a new non-mutating handler, using **stdlib `urllib.request`** (preserves `dependencies = []` — no `openai` hard dep, no `httpx`). The existing `provider_model` package already proves the lazy-import + error-sanitization pattern (`_normalize_api_error`, `_sanitize_error_message`), but importing `provider_model` into `admin-console-api` would add a cross-package dependency; the probe is simple enough for stdlib `urllib` + a local sanitize helper. [VERIFIED: `provider_model/probe.py`, `openai_runner.py`, STACK.md `dependencies = []` invariant]

**Primary recommendation:** Evolve `ProviderDoc` with a `model_allowlist: tuple[str, ...]` field. Add a code-defined `BUILTIN_VENDOR_PROFILES` tuple + `BUILTIN_MODEL_CATALOG` tuple (with `supports_vision`) in `operator-config`. Add `POST /config/providers/probe` to `admin-console-api` (stdlib `urllib`, fail-closed, no body logging). Add `providers.py` + `catalog.py` SSR modules to `admin-web-ui` mirroring Phase 75 `channels.py`. Add duplicate-`provider_id` validation. Keep `operator_config_enabled` as the single gate; no new feature flag. Document restart-to-apply; never claim live acceptance.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Built-in vendor profiles + model catalog data | API / Backend (`operator-config` package) | — | Shared authority for API + UI + Phase 77 runtime; code-defined tuple, not remote fetch (PROV-F01 deferred) |
| Persist provider list + catalog selection (refs only) | API / Backend (`admin-console-api` + `operator-config` store) | — | Phase 74 already owns `/config/providers` + `/config/catalog` PUT |
| Provider schema evolution (model_allowlist) | API / Backend (`operator-config` schemas + store + validate) | — | Frozen dataclass; additive field; `document_from_payload` + `validate_document` update |
| Duplicate provider_id + custom allowlist validation | API / Backend (`operator-config` validate) | — | Fail-closed server-side; UI shows Error — validation |
| Connection probe (non-destructive, secret-resolving) | API / Backend (`admin-console-api` probe handler) | — | operator-config bans env reads (Phase 73); admin-console-api is the process-edge tier that may resolve refs |
| Secret value resolution | Process edge (`admin-console-api` probe only) | — | `os.environ.get(ref)` at probe time; never persisted, never logged |
| SSR provider registry form | Frontend Server (`admin-web-ui/providers.py`) | API proxy | Stdlib SSR; POST → `handle_admin_put` `/config/providers` |
| SSR model catalog form | Frontend Server (`admin-web-ui/catalog.py`) | API proxy | Stdlib SSR; POST → `handle_admin_put` `/config/catalog` |
| SSR probe action | Frontend Server (`admin-web-ui` server.py) | API probe handler | POST `/config/providers/probe`; re-render with ephemeral result |
| Vision probe | Deferred Phase 77 | — | Vision config is Phase 77; this phase probes main provider endpoint only |
| Full CSRF / docs / gate honesty | Deferred Phase 78 | — | CONTEXT: incremental forms OK now; Phase 78 verifies complete surface |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `inkstatute_operator_config` | in-repo (Phase 73) | Provider/catalog schemas, store, refs-only validation | Already the config authority; extend with vendor profiles + catalog data + `model_allowlist` |
| `admin_console_api` | in-repo (Phase 74) | `/config/providers` + `/config/catalog` GET/PUT; new probe handler | Already owns auth, RBAC, config mutate; add non-mutating probe |
| `admin_web_ui` | in-repo (Phase 75) | SSR forms via stdlib `http.server` + `html.escape` + CSP | Phase 75 `channels.py` is the exact pattern to mirror |
| Python 3.11+ stdlib `urllib.request` | stdlib | Connection probe HTTP call (GET `/models`) | Preserves `dependencies = []`; no `openai`/`httpx` hard dep; probe is a single GET |
| Python 3.11+ stdlib `html` / `json` / `dataclasses` | stdlib | SSR escaping, catalog data, frozen schemas | Existing pattern across operator-config + admin-web-ui |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `openai` (optional, lazy) | 2.45.0 (PyPI, 2026-07-09) | Optional host-only runtime for provider_model runners | **Not required for Phase 76 probe** — probe uses stdlib `urllib`. Keep as optional host install for Phase 77 runtime only |
| `rbac` | in-repo | ADMIN/OPERATOR-only `/config/*` + probe | Phase 74 matrix already denies LAWYER/VIEWER on `/config` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib `urllib.request` for probe | `openai` SDK lazy import | `urllib` preserves `dependencies = []` and avoids optional-dep import complexity; probe is a single GET — SDK is overkill. Rejected: would couple admin-console-api to optional `openai` |
| stdlib `urllib.request` for probe | `httpx` / `aiohttp` | Repeatedly rejected across v1.9/v1.10 research; breaks empty-deps invariant |
| Code-defined catalog tuple | Live vendor `/models` as SoT | PROV-F01 deferred; live list is optional enrichment only; catalog SoT stays built-in |
| Code-defined catalog tuple | JSON file artifact | UI-SPEC says "code-defined (a fixed tuple)"; a tuple in `operator-config` is importable by API + UI + runtime without file IO. JSON file is viable but adds a data path; prefer tuple for MVP |
| Probe in `operator-config` | Probe in `admin-console-api` | operator-config bans env reads (Phase 73 locked decision); probe MUST resolve ref → env, so it lives in admin-console-api |

**Installation:**
```bash
# No new hard dependencies. Phase 76 uses only stdlib + in-repo packages.
pip install -e packages/operator-config
pip install -e services/admin-console-api
pip install -e services/admin-web-ui

# Optional (host-only, NOT required for Phase 76 probe):
# pip install "openai>=2.45.0,<3"   # only for Phase 77 runtime runners
```

**Version verification:**
```bash
# openai (optional, not a Phase 76 hard dep) — verified current:
# openai 2.45.0 (PyPI, 2026-07-09) [VERIFIED: PyPI registry]
python3 -c "import urllib.request, json, html, dataclasses; print('stdlib ok')"
```

## Package Legitimacy Audit

> Phase 76 installs **no external packages**. All work is stdlib + in-repo packages. No slopcheck run required (no new packages to audit).

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| (none — stdlib + in-repo only) | — | — | — | — | — | N/A |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*No external packages are installed by this phase. The optional `openai>=2.45.0,<3` is a host-only runtime install for Phase 77 runners, not a Phase 76 dependency.*

## Architecture Patterns

### System Architecture Diagram

```
Operator (browser)
  │  GET /config/providers        (SSR page)
  │  POST /config/providers       (save list)
  │  POST /config/providers/probe (non-destructive)
  │  GET /config/catalog          (SSR page)
  │  POST /config/catalog         (save selection)
  ▼
admin-web-ui (stdlib http.server)
  │  parse providers_form / catalog_form
  │  CSRF token (incremental; Phase 78 completes)
  │  html.escape all dynamic content
  ▼
admin-console-api
  │  handle_admin_get  → /config/providers | /config/catalog  (Phase 74, refs-only)
  │  handle_admin_put  → /config/providers (list) | /config/catalog (object)
  │  handle_config_probe → POST /config/providers/probe  (NEW, non-mutating)
  │     │  fail-close if api_key_ref blank → no network call
  │     │  resolve api_key_ref → os.environ (process edge ONLY)
  │     │  urllib GET {api_base_url}/models  (non-destructive)
  │     │  return generic ok/fail (never body/secret/header)
  ▼
operator-config (packages/operator-config)
  │  ProviderDoc (+ model_allowlist)  ←─ validate_document (refs + duplicates + allowlist)
  │  CatalogSelectionDoc (provider_id, model_id)
  │  BUILTIN_VENDOR_PROFILES (vendor_id → api_base_url + key ref convention)  (NEW)
  │  BUILTIN_MODEL_CATALOG (provider_id, model_id, supports_vision, desc)     (NEW)
  │  OperatorConfigStore.save (flag gate → validate → atomic write)
  ▼
.inkstatute/operator-config.json (refs only, never raw secrets)

Phase 77 (deferred): runtime reads catalog selection + supports_vision → vision router
```

### Recommended Project Structure

```
packages/operator-config/src/inkstatute_operator_config/
├── schemas.py          # MODIFY: add ProviderDoc.model_allowlist; add BuiltInCatalogEntry + catalog tuple
├── store.py            # MODIFY: document_from_payload parses model_allowlist
├── validate.py         # MODIFY: duplicate provider_id + custom allowlist-non-empty checks
├── catalog.py          # NEW: BUILTIN_VENDOR_PROFILES + BUILTIN_MODEL_CATALOG (code-defined tuples)
└── tests/              # ADD: test_catalog.py, extend test_validate_document.py, test_schemas.py

services/admin-console-api/src/admin_console_api/
├── config_api.py       # MODIFY: providers/catalog metadata (apply_semantics); add probe handler OR new module
├── probe.py            # NEW: non-destructive connection probe (stdlib urllib, fail-closed, no body log)
└── tests/              # ADD: test_config_providers.py, test_config_catalog.py, test_config_probe.py

services/admin-web-ui/src/admin_web_ui/
├── providers.py        # NEW: SSR provider registry form (render + parse), mirroring channels.py
├── catalog.py          # NEW: SSR model catalog form (render + parse), mirroring channels.py
├── server.py           # MODIFY: _SECTION_MAP + POST dispatch + probe route + nav
├── dashboard.py        # MODIFY: nav links (Provider Config, Model Catalog) + index cards
└── tests/              # ADD: test_providers_form.py, test_catalog_form.py, test_probe_action.py
```

### Pattern 1: Code-Defined Catalog + Vendor Profiles (not remote fetch)
**What:** A frozen tuple of `BuiltInCatalogEntry` dataclasses and a frozen tuple of vendor profile dicts live in `operator-config/catalog.py`. The API exposes them via GET metadata; the SSR form renders them as read-only radio rows / read-only base URLs.
**When to use:** Always for v1.10 MVP. PROV-F01 (live `/models` refresh) is deferred.
**Trade-offs:** Catalog updates require a code change + redeploy — acceptable for MVP; avoids remote-registry coupling and auto-enable-all risk.
**Example:**
```python
# packages/operator-config/src/inkstatute_operator_config/catalog.py
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class BuiltInCatalogEntry:
    provider_id: str   # "openai", "anthropic", ...
    model_id: str      # "gpt-4o", "claude-sonnet-4", ...
    supports_vision: bool
    description: str | None = None

BUILTIN_MODEL_CATALOG: tuple[BuiltInCatalogEntry, ...] = (
    BuiltInCatalogEntry("openai", "gpt-4o", True, "Multimodal main model"),
    BuiltInCatalogEntry("openai", "gpt-4o-mini", True, "Smaller multimodal model"),
    BuiltInCatalogEntry("anthropic", "claude-sonnet-4", True, "Anthropic multimodal"),
    # ...
)

@dataclass(frozen=True, slots=True)
class VendorProfile:
    vendor_id: str
    api_base_url: str
    default_key_ref_env: str   # convention only; operator still sets the ref

BUILTIN_VENDOR_PROFILES: tuple[VendorProfile, ...] = (
    VendorProfile("openai", "https://api.openai.com/v1", "OPENAI_API_KEY"),
    VendorProfile("anthropic", "https://api.anthropic.com/v1", "ANTHROPIC_API_KEY"),
    # ...
)
```

### Pattern 2: Non-Destructive Connection Probe (stdlib, fail-closed, no body log)
**What:** `POST /config/providers/probe` resolves `api_key_ref` from `os.environ` at the process edge, issues a single `urllib.request` GET to `{api_base_url}/models`, and returns a generic `ok`/`fail` status. It never calls `store.save`, never logs the response body, resolved key, or `Authorization` header, and fail-closes (no network call) when the ref is blank or unresolved.
**When to use:** PROV-04 only. Vision probe deferred to Phase 77.
**Trade-offs:** `GET /models` is the lightest non-destructive OpenAI-compatible reachability check; some custom endpoints may not implement `/models` — the probe treats non-200 as "could not reach" with the generic fail copy (no status code leaked to UI).
**Example:**
```python
# services/admin-console-api/src/admin_console_api/probe.py
import os, urllib.request, urllib.error

def probe_provider(provider_id, api_base_url, api_key_ref, *, env=None):
    # Fail-closed on missing ref — NO network call.
    if not api_key_ref or not api_key_ref.strip():
        return {"ok": False, "code": "missing_ref"}
    source = env if env is not None else os.environ
    # Resolve ref → env value at the edge ONLY.
    key = source.get(_ref_env_name(api_key_ref), "")
    if not key:
        return {"ok": False, "code": "missing_ref"}
    try:
        req = urllib.request.Request(
            f"{api_base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            # We do NOT read/log the body. Status-only.
            resp.getcode()  # touch to force response
        return {"ok": True, "code": "ok"}
    except urllib.error.HTTPError as exc:
        # Sanitize: never leak status code, body, or URL to UI/logs.
        return {"ok": False, "code": "auth_error" if exc.code in (401, 403) else "network"}
    except Exception:
        return {"ok": False, "code": "network"}
```

### Pattern 3: SSR Form Module (mirror channels.py)
**What:** Each config surface gets a dedicated module (`providers.py`, `catalog.py`) with `render_*_page`, `render_*_form`, `parse_*_form` functions, UI-SPEC copy constants, and `html.escape` on every dynamic string. The server.py dispatcher calls these like `_handle_channels`.
**When to use:** All Phase 76 SSR forms.
**Trade-offs:** One module per page keeps single-purpose composition (UI-SPEC rule); duplicates `_esc`/`_form_get` helpers — acceptable for MVP (Phase 78 may extract shared helpers).
**Example:**
```python
# services/admin-web-ui/src/admin_web_ui/providers.py
def render_providers_page(api_data, identity=None, boundary=None, *,
                          csrf_token=None, read_only=False, flash=None,
                          flash_kind="success", error_message=None,
                          probe_result=None) -> str: ...
def parse_providers_form(form) -> list[dict]:  # list body for PUT /config/providers
    # Drop blank provider_id entries; parse providers[N].* fields
    ...
```

### Pattern 4: Metadata Preservation on PUT (WR-01 carry)
**What:** When the SSR form does not expose `ProviderDoc.metadata`, the POST handler re-GETs the current section and merges stored `metadata` back into each provider entry before PUT — same as `_merge_channel_metadata_from_current` in `server.py`.
**When to use:** Provider save POST (metadata not in MVP form).
**Trade-offs:** Extra GET before PUT; preserves API-set metadata without exposing it in the UI.

## Don't Hand-Roll

| Problem | Use Instead | Why |
|---------|-------------|-----|
| Secret ref shape validation | `normalize_config_secret_ref` (Phase 73) | Already rejects raw secrets, `sk-…` markers, non-ref shapes; reuse for `api_key_ref` |
| Hermes filesystem ban | `FORBIDDEN_PATH_SUBSTRINGS` + `FORBIDDEN_HERMES_FIELD_NAMES` (Phase 73) | Already walks metadata; provider `api_base_url` / metadata scanned automatically |
| Atomic config persistence | `OperatorConfigStore.save` (Phase 73) | Flag gate → validate → temp+rename; never reimplement |
| SSR escaping + CSP | `html.escape` + `_page_template` + `CSP_HEADER` (admin-web-ui) | Existing dashboard/channels pattern; never `innerHTML` |
| RBAC + flag gating | `handle_admin_get` / `handle_admin_put` auth pipeline (Phase 74) | Already does flag → auth → RBAC → tenant; probe handler reuses the same pipeline |
| Error sanitization (probe) | Local sanitize helper (strip URLs/tokens/paths/model names) | Mirror `provider_model._sanitize_error_message` pattern; do NOT import provider_model (avoid cross-dep) |
| Planted-secret negative tests | Phase 74 test pattern (`sk-…` in body → assert 400 + absent from JSON) | Already proven in `test_config_api.py` |

## Common Pitfalls

1. **Resolving secrets inside `operator-config`** — Phase 73 locked "no `resolve_secret_ref` and no process-environment reads in operator-config package". The probe MUST live in `admin-console-api` (or another process-edge tier). Putting `os.environ.get` in `operator-config` violates the locked decision and breaks the package boundary. [VERIFIED: STATE.md Phase 73 decisions]

2. **Logging probe response bodies or resolved keys** — PROV-04 explicitly forbids logging response bodies/secrets. The probe must return generic `ok`/`fail` + a code only. Server logs at most `provider_id` + boolean. Never log `Authorization` header, resolved key, HTTP status code (leaks to UI), or `/models` response JSON. UI-SPEC copy strings are generic. [VERIFIED: UI-SPEC Probe result copy]

3. **Probe mutating config** — The probe must never call `store.save`. It is a read-only `POST` that resolves a ref + issues a GET. Route it as a distinct path (`/config/providers/probe`) so `_parse_section` (which only accepts `/config/{section}` with no sub-path) does not treat it as a section PUT. [VERIFIED: `config_api._parse_section` rejects paths with `/`]

4. **Auto-enabling all `/models` entries** — PROV-F01 (live `/models` refresh) is deferred. The probe uses `/models` only for reachability, never to populate the catalog or allowlist. The built-in catalog is code-defined. [VERIFIED: REQUIREMENTS PROV-F01 deferred, UI-SPEC "not fetched from remote"]

5. **Missing `supports_vision` on catalog entries** — Phase 77 depends on every catalog entry having a boolean `supports_vision`. The schema/dataclass must require it (no default-to-None that Phase 77 misreads as false). UI-SPEC: "required on every catalog entry (boolean)". [VERIFIED: UI-SPEC, ROADMAP Phase 77 depends on Phase 76 catalog]

6. **`model_allowlist` absent from `ProviderDoc`** — PROV-02 requires an explicit model allowlist for custom providers. The current `ProviderDoc` has no such field. Forgetting to add it (or stuffing it into `metadata`) means custom providers cannot satisfy PROV-02 and validation cannot enforce non-empty allowlist for `kind=custom`. Add as a first-class frozen-tuple field. [VERIFIED: `schemas.py` ProviderDoc has no allowlist field]

7. **Duplicate `provider_id` in the registry** — UI-SPEC requires server-side rejection of duplicate IDs. `validate_document` currently does not check provider uniqueness. Add a duplicate-scan in `OperatorConfigValidator._check_credential_refs` or a new validator method. [VERIFIED: `validate.py` has no uniqueness check]

8. **Collapsing built-in `api_base_url` to editable** — UI-SPEC: built-in vendor `api_base_url` is read-only (preset); only custom providers have an editable base URL. If the SSR form makes it always editable, an operator could point `openai` kind at an arbitrary URL and break the catalog binding. Render read-only text for built-in kind; editable input only for `custom`. [VERIFIED: UI-SPEC Interaction Contract]

9. **Probe bypassing `operator_config_enabled` flag gate** — UI-SPEC: "Probe does not bypass the flag gate." If the flag is OFF, the probe button is disabled and the handler returns the flag-off error. Do not route the probe around the flag check. [VERIFIED: UI-SPEC Form Field Contract]

10. **Echoing rejected raw secrets in validation errors** — Phase 73 invariant: validation errors expose codes@paths only. When adding duplicate/allowlist validators, never include the rejected value in the message. [VERIFIED: `validate_document` summary format]

11. **SSR POST body wiping providers on empty submit** — Mirror `_channels_post_body_usable`: reject POST bodies with no `providers[N].*` fields so an empty submit does not persist an empty list and wipe stored providers. Drop blank-`provider_id` entries on parse. [VERIFIED: `server.py _channels_post_body_usable`]

12. **Auto-claiming live acceptance** — DOC-02 / `not_live_acceptance`: saving provider/catalog config must not claim Phase 5/8/QQ `--live` acceptance. Success flash says "Restart runtime to apply" only. [VERIFIED: REQUIREMENTS DOC-02, AGENTS.md]

## Validation Architecture

**Test infrastructure:** `unittest` (existing), `pytest` runner via `scripts/run_v2_gates.py`, per-package `tests/` dirs. No new test framework. [VERIFIED: existing test layout]

### Requirements → Tests

| Requirement | Behavior | Test Type | Automated Command (<30s) |
|-------------|----------|-----------|--------------------------|
| PROV-01 | Built-in vendor profile selectable; base URL preset; no Hermes edit | unit + integration | `python -m pytest packages/operator-config/tests/test_catalog.py services/admin-console-api/tests/test_config_providers.py -q` |
| PROV-02 | Custom provider with api_base_url + api_key_ref + model allowlist persisted | unit + integration | `python -m pytest packages/operator-config/tests/test_schemas.py services/admin-console-api/tests/test_config_providers.py -q` |
| PROV-03 | Catalog selection persists provider_id + model_id; supports_vision metadata present | unit + integration | `python -m pytest packages/operator-config/tests/test_catalog.py services/admin-console-api/tests/test_config_catalog.py -q` |
| PROV-04 | Probe fail-closes on missing ref; no body/secret logging; non-mutating | unit | `python -m pytest services/admin-console-api/tests/test_config_probe.py -q` |
| SSR forms | Providers + catalog pages render + parse + POST roundtrip | unit | `python -m pytest services/admin-web-ui/tests/test_providers_form.py services/admin-web-ui/tests/test_catalog_form.py -q` |
| Planted secrets | `sk-…` in provider body → 400 + absent from JSON | unit | `python -m pytest services/admin-console-api/tests/test_config_providers.py -q` |
| Duplicate provider_id | Two entries same id → 400 invalid_config | unit | `python -m pytest packages/operator-config/tests/test_validate_document.py -q` |
| RBAC | LAWYER/VIEWER denied GET+PUT /config/providers + probe | integration | `python -m pytest services/admin-console-api/tests/test_rbac_integration.py -q` |

### Wave 0 Gaps

- No `test_config_providers.py` / `test_config_catalog.py` / `test_config_probe.py` exist yet (only `test_config_api.py` + `test_config_channels_effective.py`)
- No `test_providers_form.py` / `test_catalog_form.py` exist (only `test_channels_form.py`)
- No `test_catalog.py` in operator-config (catalog data does not exist yet)
- `ProviderDoc.model_allowlist` field + parser + validator does not exist
- Duplicate `provider_id` validator does not exist
- Probe handler + route does not exist
- SSR provider/catalog modules + server routes do not exist

**Wave 0 plan should:** add failing/scaffold tests for all the above before implementation waves, mirroring Phase 75's Wave 0 approach (scaffolds intentionally fail until later plans implement production code).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | All packages | ✓ | stdlib | — |
| `urllib.request` | Probe HTTP call | ✓ | stdlib | — |
| `openai` SDK | Phase 76 probe | ✗ (not required) | — | stdlib `urllib` (probe does not use the SDK) |
| `openai` SDK (optional) | Phase 77 runtime | not installed in CI | — | Lazy import in provider_model runners only; Phase 76 probe uses stdlib |
| `inkstatute_operator_config` | Schemas/store/catalog | ✓ | in-repo | — |
| `admin_console_api` | Config API + probe | ✓ | in-repo | — |
| `admin_web_ui` | SSR forms | ✓ | in-repo | — |

**Missing dependencies with no fallback:** none
**Missing dependencies with fallback:** `openai` SDK not required for Phase 76 (stdlib `urllib` probe); optional host install for Phase 77 only.

## Code Examples

### Evolving ProviderDoc (additive, frozen dataclass)
```python
# packages/operator-config/src/inkstatute_operator_config/schemas.py
@dataclass(frozen=True, slots=True)
class ProviderDoc:
    provider_id: str = ""
    kind: str = ""                       # "openai" | "anthropic" | ... | "custom"
    enabled: bool = False
    api_base_url: str | None = None
    api_key_ref: str | None = None
    model_allowlist: tuple[str, ...] = ()  # NEW — required non-empty for kind="custom"
    metadata: JsonObject = field(default_factory=dict)
```

### Store parser update (document_from_payload)
```python
# providers loop in document_from_payload:
allowlist_raw = item.get("model_allowlist") or ()
if not isinstance(allowlist_raw, (list, tuple)):
    raise OperatorConfigStoreError(f"providers[{index}].model_allowlist must be a list")
providers.append(ProviderDoc(
    ...,
    model_allowlist=tuple(str(m) for m in allowlist_raw),
))
```

### Duplicate + custom-allowlist validation
```python
# OperatorConfigValidator — new method called from validate():
def _check_provider_uniqueness(self, doc) -> list[ValidationIssue]:
    seen: set[str] = set()
    issues: list[ValidationIssue] = []
    for index, p in enumerate(doc.providers):
        if not p.provider_id:
            continue
        if p.provider_id in seen:
            issues.append(ValidationIssue(
                path=f"providers[{index}].provider_id",
                code="duplicate_provider_id",
                message=f"duplicate provider_id at providers[{index}]",
            ))
        seen.add(p.provider_id)
    return issues

def _check_custom_allowlist(self, doc) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for index, p in enumerate(doc.providers):
        if p.kind == "custom" and not p.model_allowlist:
            issues.append(ValidationIssue(
                path=f"providers[{index}].model_allowlist",
                code="custom_provider_requires_allowlist",
                message=f"custom providers require a non-empty model_allowlist",
            ))
    return issues
```

### SSR provider card parse (drop blanks)
```python
# services/admin-web-ui/src/admin_web_ui/providers.py
def parse_providers_form(form) -> list[dict]:
    # Collect providers[N].* fields, drop entries with blank provider_id.
    parsed = parse_qs(form, keep_blank_values=True) if isinstance(form, (str, bytes)) else form
    indices = sorted({_index_from_key(k) for k in parsed if k.startswith("providers[")})
    providers = []
    for i in indices:
        pid = _form_get(parsed, f"providers[{i}].provider_id")
        if not pid:
            continue  # blank entry dropped
        providers.append({
            "provider_id": pid,
            "kind": _form_get(parsed, f"providers[{i}].kind") or "custom",
            "enabled": _form_checkbox(parsed, f"providers[{i}].enabled"),
            "api_base_url": _form_get(parsed, f"providers[{i}].api_base_url"),
            "api_key_ref": _form_get(parsed, f"providers[{i}].api_key_ref"),
            "model_allowlist": _split_csv(_form_get(parsed, f"providers[{i}].model_allowlist")),
            "metadata": {},  # merged from current on POST (WR-01)
        })
    return providers
```

## Project Constraints (from AGENTS.md)

- **Source of truth:** V2-PRD; V1 retired. Do not reintroduce V1 requirements.
- **Hermes boundary:** Do not rebuild Hermes core/session/router/skill registry/MCP registry/model gateway. Hermes is agent backend only; configure InkStatute provider_model/channels only.
- **Secrets:** Never commit secrets/tokens/runtime DBs/logs/customer docs/raw legal payloads. Contract logs prefer refs (`raw_payload_ref`). Provider `api_key_ref` is a ref only.
- **Output boundary:** Backend/gateway/system notices suppressed/converted before WeCom delivery. Probe errors must not leak provider stack traces to ordinary users (Phase 77 owns vision error boundary; Phase 76 probe UI copy is generic).
- **Coding rules:** Keep changes scoped to Phase 76. Add tests before/with behavior changes (schemas, validators, probe, SSR parse/roundtrip). Prefer structured validators over ad hoc parsing. No new service/DB/queue/runtime dep unless Phase 76 plan requires (none required — stdlib + in-repo only). Update docs/GSD artifacts when implementation decisions change.

## Open Questions

1. **Exact built-in vendor list + catalog model entries** — UI-SPEC names `openai`, `anthropic` as examples but the full tuple is at the agent's discretion. The planner should pick a minimal, defensible set (e.g. `openai`, `anthropic`) with 2–4 catalog models each, all with explicit `supports_vision` booleans. Confirm `api_base_url` presets against current vendor docs during implementation (Anthropic base URL may differ from `https://api.anthropic.com/v1`). [ASSUMED — verify vendor base URLs at implementation time]

2. **Probe path: `GET /models` vs `GET /` vs 1-token chat completion** — `GET /models` is the lightest non-destructive OpenAI-compatible check, but not all custom endpoints implement it. Recommendation: use `GET /models` and treat any non-2xx as generic "could not reach" (no status code leaked). If a vendor is known to not implement `/models`, the probe still fail-closes safely. [ASSUMED — `GET /models` is the OpenAI-compatible convention]

3. **Anthropic probe dialect** — Anthropic Messages API uses `x-api-key` header, not `Authorization: Bearer`. The stdlib probe uses `Authorization: Bearer` (OpenAI-compatible). For built-in `anthropic` kind, the probe may need a vendor-specific header. Simplest MVP: probe is OpenAI-compatible-only; Anthropic built-in probe uses the Anthropic header convention. The planner should decide whether the probe branches on `kind` or stays OpenAI-compatible-only for MVP. [ASSUMED — recommend kind-aware header in probe helper]

4. **`CatalogSelectionDoc` referencing a provider not in the registry** — UI-SPEC says catalog save is rejected when no providers configured. Should validation also reject a catalog selection whose `provider_id` is not in the stored `providers` list? Recommend yes (cross-section consistency check in `validate_document`). [ASSUMED — recommend adding]

5. **`model_allowlist` for built-in vendors** — UI-SPEC says built-in vendors show a read-only "Built-in catalog provided" note. Should `model_allowlist` be empty/stored for built-in kind, or populated from the catalog? Recommend: built-in vendors store an empty allowlist (catalog is the authority); custom providers require a non-empty allowlist. [ASSUMED — recommend this split]

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | stdlib + in-repo only; no new deps; openai 2.45.0 verified on PyPI as optional-only |
| Architecture | HIGH | Phase 73/74/75 patterns directly verified in codebase; operator-config boundary + admin-console-api + admin-web-ui all confirmed |
| Schema evolution | HIGH | ProviderDoc, store.py, validate.py read in full; additive `model_allowlist` + new catalog data are straightforward |
| Probe design | HIGH | provider_model probe + openai_runner lazy-import pattern verified; stdlib urllib preserves empty-deps; Phase 73 env-read ban confirmed |
| Pitfalls | HIGH | All pitfalls sourced from locked STATE.md decisions, UI-SPEC copy, and direct codebase inspection |
| Built-in catalog content | MEDIUM | Exact vendor/model list is at agent discretion; vendor base URLs need implementation-time verification |

---

*Research completed: 2026-07-10*
*Ready for planning: yes*
