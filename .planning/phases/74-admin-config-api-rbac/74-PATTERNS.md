# Phase 74: Admin Config API + RBAC - Pattern Map

**Mapped:** 2026-07-10
**Files analyzed:** 12
**Analogs found:** 12 / 12

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `services/admin-console-api/src/admin_console_api/config_api.py` | controller | request-response | `packages/skill-registry/.../write_api.py` | exact |
| `services/admin-console-api/src/admin_console_api/api.py` | controller | request-response | (self — extend `handle_admin_get` + add `handle_admin_put`) | exact |
| `services/admin-console-api/src/admin_console_api/routes.py` | config | n/a | (self — extend `ROUTE_PREFIXES`) | exact |
| `services/admin-console-api/src/admin_console_api/__init__.py` | utility | n/a | (self — export new handler carefully) | exact |
| `packages/rbac/src/rbac/matrix.py` | config | request-response | (self — add `/config` like `/feedback`) | exact |
| `scripts/run_v2_gates.py` | config | n/a | (self — Phase 73 already added `operator_config_src`) | exact |
| `services/admin-console-api/tests/test_config_api.py` | test | request-response | `packages/skill-registry/tests/test_write_api.py` | exact |
| `services/admin-console-api/tests/test_read_only.py` | test | request-response | (self — **evolve**, do not delete) | exact |
| `services/admin-console-api/tests/test_rbac_integration.py` | test | request-response | (self — extend role denial cases) | exact |
| `services/admin-console-api/tests/test_routes.py` | test | n/a | (self — expect `/config` in tuple) | exact |
| `packages/rbac/tests/test_matrix.py` | test | n/a | (self — annotate `/config` ADMIN+OPERATOR) | exact |
| `packages/rbac/tests/test_scan_rbac.py` | test | n/a | (self — ROUTE↔matrix parity still holds) | exact |

**Package wiring rule:** Keep `services/admin-console-api/pyproject.toml` `dependencies = []`. Import `inkstatute_operator_config` the same way the service already imports `rbac`, `platform_runtime`, and `conversation_read_view` — via V2 gate `PYTHONPATH`, not declared package deps.

**Out of Phase 74:** channel apply (75), provider catalog (76), vision runtime (77), SSR forms (78).

---

## Pattern Assignments

### `services/admin-console-api/src/admin_console_api/config_api.py` (controller, request-response)

**Analog:** `packages/skill-registry/src/inkstatute_skill_registry/write_api.py`

**New module role:** Pure `(status, body)` handlers for `/config/*` only. Do **not** put mutate logic into `views.py` (that module stays read-only operational views).

**Imports + dual-gate pattern** (write_api lines 22–40, 128–154):
```python
from platform_runtime.feature_flags import (
    RuntimeFeatureDisabledError,
    RuntimeFeatureFlags,
)
from rbac import RbacGuard
from rbac.identity import Identity

from inkstatute_operator_config import (
    OperatorConfigDisabledError,
    OperatorConfigDocument,
    OperatorConfigStore,
    OperatorConfigStoreError,
    OperatorConfigValidationError,
    document_from_payload,
    document_to_payload,
)
```

**Flag + RBAC `_gate` for PUT** (copy write_api `_gate`, swap flag/error code):
```python
def _mutate_gate(
    flags: RuntimeFeatureFlags,
    identity: Identity,
    route_path: str,
) -> tuple[int | None, dict]:
    try:
        flags.require_enabled("operator_config_enabled")
    except RuntimeFeatureDisabledError:
        return 403, {
            "error": {
                "code": "operator_config_disabled",
                "message": "operator_config_enabled flag is False",
            },
        }
    # Prefer catching OperatorConfigDisabledError if calling store.save directly —
    # store already wraps require_operator_config_writable. HTTP layer should still
    # map OperatorConfigDisabledError → same 403 code for consistency.

    guard = RbacGuard()
    if not guard.check(identity.role, route_path):
        return 403, {
            "error": {
                "code": "forbidden",
                "message": "role not permitted for this endpoint",
                "role": identity.role.value,
            },
        }
    return None, {}
```

**Core PUT handler shape** (write_api `handle_put` lines 70–97 + store.save):
```python
def handle_config_put(
    path: str,
    body: Mapping[str, Any],
    store: OperatorConfigStore,
    identity: Identity,
    feature_flags: RuntimeFeatureFlags,
) -> tuple[int, dict[str, Any]]:
    gate_status, gate_body = _mutate_gate(feature_flags, identity, path)
    if gate_status is not None:
        return gate_status, gate_body
    try:
        document = document_from_payload(body)  # or nested resource merge
        store.save(document, feature_flags=feature_flags)
    except OperatorConfigDisabledError:
        return 403, {"error": {"code": "operator_config_disabled", "message": "..."}}
    except OperatorConfigValidationError as exc:
        return 400, {"error": {"code": "validation_error", "message": str(exc)}}
    except OperatorConfigStoreError as exc:
        return 400, {"error": {"code": "store_error", "message": str(exc)}}
    return 200, {"config": document_to_payload(document), "metadata": {"admin_api": True, "mutable": True}}
```

**GET handler:** load via `store.load()` → `document_to_payload`; never call secret resolve. Response may include `*_ref` strings (refs-only SoT) but must never include resolved secret values. Mirror health exclusion spirit from `health.py` lines 35–45 for fields like `config_path` / raw secret maps — do not echo store filesystem path in the API body.

**Secondary analog (simple handler return):** `services/admin-console-api/src/admin_console_api/gates.py` `handle_gates` (lines 63–86) — `(status, dict)` with `metadata` bag.

---

### `services/admin-console-api/src/admin_console_api/api.py` (controller, modify)

**Analog:** same file — `handle_admin_get` (lines 52–156) for auth/RBAC/tenant pipeline; skill-registry `handle_put` for the new mutate entry point.

**Current contract to preserve for operational views** (module docstring lines 1–8):
- Sessions/tasks/feedback/health/gates stay GET-only through `handle_admin_get`.
- Add a **separate** public entry: `handle_admin_put` that only dispatches `/config` (and `/config/...`).

**Auth/RBAC reuse from `handle_admin_get`** (lines 72–132) — extract shared helper or duplicate the same sequence in `handle_admin_put`:
1. `feature_flags.require_enabled("admin_api_enabled")` → 403 `admin_api_disabled`
2. If `rbac_enabled`: `resolve_identity` → 401; `RbacGuard().check(role, route_path)` → 403 `forbidden`
3. Else: static `ADMIN_API_TOKEN` path → synthetic `Identity(role=Role.ADMIN, tenant_id="default")`
4. Tenant scope resolve/enforce (same as GET) if config is tenant-scoped later; for MVP global store, still run the same pipeline for consistency

**Route dispatch addition inside GET** (after gates block, before 404):
```python
if route_path == "/config" or route_path.startswith("/config/"):
    return handle_config_get(route_path, route_query, config_store, feature_flags)
```

**New PUT entry** (skill-registry style):
```python
def handle_admin_put(
    path: str,
    body: Mapping[str, Any],
    headers: Mapping[str, str] | None,
    feature_flags: RuntimeFeatureFlags,
    config_store: OperatorConfigStore,
    env: Mapping[str, str] | None = None,
    rbac_secret: str | None = None,
) -> tuple[int, dict[str, Any]]:
    # same admin_api_enabled + auth/RBAC as GET
    # then ONLY:
    if route_path == "/config" or route_path.startswith("/config/"):
        return handle_config_put(...)
    return 404, not_found_response("route", route_path)
```

**Do not** add `handle_admin_post` / `handle_admin_delete` in this phase unless a resource design requires them — success criteria are GET + PUT.

**Update `__all__`** to export `handle_admin_put` (and keep `handle_admin_get`).

---

### `services/admin-console-api/src/admin_console_api/routes.py` (config, modify)

**Analog:** same file (lines 11–17)

```python
ROUTE_PREFIXES: tuple[str, ...] = (
    "/sessions",
    "/tasks",
    "/feedback",
    "/health",
    "/gates",
    "/config",  # Phase 74 — must appear in PERMISSIONS_MATRIX
)
```

CI scan (`scripts/scan_rbac_annotations.py`) introspects this tuple and fails if `/config` lacks a matrix entry. Update scan docstring if it still says “dispatched by handle_admin_get” only — PUT also uses the same prefix table.

---

### `packages/rbac/src/rbac/matrix.py` (config, modify)

**Analog:** same file — `/feedback` / `/health` role set (lines 13–20)

```python
PERMISSIONS_MATRIX: dict[str, frozenset[Role]] = {
    ...
    "/config": frozenset({Role.ADMIN, Role.OPERATOR}),  # ADM-01/03 — not lawyer/viewer
}
```

**Not** `/skills-write` (ADMIN-only). Success criteria require **operator** mutate access.

`RbacGuard` longest-prefix match (`guard.py` lines 32–49) covers `/config` and `/config/...` automatically once the prefix is registered.

---

### `scripts/run_v2_gates.py` (config, modify) — empty-deps wiring

**Analog:** same file — how admin already consumes empty-deps packages (lines 67–79, 142–146)

Phase 73 already defines `operator_config_src`. Phase 74 must **add it to the admin-console-api gate PYTHONPATH** (and likely `admin-web-ui`, `rbac`, `rbac-annotation-scan` if those import admin modules that now import operator-config):

```python
Gate(
    "admin-console-api",
    (py, "-m", "unittest", "discover", "-s", "services/admin-console-api/tests"),
    (
        admin_api_src,
        rbac_src,
        operator_config_src,  # ← add
        read_view_src,
        feedback_src,
        contract_src,
        platform_src,
        platform_runtime_src,
    ),
),
```

**Do not** add `inkstatute-operator-config` to `services/admin-console-api/pyproject.toml` dependencies — that would break the empty-deps convention used by skill-registry, rbac, and admin-console-api (`dependencies = []`). Runtime/tests resolve imports exclusively via PYTHONPATH composition in gates (and local developer env).

**Secondary analog:** skill-registry gate already composes `(skill_registry_src, platform_src, platform_runtime_src, rbac_src)` while skill-registry `pyproject.toml` still has `dependencies = []`.

---

### `services/admin-console-api/tests/test_config_api.py` (test, new)

**Analog:** `packages/skill-registry/tests/test_write_api.py` (lines 61–119)

**Flag-off refuse (SC#4):**
```python
class ConfigApiFeatureFlagTests(unittest.TestCase):
    def test_put_flag_disabled_returns_403(self) -> None:
        flags = RuntimeFeatureFlags(admin_api_enabled=True)  # operator_config_enabled default False
        status, body = handle_admin_put("/config", {...}, headers, flags, store, env=...)
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "operator_config_disabled")
```

**RBAC denial (SC#2):**
```python
class ConfigApiRbacTests(unittest.TestCase):
    def test_lawyer_put_returns_403(self) -> None: ...
    def test_viewer_put_returns_403(self) -> None: ...
    def test_admin_put_with_flag_on_returns_200(self) -> None: ...
    def test_operator_put_with_flag_on_returns_200(self) -> None: ...
```

Use `issue_token` + `RuntimeFeatureFlags(admin_api_enabled=True, rbac_enabled=True, operator_config_enabled=True)` like `test_rbac_integration.py` lines 94–105.

**Store isolation:** pass a temp-path `OperatorConfigStore` (Phase 73 `test_store.py` / `test_flag_gate.py` pattern) — never write to the default `.inkstatute/operator-config.json` in CI.

**Secrets:** assert GET/PUT responses never contain planted raw secrets; error messages never echo them (Phase 73 `test_secret_refs.py` spirit).

---

### `services/admin-console-api/tests/test_read_only.py` (test, modify — critical)

**Analog:** same file (lines 37–90) — **must evolve**, not stay as “no PUT exists forever.”

Phase 73 verification still asserts no `handle_admin_put`. Phase 74 success criteria change the contract to:

1. Operational views (`/sessions`, `/tasks`, `/feedback`, `/health`, `/gates`) remain read-only.
2. Config writes succeed **only** on explicit `/config/*` via `handle_admin_put`.
3. `views.py` still exposes no `create_`/`update_`/`delete_`/`write_`/`post_`/`put_` methods.

**Rewrite assertions roughly as:**
```python
def test_handle_admin_put_exists_for_config_only(self) -> None:
    self.assertTrue(hasattr(api_module, "handle_admin_put"))
    # PUT to /sessions returns 404 (not a mutate surface)
    status, body = handle_admin_put("/sessions", {}, self.headers, self.flags, store, self.env)
    self.assertEqual(status, 404)

def test_operational_get_responses_still_read_only(self) -> None:
    # keep existing metadata["read_only"] is True checks for sessions/tasks/feedback

def test_no_write_methods_on_views_module(self) -> None:
    # keep existing views_module scan — config mutate lives in config_api.py
```

Remove or replace `test_no_put_handler_exists` / `test_handle_admin_get_is_only_entry_point` so they no longer forbid `handle_admin_put` entirely.

---

### `services/admin-console-api/tests/test_rbac_integration.py` (test, modify)

**Analog:** same file — `test_viewer_gates_returns_403` / `test_lawyer_health_returns_403` (lines 115–210)

Add parallel cases for `/config`:
- ADMIN GET/PUT → 200 (with flags on)
- OPERATOR GET/PUT → 200
- LAWYER GET and PUT → 403 `forbidden`
- VIEWER GET and PUT → 403 `forbidden`

Reuse `_rbac_headers(Role.*)` helper already in the file.

---

### `services/admin-console-api/tests/test_routes.py` + `packages/rbac/tests/test_matrix.py` (test, modify)

**Analogs:** self

- `test_routes.py`: expect 6 prefixes including `/config` (update `test_route_prefixes_contains_five` → six / rename).
- `test_matrix.py`: extend `ADMIN_API_ROUTE_PREFIXES` with `/config`; add `test_config_admin_operator` asserting `frozenset({Role.ADMIN, Role.OPERATOR})`.

---

## Shared Patterns

### Empty-deps + PYTHONPATH composition (no pyproject dep violation)
**Source:** `services/admin-console-api/pyproject.toml` (`dependencies = []`) + `scripts/run_v2_gates.py` admin-console-api / skill-registry gates  
**Apply to:** importing `inkstatute_operator_config` from admin-console-api  
- Keep package metadata empty-deps.
- Add `packages/operator-config/src` to gate PYTHONPATH tuples that execute admin tests or import admin modules that transitively import operator-config.
- Local/dev: same path list as the gate.

### Dual feature-flag refuse
**Source:** `api.py` `admin_api_enabled` (lines 72–81) + skill-registry `skill_registry_write_enabled` (write_api 134–142) + operator-config `require_operator_config_writable`  
**Apply to:** PUT `/config/*`  
1. Outer: `admin_api_enabled` (whole admin API)  
2. Inner: `operator_config_enabled` (mutate only; GET may still work when OFF if product wants read of last-known/default — prefer: GET allowed when admin API on; PUT refuses when operator_config OFF)  
Error code: `operator_config_disabled` (mirror `{flag}_disabled` style).

### Auth + RbacGuard default-deny
**Source:** `api.py` lines 88–112 + `packages/rbac/src/rbac/guard.py`  
**Apply to:** both GET and PUT `/config`  
- Matrix entry required; CI scan enforces ROUTE_PREFIXES ↔ PERMISSIONS_MATRIX parity.
- Lawyer/viewer denied by matrix (not ad-hoc if-checks).

### Pure `(status, body)` handlers, no FastAPI
**Source:** `api.py`, `write_api.py`, `gates.py`  
**Apply to:** `config_api.py` + `handle_admin_put`  
- unittest-callable; inject `OperatorConfigStore` and `RuntimeFeatureFlags`.

### Store authority stays in Phase 73 package
**Source:** `packages/operator-config/.../store.py` `save`/`load`  
**Apply to:** HTTP layer only maps errors; does not reimplement validate/atomic write.  
Order already mandatory in store: flag → validate → atomic write.

### Secrets never resolved / never echoed
**Source:** `health.py` allowlist + operator-config refs-only + qqbot planted-secret tests  
**Apply to:** GET/PUT `/config` responses and error messages  
- Persist/return `*_ref` only via `document_to_payload`.
- Do not expose `config_path`, resolved env values, or planted raw secrets.

### Operational read-only contract preserved
**Source:** `test_read_only.py` + `views.py`  
**Apply to:** Phase 74 regression suite  
- Mutate surface is `/config/*` only.
- `views.py` remains write-method-free.
- Existing list/detail responses keep `metadata.read_only: True`.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| *(none)* | — | — | First admin HTTP mutate is new, but skill-registry `write_api` + existing admin GET/RBAC/route-scan stack cover every concern |

---

## Metadata

**Analog search scope:** `services/admin-console-api/`, `packages/{skill-registry,rbac,operator-config,platform-runtime}/`, `scripts/{run_v2_gates,scan_rbac_annotations}.py`, `.planning/phases/73-operator-config-foundation/{73-PATTERNS,73-03-SUMMARY}.md`, `AGENTS.md`, `74-CONTEXT.md`  
**Files scanned:** ~25 primary sources  
**Pattern extraction date:** 2026-07-10

### Key planner takeaways
1. **New module** `config_api.py` copies skill-registry `write_api` gate/handler shape; wire through new `handle_admin_put` in `api.py` — do not mutate `views.py`.
2. **RBAC:** add `/config` to `ROUTE_PREFIXES` + `PERMISSIONS_MATRIX` as ADMIN+OPERATOR; extend role-denial tests like viewer/gates.
3. **Flag:** PUT refuses with `operator_config_disabled` when OFF even for admin/operator; store already enforces the same gate.
4. **Deps:** keep admin `dependencies = []`; add `operator_config_src` to admin (and related) V2 gate PYTHONPATH lists.
5. **Evolve `test_read_only.py`:** from “no PUT exists” → “PUT exists only for `/config`; operational views stay read-only.”
