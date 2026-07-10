# Phase 73: Operator Config Foundation - Pattern Map

**Mapped:** 2026-07-10
**Files analyzed:** 11
**Analogs found:** 11 / 11

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `packages/operator-config/pyproject.toml` | config | n/a | `packages/solution-loader/pyproject.toml` | exact |
| `packages/operator-config/src/inkstatute_operator_config/__init__.py` | utility | n/a | `packages/solution-loader/src/inkstatute_solution_loader/__init__.py` | exact |
| `packages/operator-config/src/inkstatute_operator_config/schemas.py` | model | transform | `packages/channels/qqbot/src/inkstatute_channels_qqbot/config.py` | exact |
| `packages/operator-config/src/inkstatute_operator_config/validate.py` | utility | transform | `packages/solution-loader/src/inkstatute_solution_loader/manifest_validator.py` | exact |
| `packages/operator-config/src/inkstatute_operator_config/secrets.py` | utility | transform | `services/qqbot-service/src/qqbot_service/secrets.py` | exact |
| `packages/operator-config/src/inkstatute_operator_config/store.py` | service | file-I/O | `services/hermes-contract-layer/src/hermes_contract_layer/writer.py` | role-match |
| `packages/platform-runtime/src/platform_runtime/feature_flags.py` | model | request-response | (self — extend in place) | exact |
| `packages/operator-config/tests/test_schemas_refs.py` | test | transform | `services/qqbot-service/tests/test_secret_refs.py` | exact |
| `packages/operator-config/tests/test_validate_hermes_ban.py` | test | transform | `packages/contract-test-suite/tests/test_boundary_allowlist.py` | exact |
| `packages/operator-config/tests/test_store_flag_gate.py` | test | file-I/O | `packages/skill-registry/tests/test_write_api.py` | exact |
| `packages/platform-runtime/tests/test_feature_flags.py` | test | request-response | (self — extend M3-style block) | exact |

**Package home:** `packages/operator-config/` (top-level under `packages/`, sibling of `solution-loader`, `skill-registry`, `mcp-registry`). Import package name: `inkstatute_operator_config`. Do **not** put schemas/store inside `services/admin-console-api` or a new HTTP service.

**Out of Phase 73 (analogs noted for planner continuity only):**
- Admin `/config/*` HTTP handlers → Phase 74 (`skill-registry/write_api.py` + `admin-console-api/api.py`)
- Host `from_operator_doc` / dual-knob apply → Phase 75 (channel `config.py` + qqbot wiring)
- Built-in catalog JSON → Phase 76

---

## Pattern Assignments

### `packages/operator-config/pyproject.toml` (config)

**Analog:** `packages/solution-loader/pyproject.toml`

**Package layout pattern** (full file):
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "inkstatute-operator-config"
version = "0.1.0"
description = "InkStatute-owned refs-only operator config schemas, validators, and atomic store."
requires-python = ">=3.11"
dependencies = []

[tool.setuptools.packages.find]
where = ["src"]

[tool.inkstatute]
subsystem = "operator-config"
default_off_flag = "operator_config_enabled"
```

**Also mirror:** `packages/skill-registry/pyproject.toml` (`dependencies = []`, `src/` layout, `tool.inkstatute.default_off_flag`).

---

### `packages/operator-config/src/inkstatute_operator_config/__init__.py` (utility)

**Analog:** `packages/solution-loader/src/inkstatute_solution_loader/__init__.py` (lines 1–41)

**Exports pattern:**
```python
"""inkstatute-operator-config: refs-only operator config authority."""

from .schemas import ChannelDoc, ProviderDoc, ModelCatalogDoc, VisionRoutingDoc, OperatorConfigDocument
from .store import OperatorConfigStore, OperatorConfigStoreError
from .validate import OperatorConfigValidator, ValidationIssue

__all__ = [
    "ChannelDoc",
    "ProviderDoc",
    "ModelCatalogDoc",
    "VisionRoutingDoc",
    "OperatorConfigDocument",
    "OperatorConfigStore",
    "OperatorConfigStoreError",
    "OperatorConfigValidator",
    "ValidationIssue",
]
```

Keep the public surface small; defer loader/catalog re-exports until Phases 75–76.

---

### `packages/operator-config/src/inkstatute_operator_config/schemas.py` (model, transform)

**Analog:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/config.py` (lines 11–36)

**Imports + frozen dataclass pattern:**
```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class QQBotChannelConfig:
    """... carries only references to external runtime secrets (no raw secrets)."""

    channel_id: str = "qqbot"
    enabled: bool = False
    app_id_ref: str | None = None
    app_secret_ref: str | None = None
    token_secret_ref: str | None = None
    bot_secret_ref: str | None = None
    metadata: JsonObject = field(default_factory=dict)
```

**Also copy field naming from:**
- `packages/channels/wecom/.../config.py` — `token_secret_ref`, `encoding_aes_key_secret_ref`, `corp_id_ref`
- `packages/backends/provider_model/.../config.py` — `api_key_ref`, `api_base_url`, `model_name` (never raw `api_key`)

**Core schema rules for Phase 73 docs:**
- Every credential field ends in `_ref` (or is a non-secret URL/id/bool)
- `enabled: bool = False` on channel/provider docs
- No `hermes_*`, `profile_path`, `gateway_*`, or filesystem path fields that point at `~/.hermes`
- Prefer nested frozen docs aggregated into one `OperatorConfigDocument` root for the JSON store

**Secondary analog:** `packages/model-gateway/.../config.py` — `enabled: bool = False` + `metadata` bag on a frozen config root.

---

### `packages/operator-config/src/inkstatute_operator_config/validate.py` (utility, transform)

**Analog:** `packages/solution-loader/src/inkstatute_solution_loader/manifest_validator.py` (lines 21–120)

**Ban-list + issue-list pattern:**
```python
_RAW_PAYLOAD_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {
        "raw_payload",
        "raw_body",
        "secret",
        "token",
        "password",
        "api_key",
        "private_key",
    }
)

_SECRET_MARKER_RE = re.compile(
    r"(sk-|secret\s*=|password\s*=|bearer\s+[A-Za-z0-9_\-]{16,})",
    re.IGNORECASE,
)

class ManifestValidator:
    def validate(self, manifest: SolutionPackageManifest) -> list[Issue]:
        issues: list[Issue] = []
        # reject forbidden keys / secret markers; return structured issues
        ...
```

**Apply to operator-config:**
1. Reject raw secret field names (`api_key`, `token`, `password`, `bot_secret`, …) — require `*_ref`
2. Scan string values with `_SECRET_MARKER_RE` / planted `sk-…` patterns
3. Reject Hermes authority paths: `~/.hermes`, `.hermes/`, `profiles/lawfirm` as config SoT fields
4. Return structured issues (`path`, `code`, `message`, `severity`) — do not echo rejected secret values in messages

**Secondary analog (Hermes path ban tests):** `packages/contract-test-suite/tests/test_boundary_allowlist.py` lines 91–98 (`private_hermes_path` assertion) and lines 121–128 (`secret_value` / `sk-` ban).

**Tertiary analog (privacy key walk):** `packages/platform-runtime/src/platform_runtime/store.py` `_reject_forbidden_payload_storage` + `privacy_keys.ALL_FORBIDDEN_KEYS` — walk nested dicts and raise on forbidden keys.

---

### `packages/operator-config/src/inkstatute_operator_config/secrets.py` (utility, transform)

**Analog:** `services/qqbot-service/src/qqbot_service/secrets.py` (lines 35–67)

**Normalize-ref pattern (fail-closed, no secret echo):**
```python
class InvalidSecretRefError(ValueError):
    """Config *_REF value is not an allowed reference shape (message has no secret)."""


def normalize_config_secret_ref(raw: str | None, *, field: str) -> str | None:
    if raw is None:
        return None
    ref = raw.strip()
    if not ref:
        return None
    if ref.startswith("env:"):
        name = ref[4:]
        if not name or not _ENV_NAME_RE.fullmatch(name):
            raise InvalidSecretRefError(f"invalid secret reference shape for {field}")
        return f"env:{name}"
    if ref.startswith("secret://"):
        # Phase 73: allow known schemes / generalize beyond qqbot-only map
        ...
    if _ENV_NAME_RE.fullmatch(ref):
        return ref
    raise InvalidSecretRefError(f"invalid secret reference shape for {field}")
```

**Host wiring of normalize into config** — `services/qqbot-service/src/qqbot_service/config.py` lines 28–48:
```python
app_id_ref=normalize_config_secret_ref(
    mapping.get("INKSTATUTE_QQBOT_APP_ID_REF"),
    field="INKSTATUTE_QQBOT_APP_ID_REF",
),
```

**Phase 73 note:** Generalize beyond QQ-only `REF_TO_VALUE_ENV` (accept `env:NAME`, bare env keys, and a broader `secret://…` allowlist or shape check). Keep **resolution** (`resolve_secret_ref`) at process edge in hosts — package may re-export a generalized resolver later; do not read `os.environ` inside the store.

---

### `packages/operator-config/src/inkstatute_operator_config/store.py` (service, file-I/O)

**Analog (file persistence):** `services/hermes-contract-layer/src/hermes_contract_layer/writer.py` (lines 34–61)

**Path + mkdir + JSON clone pattern:**
```python
class ContractEventWriter:
    def __init__(self, path: str | Path, *, start_seq: int = 0, clock: Any | None = None) -> None:
        self.path = Path(path)
        ...

    def append(...) -> ContractLogRecord:
        ...
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(record.to_json_line())
            handle.write("\n")
```

**Atomic JSON write (stdlib — no in-repo atomic JSON store yet):** compose from `tempfile.NamedTemporaryFile` + `os.replace` (same family as `scripts/inkstatute_wecom_live_bridge.py` lines 976–986 for NamedTemporaryFile under a target dir). Recommended shape:
```python
# write tmp beside destination, fsync, then os.replace(tmp, path)
tmp = path.with_suffix(path.suffix + ".tmp")
tmp.write_text(json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
os.replace(tmp, path)
```

**Path env:** `INKSTATUTE_OPERATOR_CONFIG_PATH` (from research STACK.md).

**Mutate gate (CFG-02) inside store or a thin write facade:** copy flag-refuse pattern from skill-registry write API (below) — when `operator_config_enabled` is False, `save`/`put` raises or returns a structured disabled error **before** any disk write. Phase 74 will wire the same flag at HTTP; Phase 73 must prove the store/authority refuses writes when OFF.

**Secondary analog (in-memory registry mutate):** `packages/mcp-registry/.../admin.py` — separate write port from read registry; validate before mutate.

**Do not use:** SQLite (`sqlite_memory.py`) or a new DB — AGENTS.md + STACK.md reject new DB for MVP config.

---

### `packages/platform-runtime/src/platform_runtime/feature_flags.py` (model, modify)

**Analog:** same file — extend `RuntimeFeatureFlags` (lines 12–47)

**Default-OFF + require_enabled pattern:**
```python
@dataclass(frozen=True, slots=True)
class RuntimeFeatureFlags:
    ...
    admin_web_ui_enabled: bool = False
    lawyer_web_chat_enabled: bool = False

    def require_enabled(self, flag_name: str) -> None:
        known_flags = {field.name for field in fields(self)}
        if flag_name not in known_flags:
            raise RuntimeFeatureDisabledError(f"unknown runtime feature flag: {flag_name}")
        if not getattr(self, flag_name):
            raise RuntimeFeatureDisabledError(f"runtime feature flag disabled: {flag_name}")
```

**Phase 73 change:** add `operator_config_enabled: bool = False` (and optionally `vision_routing_enabled: bool = False` only if needed for later phases — prefer add when first used; research allows optional). Do **not** change defaults of existing flags.

**HTTP refuse pattern to mirror in store/tests (and Phase 74 API):** `packages/skill-registry/src/inkstatute_skill_registry/write_api.py` lines 128–142:
```python
try:
    flags.require_enabled("skill_registry_write_enabled")
except RuntimeFeatureDisabledError:
    return 403, {
        "error": {
            "code": "skill_registry_write_disabled",
            "message": "skill_registry_write_enabled flag is False",
        },
    }
```

**Admin GET gate (same family):** `services/admin-console-api/src/admin_console_api/api.py` lines 72–81 (`admin_api_enabled` → 403 `admin_api_disabled`).

---

### `packages/operator-config/tests/test_schemas_refs.py` (test)

**Analog:** `services/qqbot-service/tests/test_secret_refs.py` (lines 12–76)

**Planted-secret ban pattern:**
```python
PLANTED = "planted-raw-secret-value-NEVER-ON-CONFIG"

class TestQQBotHostConfigRefsOnly(unittest.TestCase):
    def test_from_env_ignores_planted_raw_secret_keys(self) -> None:
        ...
        values = set(asdict(cfg).values())
        self.assertNotIn(PLANTED, values)

    def test_from_env_rejects_raw_secret_planted_in_ref_key(self) -> None:
        with self.assertRaises(InvalidSecretRefError) as ctx:
            QQBotHostConfig.from_env({"INKSTATUTE_QQBOT_BOT_SECRET_REF": PLANTED})
        message = str(ctx.exception)
        self.assertNotIn(PLANTED, message)
```

**Apply:** schema/validator rejects docs with raw `api_key`/`token`/`sk-…`; `asdict`/serialized store payload never contains planted secrets; error messages never echo the planted value.

---

### `packages/operator-config/tests/test_validate_hermes_ban.py` (test)

**Analog:** `packages/contract-test-suite/tests/test_boundary_allowlist.py` (lines 91–98, 121–128)

```python
def test_rejects_private_hermes_paths_in_neutral_packages(self) -> None:
    source.write_text('PROFILE_PATH = "~/.hermes/profiles/lawfirm"\n', encoding="utf-8")
    with self.assertRaisesRegex(AssertionError, "private_hermes_path"):
        assert_neutral_boundary_allowlist(root)

def test_rejects_plaintext_secret_patterns(self) -> None:
    secret_like_value = "sk-" + "1234567890abcdefghijklmnop"
    fixture.write_text(json.dumps({"api_key": secret_like_value}), encoding="utf-8")
    with self.assertRaisesRegex(AssertionError, "secret_value"):
        assert_neutral_boundary_allowlist(root)
```

**Apply:** validator rejects documents that set Hermes filesystem/profile paths as config authority; store refuses to persist them.

---

### `packages/operator-config/tests/test_store_flag_gate.py` (test)

**Analog:** `packages/skill-registry/tests/test_write_api.py` (lines 61–76)

```python
class WriteApiFeatureFlagTests(unittest.TestCase):
    def test_flag_disabled_returns_403(self) -> None:
        flags = RuntimeFeatureFlags()  # default: all flags False
        status, body = handle_post(...)
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "skill_registry_write_disabled")
```

**Apply:** with `RuntimeFeatureFlags()` (default), store `save`/`put` refuses write (raises or returns disabled error); with `operator_config_enabled=True`, write succeeds to a temp path. Also assert default `RuntimeFeatureFlags().operator_config_enabled is False`.

**Secondary analog:** `packages/platform-runtime/tests/test_feature_flags.py` — introspection loop over all fields default False; M3-style block for new flag.

**Tertiary analog:** `packages/solution-loader/tests/test_solution_loader_library.py` `TestFeatureFlags` — env loader defaults OFF, truthy/malformed handling (if Phase 73 adds env loader for the flag).

---

### `packages/platform-runtime/tests/test_feature_flags.py` (test, modify)

**Analog:** same file `M3FeatureFlagDefaultTests` (lines 57–96)

Add `operator_config_enabled` to a Phase-73 / v1.10 flag tuple and assert default False + `require_enabled` raise/pass — same structure as M3_FLAGS tests. Existing `test_all_flags_default_to_false_via_introspection` already covers new fields if they default False; still add an explicit named assertion for CFG-02 clarity.

---

## Shared Patterns

### Frozen refs-only dataclasses
**Source:** `packages/channels/qqbot/.../config.py`, `packages/channels/wecom/.../config.py`, `packages/backends/provider_model/.../config.py`
**Apply to:** all operator-config schema docs
```python
@dataclass(frozen=True, slots=True)
class ...:
    enabled: bool = False
    *_ref: str | None = None  # NEVER raw secret values
```

### Default-OFF feature flags + require_enabled
**Source:** `packages/platform-runtime/src/platform_runtime/feature_flags.py`
**Apply to:** `operator_config_enabled`; store mutate gate; later admin `/config/*`
```python
flags.require_enabled("operator_config_enabled")
# → RuntimeFeatureDisabledError when False
```

### Secret-ref normalize (fail-closed, no echo)
**Source:** `services/qqbot-service/src/qqbot_service/secrets.py`
**Apply to:** every credential field on Channel/Provider docs before persist
```python
normalize_config_secret_ref(raw, field="api_key_ref")
# InvalidSecretRefError messages must not contain the rejected value
```

### Ban-list validators (secrets + Hermes paths)
**Source:** `packages/solution-loader/.../manifest_validator.py` + `packages/contract-test-suite/tests/test_boundary_allowlist.py`
**Apply to:** `validate.py` before store write
- Forbidden keys: `api_key`, `token`, `password`, `raw_payload`, …
- Forbidden markers: `sk-…`, bearer blobs
- Forbidden authority: `~/.hermes`, `.hermes/`, Hermes profile filesystem paths as SoT

### Empty-deps package scaffold
**Source:** `packages/solution-loader/pyproject.toml`, `packages/skill-registry/pyproject.toml`
**Apply to:** `packages/operator-config/`
- `dependencies = []`, `requires-python = ">=3.11"`, `src/inkstatute_*` layout, unittest

### Flag-gated mutate refuse (write surface)
**Source:** `packages/skill-registry/.../write_api.py` `_gate`
**Apply to:** store write methods in Phase 73; HTTP in Phase 74
- Error code style: `{flag}_disabled` / `operator_config_disabled`
- 403 semantics at HTTP; package-level raise/result for store

### Health / API allowlist (forward-looking for Phase 74)
**Source:** `services/admin-console-api/src/admin_console_api/health.py`
**Apply to:** future GET `/config/*` responses — expose `secrets_configured` booleans only; never `secret_refs_configured` maps, ref names, or values. Phase 73 store should already persist refs only so GET cannot leak values.

### RBAC matrix (forward-looking for Phase 74)
**Source:** `packages/rbac/src/rbac/matrix.py` + `services/admin-console-api/src/admin_console_api/routes.py`
**Apply to:** Phase 74 `/config` prefixes for `ADMIN` + `OPERATOR`; CI scan requires `ROUTE_PREFIXES` ↔ `PERMISSIONS_MATRIX` parity. Not required to land matrix entries in Phase 73 unless a stub route is added (prefer not).

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| *(none for Phase 73 core)* | — | — | Atomic JSON replace has no dedicated package helper yet — compose from stdlib `NamedTemporaryFile`/`os.replace` using hermes writer + live_bridge tempfile patterns |

---

## Metadata

**Analog search scope:** `packages/{solution-loader,skill-registry,mcp-registry,platform-runtime,channels,backends/provider_model,model-gateway,rbac,contract-test-suite}`, `services/{qqbot-service,admin-console-api,hermes-contract-layer}`, `.planning/research/{SUMMARY,ARCHITECTURE,STACK}.md`
**Files scanned:** ~45 primary sources
**Pattern extraction date:** 2026-07-10

### Key planner takeaways
1. **New package lives at** `packages/operator-config/` with `inkstatute_operator_config` — mirror solution-loader/skill-registry empty-deps scaffold.
2. **Schemas** copy channel/provider frozen `*_ref` dataclasses; **validators** copy solution-loader ban-lists + boundary-allowlist Hermes/secret bans.
3. **Store** is atomic JSON at `INKSTATUTE_OPERATOR_CONFIG_PATH`; gate writes with `operator_config_enabled` (skill-registry write_api pattern) before disk I/O.
4. **Flag** is a new field on existing `RuntimeFeatureFlags`, default `False`, tested like M3 flags + planted-secret tests from qqbot SAFE-02.
5. **Do not** add admin HTTP routes, catalog JSON, or host loaders in Phase 73 — those have clear analogs reserved for 74–76.
