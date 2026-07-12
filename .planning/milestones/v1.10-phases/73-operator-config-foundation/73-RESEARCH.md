# Phase 73: Operator Config Foundation - Research

**Researched:** 2026-07-10
**Domain:** InkStatute-owned refs-only operator config authority (schemas, atomic store, validators, default-OFF flag)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
All implementation choices are at the agent's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Locked from milestone init / PROJECT.md:
- Config secrets stay as refs; values resolve at process edge only
- Extend existing admin-console-api + admin-web-ui (stdlib SSR); no new SPA/DB/queue for MVP
- `operator_config_enabled` default OFF; dual-knob channel enablement preserved
- Never treat Hermes `~/.hermes` / profile filesystem as config authority

### Claude's Discretion
All implementation choices are at the agent's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
None — discuss phase skipped. CFG-F01..F03 and related future items remain beyond v1.10 per STATE.md.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CFG-01 | Operator can persist InkStatute-owned operator config (channels, providers, catalog selection, vision policy) in a refs-only store — never raw secrets in the store or API bodies | `packages/operator-config/` schemas + atomic JSON store; secret-ref validators; planted-secret ban-list tests |
| CFG-02 | Operator config surface gated by default-OFF `operator_config_enabled`; when OFF, mutate paths refuse writes | Add flag to `RuntimeFeatureFlags`; store `save()` / mutate helper calls `require_enabled("operator_config_enabled")` |
| CFG-03 | Config schemas/validators reject Hermes filesystem/profile paths as config authority (InkStatute store only; no `~/.hermes` writes) | Explicit Hermes path/field ban-list in validators; negative tests for `~/.hermes`, profile paths, hermes-home fields |
</phase_requirements>

## Summary

Phase 73 is the **safety foundation** for v1.10: an InkStatute-owned config authority that can persist channel/provider/catalog/vision documents as **secret refs only**, behind a **default-OFF** `operator_config_enabled` flag, and that **never** treats Hermes `~/.hermes` / profile filesystem as source of truth. Prior milestone research (`.planning/research/SUMMARY.md`) already prescribed `packages/operator-config/` + atomic JSON + flag — this phase research confirms that approach against the live codebase and narrows Phase 73 to package + flag work only.

**Do not** implement HTTP `/config/*` mutate routes (Phase 74), host apply/loaders (Phase 75), full model catalog content (Phase 76), vision runtime (Phase 77), or SSR forms (Phase 78). Phase 73 must leave `admin-console-api` read-only contract intact (`test_read_only.py` still asserts no `handle_admin_put`). Prove CFG-02 at the **package mutate path** (`OperatorConfigStore.save` / `require_operator_config_writable`); Phase 74 wires HTTP to the same gate.

**Primary recommendation:** Create empty-deps `packages/operator-config/` (schemas, refs-only validators, Hermes ban-list, atomic JSON store) and add `operator_config_enabled: bool = False` to `RuntimeFeatureFlags`; register a V2 gate. No new PyPI packages, DB, queue, or SPA.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Operator config schemas / validation | API / Backend (library package) | — | Shared authority for admin API, hosts, smoke — not browser |
| Atomic config persistence | Database / Storage (file store) | API / Backend | File-backed SoT outside git; no new DB |
| Secret-ref shape validation | API / Backend (library) | — | Validate refs at write time; never resolve/store values |
| Secret value resolution | API / Backend (process edge / hosts) | — | Existing `resolve_secret_ref` pattern; **out of Phase 73 apply scope** |
| Feature flag gate | API / Backend (`platform-runtime`) | — | Same `require_enabled` pattern as all other lanes |
| Hermes-not-SoT enforcement | API / Backend (validators) | — | Schema ban-list; no Hermes filesystem writers |
| HTTP `/config/*` mutate | API / Backend (`admin-console-api`) | — | **Phase 74** — not this phase |
| SSR config forms | Frontend Server (SSR `admin-web-ui`) | — | **Phase 78** (incremental forms may appear in 75–77) |
| Channel/provider apply | API / Backend (hosts) | — | **Phases 75–76** |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `dataclasses` + `json` + `pathlib` + `os.replace` | 3.11+ (CI floor; local probe 3.14.6) | Frozen config docs, atomic JSON store | Matches every empty-deps package; no Pydantic [VERIFIED: in-repo pyproject `requires-python = ">=3.11"`] |
| `packages/platform-runtime` `RuntimeFeatureFlags` | 0.1.0 in-repo | `operator_config_enabled=False` + `require_enabled` | Existing default-OFF lane pattern; introspection test covers all fields [VERIFIED: `feature_flags.py`] |
| New `packages/operator-config/` (`inkstatute-operator-config`) | 0.1.0 | Schemas, validators, store | Prescribed by `.planning/research/ARCHITECTURE.md` / SUMMARY [CITED: `.planning/research/SUMMARY.md`] |
| Existing channel / provider config shapes | in-repo | Field naming alignment (`*_ref`, `enabled`, `api_key_ref`) | Docs mirror `QQBotChannelConfig` / `WeComChannelConfig` / `ProviderModelBackendConfig` without importing Hermes [VERIFIED: channel + provider_model config modules] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `unittest` | stdlib | Package tests + flag default tests | Same as admin-console-api / platform-runtime |
| `scripts/run_v2_gates.py` gate entry | in-repo | Gate coverage for new `packages/operator-config/src` | Required by `test_gate_coverage.py` for top-level `packages/*/src` |
| QQBot `normalize_config_secret_ref` pattern | in-repo (`qqbot_service.secrets`) | Shape-only ref validation inspiration | Lift **policy** into operator-config validators; do not hard-depend on qqbot-service from the package [VERIFIED: `services/qqbot-service/src/qqbot_service/secrets.py`] |
| Env `INKSTATUTE_OPERATOR_CONFIG_PATH` | — | Store file location | Document in package README; path must be gitignored / outside repo [CITED: `.planning/research/STACK.md`] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `packages/operator-config/` | Put schemas inside `admin-console-api` | Couples hosts/smoke to HTTP service; rejected by ARCHITECTURE [CITED: `.planning/research/ARCHITECTURE.md`] |
| Atomic JSON file | SQLite / Postgres / Redis | Forbidden unless plan requires new DB (AGENTS.md); overkill for MVP |
| Package-level mutate gate only | HTTP PUT in Phase 73 | Breaks read-only admin contract early; Phase 74 owns `/config/*` |
| Pydantic / jsonschema hard dep | Hand validators | Would break `dependencies = []` monorepo convention |
| Hermes `~/.hermes` as store | InkStatute JSON store | Explicitly forbidden (CFG-03 / AGENTS.md) |

**Installation:**

```bash
# No new PyPI packages. Editable install only:
pip install -e packages/operator-config
pip install -e packages/platform-runtime

# Runtime path (gitignored / outside repo — never commit):
export INKSTATUTE_OPERATOR_CONFIG_PATH=/var/lib/inkstatute/operator-config.json
```

**Version verification:** No new registry packages. setuptools build backend already used across monorepo (`setuptools` present locally). Python `>=3.11` confirmed in existing pyprojects. [VERIFIED: in-repo]

## Package Legitimacy Audit

> Phase 73 installs **no new external packages**. Only a new in-repo empty-deps package.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| *(none — no PyPI adds)* | — | — | — | — | N/A | Approved (stdlib + in-repo only) |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck 0.6.1 available locally; not invoked against new names because no registry installs are recommended.*

## Architecture Patterns

### System Architecture Diagram

```text
                    ┌─────────────────────────────────────┐
                    │  Phase 73 (this phase)              │
 Operator docs ───▶ │  schemas + validate (refs-only)     │
 (channels /        │       │                             │
  providers /       │       ▼                             │
  catalog /         │  Hermes ban-list reject? ──yes──▶ error
  vision)           │       │ no                          │
                    │       ▼                             │
                    │  require_enabled(                    │
                    │    operator_config_enabled)         │
                    │       │ OFF ──▶ refuse write        │
                    │       │ ON                          │
                    │       ▼                             │
                    │  OperatorConfigStore (atomic JSON)  │
                    │  path = INKSTATUTE_OPERATOR_CONFIG_PATH
                    └─────────────────────────────────────┘
                                      │
                                      │ (later phases)
                                      ▼
                    ┌─────────────────────────────────────┐
                    │  Phase 74: admin-console-api /config/*│
                    │  Phase 75–77: host loaders / vision  │
                    │  Phase 78: SSR forms                 │
                    └─────────────────────────────────────┘

NEVER: Path.home() / ".hermes" / Hermes profile filesystem as SoT
NEVER: raw secret values in store JSON
```

### Recommended Project Structure

```
packages/operator-config/
├── pyproject.toml                 # name=inkstatute-operator-config, dependencies=[]
├── README.md                      # refs-only + flag + path env; no Hermes
├── src/inkstatute_operator_config/
│   ├── __init__.py
│   ├── schemas.py                 # OperatorConfigDocument + Channel/Provider/Catalog/Vision docs
│   ├── secrets.py                 # shape-only secret-ref normalize/validate (no resolve)
│   ├── validate.py                # document validation + Hermes ban-list
│   ├── store.py                   # load/save atomic JSON; gated save
│   ├── flags.py                   # thin require_operator_config_writable(flags) helper
│   └── errors.py                  # OperatorConfigError, OperatorConfigDisabledError, ValidationError
└── tests/
    ├── test_schemas.py
    ├── test_secret_refs.py        # planted raw secret → reject
    ├── test_hermes_banlist.py     # ~/.hermes / profile paths → reject
    ├── test_store.py              # atomic write + round-trip
    └── test_flag_gate.py          # save refused when flag OFF

packages/platform-runtime/src/platform_runtime/feature_flags.py
  # ADD: operator_config_enabled: bool = False

scripts/run_v2_gates.py
  # ADD: operator-config unittest gate + compileall path
```

### Pattern 1: Package Authority Before HTTP

**What:** Persist and validate through `inkstatute_operator_config` only. Admin HTTP (Phase 74) becomes a thin caller.
**When to use:** Always for CFG-01..03.
**Example:**

```python
# Source: in-repo pattern adapted from qqbot_service.secrets + RuntimeFeatureFlags
from platform_runtime.feature_flags import RuntimeFeatureFlags
from inkstatute_operator_config.store import OperatorConfigStore
from inkstatute_operator_config.flags import require_operator_config_writable

flags = RuntimeFeatureFlags()  # operator_config_enabled=False
store = OperatorConfigStore(path)
require_operator_config_writable(flags)  # raises → refuse write
store.save(document, feature_flags=flags)
```

### Pattern 2: Refs-Only Documents

**What:** Credential fields are `*_ref` / `api_key_ref` only. Accept `env:NAME`, known `secret://…` shapes, or bare env-key identifiers. Reject planted raw values without echoing them in errors.
**When to use:** Every credential field on channel/provider docs.
**Example:**

```python
# Source: services/qqbot-service/src/qqbot_service/secrets.py (normalize_config_secret_ref)
# Phase 73: validate shape only — do NOT resolve values into the store.
@dataclass(frozen=True, slots=True)
class ChannelDoc:
    channel_id: str
    enabled: bool = False
    # e.g. token_secret_ref: str | None  — NEVER token: str
```

### Pattern 3: Hermes Ban-List at Schema Boundary

**What:** Validators reject documents that assert Hermes filesystem/profile authority (`~/.hermes`, `.hermes/`, `hermes_home`, `profile_path` pointing at Hermes, etc.). Store never writes those paths.
**When to use:** On every `validate_document` / `save` path (CFG-03).

### Anti-Patterns to Avoid

- **HTTP mutate in Phase 73:** Breaks `test_read_only.py` contract; belongs in Phase 74.
- **Resolving secrets into the store:** Values belong at process edge only (hosts).
- **Writing Hermes profiles / `~/.hermes`:** Collapses ownership boundary (Pitfall 1).
- **Defaulting `operator_config_enabled=True`:** Accidental writes; violates CFG-02.
- **New DB/queue/SPA:** Locked out by PROJECT / AGENTS / STACK.
- **Collapsing dual-knob into schema `enabled` alone:** Preserve platform flag AND doc `enabled` semantics for later phases; Phase 73 schemas keep `enabled` default False but do not replace `RuntimeFeatureFlags.qqbot_channel_enabled`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Feature-flag framework | Custom toggle registry | `RuntimeFeatureFlags.require_enabled` | Introspection tests already enforce all flags default False |
| Secret resolution crypto | New vault client | Shape validation now; host `resolve_secret_ref` later | SAFE-02 already proven in qqbot-service |
| Config DB | SQLite/Postgres schema | Atomic JSON via `os.replace` | AGENTS.md; STACK rejects new DB for MVP |
| Admin auth stack | New token system | Existing admin-console-api auth (Phase 74) | Reuse static token / RBAC |
| Hermes config sync | Profile/filesystem writer | InkStatute store only | CFG-03 / AGENTS.md |

**Key insight:** The hard problems (refs-only, default-OFF, Hermes-not-SoT) are **validation + gate** problems, not infrastructure problems. Hand-roll validators on dataclasses; do not invent a new platform.

## Common Pitfalls

### Pitfall 1: Configuring Hermes from the console / store
**What goes wrong:** Store accepts `hermes_profile_path` / `~/.hermes` and becomes a Hermes editor.
**Why it happens:** Operators want “one place for everything.”
**How to avoid:** Explicit ban-list + negative tests; README states InkStatute SoT only.
**Warning signs:** Any `Path.home() / ".hermes"` in operator-config package.

### Pitfall 2: Raw secrets in persisted JSON
**What goes wrong:** `api_key`, WeCom token, or `sk-…` lands in store file or error messages.
**Why it happens:** UI/API convenience; copying env values into `*_REF` fields.
**How to avoid:** Shape-only validators; planted-secret fixtures; errors must not echo rejected values (same as `InvalidSecretRefError`).
**Warning signs:** Store round-trip tests that assert raw key equality.

### Pitfall 3: Flag-off writes still succeed
**What goes wrong:** `save()` works whenever path is writable, ignoring `operator_config_enabled`.
**Why it happens:** Persistence treated as SoT above flags (Pitfall 10 in PITFALLS.md).
**How to avoid:** `save()` / mutate helper **must** call `require_enabled("operator_config_enabled")`; tests with default flags.
**Warning signs:** Store tests that never construct `RuntimeFeatureFlags`.

### Pitfall 4: Breaking admin read-only contract early
**What goes wrong:** Phase 73 adds `handle_admin_put` and fails `test_read_only.py`.
**Why it happens:** Misreading CFG-02 “endpoints” as requiring HTTP now.
**How to avoid:** Package-level mutate path only; leave `ROUTE_PREFIXES` unchanged until Phase 74.
**Warning signs:** Diffs under `services/admin-console-api/` beyond maybe a comment/README pointer.

### Pitfall 5: Missing gate coverage for new package
**What goes wrong:** `test_gate_coverage.py` fails because `packages/operator-config/src` is uncovered.
**Why it happens:** New top-level package without `run_v2_gates` entry.
**How to avoid:** Add unittest discover gate + compileall path in the same plan wave as the package.
**Warning signs:** CI red on gate-coverage only.

### Pitfall 6: Auto-closing carried human gates
**What goes wrong:** Config foundation smoke claims Phase 5 / Phase 8 / QQ live acceptance.
**Why it happens:** Over-eager milestone docs.
**How to avoid:** No live-acceptance claims in Phase 73 artifacts; preserve `not_live_acceptance` honesty for later DOC-02.
**Warning signs:** STATE.md human-gate rows flipped without human evidence.

## Code Examples

### Atomic JSON save (recommended)

```python
# Source: standard atomic replace pattern (stdlib); no in-repo OperatorConfigStore yet
# [ASSUMED] exact helper API names — planner may adjust
import json
import os
from pathlib import Path

def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)  # atomic on same filesystem
```

### Flag-gated mutate

```python
# Source: packages/platform-runtime/src/platform_runtime/feature_flags.py
from platform_runtime.feature_flags import RuntimeFeatureFlags, RuntimeFeatureDisabledError

def require_operator_config_writable(flags: RuntimeFeatureFlags) -> None:
    flags.require_enabled("operator_config_enabled")
```

### Secret-ref shape (policy lift)

```python
# Source: services/qqbot-service/src/qqbot_service/secrets.py
# Accept env:NAME | secret://… | bare ENV_NAME; reject other strings fail-closed
# without echoing the rejected value.
```

### Hermes ban-list (illustrative)

```python
# [ASSUMED] exact patterns — verify in tests
FORBIDDEN_PATH_SUBSTRINGS = (
    "/.hermes",
    "~/.hermes",
    "\\.hermes",
)
FORBIDDEN_FIELD_NAMES = frozenset({
    "hermes_home",
    "hermes_profile_path",
    "hermes_config_path",
    "profile_filesystem_path",
})
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Env-only channel/provider config (`from_env`) | InkStatute operator-config store + env fallback (later phases) | v1.10 | Console can persist refs-only docs |
| Admin Console API read-only | Separate `/config/*` mutate surface (Phase 74) behind new flag | v1.10 | Preserves sessions/tasks read-only |
| Hermes as informal ops config | Hermes agent-backend only; InkStatute owns ops config | Project rule | CFG-03 enforceable in schema |

**Deprecated/outdated:**
- Treating Hermes `~/.hermes` as InkStatute channel/provider SoT — never for this product.
- Storing raw API keys in config JSON “for MVP” — never (SAFE-02).

## File Touch Points (Planner)

| Path | Action | Phase 73? |
|------|--------|-----------|
| `packages/operator-config/**` | **CREATE** package + tests | Yes |
| `packages/platform-runtime/src/platform_runtime/feature_flags.py` | **ADD** `operator_config_enabled: bool = False` | Yes |
| `packages/platform-runtime/tests/test_feature_flags.py` | Covered by introspection; optional explicit assert | Yes (light) |
| `scripts/run_v2_gates.py` | **ADD** gate + compileall entry | Yes |
| `.gitignore` / package README | Ensure runtime config path not committed | Yes |
| `.env.example` | Optional stub for `INKSTATUTE_OPERATOR_CONFIG_PATH` + flag note | Optional |
| `services/admin-console-api/**` | No mutate handlers | **No** (Phase 74) |
| `packages/rbac/src/rbac/matrix.py` | `/config` prefixes | **No** (Phase 74) |
| `services/qqbot-service` / `wecom-service` loaders | Apply docs | **No** (Phase 75) |
| Built-in model catalog JSON content | Full vendor lists | **No** (Phase 76; Phase 73 may include empty/stub `CatalogSelectionDoc` schema only) |
| Vision router runtime | | **No** (Phase 77) |

## Recommended Approach (Prescriptive)

1. **Create `packages/operator-config/`** with `dependencies = []`, package name `inkstatute-operator-config`, import root `inkstatute_operator_config`.
2. **Define frozen dataclass documents** covering CFG-01 surface:
   - Root `OperatorConfigDocument` (version/etag optional; keep simple — `schema_version: int = 1`)
   - `channels`: qqbot + wecom docs (`enabled` default False + `*_ref` fields aligned with existing channel configs)
   - `providers`: list/map of provider docs (`api_base_url`, `api_key_ref`, `kind`, `enabled`)
   - `catalog`: selection doc (`provider_id`, `model_id` — not full vendor catalog content)
   - `vision`: policy doc (`routing_mode`, `main_model_id`, `vision_model_id` — schema only)
3. **Implement `validate_document`** + `normalize_secret_ref` (shape only) + Hermes ban-list.
4. **Implement `OperatorConfigStore`** load/save with atomic `os.replace`; path from constructor / `INKSTATUTE_OPERATOR_CONFIG_PATH`.
5. **Gate all writes** with `feature_flags.require_enabled("operator_config_enabled")`.
6. **Add flag** to `RuntimeFeatureFlags` default False (introspection test auto-covers).
7. **Register V2 gate** for the new package.
8. **Do not** add admin HTTP PUT, RBAC `/config`, host wiring, or vision runtime.

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Scope bleed into Phase 74–78 | High | Hard file allowlist in plans; keep admin read-only tests green |
| Secret echo in validation errors | High | Copy qqbot `InvalidSecretRefError` no-echo rule |
| Incomplete Hermes ban-list | Medium | Test matrix of path variants + forbidden field names |
| Store path committed to git | Medium | Document gitignored path; add ignore pattern if default under repo |
| Flag name drift (`config_enabled` vs `operator_config_enabled`) | Low | Lock name to REQUIREMENTS: `operator_config_enabled` |

## Open Questions (RESOLVED)

1. **Should Phase 73 include a minimal stub catalog JSON file?**
   - What we know: Full built-in vendor catalog is Phase 76 (PROV-*).
   - What's unclear: Whether `CatalogSelectionDoc` needs a read-only empty catalog helper now.
   - Recommendation: Schema + empty/default selection only; defer catalog data file to Phase 76.
   - **RESOLVED:** Catalog schema-only stub (`CatalogSelectionDoc` with provider_id/model_id); no vendor catalog JSON file in Phase 73 (Plans 73-01 / 73-02). Full catalog content deferred to Phase 76.

2. **Generalize `resolve_secret_ref` into platform-runtime / channel-core now?**
   - What we know: QQ host owns a QQ-specific `REF_TO_VALUE_ENV` map.
   - What's unclear: Shared resolver vs shape-only validator in operator-config.
   - Recommendation: Phase 73 = **shape validation only** in operator-config. Lift/shared resolve is optional later when hosts apply docs (Phase 75+). Avoid qqbot-service import from operator-config.
   - **RESOLVED:** Shape-only secret refs in `inkstatute_operator_config.secrets` (normalize/validate; no resolve, no qqbot-service hard dep). Host resolve deferred to Phase 75+ (Plans 73-01 / 73-02).

3. **Add `vision_routing_enabled` flag in Phase 73?**
   - What we know: SUMMARY lists it as optional; CFG-02 only names `operator_config_enabled`.
   - Recommendation: **Defer** `vision_routing_enabled` to Phase 77 unless planner wants both flags front-loaded. Prefer one flag for CFG-02 clarity.
   - **RESOLVED:** Defer `vision_routing_enabled` to Phase 77. Phase 73 adds only `operator_config_enabled: bool = False` (Plan 73-03). Vision policy remains a schema stub (`VisionPolicyDoc`) without a runtime flag.

4. **ETag / optimistic concurrency on store?**
   - What we know: ARCHITECTURE mentions version/etag; CFG-F02 audit is deferred.
   - Recommendation: Optional `schema_version` integer; skip etag/audit until CFG-F02.
   - **RESOLVED:** Skip etag/optimistic concurrency. Store uses `schema_version: int = 1` only; etag/audit deferred to CFG-F02 (Plans 73-01 schemas / 73-03 store).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | Package runtime | ✓ | 3.14.6 (local) | — |
| `unittest` | Tests | ✓ | stdlib | — |
| `pytest` | Optional runner | ✓ | present | Prefer `python -m unittest` to match gates |
| setuptools | Editable install | ✓ | 83.0.0 | — |
| New PyPI packages | — | N/A | — | None required |
| Postgres / Redis / Docker | Config store | N/A | — | Not used |
| Graphify | Cross-doc intel | ✗ | disabled | Skipped — research used planning docs + codebase |

**Missing dependencies with no fallback:** none

**Missing dependencies with fallback:** graphify disabled — used SUMMARY/ARCHITECTURE/STACK/PITFALLS + live code instead.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `unittest` (stdlib; matches admin-console-api / platform-runtime gates) |
| Config file | none — discover via `python -m unittest discover -s packages/operator-config/tests` |
| Quick run command | `PYTHONPATH=packages/operator-config/src:packages/platform-runtime/src python -m unittest discover -s packages/operator-config/tests -q` |
| Full suite command | Same discover + `packages/platform-runtime/tests/test_feature_flags.py` + gate-coverage |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CFG-01 | Persist channel/provider/catalog/vision docs; refs only | unit | `… test_store.py test_secret_refs.py` | ❌ Wave 0 |
| CFG-01 | Planted raw secret rejected; not stored | unit | `… test_secret_refs.py` | ❌ Wave 0 |
| CFG-02 | `operator_config_enabled` defaults False | unit | `… test_feature_flags.py` (introspection) + `test_flag_gate.py` | ⚠️ flag field ❌; introspection ✅ |
| CFG-02 | `save()` refuses when flag OFF | unit | `… test_flag_gate.py` | ❌ Wave 0 |
| CFG-02 | `save()` succeeds when flag ON + valid doc | unit | `… test_flag_gate.py` / `test_store.py` | ❌ Wave 0 |
| CFG-03 | Reject `~/.hermes` / profile filesystem authority fields | unit | `… test_hermes_banlist.py` | ❌ Wave 0 |
| meta | New package covered by V2 gate | meta | `python -m unittest packages.contract-test-suite.tests.test_gate_coverage` | ✅ harness; ❌ entry |

### Sampling Rate

- **Per task commit:** operator-config unittest discover (quick)
- **Per wave merge:** operator-config + platform-runtime feature flag tests + gate-coverage
- **Phase gate:** Full above green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `packages/operator-config/` package skeleton + `pyproject.toml` (`dependencies = []`)
- [ ] `packages/operator-config/tests/test_schemas.py` — CFG-01 document shapes
- [ ] `packages/operator-config/tests/test_secret_refs.py` — planted secret rejection
- [ ] `packages/operator-config/tests/test_hermes_banlist.py` — CFG-03
- [ ] `packages/operator-config/tests/test_store.py` — atomic persist round-trip
- [ ] `packages/operator-config/tests/test_flag_gate.py` — CFG-02 mutate refuse
- [ ] `scripts/run_v2_gates.py` entry for operator-config
- [ ] `RuntimeFeatureFlags.operator_config_enabled` field

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (Phase 73) | Deferred to Phase 74 admin auth reuse |
| V3 Session Management | no | — |
| V4 Access Control | partial | Flag gate on mutate; RBAC in Phase 74 |
| V5 Input Validation | yes | Dataclass validators; refs-only; Hermes ban-list |
| V6 Cryptography | no | No new crypto; do not store secret material |

### Known Threat Patterns for operator-config

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Raw secret persistence | Information Disclosure | Refs-only schema + planted-secret tests |
| Hermes filesystem as SoT | Tampering / Elevation | Ban-list validators; no Path.home()/.hermes writers |
| Flag-off mutation | Elevation of Privilege | `require_enabled("operator_config_enabled")` on every save |
| Secret echo in errors | Information Disclosure | Fail-closed errors without rejected value (qqbot pattern) |
| Config file committed to git | Information Disclosure | Path outside repo / gitignore; never commit runtime JSON |

## Project Constraints (from .cursor/rules/)

No `.cursor/rules/` directory present in this workspace. Enforce instead from `AGENTS.md` + planning locks:

- No new service/DB/queue unless plan requires — **file store only**
- Secrets as refs; no raw legal/secret payloads in stores
- Do not rebuild Hermes core; do not use `~/.hermes` as config authority
- Keep changes scoped to active phase
- Add tests with behavior changes (schemas, validators, dedupe/gates)
- Carried human gates must not be auto-closed

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Exact module/API names (`OperatorConfigStore`, `require_operator_config_writable`, document class names) are planner-flexible | Code Examples / Structure | Low — rename without behavior change |
| A2 | Hermes ban-list substring/field set is illustrative; final list refined in plan tests | Code Examples | Medium — incomplete ban-list could miss a path variant |
| A3 | Phase 73 should not add `vision_routing_enabled` yet | Open Questions (RESOLVED) | Low — can add in Phase 77 without breaking CFG-02 |
| A4 | Atomic `os.replace` of `.tmp` sibling is sufficient (same filesystem) | Code Examples | Low — document if operators place store on exotic mounts |

**If this table is empty:** N/A — assumptions listed above need planner awareness, not user product decisions (discuss was skipped; locks already cover product constraints).

## Sources

### Primary (HIGH confidence)
- In-repo: `.planning/phases/73-operator-config-foundation/73-CONTEXT.md`, `.planning/REQUIREMENTS.md` (CFG-01..03), `.planning/ROADMAP.md` Phase 73, `.planning/STATE.md`, `.planning/PROJECT.md`
- In-repo: `.planning/research/SUMMARY.md`, `ARCHITECTURE.md`, `STACK.md`, `PITFALLS.md`, `FEATURES.md` (2026-07-10)
- In-repo: `packages/platform-runtime/src/platform_runtime/feature_flags.py` + `tests/test_feature_flags.py`
- In-repo: `services/qqbot-service/src/qqbot_service/secrets.py` + `tests/test_secret_refs.py`
- In-repo: `packages/channels/{qqbot,wecom}/.../config.py`, `packages/backends/provider_model/.../config.py`
- In-repo: `services/admin-console-api` (`api.py`, `routes.py`, `tests/test_read_only.py`, `tests/test_feature_flag.py`)
- In-repo: `packages/rbac/src/rbac/matrix.py`, `packages/contract-test-suite/tests/test_gate_coverage.py`, `scripts/run_v2_gates.py`
- In-repo: `AGENTS.md` (no new DB/queue; Hermes boundary; secrets)

### Secondary (MEDIUM confidence)
- `.planning/research/*` recommendations for package split and `INKSTATUTE_OPERATOR_CONFIG_PATH` naming

### Tertiary (LOW confidence)
- Exact Hermes ban-list enumeration completeness — validate via test matrix in execution
- Whether optional `.env.example` stub lands in Phase 73 vs 78 docs wave

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — empty-deps + flag + file store verified in-repo; no new registry deps
- Architecture: HIGH — aligns with prior research + live admin/channel/secret patterns; Phase 73/74 boundary explicit
- Pitfalls: HIGH — mapped from PITFALLS.md + concrete test_read_only / gate-coverage failure modes

**Research date:** 2026-07-10
**Valid until:** 2026-08-09 (30 days — stable in-repo patterns)
