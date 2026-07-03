# Phase 37 Research — Skill Registry Read

**Phase:** 37
**Slug:** skill-registry-read
**Requirements:** SKILL-01, SKILL-02
**Depends on:** Phase 36 (COMPLETE — `skill_registry_enabled` feature flag added, defaults to `False`)
**Created:** 2026-07-04

---

## 1. Summary

- **`NeutralSkillDescriptor` already exists** in the platform contract at `packages/platform-contract/src/platform_contract/events.py:104-112`. It is a frozen, slotted dataclass with fields `skill_id`, `name`, `description`, `input_schema_ref`, `output_schema_ref`, `required_tool_refs`, and `metadata`. No schema changes are required — this satisfies the SAFETY-06 contract freeze constraint.

- **Skill metadata source is solution-pack manifests, not a live Hermes API.** The lawfirm and demo_non_legal solution packs declare skills in `solutions/lawfirm/manifest.json:12-41` and `solutions/demo_non_legal/manifest.json:13-42`. Each skill entry has `name`, `description`, `intent`, `required_tools`, and `risk_level`. The PRD §3.2 (`docs/requirements/V2-PRD.md:118`) confirms: "V2 不建独立 Skill Registry，只通过 Hermes router 日志和 skill index 读取 skill 元数据." The skill-registry reads manifest metadata and normalizes it into `NeutralSkillDescriptor` records — it does NOT call a Hermes API or read runtime profile files (those are not committed to the repo).

- **The manifest skill shape differs from `NeutralSkillDescriptor`.** Manifest skills use `name` (not `skill_id`), `intent` (maps to `metadata.intent`), `required_tools` (maps to `required_tool_refs`), and `risk_level` (maps to `metadata.risk_level`). A mapper function is needed to convert manifest skill dicts → `NeutralSkillDescriptor` records. The `skill_id` should be derived as `{solution_id}/{skill_name}` to ensure uniqueness across solution packs.

- **Cloudflare agent-skills-discovery convention** (RFC v0.2.0) requires an index at `/.well-known/agent-skills/index.json` with a top-level `$schema` field and a `skills` array. Each skill entry requires: `name` (1-64 chars, lowercase alphanumeric + hyphens), `type` (`"skill-md"` or `"archive"`), `description` (max 1024 chars), `url` (path to skill artifact), and `digest` (`sha256:<hex>` of the artifact bytes). The `$schema` URI is `https://schemas.agentskills.io/discovery/0.2.0/schema.json`.

- **The Skill Registry should be a new package** at `packages/skill-registry/` per the architecture research (`.planning/research/ARCHITECTURE.md:112`). It follows the same pattern as `packages/solution-loader/` — a library package with `pyproject.toml`, `src/`, and `tests/`. Dependencies: `platform-contract` only (for `NeutralSkillDescriptor`).

- **Feature flag `skill_registry_enabled` already exists** at `packages/platform-runtime/src/platform_runtime/feature_flags.py:21` with default `False`. The `require_enabled()` method (line 27-32) uses dataclass introspection and already recognizes this flag. No changes to feature_flags.py are needed.

- **API pattern follows `conversation-read-view`** — a pure `handle_get(path, query, ...)` function that returns `(status_code, body)` tuples (see `services/conversation-read-view/src/conversation_read_view/api.py:11-58`). No FastAPI/aiohttp dependency; the codebase uses pure-Python route handlers tested via `unittest`. The Skill Registry API should follow the same pattern.

- **Read-only enforcement is structural.** The `SkillRegistry` Protocol exposes only `list_skills()`, `get_skill()`, and `search()` — no write/update/delete methods. A test must assert that no mutating methods exist on the registry class.

- **V2 gate integration requires a new gate** in `scripts/run_v2_gates.py` for the `skill-registry` package, plus updating the `compileall` gate to include the new `packages/skill-registry/src` directory. The GATE-01 meta-test (Phase 44) will later assert every `packages/*/src` is covered.

- **Privacy is low-risk.** Skill metadata (name, description, intent, required tools, risk level) contains no secrets, customer documents, or raw legal payloads. The manifest `secret_templates` field lists only secret *names*, not values. No `scrub_contract_payload` is needed for skill descriptors, but the registry must not expose `secret_templates` or `secret_ref` values from MCP descriptors.

---

## 2. Hermes Skill Metadata Source

### 2.1 Solution-Pack Manifests (Primary Source)

The skill metadata source for the Skill Registry is the solution-pack manifest files. There are two solution packs in the repo:

**Lawfirm manifest:** `solutions/lawfirm/manifest.json`
```json
{
  "solution_id": "lawfirm",
  "version": "1.0.0",
  "skills": [
    {
      "name": "case_qa",
      "description": "Answer factual legal questions with citations.",
      "intent": "factual_qa",
      "required_tools": ["law_search"],
      "risk_level": "medium"
    },
    {
      "name": "contract_draft",
      "description": "Draft contract clauses with citation hooks.",
      "intent": "drafting",
      "required_tools": ["docx_writer"],
      "risk_level": "high"
    },
    {
      "name": "litigation_summary",
      "description": "Summarize case materials for litigation strategy.",
      "intent": "analysis",
      "required_tools": ["law_search"],
      "risk_level": "high"
    },
    {
      "name": "compliance_review",
      "description": "Review contract or policy for compliance issues.",
      "intent": "review",
      "required_tools": ["law_search"],
      "risk_level": "medium"
    }
  ],
  ...
}
```

**Demo non-legal manifest:** `solutions/demo_non_legal/manifest.json`
```json
{
  "solution_id": "demo_non_legal",
  "skills": [
    {"name": "lesson_qa", "description": "...", "intent": "factual_qa", "required_tools": ["curriculum_db"], "risk_level": "low"},
    {"name": "homework_review", "description": "...", "intent": "review", "required_tools": [], "risk_level": "low"},
    {"name": "syllabus_lookup", "description": "...", "intent": "lookup", "required_tools": ["curriculum_db"], "risk_level": "low"},
    {"name": "quiz_generator", "description": "...", "intent": "generation", "required_tools": [], "risk_level": "medium"}
  ],
  ...
}
```

### 2.2 Manifest Skill Shape vs. NeutralSkillDescriptor

The manifest `skills[]` array uses a solution-pack-specific shape that differs from `NeutralSkillDescriptor`:

| Manifest field | NeutralSkillDescriptor field | Mapping |
|----------------|------------------------------|---------|
| `name` | `skill_id` | Derive as `{solution_id}/{name}` for uniqueness |
| `name` | `name` | Direct copy |
| `description` | `description` | Direct copy |
| `required_tools` | `required_tool_refs` | Direct copy (list of tool name strings) |
| `intent` | `metadata.intent` | Stored in metadata bag |
| `risk_level` | `metadata.risk_level` | Stored in metadata bag |
| (none) | `input_schema_ref` | `None` (not declared in manifest) |
| (none) | `output_schema_ref` | `None` (not declared in manifest) |

### 2.3 How Manifests Are Currently Loaded

The existing `DefaultSolutionLoader` (`packages/solution-loader/src/inkstatute_solution_loader/loader.py:44-51`) wraps a `SolutionPackageManifest` in a `Solution` object. The manifest is constructed from JSON in tests via a helper like `_manifest_from_json()` (`packages/contract-test-suite/tests/test_phase13_solution_evidence.py:48-59`):

```python
def _manifest_from_json(path: Path, fallback_solution_id: str) -> SolutionPackageManifest:
    data = json.loads(path.read_text(encoding="utf-8"))
    return SolutionPackageManifest(
        solution_id=data.get("solution_id", fallback_solution_id),
        version=data.get("version", "1.0.0"),
        manifest_ref=data.get("manifest_ref"),
        metadata={
            k: v
            for k, v in data.items()
            if k not in {"solution_id", "version", "manifest_ref"}
        },
    )
```

Note: The current manifest JSON stores `skills` inside `metadata` (not as a top-level `SolutionPackageManifest.skills` field). The `SolutionPackageManifest` dataclass (`events.py:410-423`) has a `skills: list[NeutralSkillDescriptor]` field, but the current manifest loading code puts everything except `solution_id`/`version`/`manifest_ref` into `metadata`. The Skill Registry should read the `skills` array from `manifest.metadata.get("skills", [])` — this is the same pattern used by `LawfirmHermesMaterializer._render_skill_template()` at `solutions/lawfirm/src/inkstatute_solutions_lawfirm/hermes_materializer.py:189-190`:

```python
skills = manifest.metadata.get("skills", []) if manifest.metadata else []
```

### 2.4 PRD Context

PRD §3.2 (`docs/requirements/V2-PRD.md:118`):
> 101 个顶层目录、约 312 个 skill。来源：`ai-for-china-legal`（symlink）、`legal-skills`（copy+同步脚本）、方法论 skill、平台 skill。V2 不建独立 Skill Registry，只通过 Hermes router 日志和 skill index 读取 skill 元数据，归一化进 `ExecutionTrace.active_skill_name`。

PRD §4.3 (`docs/requirements/V2-PRD.md:720`):
> 4.3 Skill Registry | 降级为读取 Hermes skill index（3.2）

The Skill Registry reads skill metadata from solution-pack manifests (the committed, sanitized representation of Hermes skill index). It does NOT read from a live Hermes profile directory (those are runtime artifacts, not committed). The architecture research confirms this (`.planning/research/ARCHITECTURE.md:61`):
> The skill-registry reads Hermes skill index/metadata files (descriptions, input/output schemas, required tools) and normalizes them into `NeutralSkillDescriptor` records. It does NOT call an API — it reads files from the profile bundle.

### 2.5 Hermes Mapper Skill References

The Hermes contract-layer mapper (`services/hermes-contract-layer/src/hermes_contract_layer/mapper.py`) extracts skill metadata from hook context:
- Line 53: `primary_skill = _string_or_none(context.get("active_skill_name") or context.get("skill_name"))`
- Line 95: `"primary_skill": primary_skill`
- Line 124: `"active_skill_name": primary_skill`

This is the runtime skill *execution* path. The Skill Registry is a separate, static metadata path — it does not integrate with the mapper in Phase 37. Phase 38 (Router Service) will use the Skill Registry for skill validation during routing.

---

## 3. NeutralSkillDescriptor Schema

### 3.1 Existing Definition (No Changes Needed)

**File:** `packages/platform-contract/src/platform_contract/events.py:104-112`

```python
@dataclass(frozen=True, slots=True)
class NeutralSkillDescriptor:
    skill_id: str
    name: str
    description: str | None = None
    input_schema_ref: str | None = None
    output_schema_ref: str | None = None
    required_tool_refs: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)
```

**Exported from:** `packages/platform-contract/src/platform_contract/__init__.py:55` and `events.__all__` at line 575.

**JSON Schema definition:** `packages/platform-contract/src/platform_contract/schemas/common.schema.json:236-262`:
```json
"neutral_skill_descriptor": {
  "type": "object",
  "additionalProperties": false,
  "required": ["skill_id", "name"],
  "properties": {
    "skill_id": {"type": "string"},
    "name": {"type": "string"},
    "description": {"type": "string"},
    "input_schema_ref": {"type": "string"},
    "output_schema_ref": {"type": "string"},
    "required_tool_refs": {"type": "array", "items": {"type": "string"}},
    "metadata": {"$ref": "#/$defs/metadata"}
  }
}
```

**Used by:** `SolutionPackageManifest.skills: list[NeutralSkillDescriptor]` at `events.py:414`.

**Self-check:** `packages/platform-contract/scripts/self_check.py:342` and `:390` verify `NeutralSkillDescriptor` is a dataclass with fields and has schema parity.

### 3.2 SAFETY-06 Contract Freeze Implication

The contract freeze test (`packages/contract-test-suite/tests/test_contract_freeze.py`) compares SHA-256 hashes of schema files against a v1.5 baseline in `fixtures/contract_freeze_baseline.json`. Since `NeutralSkillDescriptor` and its schema already exist, **no schema files need to be modified** for Phase 37. The Skill Registry is a pure consumer of the existing contract — it imports `NeutralSkillDescriptor` and produces instances. This is critical: modifying `common.schema.json` or `events.py` would break the contract freeze gate.

### 3.3 Fields Available for Search/Filter

The `NeutralSkillDescriptor` fields that support the required search operations:
- **Filter by tag:** Use `metadata.risk_level` or `metadata.intent` as tag-like fields. The manifest skills have `intent` (e.g., "factual_qa", "drafting", "analysis", "review") and `risk_level` (e.g., "low", "medium", "high"). The `search()` operation should accept a `tag` parameter that matches against `metadata` keys.
- **Filter by category:** Use `metadata.intent` as the category. The `search()` operation should accept a `category` parameter matching `metadata.intent`.
- **Filter by name substring:** Match against the `name` field (case-insensitive substring).

---

## 4. Cloudflare agent-skills-discovery Convention

### 4.1 RFC Source

**Repository:** `https://github.com/cloudflare/agent-skills-discovery-rfc`
**Schema version:** v0.2.0
**Schema URI:** `https://schemas.agentskills.io/discovery/0.2.0/schema.json`

### 4.2 Index Format

The index is served at `/.well-known/agent-skills/index.json`:

```json
{
  "$schema": "https://schemas.agentskills.io/discovery/0.2.0/schema.json",
  "skills": [
    {
      "name": "code-review",
      "type": "skill-md",
      "description": "Review code for bugs, security issues, and best practices.",
      "url": "/.well-known/agent-skills/code-review/SKILL.md",
      "digest": "sha256:c4d5e6f7..."
    },
    {
      "name": "wrangler",
      "type": "archive",
      "description": "Deploy and manage Cloudflare Workers projects.",
      "url": "/.well-known/agent-skills/wrangler.tar.gz",
      "digest": "sha256:a1b2c3d4..."
    }
  ]
}
```

### 4.3 Required Fields Per Skill Entry

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Skill identifier. 1-64 chars, lowercase alphanumeric + hyphens only, no leading/trailing/consecutive hyphens. |
| `type` | Yes | Distribution type. MUST be `"skill-md"` (single SKILL.md file) or `"archive"` (bundled archive). |
| `description` | Yes | Brief description of what the skill does. Max 1024 chars. |
| `url` | Yes | URL to the skill artifact. Can be relative, path-absolute, or fully qualified. |
| `digest` | Yes | SHA-256 content digest of the artifact at `url`, formatted as `sha256:<hex>`. |

### 4.4 Adaptation for InkStatute Skill Registry

The InkStatute Skill Registry exposes skill *metadata* (descriptors), not skill *artifacts* (SKILL.md files). For the discovery endpoint, the registry should:

1. **`name`:** Use the `NeutralSkillDescriptor.name` field. Manifest skill names like `case_qa` need to be converted to hyphenated form (`case-qa`) to conform to the naming spec (lowercase alphanumeric + hyphens). Alternatively, if the name already conforms, use as-is.

2. **`type`:** Use `"skill-md"` since the registry represents skill metadata that would correspond to a SKILL.md file. This is the closest match — the registry does not serve archives.

3. **`description`:** Use `NeutralSkillDescriptor.description` (truncated to 1024 chars if needed).

4. **`url`:** Construct as `/.well-known/agent-skills/{name}/SKILL.md` — a path-absolute URL following the convention. The registry does not actually serve the SKILL.md file in Phase 37 (that would be a future enhancement), but the URL follows the convention for discovery purposes. Alternatively, the URL could point to the Skill Registry's own `get_skill` endpoint: `/skills/{skill_id}`.

5. **`digest`:** Compute `sha256:<hex>` over the serialized `NeutralSkillDescriptor` JSON representation. Since there is no physical artifact file, the digest is computed over the canonical JSON of the descriptor. This provides integrity verification for the metadata itself.

### 4.5 Top-Level Fields

The index MUST include:
- `$schema`: `"https://schemas.agentskills.io/discovery/0.2.0/schema.json"`
- `skills`: Array of skill entries

---

## 5. API Design

### 5.1 Package Structure

New package: `packages/skill-registry/`

```
packages/skill-registry/
├── pyproject.toml
├── README.md
├── src/
│   └── inkstatute_skill_registry/
│       ├── __init__.py
│       ├── registry.py          # SkillRegistry class + Protocol
│       ├── mapper.py            # manifest skill dict → NeutralSkillDescriptor
│       ├── api.py               # handle_get() route handler
│       └── discovery.py         # well-known index builder
└── tests/
    ├── test_registry.py
    ├── test_api.py
    └── test_discovery.py
```

### 5.2 pyproject.toml (Following solution-loader pattern)

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "inkstatute-skill-registry"
version = "0.1.0"
description = "Read-only Skill Registry exposing Hermes skill metadata as NeutralSkillDescriptor records."
requires-python = ">=3.11"
dependencies = []

[tool.setuptools.packages.find]
where = ["src"]

[tool.inkstatute]
subsystem = "skill-registry"
default_off_flag = "skill_registry_enabled"
```

### 5.3 SkillRegistry Class

**File:** `packages/skill-registry/src/inkstatute_skill_registry/registry.py`

```python
from __future__ import annotations
from typing import Protocol
from platform_contract import NeutralSkillDescriptor


class SkillRegistryPort(Protocol):
    """Read-only Skill Registry protocol — no write methods."""
    def list_skills(self) -> list[NeutralSkillDescriptor]: ...
    def get_skill(self, skill_id: str) -> NeutralSkillDescriptor | None: ...
    def search(
        self,
        tag: str | None = None,
        category: str | None = None,
        name_substring: str | None = None,
    ) -> list[NeutralSkillDescriptor]: ...


class SkillRegistry:
    """Concrete read-only Skill Registry backed by solution-pack manifests."""

    def __init__(self, skills: list[NeutralSkillDescriptor]) -> None:
        self._skills = list(skills)
        self._by_id = {s.skill_id: s for s in self._skills}

    def list_skills(self) -> list[NeutralSkillDescriptor]:
        return list(self._skills)

    def get_skill(self, skill_id: str) -> NeutralSkillDescriptor | None:
        return self._by_id.get(skill_id)

    def search(
        self,
        tag: str | None = None,
        category: str | None = None,
        name_substring: str | None = None,
    ) -> list[NeutralSkillDescriptor]:
        results = self._skills
        if tag is not None:
            results = [s for s in results if tag in s.metadata.get("tags", []) or s.metadata.get("risk_level") == tag]
        if category is not None:
            results = [s for s in results if s.metadata.get("intent") == category]
        if name_substring is not None:
            needle = name_substring.lower()
            results = [s for s in results if needle in s.name.lower()]
        return list(results)
```

**Read-only enforcement:** The class has no `add_skill`, `update_skill`, `delete_skill`, or any mutating method. The `_skills` list is set at construction time and never modified. A test should assert that `dir(SkillRegistry)` contains no methods starting with `add`, `create`, `update`, `delete`, `remove`, `put`, or `post`.

### 5.4 Manifest-to-Descriptor Mapper

**File:** `packages/skill-registry/src/inkstatute_skill_registry/mapper.py`

```python
from __future__ import annotations
from typing import Any, Mapping
from platform_contract import NeutralSkillDescriptor


def manifest_skill_to_descriptor(
    solution_id: str,
    skill: Mapping[str, Any],
) -> NeutralSkillDescriptor:
    """Convert a manifest skill dict to a NeutralSkillDescriptor."""
    name = str(skill.get("name", ""))
    skill_id = f"{solution_id}/{name}"
    return NeutralSkillDescriptor(
        skill_id=skill_id,
        name=name,
        description=skill.get("description"),
        required_tool_refs=list(skill.get("required_tools", [])),
        metadata={
            "intent": skill.get("intent"),
            "risk_level": skill.get("risk_level"),
            "solution_id": solution_id,
        },
    )


def load_skills_from_manifests(
    manifest_paths: list[Path],
) -> list[NeutralSkillDescriptor]:
    """Load skills from multiple solution-pack manifest JSON files."""
    import json
    skills: list[NeutralSkillDescriptor] = []
    for path in manifest_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        solution_id = data.get("solution_id", path.parent.name)
        for skill in data.get("skills", []):
            skills.append(manifest_skill_to_descriptor(solution_id, skill))
    return skills
```

### 5.5 API Route Handler

**File:** `packages/skill-registry/src/inkstatute_skill_registry/api.py`

Following the `conversation-read-view` pattern (`services/conversation-read-view/src/conversation_read_view/api.py:11-58`):

```python
from __future__ import annotations
from typing import Any, Mapping
from urllib.parse import parse_qs
from .registry import SkillRegistry


def handle_get(
    path: str,
    query: str | Mapping[str, str] | None,
    registry: SkillRegistry,
) -> tuple[int, dict[str, Any]]:
    route_path, route_query = _split_path_query(path, query)

    # SKILL-02: Cloudflare agent-skills-discovery endpoint
    if route_path == "/.well-known/agent-skills/index.json":
        return _discovery_index(registry)

    # SKILL-01: list skills
    if route_path == "/skills":
        skills = registry.list_skills()
        return 200, {
            "items": [_descriptor_to_dict(s) for s in skills],
            "count": len(skills),
            "metadata": {"read_only": True, "source": "solution_pack_manifests"},
        }

    # SKILL-01: get single skill
    if route_path.startswith("/skills/"):
        skill_id = route_path.removeprefix("/skills/")
        skill = registry.get_skill(skill_id)
        if skill is None:
            return 404, _not_found("skill", skill_id)
        return 200, _descriptor_to_dict(skill)

    # SKILL-01: search skills
    if route_path == "/skills/search":
        tag = route_query.get("tag")
        category = route_query.get("category")
        name_substring = route_query.get("name")
        results = registry.search(tag=tag, category=category, name_substring=name_substring)
        return 200, {
            "items": [_descriptor_to_dict(s) for s in results],
            "count": len(results),
            "metadata": {"read_only": True, "filters": {"tag": tag, "category": category, "name": name_substring}},
        }

    return 404, _not_found("route", route_path)
```

### 5.6 Feature Flag Integration

The API handler should check `skill_registry_enabled` before processing. Following the pattern from `feature_flags.py:27-32`:

```python
from platform_runtime import RuntimeFeatureFlags, RuntimeFeatureDisabledError

def handle_get(
    path: str,
    query: str | Mapping[str, str] | None,
    registry: SkillRegistry,
    flags: RuntimeFeatureFlags | None = None,
) -> tuple[int, dict[str, Any]]:
    if flags is not None:
        flags.require_enabled("skill_registry_enabled")
    # ... route handling
```

When the flag is disabled (default), the handler raises `RuntimeFeatureDisabledError` or returns a 503 response. The test must verify that the default-off flag blocks access.

### 5.7 Discovery Index Builder

**File:** `packages/skill-registry/src/inkstatute_skill_registry/discovery.py`

```python
import hashlib
import json
from platform_contract import NeutralSkillDescriptor

SCHEMA_URI = "https://schemas.agentskills.io/discovery/0.2.0/schema.json"


def build_discovery_index(skills: list[NeutralSkillDescriptor]) -> dict:
    """Build the /.well-known/agent-skills/index.json payload."""
    entries = []
    for skill in skills:
        canonical = json.dumps(_descriptor_to_dict(skill), sort_keys=True).encode("utf-8")
        digest = hashlib.sha256(canonical).hexdigest()
        entries.append({
            "name": _normalize_skill_name(skill.name),
            "type": "skill-md",
            "description": (skill.description or "")[:1024],
            "url": f"/.well-known/agent-skills/{_normalize_skill_name(skill.name)}/SKILL.md",
            "digest": f"sha256:{digest}",
        })
    return {"$schema": SCHEMA_URI, "skills": entries}


def _normalize_skill_name(name: str) -> str:
    """Convert skill name to agent-skills naming spec (lowercase, hyphens)."""
    return name.replace("_", "-").lower()
```

---

## 6. Implementation Plan Guidance

### 6.1 SKILL-01: list_skills, get_skill, search

**Implementation approach:**

1. **Create `packages/skill-registry/` package** with `pyproject.toml`, `src/inkstatute_skill_registry/`, and `tests/`.

2. **Implement `mapper.py`** — `manifest_skill_to_descriptor()` and `load_skills_from_manifests()` functions that read `solutions/*/manifest.json` files and produce `NeutralSkillDescriptor` records. The `skill_id` is `{solution_id}/{skill_name}` for cross-pack uniqueness.

3. **Implement `registry.py`** — `SkillRegistryPort` Protocol (read-only: `list_skills`, `get_skill`, `search`) and `SkillRegistry` concrete class. The registry is constructed with a pre-loaded list of descriptors. No I/O at query time.

4. **Implement `api.py`** — `handle_get()` route handler following the `conversation-read-view` pattern. Routes:
   - `GET /skills` → list all skills
   - `GET /skills/{skill_id}` → get single skill
   - `GET /skills/search?tag=&category=&name=` → search with filters

5. **Feature flag check** — The handler accepts an optional `RuntimeFeatureFlags` and calls `require_enabled("skill_registry_enabled")` before processing. Default-off behavior is tested.

6. **Read-only enforcement test** — Assert no mutating methods exist on `SkillRegistry`.

**Files to create:**
- `packages/skill-registry/pyproject.toml`
- `packages/skill-registry/README.md`
- `packages/skill-registry/src/inkstatute_skill_registry/__init__.py`
- `packages/skill-registry/src/inkstatute_skill_registry/registry.py`
- `packages/skill-registry/src/inkstatute_skill_registry/mapper.py`
- `packages/skill-registry/src/inkstatute_skill_registry/api.py`
- `packages/skill-registry/tests/test_registry.py`
- `packages/skill-registry/tests/test_api.py`

### 6.2 SKILL-02: Well-Known Discovery Endpoint

**Implementation approach:**

1. **Implement `discovery.py`** — `build_discovery_index()` function that converts `NeutralSkillDescriptor[]` to the Cloudflare agent-skills-discovery index format with `$schema`, `skills[]` (name, type, description, url, digest).

2. **Add route in `api.py`** — `GET /.well-known/agent-skills/index.json` returns the discovery index.

3. **Name normalization** — Skill names from manifests use underscores (e.g., `case_qa`). The agent-skills naming spec requires lowercase alphanumeric + hyphens. Convert `_` to `-` (e.g., `case-qa`).

4. **Digest computation** — Compute `sha256:<hex>` over the canonical JSON serialization of the `NeutralSkillDescriptor`. This provides metadata integrity verification.

5. **URL construction** — `/.well-known/agent-skills/{normalized_name}/SKILL.md` per the convention. The registry does not serve the actual SKILL.md file in Phase 37 (future enhancement), but the URL follows the convention.

**Files to create:**
- `packages/skill-registry/src/inkstatute_skill_registry/discovery.py`
- `packages/skill-registry/tests/test_discovery.py`

### 6.3 Success Criterion 3: Read-Only + Feature Flag Default-Off

**Implementation approach:**

1. **Read-only assertion test** — In `test_registry.py`, assert that `SkillRegistry` has no methods matching write patterns (`add_*`, `create_*`, `update_*`, `delete_*`, `remove_*`, `put_*`).

2. **Feature flag default-off test** — In `test_api.py`, verify that `RuntimeFeatureFlags()` (default) has `skill_registry_enabled=False` and that the API handler rejects requests when the flag is disabled. This test already exists in `packages/platform-runtime/tests/test_feature_flags.py:20` (`self.assertFalse(flags.skill_registry_enabled)`) — no changes needed there.

3. **No write routes test** — Assert that `handle_get` only accepts GET-style routes and that no POST/PUT/DELETE handlers exist.

---

## 7. Test Strategy

### 7.1 Test Files

| File | Purpose |
|------|---------|
| `packages/skill-registry/tests/test_registry.py` | Unit tests for `SkillRegistry` (list, get, search, read-only enforcement) |
| `packages/skill-registry/tests/test_api.py` | Unit tests for `handle_get()` route handler (all routes, feature flag, 404s) |
| `packages/skill-registry/tests/test_discovery.py` | Unit tests for `build_discovery_index()` (format, fields, digest, name normalization) |
| `packages/skill-registry/tests/test_mapper.py` | Unit tests for `manifest_skill_to_descriptor()` (field mapping, skill_id derivation) |

### 7.2 Test Cases

**test_registry.py:**
- `test_list_skills_returns_all_descriptors` — Load from lawfirm + demo_non_legal manifests, assert 8 skills total (4 + 4).
- `test_get_skill_returns_descriptor_by_id` — `get_skill("lawfirm/case_qa")` returns the correct descriptor.
- `test_get_skill_returns_none_for_unknown_id` — `get_skill("unknown/skill")` returns `None`.
- `test_search_by_tag_risk_level` — `search(tag="high")` returns skills with `metadata.risk_level == "high"`.
- `test_search_by_category_intent` — `search(category="factual_qa")` returns skills with `metadata.intent == "factual_qa"`.
- `test_search_by_name_substring` — `search(name_substring="case")` returns skills with "case" in name (case-insensitive).
- `test_search_with_no_filters_returns_all` — `search()` with no filters returns all skills.
- `test_search_with_multiple_filters` — `search(tag="medium", category="review")` applies AND logic.
- `test_registry_is_read_only` — Assert no methods on `SkillRegistry` match write patterns (`add_`, `create_`, `update_`, `delete_`, `remove_`, `put_`).
- `test_registry_does_not_mutate_internal_list` — `list_skills()` returns a copy; modifying the returned list does not affect the registry.

**test_api.py:**
- `test_get_skills_list_returns_200` — `handle_get("/skills", "", registry)` returns 200 with items array.
- `test_get_skill_by_id_returns_200` — `handle_get("/skills/lawfirm/case_qa", "", registry)` returns 200.
- `test_get_skill_unknown_id_returns_404` — `handle_get("/skills/unknown", "", registry)` returns 404.
- `test_search_skills_returns_200` — `handle_get("/skills/search?tag=high", "", registry)` returns 200 with filtered results.
- `test_search_skills_with_category_filter` — `handle_get("/skills/search?category=factual_qa", "", registry)` returns filtered results.
- `test_search_skills_with_name_filter` — `handle_get("/skills/search?name=case", "", registry)` returns filtered results.
- `test_unknown_route_returns_404` — `handle_get("/unknown", "", registry)` returns 404.
- `test_feature_flag_disabled_rejects_request` — With default `RuntimeFeatureFlags()`, handler rejects (raises `RuntimeFeatureDisabledError` or returns 503).
- `test_feature_flag_enabled_allows_request` — With `RuntimeFeatureFlags(skill_registry_enabled=True)`, handler processes normally.
- `test_no_write_endpoints_exist` — Assert `handle_get` does not handle POST/PUT/DELETE paths.

**test_discovery.py:**
- `test_discovery_index_has_schema_field` — Index has `$schema` set to the v0.2.0 URI.
- `test_discovery_index_has_skills_array` — Index has `skills` array with correct count.
- `test_discovery_skill_entry_has_required_fields` — Each entry has `name`, `type`, `description`, `url`, `digest`.
- `test_discovery_skill_name_is_normalized` — `case_qa` → `case-qa` (hyphenated, lowercase).
- `test_discovery_skill_type_is_skill_md` — All entries have `type: "skill-md"`.
- `test_discovery_skill_url_follows_convention` — URL is `/.well-known/agent-skills/{name}/SKILL.md`.
- `test_discovery_skill_digest_is_sha256_format` — Digest is `sha256:<64-hex-chars>`.
- `test_discovery_description_max_1024_chars` — Description is truncated to 1024 chars.
- `test_well_known_endpoint_returns_index` — `handle_get("/.well-known/agent-skills/index.json", "", registry)` returns 200 with the index.

**test_mapper.py:**
- `test_manifest_skill_to_descriptor_maps_fields` — `name` → `skill_id` (prefixed), `description` → `description`, `required_tools` → `required_tool_refs`, `intent` → `metadata.intent`, `risk_level` → `metadata.risk_level`.
- `test_skill_id_includes_solution_id` — `skill_id` is `"{solution_id}/{name}"`.
- `test_load_skills_from_manifests_loads_all_packs` — Loading both manifest files produces 8 descriptors.

### 7.3 Fixtures

Tests should load manifests from the real solution-pack paths:
```python
REPO_ROOT = Path(__file__).resolve().parents[3]
LAWFIRM_MANIFEST = REPO_ROOT / "solutions" / "lawfirm" / "manifest.json"
DEMO_MANIFEST = REPO_ROOT / "solutions" / "demo_non_legal" / "manifest.json"
```

This follows the pattern from `packages/contract-test-suite/tests/test_phase13_solution_evidence.py:43-45`.

### 7.4 Test Runner

Tests use `unittest` (no pytest), matching the existing pattern:
```python
if __name__ == "__main__":
    unittest.main()
```

---

## 8. V2 Gate Integration

### 8.1 New Gate

A new gate must be added to `scripts/run_v2_gates.py` in the `_gates()` function (line 42-128). Following the existing pattern:

```python
skill_registry_src = repo_root / "packages" / "skill-registry" / "src"

Gate(
    "skill-registry",
    (py, "-m", "unittest", "discover", "-s", "packages/skill-registry/tests"),
    (skill_registry_src, platform_src),
),
```

The `pythonpath` must include `skill_registry_src` (for the `inkstatute_skill_registry` package) and `platform_src` (for the `platform_contract` dependency).

### 8.2 compileall Gate Update

The `compileall` gate (line 109-127) must be updated to include the new package:

```python
Gate(
    "compileall",
    (
        py,
        "-m",
        "compileall",
        "packages/platform-contract/src",
        ...
        "packages/skill-registry/src",  # NEW
        ...
    ),
),
```

### 8.3 contract-test-suite Gate Update

The `contract-test-suite` gate (line 100-104) has a `pythonpath` that includes all package/service src directories. It should be updated to include `skill_registry_src` so that contract-test-suite tests can import the skill registry if needed:

```python
Gate(
    "contract-test-suite",
    (py, "-m", "unittest", "discover", "-s", "packages/contract-test-suite/tests"),
    (contract_src, platform_src, platform_runtime_src, wecom_src, hermes_src, hermes_backend_src, read_view_src, feedback_src, solution_loader_src, lawfirm_solution_src, demo_non_legal_solution_src, skill_registry_src),  # ADD skill_registry_src
),
```

### 8.4 GATE-01 (Phase 44) Future Impact

Phase 44 (GATE-01) will add a meta-test asserting every `packages/*/src` and `services/*/src` directory is covered by a gate. By adding the `skill-registry` gate now, Phase 44's meta-test will pass for this package.

### 8.5 SAFETY-06 Contract Freeze

The contract freeze test (`packages/contract-test-suite/tests/test_contract_freeze.py`) compares schema file hashes against a baseline. **Phase 37 must NOT modify any file in `packages/platform-contract/src/platform_contract/schemas/` or the Python binding files.** The Skill Registry is a pure consumer of `NeutralSkillDescriptor` — no contract changes needed. This is verified by the freeze gate staying green.

---

## 9. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Contract freeze violation** — Modifying `events.py` or schema files breaks SAFETY-06 | Low | High — gate failure blocks all M2 | Skill Registry only *imports* `NeutralSkillDescriptor`; no modifications to contract files. Verify freeze gate stays green. |
| **Manifest skill shape mismatch** — Manifest skills use `name` not `skill_id`, `required_tools` not `required_tool_refs` | Medium | Low — mapper handles translation | Implement explicit `manifest_skill_to_descriptor()` mapper with field-by-field mapping. Test all field mappings. |
| **Skill name normalization for discovery** — Manifest names use underscores (`case_qa`), agent-skills spec requires hyphens (`case-qa`) | Medium | Low — discovery clients may reject non-conforming names | Implement `_normalize_skill_name()` that converts `_` to `-` and lowercases. Test normalization. |
| **Feature flag bypass** — API handler accessible without flag check | Low | Medium — violates default-off posture | Handler accepts `RuntimeFeatureFlags` and calls `require_enabled()`. Test both disabled and enabled states. |
| **Write method accidentally added** — Future developer adds a mutating method | Low | Medium — violates read-only requirement | Add a test that asserts no write-pattern methods exist on `SkillRegistry`. |
| **Digest computation non-determinism** — JSON serialization order affects digest | Medium | Low — digest changes between runs | Use `json.dumps(..., sort_keys=True)` for canonical serialization. Test digest stability. |
| **Gate count increase breaks CI** — Adding a new gate increases total test time | Low | Low | The skill-registry package has ~20 tests; minimal impact on gate execution time. |
| **Solution manifest path assumptions** — Tests hardcode `solutions/lawfirm/manifest.json` path | Low | Low — paths are stable in the repo | Use `REPO_ROOT` relative paths following the existing test pattern. |

---

## 10. Validation Architecture

### 10.1 Per-Task Verification Map

| Task | Verification Method | Gate |
|------|---------------------|------|
| Create `packages/skill-registry/` package structure | `compileall` gate passes with new src dir | compileall |
| Implement `SkillRegistry` with `list_skills`, `get_skill`, `search` | `test_registry.py` — all 10 test cases pass | skill-registry |
| Implement manifest-to-descriptor mapper | `test_mapper.py` — all 3 test cases pass | skill-registry |
| Implement `handle_get()` API route handler | `test_api.py` — all 10 test cases pass | skill-registry |
| Implement `build_discovery_index()` | `test_discovery.py` — all 9 test cases pass | skill-registry |
| Add `/.well-known/agent-skills/index.json` route | `test_discovery.py::test_well_known_endpoint_returns_index` passes | skill-registry |
| Feature flag default-off enforcement | `test_api.py::test_feature_flag_disabled_rejects_request` passes | skill-registry |
| Read-only enforcement (no write methods) | `test_registry.py::test_registry_is_read_only` passes | skill-registry |
| Add `skill-registry` gate to `run_v2_gates.py` | `python scripts/run_v2_gates.py --list` includes `skill-registry` | v2-acceptance-traceability |
| Update `compileall` gate | `compileall` gate passes with new path | compileall |
| All 9 existing gates stay green | `python scripts/run_v2_gates.py` exits 0 | all gates |
| Contract freeze not violated | `contract-test-suite` gate passes (freeze test green) | contract-test-suite |

### 10.2 Gate Execution Order

```bash
# 1. Run new skill-registry gate
PYTHONPATH=packages/skill-registry/src:packages/platform-contract/src \
  python -m unittest discover -s packages/skill-registry/tests

# 2. Run full V2 gate suite
python scripts/run_v2_gates.py
```

### 10.3 Success Criteria Verification

| Success Criterion | How Verified |
|-------------------|--------------|
| 1. `list_skills`, `get_skill`, `search` return `NeutralSkillDescriptor` records | `test_registry.py` — all list/get/search tests pass with real manifest data |
| 2. `/.well-known/agent-skills/index.json` returns discovery index | `test_discovery.py::test_well_known_endpoint_returns_index` — 200 with `$schema`, `skills[]` |
| 3. Read-only + `skill_registry_enabled` defaults to `False` | `test_registry.py::test_registry_is_read_only` + `test_api.py::test_feature_flag_disabled_rejects_request` + existing `test_feature_flags.py:20` |

---

## 11. Key File References

| File | Line(s) | Relevance |
|------|---------|-----------|
| `packages/platform-contract/src/platform_contract/events.py` | 104-112 | `NeutralSkillDescriptor` dataclass definition |
| `packages/platform-contract/src/platform_contract/events.py` | 410-423 | `SolutionPackageManifest` with `skills: list[NeutralSkillDescriptor]` |
| `packages/platform-contract/src/platform_contract/__init__.py` | 55 | `NeutralSkillDescriptor` export |
| `packages/platform-contract/src/platform_contract/schemas/common.schema.json` | 236-262 | `neutral_skill_descriptor` JSON Schema definition |
| `packages/platform-runtime/src/platform_runtime/feature_flags.py` | 21 | `skill_registry_enabled: bool = False` |
| `packages/platform-runtime/src/platform_runtime/feature_flags.py` | 27-32 | `require_enabled()` method |
| `packages/platform-runtime/tests/test_feature_flags.py` | 20 | `assertFalse(flags.skill_registry_enabled)` |
| `solutions/lawfirm/manifest.json` | 12-41 | Lawfirm skills array (4 skills) |
| `solutions/demo_non_legal/manifest.json` | 13-42 | Demo non-legal skills array (4 skills) |
| `solutions/lawfirm/src/inkstatute_solutions_lawfirm/hermes_materializer.py` | 189-190 | Pattern for reading skills from manifest metadata |
| `services/conversation-read-view/src/conversation_read_view/api.py` | 11-58 | API route handler pattern to follow |
| `services/conversation-read-view/tests/test_api.py` | 1-79 | API test pattern to follow |
| `packages/solution-loader/pyproject.toml` | 1-15 | Package structure pattern to follow |
| `packages/solution-loader/src/inkstatute_solution_loader/__init__.py` | 1-40 | Package __init__ pattern to follow |
| `scripts/run_v2_gates.py` | 42-128 | Gate definitions (add new gate here) |
| `packages/contract-test-suite/tests/test_contract_freeze.py` | 1-50 | Contract freeze test (must stay green) |
| `.planning/research/ARCHITECTURE.md` | 57-65, 112, 150-155 | Skill Registry architecture design |
| `docs/requirements/V2-PRD.md` | 118 | PRD §3.2 — skill metadata source |
| `docs/requirements/V2-PRD.md` | 720 | PRD §4.3 — Skill Registry downgraded to read-only |
