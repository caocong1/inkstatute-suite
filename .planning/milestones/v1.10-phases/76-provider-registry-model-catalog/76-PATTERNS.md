# Phase 76: Provider Registry + Model Catalog - Pattern Map

**Mapped:** 2026-07-10
**Files analyzed:** 14 (7 new, 7 modified)
**Analogs found:** 14 / 14

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `packages/operator-config/src/inkstatute_operator_config/schemas.py` (MODIFY) | model | transform | `packages/operator-config/src/inkstatute_operator_config/schemas.py` (self — `ProviderDoc`) | exact (self-evolve) |
| `packages/operator-config/src/inkstatute_operator_config/catalog.py` (NEW) | model / config | transform | `packages/operator-config/src/inkstatute_operator_config/schemas.py` (`ProviderDoc` frozen dataclass pattern) | role-match |
| `packages/operator-config/src/inkstatute_operator_config/store.py` (MODIFY) | store | CRUD | `packages/operator-config/src/inkstatute_operator_config/store.py` (self — `document_from_payload` providers loop) | exact (self-evolve) |
| `packages/operator-config/src/inkstatute_operator_config/validate.py` (MODIFY) | middleware | CRUD | `packages/operator-config/src/inkstatute_operator_config/validate.py` (self — `_check_credential_refs`) | exact (self-evolve) |
| `packages/operator-config/src/inkstatute_operator_config/__init__.py` (MODIFY) | config | transform | `packages/operator-config/src/inkstatute_operator_config/__init__.py` (self — public re-exports) | exact (self-evolve) |
| `services/admin-console-api/src/admin_console_api/probe.py` (NEW) | service | request-response | `packages/backends/provider_model/src/inkstatute_backends_provider_model/probe.py` + `openai_runner.py` (`_sanitize_error_message`) | role-match |
| `services/admin-console-api/src/admin_console_api/config_api.py` (MODIFY) | controller | request-response | `services/admin-console-api/src/admin_console_api/config_api.py` (self — `handle_config_get`/`handle_config_put`) | exact (self-evolve) |
| `services/admin-console-api/src/admin_console_api/api.py` (MODIFY) | controller | request-response | `services/admin-console-api/src/admin_console_api/api.py` (self — `handle_admin_get` route dispatch) | exact (self-evolve) |
| `services/admin-console-api/src/admin_console_api/routes.py` (MODIFY) | config | transform | `services/admin-console-api/src/admin_console_api/routes.py` (self — `ROUTE_PREFIXES`) | exact (self-evolve) |
| `services/admin-web-ui/src/admin_web_ui/providers.py` (NEW) | component | request-response | `services/admin-web-ui/src/admin_web_ui/channels.py` | exact |
| `services/admin-web-ui/src/admin_web_ui/catalog.py` (NEW) | component | request-response | `services/admin-web-ui/src/admin_web_ui/channels.py` | exact |
| `services/admin-web-ui/src/admin_web_ui/server.py` (MODIFY) | controller | request-response | `services/admin-web-ui/src/admin_web_ui/server.py` (self — `_handle_channels` + `_SECTION_MAP`) | exact (self-evolve) |
| `services/admin-web-ui/src/admin_web_ui/dashboard.py` (MODIFY) | component | transform | `services/admin-web-ui/src/admin_web_ui/dashboard.py` (self — `_page_template` nav_items) | exact (self-evolve) |
| `packages/operator-config/tests/test_catalog.py` (NEW) | test | transform | `packages/operator-config/tests/test_schemas.py` | role-match |
| `services/admin-console-api/tests/test_config_providers.py` (NEW) | test | request-response | `services/admin-console-api/tests/test_config_api.py` | exact |
| `services/admin-console-api/tests/test_config_catalog.py` (NEW) | test | request-response | `services/admin-console-api/tests/test_config_api.py` | exact |
| `services/admin-console-api/tests/test_config_probe.py` (NEW) | test | request-response | `services/admin-console-api/tests/test_config_api.py` + `test_channels_form.py` fake-get pattern | role-match |
| `services/admin-web-ui/tests/test_providers_form.py` (NEW) | test | request-response | `services/admin-web-ui/tests/test_channels_form.py` | exact |
| `services/admin-web-ui/tests/test_catalog_form.py` (NEW) | test | request-response | `services/admin-web-ui/tests/test_channels_form.py` | exact |
| `packages/operator-config/tests/test_validate_document.py` (MODIFY) | test | CRUD | `packages/operator-config/tests/test_validate_document.py` (self) | exact (self-evolve) |
| `packages/operator-config/tests/test_schemas.py` (MODIFY) | test | transform | `packages/operator-config/tests/test_schemas.py` (self) | exact (self-evolve) |

## Pattern Assignments

### `packages/operator-config/src/inkstatute_operator_config/schemas.py` (model, transform)

**Analog:** self — `ProviderDoc` dataclass (lines 65-74)

**Existing `ProviderDoc` to extend** (lines 65-74):
```python
@dataclass(frozen=True, slots=True)
class ProviderDoc:
    """Provider registry entry: refs-only credentials, disabled by default."""

    provider_id: str = ""
    kind: str = ""
    enabled: bool = False
    api_base_url: str | None = None
    api_key_ref: str | None = None
    metadata: JsonObject = field(default_factory=dict)
```

**Additive field** — insert `model_allowlist: tuple[str, ...] = ()` between `api_key_ref` and `metadata` (RESEARCH lines 351-363). Keep `frozen=True, slots=True`. Also add `BuiltInCatalogEntry` + `VendorProfile` frozen dataclasses here OR in the new `catalog.py` (RESEARCH recommends `catalog.py` — see below). `CatalogSelectionDoc` (lines 77-82) already has `provider_id` + `model_id` — no change needed.

**Imports pattern** (lines 6-9):
```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
```

**`__all__` update** (lines 13-21) — add `"BuiltInCatalogEntry"` if defined here, or leave to `catalog.py`.

---

### `packages/operator-config/src/inkstatute_operator_config/catalog.py` (NEW — model/config, transform)

**Analog:** `packages/operator-config/src/inkstatute_operator_config/schemas.py` (`ProviderDoc` frozen dataclass pattern) + RESEARCH Pattern 1 (lines 176-210)

**Imports pattern** (copy from `schemas.py` lines 6-9):
```python
from __future__ import annotations
from dataclasses import dataclass
```

**Core pattern — frozen dataclass tuples** (RESEARCH lines 181-210):
```python
@dataclass(frozen=True, slots=True)
class BuiltInCatalogEntry:
    provider_id: str
    model_id: str
    supports_vision: bool
    description: str | None = None

BUILTIN_MODEL_CATALOG: tuple[BuiltInCatalogEntry, ...] = (
    BuiltInCatalogEntry("openai", "gpt-4o", True, "Multimodal main model"),
    # ...
)

@dataclass(frozen=True, slots=True)
class VendorProfile:
    vendor_id: str
    api_base_url: str
    default_key_ref_env: str

BUILTIN_VENDOR_PROFILES: tuple[VendorProfile, ...] = (
    VendorProfile("openai", "https://api.openai.com/v1", "OPENAI_API_KEY"),
    # ...
)
```

Mirror the `frozen=True, slots=True` dataclass convention from `schemas.py` (lines 24, 41, 57, 65, 77, 85, 94). `supports_vision` must be a required bool (no default-to-None — RESEARCH Pitfall 5, line 289). Export via `__all__`.

---

### `packages/operator-config/src/inkstatute_operator_config/store.py` (store, CRUD)

**Analog:** self — `document_from_payload` providers loop (lines 103-120)

**Existing providers parse loop to extend** (lines 103-120):
```python
providers: list[ProviderDoc] = []
for index, item in enumerate(providers_raw):
    if not isinstance(item, Mapping):
        raise OperatorConfigStoreError(f"providers[{index}] must be an object")
    providers.append(
        ProviderDoc(
            provider_id=str(item.get("provider_id", "")),
            kind=str(item.get("kind", "")),
            enabled=bool(item.get("enabled", False)),
            api_base_url=_optional_str(
                item.get("api_base_url"), f"providers[{index}].api_base_url"
            ),
            api_key_ref=_optional_str(
                item.get("api_key_ref"), f"providers[{index}].api_key_ref"
            ),
            metadata=dict(_as_object(item.get("metadata"), f"providers[{index}].metadata")),
        )
    )
```

**Add `model_allowlist` parse** (RESEARCH lines 366-374) — insert before `metadata=`:
```python
allowlist_raw = item.get("model_allowlist") or ()
if not isinstance(allowlist_raw, (list, tuple)):
    raise OperatorConfigStoreError(f"providers[{index}].model_allowlist must be a list")
# ... then in ProviderDoc(...):
model_allowlist=tuple(str(m) for m in allowlist_raw),
```

**Imports pattern** (lines 8-29) — add `BuiltInCatalogEntry`, `VendorProfile` to the `from .schemas import (...)` block only if they live in `schemas.py`; otherwise import from `.catalog` in `__init__.py` re-export. `document_from_payload` / `document_to_payload` (lines 50-52) use `asdict` — the new field serializes automatically.

**Error handling pattern** — `OperatorConfigStoreError` with `f"providers[{index}].<field> must be ..."` (lines 98, 106). Reuse `_optional_str` (lines 64-70) and `_as_object` (lines 55-61) helpers.

---

### `packages/operator-config/src/inkstatute_operator_config/validate.py` (middleware, CRUD)

**Analog:** self — `_check_credential_refs` (lines 89-121) + `validate` (lines 83-87)

**Existing validator dispatch** (lines 83-87):
```python
def validate(self, doc: OperatorConfigDocument) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues.extend(self._check_credential_refs(doc))
    issues.extend(self._walk_value("", asdict(doc)))
    return issues
```

**Add two new validator methods** (RESEARCH lines 378-404) and call them from `validate()`:
```python
issues.extend(self._check_provider_uniqueness(doc))
issues.extend(self._check_custom_allowlist(doc))
```

**Duplicate provider_id pattern** (RESEARCH lines 380-393):
```python
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
```

**Custom allowlist pattern** (RESEARCH lines 395-404):
```python
def _check_custom_allowlist(self, doc) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for index, p in enumerate(doc.providers):
        if p.kind == "custom" and not p.model_allowlist:
            issues.append(ValidationIssue(
                path=f"providers[{index}].model_allowlist",
                code="custom_provider_requires_allowlist",
                message="custom providers require a non-empty model_allowlist",
            ))
    return issues
```

**Error message invariant** — `validate_document` (lines 207-223) raises `OperatorConfigValidationError` with `codes@paths` only, never the rejected value (RESEARCH Pitfall 10, line 299). Follow the `ValidationIssue(path=..., code=..., message=...)` shape (lines 70-77).

**Imports pattern** (lines 7-15) — no new imports needed; `OperatorConfigDocument` already imported from `.schemas`.

---

### `packages/operator-config/src/inkstatute_operator_config/__init__.py` (config, transform)

**Analog:** self — public re-exports (lines 3-43)

**Pattern** — add new symbols to the appropriate `from .<module> import (...)` block and to `__all__` (lines 23-43). If `catalog.py` is new:
```python
from .catalog import (
    BUILTIN_MODEL_CATALOG,
    BUILTIN_VENDOR_PROFILES,
    BuiltInCatalogEntry,
    VendorProfile,
)
```
Add `"BUILTIN_MODEL_CATALOG"`, `"BUILTIN_VENDOR_PROFILES"`, `"BuiltInCatalogEntry"`, `"VendorProfile"` to `__all__`. Keep alphabetical-ish ordering as in existing list.

---

### `services/admin-console-api/src/admin_console_api/probe.py` (NEW — service, request-response)

**Analog:** `packages/backends/provider_model/src/inkstatute_backends_provider_model/probe.py` (structure) + `openai_runner.py` `_sanitize_error_message` (sanitization) + RESEARCH Pattern 2 (lines 212-244)

**Imports pattern** (RESEARCH lines 218-219):
```python
from __future__ import annotations
import os
import urllib.request
import urllib.error
```
Use **stdlib only** — no `openai`/`httpx` (RESEARCH Standard Stack line 66; preserves `dependencies = []`).

**Core pattern — fail-closed probe** (RESEARCH lines 221-244):
```python
def probe_provider(provider_id, api_base_url, api_key_ref, *, env=None):
    if not api_key_ref or not api_key_ref.strip():
        return {"ok": False, "code": "missing_ref"}
    source = env if env is not None else os.environ
    key = source.get(_ref_env_name(api_key_ref), "")
    if not key:
        return {"ok": False, "code": "missing_ref"}
    try:
        req = urllib.request.Request(
            f"{api_base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.getcode()  # touch to force response; do NOT read body
        return {"ok": True, "code": "ok"}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "code": "auth_error" if exc.code in (401, 403) else "network"}
    except Exception:
        return {"ok": False, "code": "network"}
```

**Error sanitization pattern** — mirror `openai_runner._sanitize_error_message` (lines 271-284) but as a **local** helper (do NOT import `provider_model` — RESEARCH line 38, line 276):
```python
import re
_URL_RE = re.compile(r"https?://\S+")
_TOKEN_RE = re.compile(r"token=\S+")
_PATH_RE = re.compile(r"/(?:home|Users)[/\w.\-]*")
_MODEL_RE = re.compile(r"\b(?:gpt|claude|gemini)[-\w]*", re.IGNORECASE)

def _sanitize_probe_message(msg: str) -> str:
    sanitized = _URL_RE.sub("[url_redacted]", msg)
    sanitized = _TOKEN_RE.sub("token=[redacted]", sanitized)
    sanitized = _PATH_RE.sub("[redacted]", sanitized)
    sanitized = _MODEL_RE.sub("[model_redacted]", sanitized)
    return sanitized
```

**Critical invariants** (RESEARCH Pitfalls 1-4, lines 281-288):
- Never log response body, resolved key, `Authorization` header, or HTTP status code (leaks to UI)
- Never call `store.save` — non-mutating
- Return generic `{"ok": bool, "code": str}` only
- `os.environ.get` lives here (process edge), NOT in `operator-config`

**`_ref_env_name` helper** — strip `env:` prefix from `api_key_ref` to get the env var name (convention from `channels.py` REF_HELP line 29-32: `env:NAME`, bare `ENV_NAME`, or `secret://path`). For `secret://` refs, fail-closed (no resolver in this tier).

---

### `services/admin-console-api/src/admin_console_api/config_api.py` (controller, request-response)

**Analog:** self — `handle_config_get` (lines 30-54) + `handle_config_put` (lines 57-106)

**Existing `_parse_section`** (lines 109-118) — rejects paths with `/` (line 114: `if not remainder or "/" in remainder: return None`). The probe route `/config/providers/probe` contains a sub-path, so `_parse_section` will return `None` → 404. **Wire the probe BEFORE the section parser** or as a distinct route in `api.py`.

**`_config_metadata`** (lines 169-183) — add `apply_semantics = "restart_required"` for `providers` and `catalog` sections (mirror line 181-182 for `channels`):
```python
if section in ("channels", "providers", "catalog"):
    metadata["apply_semantics"] = "restart_required"
```

**`_normalize_section_body`** (lines 121-166) — `providers` branch (lines 130-147) already accepts a list; `catalog` branch falls through to the Mapping path (lines 149-166). Add catalog-specific metadata enrichment if needed (e.g. expose `BUILTIN_MODEL_CATALOG` in the GET `metadata` block so the SSR form can render vision badges without a second call).

**Error handling pattern** — `_error(code, message)` (lines 235-246) + `_safe_store_message` (lines 264-270). Reuse for probe errors. Never echo rejected secrets (RESEARCH Pitfall 10).

**Imports pattern** (lines 8-19) — add `from .probe import probe_provider` if the probe handler lives here, OR keep probe as a separate handler invoked from `api.py`.

---

### `services/admin-console-api/src/admin_console_api/api.py` (controller, request-response)

**Analog:** self — `handle_admin_get` route dispatch (lines 131-172) + `handle_admin_put` (lines 175-212)

**Existing `/config/` route branch** (lines 168-170):
```python
if route_path == "/config" or route_path.startswith("/config/"):
    store = config_store if config_store is not None else OperatorConfigStore()
    return handle_config_get(route_path, store, feature_flags)
```

**Add probe route** — insert a specific match for `/config/providers/probe` BEFORE the generic `/config/` branch (because `_parse_section` rejects sub-paths — RESEARCH Pitfall 3, line 285):
```python
if route_path == "/config/providers/probe":
    store = config_store if config_store is not None else OperatorConfigStore()
    return handle_config_probe(route_path, body, store, feature_flags, env=env)
```

The probe is a **POST** (non-mutating). Either route it through `handle_admin_put` (which already auth-gates `/config/*`) or add a dedicated `handle_admin_post` path. RESEARCH recommends a distinct path so `_parse_section` does not treat it as a section PUT (line 285). Reuse `_authenticate_admin` (lines 51-128) for the same flag → auth → RBAC → tenant pipeline — the probe must NOT bypass `operator_config_enabled` (RESEARCH Pitfall 9, line 297).

**Imports pattern** (lines 27-30) — add `from .probe import handle_config_probe` (or `probe_provider`).

---

### `services/admin-console-api/src/admin_console_api/routes.py` (config, transform)

**Analog:** self — `ROUTE_PREFIXES` (lines 11-18)

**Existing tuple** (lines 11-18):
```python
ROUTE_PREFIXES: tuple[str, ...] = (
    "/sessions",
    "/tasks",
    "/feedback",
    "/health",
    "/gates",
    "/config",
)
```

The probe route `/config/providers/probe` is under the `/config` prefix, which is already listed. **No change needed** unless the RBAC scan requires an explicit `/config/providers/probe` entry — verify against `scripts/scan_rbac_annotations.py`. The `/config` prefix already covers it (RESEARCH line 275: Phase 74 RBAC matrix denies LAWYER/VIEWER on `/config`).

---

### `services/admin-web-ui/src/admin_web_ui/providers.py` (NEW — component, request-response)

**Analog:** `services/admin-web-ui/src/admin_web_ui/channels.py` (exact match — Phase 75 SSR form module)

**Imports pattern** (copy from `channels.py` lines 7-16):
```python
from __future__ import annotations
import html
from typing import Any, Mapping
from urllib.parse import parse_qs
from rbac import Identity
from .boundary import AdminUiBoundary
from .dashboard import _page_template
```

**UI-SPEC copy constants** (mirror `channels.py` lines 18-47) — define `PAGE_TITLE`, `PRIMARY_CTA`, `RESTART_NOTICE`, `SUCCESS_FLASH`, `REF_HELP`, `ERROR_VALIDATION`, `ERROR_FLAG_OFF`, `ERROR_FORBIDDEN`, `ERROR_GENERIC` as module-level strings. Flash must say "Restart runtime to apply" (RESEARCH Pitfall 12, line 303).

**`_esc` helper** (copy `channels.py` lines 62-63):
```python
def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)
```

**`render_providers_page` + `render_providers_form`** (mirror `channels.py` lines 255-359) — render provider cards with:
- Built-in vendor: read-only `api_base_url` text + `<select>` of vendor IDs (RESEARCH Pitfall 8, line 295)
- Custom: editable `api_base_url` + `api_key_ref` + comma-separated `model_allowlist` (RESEARCH lines 407-429)
- `enabled` checkbox per provider (mirror `_knob_row` lines 109-129)
- Probe button per provider card (POST to `/config/providers/probe`) — re-render with ephemeral `probe_result` (RESEARCH line 254-256)
- Drop blank-`provider_id` entries on parse (RESEARCH Pitfall 11, line 301)

**`parse_providers_form`** (mirror `channels.py` lines 385-420 + RESEARCH lines 407-429):
```python
def parse_providers_form(form) -> list[dict]:
    # Collect providers[N].* fields, drop entries with blank provider_id.
    parsed = parse_qs(form, keep_blank_values=True) if isinstance(form, (str, bytes)) else form
    indices = sorted({_index_from_key(k) for k in parsed if k.startswith("providers[")})
    providers = []
    for i in indices:
        pid = _form_get(parsed, f"providers[{i}].provider_id")
        if not pid:
            continue
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

**`_form_get` / `_form_checkbox` helpers** (copy `channels.py` lines 362-382). Add `_split_csv` helper for comma-separated allowlist. Add `_index_from_key` helper to extract `N` from `providers[N].field`.

**`render` alias** (mirror `channels.py` line 424): `render = render_providers_page`.

**`__all__`** (mirror `channels.py` lines 426-439).

---

### `services/admin-web-ui/src/admin_web_ui/catalog.py` (NEW — component, request-response)

**Analog:** `services/admin-web-ui/src/admin_web_ui/channels.py` (exact match)

**Imports pattern** — same as `providers.py` above (copy `channels.py` lines 7-16). Additionally import `BUILTIN_MODEL_CATALOG` from `inkstatute_operator_config` to render the radio list with vision badges (RESEARCH line 31, line 177).

**`render_catalog_page` + `render_catalog_form`** — render a radio list of `BUILTIN_MODEL_CATALOG` entries, each with:
- `provider_id` + `model_id` radio value
- `supports_vision` badge (RESEARCH line 31)
- `description` text
- Currently selected entry checked (from `CatalogSelectionDoc` stored `provider_id` + `model_id`)

**`parse_catalog_form`** (mirror `channels.py` `parse_channels_form` lines 385-420) — returns `{"provider_id": ..., "model_id": ...}` (object body for PUT `/config/catalog`, per `config_api._normalize_section_body` Mapping path lines 149-166).

**UI-SPEC copy constants + `_esc` + `_form_get`** — duplicate from `channels.py` (acceptable for MVP — RESEARCH Pattern 3 line 249 says Phase 78 may extract shared helpers).

**`render` alias + `__all__`** — mirror `channels.py` lines 424-439.

---

### `services/admin-web-ui/src/admin_web_ui/server.py` (controller, request-response)

**Analog:** self — `_SECTION_MAP` (lines 52-60) + `_handle_channels` (lines 278-427)

**`_SECTION_MAP` extension** (lines 52-60) — add provider + catalog routes:
```python
_SECTION_MAP = {
    "/": "index",
    "/sessions": "sessions",
    "/tasks": "tasks",
    "/feedback": "feedback",
    "/health": "health",
    "/gates": "gates",
    "/config/channels": "channels",
    "/config/providers": "providers",
    "/config/catalog": "catalog",
}
```

**POST dispatch extension** (lines 177-183) — currently only `_CHANNELS_PATH` allows POST. Add `/config/providers` + `/config/catalog` + `/config/providers/probe`:
```python
_CONFIG_POST_PATHS = {_CHANNELS_PATH, "/config/providers", "/config/catalog", "/config/providers/probe"}
if http_method == "POST" and route_path not in _CONFIG_POST_PATHS:
    ...  # 405
```

**`_handle_channels` pattern to clone** (lines 278-427) — create `_handle_providers` and `_handle_catalog` following the same flow:
1. Generate CSRF token (`secrets.token_urlsafe(16)`, line 297)
2. POST: check `_providers_post_body_usable` (mirror `_channels_post_body_usable` lines 65-79 — reject empty POST to avoid wiping stored providers, RESEARCH Pitfall 11)
3. `parse_providers_form` → merge metadata from current GET (mirror `_merge_channel_metadata_from_current` lines 82-100, RESEARCH Pattern 4 lines 262-265)
4. `client.proxy_put` → `handle_admin_put` `/config/providers`
5. On success: re-render with `SUCCESS_FLASH`; on error: map `code` → error message (lines 370-379)
6. GET: `client.proxy` → `render_providers_page`

**Probe action** — POST `/config/providers/probe` calls `handle_admin_put` (or a new probe handler) with the provider's `provider_id`; re-render the providers page with ephemeral `probe_result` (RESEARCH line 254). The probe result is **never** persisted and **never** logged with body/secret (RESEARCH Pitfall 2).

**Imports pattern** (lines 34-43) — add:
```python
from .providers import (
    parse_providers_form,
    render_providers_page,
    SUCCESS_FLASH as PROVIDERS_SUCCESS_FLASH,
    # ...
)
from .catalog import (
    parse_catalog_form,
    render_catalog_page,
    # ...
)
```

**`_guard_path`** (lines 114-120) — already maps `/config/*` to `/config` RBAC prefix (line 118). No change needed; providers/catalog/probe inherit the same RBAC guard.

**`MAX_CHANNELS_POST_BYTES`** (line 50) — rename to a generic `MAX_CONFIG_POST_BYTES` or add `MAX_PROVIDERS_POST_BYTES` (providers form with allowlist may be slightly larger; 64 KiB is still plenty).

---

### `services/admin-web-ui/src/admin_web_ui/dashboard.py` (component, transform)

**Analog:** self — `_page_template` `nav_items` (lines 71-79)

**Existing nav_items** (lines 71-79):
```python
nav_items = [
    ("/", "Dashboard"),
    ("/sessions", "Sessions"),
    ("/tasks", "Tasks"),
    ("/feedback", "Feedback Review"),
    ("/health", "Health"),
    ("/gates", "Gates"),
    ("/config/channels", "Channel Config"),
]
```

**Add two nav links** (RESEARCH line 172):
```python
    ("/config/providers", "Provider Config"),
    ("/config/catalog", "Model Catalog"),
```

**Index cards** — if `_render_index` (referenced line 195) renders dashboard cards, add provider/catalog status cards. Read the rest of `_render_index` to match the card pattern (uses `_render_kv_table` lines 47-54 and `_render_items` lines 57-65).

---

### `packages/operator-config/tests/test_catalog.py` (NEW — test, transform)

**Analog:** `packages/operator-config/tests/test_schemas.py`

**Imports pattern** (copy `test_schemas.py` lines 1-16):
```python
from __future__ import annotations
import unittest
from dataclasses import fields, is_dataclass
from inkstatute_operator_config.catalog import (
    BUILTIN_MODEL_CATALOG,
    BUILTIN_VENDOR_PROFILES,
    BuiltInCatalogEntry,
    VendorProfile,
)
```

**Core test pattern** (mirror `test_schemas.py` lines 49-57):
```python
class TestBuiltInCatalog(unittest.TestCase):
    def test_catalog_entries_frozen_dataclass(self):
        self.assertTrue(is_dataclass(BuiltInCatalogEntry))
    def test_every_entry_has_supports_vision_bool(self):
        for entry in BUILTIN_MODEL_CATALOG:
            self.assertIsInstance(entry.supports_vision, bool)  # RESEARCH Pitfall 5
    def test_vendor_profiles_have_base_url_and_key_env(self):
        for profile in BUILTIN_VENDOR_PROFILES:
            self.assertTrue(profile.api_base_url)
            self.assertTrue(profile.default_key_ref_env)
```

---

### `services/admin-console-api/tests/test_config_providers.py` (NEW — test, request-response)

**Analog:** `services/admin-console-api/tests/test_config_api.py` (exact match)

**Imports pattern** (copy `test_config_api.py` lines 1-14):
```python
from __future__ import annotations
import json, tempfile, unittest
from pathlib import Path
from typing import Any
from admin_console_api.api import handle_admin_get, handle_admin_put
from inkstatute_operator_config.store import OperatorConfigStore
from platform_runtime.feature_flags import RuntimeFeatureFlags
from rbac import Role, issue_token
```

**Fixture pattern** (copy `test_config_api.py` lines 27-59) — `SK_PLANTED`, `_VALID_PROVIDERS` (already defined lines 50-59 — extend with `model_allowlist`), `FakeReadModel` (lines 17-25), `ConfigApiStaticTokenTests.setUp` (lines 69-81).

**Planted-secret negative test** (mirror `test_config_api.py` lines 155-172 — `test_flag_off_put_refuses_without_file_side_effects`):
```python
def test_planted_sk_in_provider_body_rejected(self):
    providers = [{"provider_id": "x", "kind": "custom", "api_key_ref": SK_PLANTED, "model_allowlist": ["m"]}]
    status, body = handle_admin_put("/config/providers", providers, self.headers, self.flags, self.env, config_store=self.store)
    self.assertEqual(status, 400)
    self.assertNotIn(SK_PLANTED, json.dumps(body))
```

**RBAC test** (mirror `test_config_api.py` lines 117-153 — `test_operator_rbac_get_put_providers` already exists; add LAWYER/VIEWER denial).

**Duplicate provider_id test** — PUT two providers with same `provider_id` → assert 400 + `invalid_config` (RESEARCH line 319).

---

### `services/admin-console-api/tests/test_config_catalog.py` (NEW — test, request-response)

**Analog:** `services/admin-console-api/tests/test_config_api.py`

Same imports/fixture pattern as `test_config_providers.py` above. Test catalog PUT (object body) + GET roundtrip; assert `provider_id` + `model_id` persist. Test catalog selection referencing a provider not in registry → 400 (RESEARCH Open Question 4, line 447).

---

### `services/admin-console-api/tests/test_config_probe.py` (NEW — test, request-response)

**Analog:** `services/admin-console-api/tests/test_config_api.py` + `services/admin-web-ui/tests/test_channels_form.py` (fake-get pattern)

**Imports pattern**:
```python
from __future__ import annotations
import unittest
from admin_console_api.probe import probe_provider
```

**Core test pattern** — unit-test `probe_provider` directly with injectable `env`:
```python
class TestProbeProvider(unittest.TestCase):
    def test_fail_closed_on_blank_ref(self):
        result = probe_provider("openai", "https://api.openai.com/v1", "", env={})
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "missing_ref")
    def test_fail_closed_on_unresolved_ref(self):
        result = probe_provider("openai", "https://api.openai.com/v1", "env:MISSING", env={})
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "missing_ref")
```

**No-body-logging assertion** — mock `urllib.request.urlopen` and assert the response body is never read/logged (RESEARCH Pitfall 2). Use `unittest.mock.patch`.

**Non-mutating assertion** — assert `store.save` is never called (inject a fake store and assert zero calls).

**Integration test** — wire through `handle_admin_put`/`handle_admin_get` with RBAC OPERATOR token (mirror `test_config_api.py` lines 117-153) to prove the probe route is flag-gated and RBAC-denied for LAWYER/VIEWER.

---

### `services/admin-web-ui/tests/test_providers_form.py` (NEW — test, request-response)

**Analog:** `services/admin-web-ui/tests/test_channels_form.py` (exact match)

**Imports pattern** (copy `test_channels_form.py` lines 10-31):
```python
from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode
from admin_console_api.api import handle_admin_get as real_handle_admin_get
from admin_console_api.api import handle_admin_put as real_handle_admin_put
from admin_web_ui.api_client import AdminApiClient
from admin_web_ui.providers import (parse_providers_form, render_providers_page, PRIMARY_CTA, SUCCESS_FLASH)
from admin_web_ui.server import handle_admin_web_ui_request
from inkstatute_operator_config.store import OperatorConfigStore
from platform_runtime.feature_flags import RuntimeFeatureFlags
from rbac import Identity, Role, issue_token
```

**Scaffold test pattern** (mirror `test_channels_form.py` lines 120-191 — `ChannelsFormScaffoldTests`):
```python
class ProvidersFormScaffoldTests(unittest.TestCase):
    def test_providers_module_exists_with_render_helpers(self):
        # assert providers.py exists + render_providers_page importable
    def test_server_routes_config_providers_get_and_post(self):
        # assert /config/providers in server.py + "Save" CTA present
    def test_providers_form_does_not_claim_live_human_gate_closure(self):
        # assert no "lawyer trial acceptance complete" etc.
```

**Behavior test pattern** (mirror `test_channels_form.py` lines 194+ — `ChannelsFormBehaviorTests`): fake GET returns provider list; POST `urlencode`d form body → assert `proxy_put` called with parsed providers list; assert blank-`provider_id` entries dropped; assert metadata merged from current GET.

---

### `services/admin-web-ui/tests/test_catalog_form.py` (NEW — test, request-response)

**Analog:** `services/admin-web-ui/tests/test_channels_form.py` (exact match)

Same scaffold + behavior pattern as `test_providers_form.py`. Test catalog radio list renders `BUILTIN_MODEL_CATALOG` entries with vision badges; POST persists `provider_id` + `model_id`; catalog save rejected when no providers configured (UI-SPEC).

---

### `packages/operator-config/tests/test_validate_document.py` (MODIFY — test, CRUD)

**Analog:** self — existing planted-secret tests (lines 77-128)

**Add duplicate provider_id test** (RESEARCH line 319):
```python
def test_rejects_duplicate_provider_id(self):
    doc = OperatorConfigDocument(providers=(
        ProviderDoc(provider_id="openai", kind="openai", api_key_ref="env:OPENAI_API_KEY"),
        ProviderDoc(provider_id="openai", kind="openai", api_key_ref="env:OPENAI_API_KEY2"),
    ))
    with self.assertRaises(OperatorConfigValidationError) as ctx:
        validate_document(doc)
    self.assertIn("duplicate_provider_id", str(ctx.exception))
```

**Add custom-allowlist-empty test**:
```python
def test_rejects_custom_provider_without_allowlist(self):
    doc = OperatorConfigDocument(providers=(
        ProviderDoc(provider_id="custom1", kind="custom", api_key_ref="env:CUSTOM_KEY", model_allowlist=()),
    ))
    with self.assertRaises(OperatorConfigValidationError):
        validate_document(doc)
```

**Error message no-echo invariant** (mirror lines 87-88, 104-105, 127-128) — assert rejected value not in `str(ctx.exception)`.

---

### `packages/operator-config/tests/test_schemas.py` (MODIFY — test, transform)

**Analog:** self — `TestOperatorConfigDocumentDefaults` (lines 49-57)

**Add `model_allowlist` default test**:
```python
def test_provider_doc_defaults_model_allowlist_empty_tuple(self):
    p = ProviderDoc()
    self.assertEqual(p.model_allowlist, ())
def test_provider_doc_model_allowlist_accepts_tuple(self):
    p = ProviderDoc(provider_id="c", kind="custom", model_allowlist=("m1", "m2"))
    self.assertEqual(p.model_allowlist, ("m1", "m2"))
```

**Update `_credential_field_names` exclusion set** (lines 25-43) — add `"model_allowlist"` to the non-credential structural field skip-list so it is not flagged as a credential carrier.

---

## Shared Patterns

### Frozen Dataclass Schemas
**Source:** `packages/operator-config/src/inkstatute_operator_config/schemas.py` lines 24, 41, 57, 65, 77, 85, 94
**Apply to:** `catalog.py` (`BuiltInCatalogEntry`, `VendorProfile`), `schemas.py` (`ProviderDoc` extension)
```python
@dataclass(frozen=True, slots=True)
class ProviderDoc:
    ...
```
Always `frozen=True, slots=True`. Credential fields are `*_ref` only. Defaults use `field(default_factory=...)` for mutable defaults.

### Refs-Only Secret Validation
**Source:** `packages/operator-config/src/inkstatute_operator_config/validate.py` lines 89-121 + `secrets.normalize_config_secret_ref`
**Apply to:** `validate.py` new `_check_provider_uniqueness` + `_check_custom_allowlist`; any new `*_ref` field
```python
for path, value in pairs:
    try:
        normalize_config_secret_ref(value, field=path)
    except InvalidSecretRefError:
        issues.append(ValidationIssue(path=path, code="invalid_secret_ref", message=...))
```
Error messages never echo the rejected value (RESEARCH Pitfall 10). Reuse `normalize_config_secret_ref` from `secrets.py` for `api_key_ref` shape validation.

### SSR Form Module Structure
**Source:** `services/admin-web-ui/src/admin_web_ui/channels.py` (full file, 439 lines)
**Apply to:** `providers.py`, `catalog.py`
- Module-level UI-SPEC copy constants (lines 18-47)
- `_esc` helper using `html.escape(str(value), quote=True)` (lines 62-63)
- `render_*_page` (full HTML via `_page_template`) + `render_*_form` (form body) (lines 255-359)
- `parse_*_form` returning PUT body shape (lines 385-420)
- `_form_get` / `_form_checkbox` helpers (lines 362-382)
- `render` alias + `__all__` (lines 424-439)
- Never `innerHTML`; never resolve secrets; CSP header set by server

### SSR POST → PUT Proxy Flow
**Source:** `services/admin-web-ui/src/admin_web_ui/server.py` `_handle_channels` lines 278-427
**Apply to:** `_handle_providers`, `_handle_catalog`, probe action in `server.py`
```python
# 1. CSRF token
csrf_token = secrets.token_urlsafe(16)
# 2. Reject empty POST body (avoid wiping stored config)
if not _channels_post_body_usable(form_body): return 400, ...
# 3. Parse form
section_payload = parse_channels_form(form_body)
# 4. Merge metadata from current GET (WR-01)
get_status, get_data = client.proxy(handle_admin_get, _CHANNELS_PATH, ...)
section_payload = _merge_channel_metadata_from_current(section_payload, current)
# 5. PUT via proxy
put_status, put_data = client.proxy_put(handle_admin_put, _CHANNELS_PATH, section_payload, ...)
# 6. Render success or error
```

### Config API Handler (status, body) Adapter
**Source:** `services/admin-console-api/src/admin_console_api/config_api.py` lines 30-106
**Apply to:** probe handler in `config_api.py` or `probe.py`
```python
def handle_config_get(path, store, feature_flags) -> tuple[int, dict[str, Any]]:
    section = _parse_section(path)
    if section is None: return 404, _not_found("route", path)
    try:
        document = store.load()
    except OperatorConfigValidationError as exc:
        return 400, _error("invalid_config", str(exc))
    ...
```
Pure `(status, body)` adapters — auth/RBAC live in `api.handle_admin_*`. Error envelope: `_error(code, message)` (lines 235-246). Never echo store filesystem paths (`_safe_store_message` lines 264-270).

### Auth + RBAC + Flag Pipeline
**Source:** `services/admin-console-api/src/admin_console_api/api.py` `_authenticate_admin` lines 51-128
**Apply to:** probe route in `api.py`
```python
auth = _authenticate_admin(path, None, headers, feature_flags, env, rbac_secret)
if auth[0] is not None: return auth
route_path, _query, identity, tenant_filter = auth[1]
```
Flag gate → auth → RBAC → tenant. Probe must NOT bypass `operator_config_enabled` (RESEARCH Pitfall 9). `/config` prefix already in RBAC matrix (denies LAWYER/VIEWER).

### Error Sanitization (Probe)
**Source:** `packages/backends/provider_model/src/inkstatute_backends_provider_model/openai_runner.py` lines 271-284
**Apply to:** `probe.py` local `_sanitize_probe_message` helper (do NOT import provider_model)
```python
_URL_RE = re.compile(r"https?://\S+")
_TOKEN_RE = re.compile(r"token=\S+")
_PATH_RE = re.compile(r"/(?:home|Users)[/\w.\-]*")
_MODEL_RE = re.compile(r"\b(?:gpt|claude|gemini)[-\w]*", re.IGNORECASE)
def _sanitize_error_message(msg: str) -> str:
    sanitized = _URL_RE.sub("[url_redacted]", msg)
    ...
```
Strip URLs, tokens, file paths, model names. Probe returns generic `ok`/`fail` + code only — never body, status code, or key (RESEARCH Pitfall 2).

### Test Fixture Pattern (Config API)
**Source:** `services/admin-console-api/tests/test_config_api.py` lines 17-81
**Apply to:** `test_config_providers.py`, `test_config_catalog.py`, `test_config_probe.py`
```python
class FakeReadModel:
    def list_conversations(self, **kwargs): return []
    def list_tasks(self, **kwargs): return []
# setUp: tempfile.TemporaryDirectory → OperatorConfigStore → RuntimeFeatureFlags → env → headers
SK_PLANTED = "sk-" + "1234567890abcdefghijklmnop"
```
Planted-secret negative tests assert 400 + secret absent from JSON body (RESEARCH line 277, line 318).

### Test Scaffold + Behavior Pattern (SSR Form)
**Source:** `services/admin-web-ui/tests/test_channels_form.py` lines 33-209
**Apply to:** `test_providers_form.py`, `test_catalog_form.py`
- `_SERVER_SRC` / `_CHANNELS_SRC` path constants for source-text assertions (lines 33-41)
- `_FAKE_CHANNELS_GET` fixture dict (lines 43-93)
- `_make_fake_get` factory (lines 96-117)
- `ChannelsFormScaffoldTests` — source-text existence checks (lines 120-191)
- `ChannelsFormBehaviorTests` — full GET/POST roundtrip with real `handle_admin_put` (lines 194+)
- Assert no live-gate closure claims (lines 184-191)

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | — | — | All files have a close analog (self-evolve or `channels.py` mirror) |

## Metadata

**Analog search scope:**
- `packages/operator-config/src/inkstatute_operator_config/` (schemas, store, validate, __init__, secrets)
- `services/admin-console-api/src/admin_console_api/` (api, config_api, routes, auth, gates, health, views)
- `services/admin-web-ui/src/admin_web_ui/` (channels, server, dashboard, api_client, boundary)
- `packages/backends/provider_model/src/inkstatute_backends_provider_model/` (probe, openai_runner)
- `packages/operator-config/tests/` (test_schemas, test_validate_document)
- `services/admin-console-api/tests/` (test_config_api)
- `services/admin-web-ui/tests/` (test_channels_form)

**Files scanned:** 18 source + 4 test = 22
**Pattern extraction date:** 2026-07-10
