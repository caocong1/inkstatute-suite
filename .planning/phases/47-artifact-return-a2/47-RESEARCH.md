# Phase 47: Artifact Return (A2) - Research

**Researched:** 2026-07-06
**Domain:** Artifact collection, ref-based schema, output boundary metadata filtering, AgentResult.artifacts population
**Confidence:** HIGH

## Summary

Phase 47 productizes the frozen `collect_artifacts()` method on the Codex and provider_model adapters. The contract surfaces are already in place and frozen — `BackendAdapter` has 9 methods (including `collect_artifacts`), `ArtifactRecord` (protocols.py) has `artifact_id`, `kind`, `uri_ref`, `name`, `metadata` fields, and `AgentResult` has an `artifacts: list[Artifact]` field. Both adapters currently have a stub `collect_artifacts()` that returns an empty list (`self._artifacts.get(run_id, ())`), and `submit_run` sets `self._artifacts[run_id] = []` — no artifacts are ever populated. This phase replaces those stubs with real artifact collection from `CodexExecResult.artifact_refs` and `ProviderModelExecResult.artifact_refs`, populates `AgentResult.artifacts` with ref-based `Artifact` entries, and enforces output boundary filtering on artifact metadata.

The Hermes adapter is the reference implementation — its `submit_run` calls `_artifact_records(run_id, result.artifact_refs, result.metadata)` to build `ArtifactRecord` entries from refs and stores them in `self._artifacts[run_id]`. Its `collect_artifacts()` calls `self._require_run(run_id)` before returning the stored list. Both Codex and provider_model adapters need the same pattern: build `ArtifactRecord` entries from `result.artifact_refs` in `submit_run`, store them, and return them from `collect_artifacts()`.

The output boundary (`output_boundary.py`) currently filters stream event text via regex rules and an event-type allowlist, but has no artifact metadata filtering. Phase 47 adds an artifact metadata allowlist that permits only safe fields (`sha256`, `size_bytes`, `content_ref`, `kind`, `name`, `mime_type`, `source`) and strips backend noise (model names, API error traces, function call internals) from artifact metadata before it reaches `AgentResult.artifacts` or `ArtifactRecord.metadata`.

**Primary recommendation:** Implement `collect_artifacts()` on both adapters by populating `_artifacts[run_id]` from `result.artifact_refs` in `submit_run` (mirroring the Hermes `_artifact_records` pattern), populate `AgentResult.artifacts` with ref-based `Artifact` entries (`uri` = ref, `metadata` contains `sha256`/`size_bytes`), add `filter_artifact_metadata()` to `output_boundary.py` with an allowlist, apply it in both adapters when building artifact records, and update the manifest `artifact_return_support` capability to `True` — all without modifying any frozen contract surface.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
Discuss phase was skipped per `workflow.skip_discuss`. All implementation choices are at Claude's discretion. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Claude's Discretion
All implementation choices are at Claude's discretion — use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
None — discuss phase skipped.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ARTIFACT-01 | Adapters return artifacts via frozen `collect_artifacts()` and populate `AgentResult.artifacts` with ref-based schema (`content_ref`, `sha256`, `size_bytes`); no inline binary content appears in any artifact record or contract event | §Architecture Patterns (adapter artifact collection), §Code Examples (ArtifactRecord + Artifact), §Common Pitfalls (inline binaries) |
| ARTIFACT-02 | Artifact metadata enforces the output boundary — backend noise (model names, API error traces, function call internals) is filtered from artifact metadata fields via an allowlist | §Architecture Patterns (output boundary allowlist), §Code Examples (filter_artifact_metadata), §Common Pitfalls (metadata leakage) |
</phase_requirements>

## Project Constraints (from AGENTS.md)

- **Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads.** Artifact records must use `uri_ref`-style references, not inline content. [VERIFIED: AGENTS.md §Safety And Privacy]
- **Contract logs should prefer references such as `raw_payload_ref`.** Artifact metadata must not store sensitive full text by default. [VERIFIED: AGENTS.md §Safety And Privacy]
- **Backend/gateway/system notices are not user-facing.** Artifact metadata passes through output boundary allowlist before reaching `AgentResult.artifacts` — backend noise filtered. [VERIFIED: AGENTS.md §Safety And Privacy]
- **Add tests before or with behavior changes**, especially for schemas, mappers, event ordering, dedupe, and fixture replay. [VERIFIED: AGENTS.md §Coding Rules]
- **Prefer structured parsers and schema validators over ad hoc string parsing.** Use structured artifact ref parsing, not regex on raw content. [VERIFIED: AGENTS.md §Coding Rules]
- **Do not introduce a new service, database, queue, or runtime dependency.** `dependencies = []` invariant must be preserved on both adapter packages. [VERIFIED: AGENTS.md §Coding Rules, pyproject.toml]
- **Keep changes scoped to the active GSD phase and its plan.** [VERIFIED: AGENTS.md §Coding Rules]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Codex artifact collection from `artifact_refs` | Backend adapter (codex) | — | Adapter owns provider-specific artifact ref parsing; runner provides refs |
| Provider_model artifact collection from `artifact_refs` | Backend adapter (provider_model) | — | Adapter owns provider-specific artifact ref parsing; runner provides refs |
| `AgentResult.artifacts` population | Backend adapter | — | Adapter is the authority for run results including artifacts |
| Artifact metadata output boundary filtering | Platform runtime (output_boundary) | — | Runtime owns the boundary between backend and channels |
| `artifact_return_support` capability declaration | Backend adapter (manifest) | — | Manifest truthfully declares artifact return support |
| Provider response file output extraction | Backend adapter (openai_runner) | — | Runner parses provider response and populates `artifact_refs` |

## Standard Stack

### Core

No new external packages are installed. This phase uses only the existing Python standard library and existing project packages. [VERIFIED: codebase grep — `dependencies = []` in both adapter pyproject.toml files]

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `hashlib` | 3.14+ | SHA-256 checksums for artifact content | Already used in all adapters [VERIFIED: codebase] |
| `platform-contract` | existing | `Artifact`, `ArtifactRecord`, `AgentResult`, `ArtifactKind` | Frozen contract — no modifications [VERIFIED: test_contract_freeze.py] |
| `platform-runtime` | existing | `ArtifactRecord` (protocol), `DefaultAssistantOutputBoundary` | Runtime owns output boundary [VERIFIED: codebase] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `inkstatute_backends_codex` | existing | Codex adapter + exec runner | Codex artifact collection |
| `inkstatute_backends_provider_model` | existing | provider_model adapter + OpenAI runner | Provider_model artifact collection |
| `inkstatute_backends_hermes` | existing | Hermes adapter (reference implementation) | Reference pattern for `_artifact_records` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `uri_ref` field on `ArtifactRecord` for content reference | `content_ref` field | Must use existing frozen `ArtifactRecord` schema — `uri_ref` is the ref field. `content_ref`, `sha256`, `size_bytes` go into `metadata` dict. |
| New `ArtifactMetadata` dataclass | `metadata: JsonObject` dict on `ArtifactRecord` | Must use existing frozen schema. Metadata dict is the extension point. |
| Inline binary content in artifact records | `uri_ref` + metadata refs | Rejected — violates AGENTS.md safety rules. All content must be ref-based. |

**Installation:**
```bash
# No packages to install — this phase uses only existing project packages and Python stdlib
```

**Version verification:** Not applicable — no new packages installed. Python 3.14.6 confirmed on the target machine. [VERIFIED: `python3 --version`]

## Package Legitimacy Audit

> No external packages are installed in this phase. All work uses existing project packages and Python stdlib. The `dependencies = []` invariant on both adapter packages must be preserved. [VERIFIED: `packages/backends/codex/pyproject.toml:15`, `packages/backends/provider_model/pyproject.toml:15`]

## Architecture Patterns

### System Architecture Diagram

```
Runner (CodexExecRunner / ProviderModelRunner)
    │  invoke(req) → CodexExecResult / ProviderModelExecResult
    │  result.artifact_refs: list[str]  (ref-based, no inline binaries)
    │
    ▼
BackendAdapter.submit_run(req)
    │  _artifact_records(run_id, result.artifact_refs, result.metadata)
    │    │  For each ref:
    │    │    ArtifactRecord(artifact_id, kind, uri_ref=ref, name, metadata=filtered)
    │    │    Artifact(artifact_id, kind, uri=ref, name, metadata=filtered)
    │    │  filter_artifact_metadata() applied to each metadata dict
    │    │
    │    ▼
    │  self._artifacts[run_id] = [ArtifactRecord, ...]
    │  AgentResult.artifacts = [Artifact, ...]
    │
    ▼
BackendAdapter.collect_artifacts(run_id)
    │  self._require_run(run_id)
    │  return list(self._artifacts[run_id])
    │
    ▼
ArtifactRecord (ref-based: uri_ref, metadata.sha256, metadata.size_bytes)
    │  No inline binary content anywhere
```

### Pattern: Ref-Based Artifact Schema

The frozen `ArtifactRecord` (protocols.py:158-163) uses `uri_ref` as the content reference field. The `Artifact` dataclass (events.py:61-70) uses `uri` as the content reference field. Both have a `metadata: JsonObject` dict for extensible fields. The ref-based schema means:

- `uri_ref` / `uri` — points to the artifact content location (never inline)
- `metadata["sha256"]` — content hash for integrity verification
- `metadata["size_bytes"]` — content size for budget tracking
- `metadata["content_ref"]` — alternative content reference (if different from uri_ref)
- `metadata["mime_type"]` — content type

No field ever contains raw binary content. [VERIFIED: protocols.py:158-163, events.py:61-70]

### Pattern: Hermes Reference Implementation

The Hermes adapter (adapter.py:206-208, 340-351) is the reference for artifact collection:

```python
async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]:
    self._require_run(run_id)
    return list(self._artifacts.get(run_id, ()))

def _artifact_records(run_id, refs, metadata):
    kind = str(metadata.get("artifact_kind", "backend_ref"))
    return [
        ArtifactRecord(
            artifact_id=f"{run_id}-artifact-{index:03d}",
            kind=kind,
            uri_ref=ref,
            name=f"{run_id}-artifact-{index:03d}",
            metadata={"source": "hermes_oneshot"},
        )
        for index, ref in enumerate(refs, start=1)
    ]
```

In `submit_run` (line 128): `self._artifacts[run_id] = _artifact_records(run_id, result.artifact_refs, result.metadata)`. [VERIFIED: hermes/adapter.py:128, 206-208, 340-351]

### Pattern: Output Boundary Artifact Metadata Allowlist

The output boundary (`output_boundary.py`) currently filters stream event text. Phase 47 adds artifact metadata filtering via an allowlist of permitted keys:

```python
_ALLOWED_ARTIFACT_METADATA_KEYS = frozenset({
    "sha256", "size_bytes", "content_ref", "kind",
    "name", "mime_type", "source", "source_refs",
    "template_ref", "features", "created_at",
})

def filter_artifact_metadata(metadata: JsonObject) -> JsonObject:
    """Filter artifact metadata to allowed keys only, strip backend noise."""
    filtered = {}
    for key, value in metadata.items():
        if key.lower() not in _ALLOWED_ARTIFACT_METADATA_KEYS:
            continue
        filtered[key] = _sanitize_artifact_value(value)
    return filtered
```

This strips model names, API error traces, function call internals, and any key not in the allowlist. [ASSUMED — new code to be added]

## Don't Hand-Roll

| What | Use Instead | Why |
|------|-------------|-----|
| Artifact record construction | `_artifact_records()` helper pattern (from Hermes) | Proven pattern, consistent ID generation, ref-based schema |
| Metadata filtering | `filter_artifact_metadata()` allowlist function | Structured allowlist, not ad hoc regex on metadata values |
| SHA-256 checksums | `hashlib.sha256()` (stdlib) | Already used throughout the codebase |
| Artifact ID generation | `f"{run_id}-artifact-{index:03d}"` pattern | Consistent with Hermes adapter, deterministic, traceable |

## Common Pitfalls

1. **Inline binary content in artifact records** — Never put raw bytes or base64-encoded content in `ArtifactRecord.metadata` or `Artifact.metadata`. Use `uri_ref`/`uri` for content references and `sha256`/`size_bytes` in metadata for verification. [VERIFIED: AGENTS.md §Safety And Privacy]

2. **Backend noise in artifact metadata** — Model names (e.g., "gpt-4"), API error traces, function call internals must not appear in artifact metadata. Use the allowlist filter to strip them. [VERIFIED: AGENTS.md §Safety And Privacy, output_boundary.py existing patterns]

3. **Not calling `_require_run()` in `collect_artifacts()`** — The Codex adapter's current `collect_artifacts()` does NOT call `_require_run()` (line 235-236), while Hermes does (line 207). This means `collect_artifacts("unknown-run")` returns `[]` instead of raising `KeyError`. Must fix to match Hermes pattern. [VERIFIED: codex/adapter.py:235-236 vs hermes/adapter.py:206-208]

4. **`artifact_return_support=False` in manifest** — Both Codex and provider_model manifests currently declare `artifact_return_support=False`. After implementing artifact collection, this should be `True` to truthfully declare the capability. [VERIFIED: codex/manifest.py:50, provider_model/manifest.py:54]

5. **Not populating `AgentResult.artifacts`** — `AgentResult` has an `artifacts: list[Artifact]` field (events.py:147) that is currently always empty. Must populate it with `Artifact` entries from `result.artifact_refs` in `submit_run`. [VERIFIED: events.py:147, codex/adapter.py:132, provider_model/adapter.py:131]

6. **Modifying frozen contract surfaces** — `ArtifactRecord` fields (protocols.py:158-163), `Artifact` fields (events.py:61-70), `BackendAdapter` method signatures are all frozen. Must not add/remove/rename fields. [VERIFIED: test_contract_freeze.py, test_contract_count_freeze.py]

## Code Examples

### ArtifactRecord (protocols.py — frozen, used by collect_artifacts)

```python
@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_id: str
    kind: str
    uri_ref: str          # Content reference — never inline binary
    name: str | None = None
    metadata: JsonObject = field(default_factory=dict)  # sha256, size_bytes, etc.
```
[VERIFIED: protocols.py:158-163]

### Artifact (events.py — frozen, used by AgentResult.artifacts)

```python
@dataclass(frozen=True, slots=True)
class Artifact:
    artifact_id: str
    kind: ArtifactKind | str
    name: str
    uri: str              # Content reference — never inline binary
    mime_type: str | None = None
    template_ref: str | None = None
    features: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)  # sha256, size_bytes, etc.
```
[VERIFIED: events.py:61-70]

### Hermes _artifact_records (reference implementation)

```python
def _artifact_records(run_id: str, refs: list[str], metadata: JsonObject) -> list[ArtifactRecord]:
    kind = str(metadata.get("artifact_kind", "backend_ref"))
    return [
        ArtifactRecord(
            artifact_id=f"{run_id}-artifact-{index:03d}",
            kind=kind,
            uri_ref=ref,
            name=f"{run_id}-artifact-{index:03d}",
            metadata={"source": "hermes_oneshot"},
        )
        for index, ref in enumerate(refs, start=1)
    ]
```
[VERIFIED: hermes/adapter.py:340-351]

### Codex adapter current stub (to be replaced)

```python
# submit_run (line 136):
self._artifacts[run_id] = []

# collect_artifacts (line 235-236):
async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]:
    return list(self._artifacts.get(run_id, ()))
```
[VERIFIED: codex/adapter.py:136, 235-236]

### Provider_model adapter current stub (to be replaced)

```python
# submit_run (line 135):
self._artifacts[run_id] = []

# collect_artifacts (line 234-235):
async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]:
    return list(self._artifacts.get(run_id, ()))
```
[VERIFIED: provider_model/adapter.py:135, 234-235]

### Output boundary current state (no artifact metadata filtering)

```python
class DefaultAssistantOutputBoundary:
    def apply(self, visibility_target, text=None, event_metadata=None, event_type=None):
        # Filters stream event text via regex rules + event-type allowlist
        # No artifact metadata filtering exists
```
[VERIFIED: output_boundary.py:39-95]
