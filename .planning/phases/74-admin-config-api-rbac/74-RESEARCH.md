# Phase 74: Admin Config API + RBAC - Research

**Researched:** 2026-07-10
**Domain:** Admin Console API mutate surface + RBAC matrix extension over Phase 73 operator-config store
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
All implementation choices are at the agent's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Locked from prior phases / PROJECT.md:
- Config writes only on explicit `/config/*` (do not break admin read-only contract)
- `operator_config_enabled` default OFF; PUT refuses when OFF
- Secrets as refs only; never echo resolved secrets in GET
- Extend existing admin-console-api; no new SPA/DB/queue
- Phase 73 package `inkstatute_operator_config` is the store authority

### Claude's Discretion
All implementation choices are at the agent's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
Channel apply (75), provider catalog (76), vision runtime (77), SSR forms (78) are out of scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ADM-01 | Admin/operator roles can GET/PUT config resources; lawyer/viewer roles are denied mutate | Extend `PERMISSIONS_MATRIX` with `/config` for `ADMIN`+`OPERATOR` only; `handle_admin_put` + RBAC integration tests for lawyer/viewer 403 |
| ADM-03 | Existing read-only admin views remain read-only; config writes use explicit `/config/*` | Evolve `test_read_only.py` to prove operational routes reject writes; only `/config/*` accepts PUT; keep sessions/tasks/feedback/health/gates GET metadata `read_only: true` |
</phase_requirements>

## Summary

Phase 74 wires HTTP onto the Phase 73 `inkstatute_operator_config` authority without weakening the existing read-only operational admin surface. The in-repo pattern is already proven: pure `(status, body)` handlers in `admin-console-api`, default-deny `RbacGuard` + `PERMISSIONS_MATRIX`, CI scan of `ROUTE_PREFIXES`, and a separate write API pattern in `skill-registry.write_api` (flag gate → RBAC → mutate). [VERIFIED: codebase]

**Primary recommendation:** Add `/config` to `ROUTE_PREFIXES` and `PERMISSIONS_MATRIX` (ADMIN+OPERATOR only); implement `handle_admin_put` that accepts **only** `/config/{channels,providers,catalog,vision}`; extend `handle_admin_get` for the same paths; persist via `OperatorConfigStore` with section merge + `validate_document`; map `OperatorConfigDisabledError` → 403. Evolve (do not delete) `test_read_only.py` so operational views stay write-proof while `/config/*` is the sole mutate surface.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Config GET/PUT HTTP | API / Backend (`admin-console-api`) | — | Existing admin auth/RBAC/route scan live here; no new service |
| Role authorization | API / Backend (`packages/rbac`) | — | `PERMISSIONS_MATRIX` + `RbacGuard` longest-prefix match |
| Config persistence / validation | Library (`packages/operator-config`) | — | Phase 73 SoT; HTTP must not reimplement schemas/store |
| Feature-flag mutate gate | Library (`platform-runtime` + operator-config flags) | API maps errors | `require_operator_config_writable` already refuses disk writes when OFF |
| Operational read views | API / Backend (existing views) | — | Must remain read-only; no write handlers on sessions/tasks/feedback/health/gates |
| SSR config forms | Frontend Server (admin-web-ui) | — | **Out of scope** (Phase 78 / ADM-02) |
| Channel/provider apply | Host / runtime | — | **Out of scope** (Phases 75–76) |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `admin-console-api` | 0.1.0 in-repo | HTTP handlers + route table | Existing auth, tenant guard, gate entry; empty deps |
| `inkstatute_operator_config` | Phase 73 package | Schemas, validate, store, flag gate | Locked store authority |
| `rbac` | in-repo | `Role`, `RbacGuard`, `PERMISSIONS_MATRIX`, tokens | Default-deny matrix + CI scan |
| `platform_runtime.feature_flags` | in-repo | `admin_api_enabled`, `rbac_enabled`, `operator_config_enabled` | Dual flag pattern already used by skill-registry writes |
| Python `unittest` | stdlib | Handler + RBAC + read-only regression tests | Matches all admin/operator-config gates |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `OperatorConfigStore.document_from_payload` / `document_to_payload` | Phase 73 | JSON ↔ frozen doc | PUT body parse / GET serialize |
| `skill-registry.write_api` pattern | in-repo | Flag + RBAC gate before mutate | Template for `handle_admin_put` gating order |
| `scripts/scan_rbac_annotations.py` | in-repo | Fail CI if route lacks matrix entry | Must stay green after adding `/config` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Extend `admin-console-api` | New `services/config-service` | Rejected — locked: no new service/auth stack [CITED: .planning/research/ARCHITECTURE.md] |
| Method-aware single dispatcher | Separate FastAPI app | Rejected — empty-deps pure handlers are the house style |
| PATCH partial fields | Full-section PUT | Prefer section PUT (channels/providers/catalog/vision) matching RESEARCH deliverables; simpler allowlist |
| ADMIN-only PUT | ADMIN+OPERATOR PUT | ROADMAP SC#1 and ADM-01 require both roles can GET and PUT |

**Installation:** No new PyPI packages. Wire existing packages via PYTHONPATH / editable installs already used by V2 gates.

```bash
# No npm/pip install required for Phase 74
# Gate PYTHONPATH must add packages/operator-config/src to admin-console-api gate
```

**Version verification:** In-repo packages only — no registry install. Confirmed importable: `OperatorConfigStore`, `RuntimeFeatureFlags.operator_config_enabled=False`, `PERMISSIONS_MATRIX` keys, `ROUTE_PREFIXES`. [VERIFIED: local import + unittest]

## Package Legitimacy Audit

> Phase 74 installs **no** new external packages.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| — | — | — | — | — | — | N/A — no new installs |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck not required — no external package installs in this phase.*

## Architecture Patterns

### System Architecture Diagram

```text
Caller (admin-web-ui later / tests now)
    │  Authorization: Bearer <static|RBAC token>
    ▼
┌─────────────────────────────────────────────────────────────┐
│ admin-console-api                                           │
│  1. require admin_api_enabled                               │
│  2. auth (static → synthetic ADMIN | RBAC resolve_identity) │
│  3. RbacGuard.check(role, path)  ← PERMISSIONS_MATRIX       │
│  4. TenantGuard (existing; config is single-tenant MVP)     │
│                                                             │
│  GET  /sessions|/tasks|/feedback|/health|/gates  → views    │
│       (read_only metadata; NO write handlers)               │
│                                                             │
│  GET  /config/{channels|providers|catalog|vision}           │
│       → load OperatorConfigStore → section JSON (refs only) │
│                                                             │
│  PUT  /config/{channels|providers|catalog|vision}           │
│       → require_operator_config_writable (via store.save)   │
│       → merge section into full OperatorConfigDocument      │
│       → validate_document → atomic save                     │
│                                                             │
│  PUT  /sessions|/tasks|...  → 405 method_not_allowed        │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
              packages/operator-config
              OperatorConfigStore (flag → validate → atomic JSON)
```

### Recommended Project Structure

```text
services/admin-console-api/
├── src/admin_console_api/
│   ├── api.py              # extend GET dispatch; add handle_admin_put
│   ├── routes.py           # add "/config" to ROUTE_PREFIXES
│   ├── config_api.py       # NEW: section GET/PUT handlers + error mapping
│   ├── auth.py             # unchanged
│   ├── views.py            # unchanged (no write methods)
│   ├── health.py / gates.py
│   └── __init__.py         # export handle_admin_put
├── tests/
│   ├── test_read_only.py   # EVOLVE: operational write-proof + config-only PUT
│   ├── test_config_api.py  # NEW: GET/PUT happy paths, flag OFF, planted secrets
│   ├── test_rbac_integration.py  # ADD: /config role matrix cases
│   └── test_contract_freeze.py   # FIX: expect operator_config_enabled
packages/rbac/src/rbac/
└── matrix.py               # add "/config": {ADMIN, OPERATOR}
packages/rbac/tests/
└── test_matrix.py          # update ADMIN_API_ROUTE_PREFIXES + assertions
scripts/run_v2_gates.py     # add operator-config src to admin-console-api PYTHONPATH
```

### Pattern 1: Separate Mutate Entry Point (skill-registry analog)
**What:** Keep `handle_admin_get` for reads; add `handle_admin_put(path, body, …)` for config writes only — same pure-function style as `inkstatute_skill_registry.write_api.handle_put`.
**When to use:** Any admin mutate surface that must not weaken existing GET-only operational routes.
**Example:**
```python
# Source: packages/skill-registry/src/inkstatute_skill_registry/write_api.py
# Gate order: feature flag → RbacGuard → dispatch
# For config PUT: admin_api_enabled (outer) → RBAC /config → store.save
# (store.save calls require_operator_config_writable)
```

### Pattern 2: Section Merge Over Full Document
**What:** PUT body replaces one section (`channels` | `providers` | `catalog` | `vision`); handler loads full doc, replaces that field, validates whole document, saves.
**When to use:** Always for Phase 74 — matches SUMMARY deliverable paths and keeps Hermes/refs validators on the full tree.
**Example:**
```python
# Source: packages/operator-config/src/inkstatute_operator_config/store.py
from inkstatute_operator_config import OperatorConfigStore, OperatorConfigDocument
from inkstatute_operator_config.store import document_from_payload, document_to_payload
from dataclasses import replace

store = OperatorConfigStore(path)
current = store.load()
# parse section payload → typed section dataclass
updated = replace(current, channels=new_channels)  # or providers/catalog/vision
store.save(updated, feature_flags=flags)
```

### Pattern 3: RBAC Longest-Prefix Matrix Entry
**What:** Single matrix key `"/config"` covering `/config/channels` etc. via `RbacGuard._resolve` prefix rules.
**When to use:** All `/config/*` routes — one annotation keeps `scan_rbac_annotations.py` simple.
**Example:**
```python
# Source: packages/rbac/src/rbac/matrix.py + guard.py
PERMISSIONS_MATRIX["/config"] = frozenset({Role.ADMIN, Role.OPERATOR})
# endpoint "/config/channels" matches prefix "/config" + "/"
```

### Anti-Patterns to Avoid
- **Adding PUT handlers on `/sessions|/tasks|/feedback`:** Violates ADM-03 and ROADMAP SC#3.
- **Resolving secret refs in GET responses:** Echoes secrets; return stored `*_ref` strings only; never call host resolvers. [VERIFIED: operator-config README — resolve at process edge]
- **Bypassing `OperatorConfigStore.save`:** Hand-rolling JSON writes skips flag gate + validate + atomic replace.
- **Lawyer/viewer matrix entry on `/config`:** Violates ADM-01 / SC#2.
- **New FastAPI/DB/queue/SPA:** Locked out of scope.
- **Leaving `test_no_put_handler_exists` unchanged:** Would block legitimate `handle_admin_put`; evolve the contract instead of deleting coverage.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Config schema / Hermes ban / refs validation | Ad hoc dict checks in API | `validate_document` + store | Already fail-closed; no-echo errors |
| Atomic JSON persist | Direct `Path.write_text` in API | `OperatorConfigStore.save` | Flag gate + tmp+replace |
| Role checks | Inline `if role == admin` | `RbacGuard` + matrix | Default-deny + CI scan |
| Auth / token parse | New auth module | Existing `auth.py` + `resolve_identity` | Same as GET path |
| Secret resolution | Import qqbot `resolve_secret_ref` | Do not resolve in Phase 74 | Hosts own resolve (Phase 75+) |

**Key insight:** Phase 74 is an HTTP + RBAC adapter over an already-complete mutate authority. Complexity belongs in tests that prove the boundary, not in reimplementing the store.

## Common Pitfalls

### Pitfall 1: Breaking `test_read_only.py` without replacing the contract
**What goes wrong:** Adding `handle_admin_put` fails `test_no_put_handler_exists`; deleting the test loses ADM-03 protection.
**Why it happens:** Phase 42/43 froze “no PUT exists” as the read-only proof.
**How to avoid:** Rewrite assertions to: (a) PUT on operational prefixes → 405; (b) views module still has no `create_/update_/put_` helpers; (c) GET responses still set `metadata.read_only=True`; (d) only `/config/*` returns 2xx from PUT when authorized + flag ON.
**Warning signs:** Gate `admin-console-api` red on read-only tests; or green with no operational write-denial cases.

### Pitfall 2: Flag OFF checked only in HTTP, not store
**What goes wrong:** HTTP returns 403 but a code path writes JSON anyway; or HTTP skips check and relies solely on store (OK) but tests only mock HTTP.
**Why it happens:** Dual gates (`admin_api_enabled` vs `operator_config_enabled`) confuse implementers.
**How to avoid:** Always call `store.save(..., feature_flags=flags)` so package gate is authoritative; map `OperatorConfigDisabledError` → 403 `operator_config_disabled`; assert no file side effects when OFF (reuse Phase 73 pattern).
**Warning signs:** PUT with flag OFF creates `.inkstatute/operator-config.json`.

### Pitfall 3: Lawyer bypass via static-token or unannotated route
**What goes wrong:** `/config` missing from matrix → default-deny (safe) OR accidentally added to sessions-like all-roles set; or PUT routed before RBAC.
**Why it happens:** Copy-paste from `/sessions` matrix entry.
**How to avoid:** Matrix roles exactly `{ADMIN, OPERATOR}`; RBAC tests for LAWYER/VIEWER GET and PUT → 403; keep auth→RBAC→dispatch order identical to GET.
**Warning signs:** `scan_rbac_annotations` fails; or lawyer PUT returns 200.

### Pitfall 4: Planted raw secrets accepted or echoed
**What goes wrong:** PUT with `api_key: "sk-…"` persists or 400 message echoes the value.
**Why it happens:** Skipping `validate_document` or stringifying exceptions carelessly.
**How to avoid:** Persist only through store; assert 400 + message does not contain planted secret; GET returns refs only.
**Warning signs:** Response body contains `sk-` or raw token substrings.

### Pitfall 5: Stale `test_contract_freeze` expected flag set
**What goes wrong:** Admin gate fails on `operator_config_enabled` not in expected set (already failing today after Phase 73).
**Why it happens:** Phase 73 added the flag; admin freeze allowlist not updated.
**How to avoid:** Wave 0 — add `operator_config_enabled` to `expected_flags` in `test_contract_freeze.py`.
**Warning signs:** `test_no_new_fields_added_to_feature_flags` FAIL (observed 2026-07-10). [VERIFIED: local unittest]

### Pitfall 6: Forgetting operator-config on admin gate PYTHONPATH
**What goes wrong:** ImportError for `inkstatute_operator_config` in CI gate.
**How to avoid:** Extend `scripts/run_v2_gates.py` admin-console-api Gate tuple with `packages/operator-config/src`.
**Warning signs:** Gate green locally with manual PYTHONPATH but red in `run_v2_gates.py`.

## Code Examples

### handle_admin_put skeleton (prescriptive)
```python
# Pattern source: services/admin-console-api/src/admin_console_api/api.py
# + packages/skill-registry/.../write_api.py
def handle_admin_put(
    path: str,
    body: Mapping[str, Any] | None,
    headers: Mapping[str, str] | None,
    feature_flags: RuntimeFeatureFlags,
    env: Mapping[str, str] | None = None,
    *,
    store: OperatorConfigStore | None = None,
    rbac_secret: str | None = None,
) -> tuple[int, dict[str, Any]]:
    # 1) admin_api_enabled
    # 2) auth + RbacGuard (same as GET)
    # 3) if not path under /config/ → 405 method_not_allowed
    # 4) dispatch config_api.handle_config_put(...)
    ...
```

### Error mapping
```python
# Source: packages/operator-config/.../errors.py + skill-registry write_api gate style
# OperatorConfigDisabledError → 403 {"error":{"code":"operator_config_disabled",...}}
# OperatorConfigValidationError → 400 {"error":{"code":"invalid_config","message":...}}  # no secret echo
# OperatorConfigStoreError → 500 {"error":{"code":"config_store_error",...}}  # no path secrets
```

### GET response shape (refs only)
```python
# Serialize via document_to_payload / asdict — includes *_ref strings, never resolved values
{
  "data": { ... section or fields ... },
  "metadata": {
    "admin_api": True,
    "config_surface": True,
    "operator_config_enabled": flags.operator_config_enabled,
    "read_only": False,  # config surface is writable when flag+RBAC allow
  },
}
```

### RBAC matrix addition
```python
# Source: packages/rbac/src/rbac/matrix.py
"/config": frozenset({Role.ADMIN, Role.OPERATOR}),
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Admin API strictly no PUT symbol | Explicit `/config/*` PUT only | Phase 74 | Preserves ADM-03 while enabling ADM-01 |
| Package-only CFG-02 gate | HTTP maps `OperatorConfigDisabledError` | Phase 74 | ROADMAP SC#4 observable over HTTP |
| Matrix without `/config` | `/config` ADMIN+OPERATOR | Phase 74 | Lawyer/viewer default-deny |

**Deprecated/outdated:**
- Asserting `not hasattr(api_module, "handle_admin_put")` as the sole read-only proof — replace with method/path-scoped write denial.
- Treating health allowlist (strip refs) as the model for config GET — config GET must return editable refs.

## File Touch Points (Planner)

| Path | Action | Notes |
|------|--------|-------|
| `services/admin-console-api/src/admin_console_api/config_api.py` | **CREATE** | Section GET/PUT + error mapping |
| `services/admin-console-api/src/admin_console_api/api.py` | **MODIFY** | GET `/config/*` dispatch; add `handle_admin_put` |
| `services/admin-console-api/src/admin_console_api/routes.py` | **MODIFY** | Add `"/config"` |
| `services/admin-console-api/src/admin_console_api/__init__.py` | **MODIFY** | Export `handle_admin_put` |
| `services/admin-console-api/README.md` | **MODIFY** | Document config surface + flags + read-only operational views |
| `services/admin-console-api/tests/test_config_api.py` | **CREATE** | ADM-01/03 + SC#4 + planted-secret tests |
| `services/admin-console-api/tests/test_read_only.py` | **MODIFY** | Evolve contract (see Pitfall 1) |
| `services/admin-console-api/tests/test_rbac_integration.py` | **MODIFY** | Lawyer/viewer/admin/operator `/config` cases |
| `services/admin-console-api/tests/test_contract_freeze.py` | **MODIFY** | Add `operator_config_enabled` to expected set (Wave 0) |
| `packages/rbac/src/rbac/matrix.py` | **MODIFY** | `/config` → ADMIN+OPERATOR |
| `packages/rbac/tests/test_matrix.py` | **MODIFY** | Include `/config` in route list + role assert |
| `scripts/run_v2_gates.py` | **MODIFY** | operator-config on admin-console-api PYTHONPATH |
| `packages/operator-config/**` | **Avoid unless needed** | Prefer import public API; optionally export `document_from_payload` from package `__init__` if API needs it |

**Do not touch:** admin-web-ui SSR (78), channel hosts (75), catalog content (76), vision runtime (77), Hermes paths, new DB/queue.

## Recommended Approach (Prescriptive)

1. **Wave 0:** Fix `test_contract_freeze.py` expected flags to include `operator_config_enabled` (unblocks admin gate).
2. **RBAC first:** Add `"/config"` to `PERMISSIONS_MATRIX` and `ROUTE_PREFIXES`; update matrix tests + scan.
3. **Config handlers:** New `config_api.py` with GET/PUT for four sections; section merge via `dataclasses.replace`; persist only through `OperatorConfigStore`.
4. **API wiring:** Extend `handle_admin_get` for `/config/*`; add `handle_admin_put` that 405s non-config paths after auth/RBAC (or 404 before RBAC for unknown — prefer **auth then 405** so unauthorized callers still get 401).
5. **Flags:** PUT always goes through `store.save` so OFF → `OperatorConfigDisabledError` → 403 even for ADMIN/OPERATOR. GET allowed when flag OFF (returns defaults/file).
6. **Secrets:** No resolve; planted raw keys → 400 via validate; assert no echo in tests.
7. **Read-only evolution:** Rewrite `test_read_only.py` per Pitfall 1; keep operational GET `read_only: true`.
8. **Gate PYTHONPATH:** Add `packages/operator-config/src` to admin-console-api gate.
9. **Roles:** ADMIN+OPERATOR for GET and PUT; LAWYER/VIEWER denied both (stricter than “mutate only,” matches SUMMARY/FEATURES and prevents ref leakage to lawyers).

**Discretion recommendation on GET for lawyer/viewer:** Deny entirely on `/config` (not only PUT). ADM-01 text emphasizes mutate denial, but credential refs are still sensitive operational data; existing `/health` already excludes lawyers. [ASSUMED product preference — aligns with research SUMMARY; confirm only if product wants lawyer read of refs]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Lawyer/viewer should be denied config **GET** as well as PUT | Recommended Approach | If product wants lawyer read of non-secret config, matrix would allow GET-only — would need separate GET vs PUT authz (matrix is path-only today) |
| A2 | Section-scoped PUT (not whole-document PUT only) is the desired API shape | Architecture Patterns | Whole-doc PUT `/config` alone would still meet ADM-01 but diverge from SUMMARY path list |
| A3 | Single-tenant config (no per-tenant store files) for MVP | Architecture diagram | Multi-tenant would need path/tenant scoping later |
| A4 | `document_from_payload` may be imported from `.store` submodule without re-export | File Touch Points | Minor API polish if planner prefers package `__init__` export |

**If A1 needs confirmation:** Matrix cannot express method-level ACL today without a second check in `handle_admin_put` / GET. Path-level ADMIN+OPERATOR for both methods is the implementable default.

## Open Questions

> **Resolved at plan-phase 2026-07-10** — decisions locked into `74-0{1,2,3}-PLAN.md` / `74-VALIDATION.md`.

1. **Whole-document GET `/config` in addition to section routes?**
   - **RESOLVED: sections-only.** Implement `/config/{channels,providers,catalog,vision}` only; bare `GET /config` returns 404. Full-document GET deferred unless a later phase needs it.

2. **Should PUT on `/sessions` return 405 or 404?**
   - **RESOLVED: 405** with `method_not_allowed` after successful auth (stronger ADM-03 signal than 404).

3. **Export `document_from_payload` from package `__init__`?**
   - **RESOLVED: no re-export.** Import from `inkstatute_operator_config.store` in Phase 74.

4. **Lawyer/viewer GET on `/config`? (Assumptions Log A1)**
   - **RESOLVED: deny GET and PUT.** Path-level `ADMIN+OPERATOR` only (credential refs are sensitive; matrix is path-only).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | admin-console-api / operator-config | ✓ | 3.14.6 | — |
| `unittest` | gate tests | ✓ | stdlib | — |
| `packages/operator-config` | config handlers | ✓ | Phase 73 | — |
| `packages/rbac` | matrix / guard | ✓ | in-repo | — |
| FastAPI / new DB | — | N/A | — | Do not use |
| admin-web-ui SSR | — | present but OOS | — | Phase 78 |

**Missing dependencies with no fallback:** none

**Missing dependencies with fallback:** none

Step 2.6: External tools beyond Python stdlib + in-repo packages — none required.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Python `unittest` (stdlib) |
| Config file | none — discovery via `python -m unittest discover` |
| Quick run command | `PYTHONPATH=packages/operator-config/src:packages/rbac/src:services/admin-console-api/src:packages/platform-runtime/src:services/conversation-read-view/src:services/feedback-service/src:packages/platform-contract/src python -m unittest services.admin-console-api.tests.test_config_api services.admin-console-api.tests.test_read_only -q` |
| Full suite command | `python scripts/run_v2_gates.py` (or admin-console-api + rbac gates) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ADM-01 | Admin/operator GET+PUT `/config/*` 200 | unit/integration | `… test_config_api.py` + `test_rbac_integration.py` | ❌ Wave 0 |
| ADM-01 | Lawyer/viewer PUT (and GET) `/config/*` 403 | integration | `… test_rbac_integration.py` | ❌ Wave 0 |
| ADM-03 | PUT `/sessions|/tasks|/feedback|/health|/gates` → 405 | unit | `… test_read_only.py` | ⚠️ exists but must evolve |
| ADM-03 | Operational GET still `metadata.read_only=True` | unit | `… test_read_only.py` | ✅ keep |
| SC#4 / CFG-02 | PUT with `operator_config_enabled=False` → 403, no file write | unit | `… test_config_api.py` | ❌ Wave 0 |
| SAFE | Planted `api_key`/`sk-` → 400, no echo | unit | `… test_config_api.py` | ❌ Wave 0 |
| RBAC scan | `/config` in ROUTE_PREFIXES ↔ matrix | unit/CI | `scripts/scan_rbac_annotations.py` | ✅ extend |
| Carry | `operator_config_enabled` in freeze allowlist | unit | `… test_contract_freeze.py` | ⚠️ broken today |

### Sampling Rate
- **Per task commit:** focused `unittest` modules touched by the task
- **Per wave merge:** full `services/admin-console-api/tests` + `packages/rbac/tests`
- **Phase gate:** `run_v2_gates.py` admin-console-api + rbac + operator-config green

### Wave 0 Gaps
- [ ] Fix `test_contract_freeze.py` expected flags (`operator_config_enabled`) — currently FAIL
- [ ] Create `tests/test_config_api.py`
- [ ] Evolve `tests/test_read_only.py` write-denial contract
- [ ] Extend `test_rbac_integration.py` for `/config`
- [ ] Add operator-config to admin-console-api gate PYTHONPATH
- [ ] Framework install: none

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Existing Bearer static token / RBAC HMAC token |
| V3 Session Management | no | Short-lived RBAC tokens already; no new sessions |
| V4 Access Control | yes | `PERMISSIONS_MATRIX` + `RbacGuard` default-deny; lawyer/viewer denied `/config` |
| V5 Input Validation | yes | `validate_document` + `document_from_payload` fail-closed |
| V6 Cryptography | no new | Reuse HMAC compare_digest / RBAC token; never hand-roll crypto |

### Known Threat Patterns for admin config API

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Lawyer mutates channel/provider refs | Elevation of Privilege | Matrix ADMIN+OPERATOR only; RBAC tests |
| Write via operational route | Tampering | PUT only on `/config/*`; 405 elsewhere |
| Flag-off write still persists | Tampering | `OperatorConfigStore.save` → `require_operator_config_writable` |
| Raw secret in PUT body | Information Disclosure / Tampering | `FORBIDDEN_RAW_SECRET_KEYS` + marker regex; 400 no-echo |
| Resolved secret in GET | Information Disclosure | Never call resolve; return refs only |
| Unannotated new route | Elevation of Privilege | `ROUTE_PREFIXES` + `scan_rbac_annotations.py` |
| Path traversal / Hermes SoT | Tampering | Existing Hermes ban-list in validate |

## Project Constraints (from .cursor/rules/)

No `.cursor/rules/` directory present in this workspace. Applicable constraints come from `AGENTS.md` / CONTEXT:

- Keep changes scoped to active GSD phase
- Never commit secrets, tokens, runtime config store files
- Do not introduce new service/DB/queue unless required
- Prefer schema validators over ad hoc parsing
- Tests with behavior changes (RBAC, dedupe, fixtures)

## Sources

### Primary (HIGH confidence)
- In-repo: `.planning/phases/74-admin-config-api-rbac/74-CONTEXT.md`
- In-repo: `.planning/REQUIREMENTS.md` ADM-01, ADM-03; `.planning/ROADMAP.md` Phase 74
- In-repo: Phase 73 `73-VERIFICATION.md`, `73-03-SUMMARY.md`, `packages/operator-config/**`
- In-repo: `services/admin-console-api` (`api.py`, `routes.py`, `auth.py`, `test_read_only.py`, `test_rbac_integration.py`)
- In-repo: `packages/rbac` (`matrix.py`, `guard.py`), `scripts/scan_rbac_annotations.py`
- In-repo: `packages/skill-registry/.../write_api.py` (mutate gate pattern)
- In-repo: `.planning/research/SUMMARY.md`, `STACK.md`, `ARCHITECTURE.md`, `FEATURES.md`

### Secondary (MEDIUM confidence)
- FEATURES.md AuthZ row allowing “admin or admin+operator” — resolved to ADMIN+OPERATOR by ROADMAP SC#1

### Tertiary (LOW confidence)
- None material for Phase 74 implementation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all in-repo, Phase 73 verified, no new deps
- Architecture: HIGH — clear extension of existing admin + RBAC + skill-registry write pattern
- Pitfalls: HIGH — read-only test evolution and freeze drift already observed locally

**Research date:** 2026-07-10
**Valid until:** 2026-08-09 (30 days — stable in-repo patterns)
