---
phase: 13-solutionloader-lawyer-non-legal-solutions
status: findings
reviewed_at: 2026-06-30
reviewer: gsd-code-reviewer
depth: standard
files_reviewed: 26
critical_count: 2
warning_count: 7
info_count: 6
---

# Phase 13 Code Review

**Goal:** Prove the lawyer pack is a backend-portable solution (not platform core) and that a non-legal pack runs through the same contracts unchanged.

## Summary

Phase 13 ships a stdlib-only SolutionLoader with backend-neutral lawfirm and demo_non_legal solution packs, a privacy scanner, and 79 passing tests. Manifest neutrality, sanitization atomicity, default-off gating, and composability are structurally sound. However, the code review identified 2 Critical findings, 7 Warnings, and 6 Info items. The Critical findings are: (1) the `MaterializerRegistry` silently overwrites duplicate `backend_id` registrations, so registering both `LawfirmHermesMaterializer` and `DemoNonLegalHermesMaterializer` against `backend_id="hermes"` causes the demo materializer to silently replace the lawfirm one — the composability tests pass because both materializers share identical structure, masking the defect; (2) the `ManifestValidator.validate()` dataclass path scans only `solution_id`/`version`/`manifest_ref` for secret markers, not `metadata` string values, contradicting the plan's "secret marker in any field" acceptance criterion.

## Findings

| Severity | ID | File | Line | Rule | Description | Fix |
|----------|----|------|------|------|-------------|-----|
| Critical | CR-01 | packages/solution-loader/src/inkstatute_solution_loader/materializer_registry.py | register() | registry-collision | Both lawfirm and demo materializers register under `backend_id="hermes"`; the second silently overwrites the first. Composability tests pass because both materializers share identical structure, masking the wrong-dispatch defect. Contradicts Plan 13-03's "both packs register into the same MaterializerRegistry without conflict" claim. | Either (a) key the registry by `(backend_id, solution_id)` tuple, or (b) raise/warn on duplicate `backend_id` registration, or (c) document that one materializer per backend_id is the intended model and update the composability test to assert only one materializer is active per backend. |
| Critical | CR-02 | packages/solution-loader/src/inkstatute_solution_loader/manifest_validator.py | validate() | incomplete-secret-scan | The dataclass validation path scans only `solution_id`, `version`, `manifest_ref` for secret markers. `metadata` string values (e.g., `metadata.description`, `metadata.persona_ref`) are NOT scanned. Plan 13-01 acceptance criterion says "secret marker in any field" but the implementation only covers 3 fields. A manifest with `metadata.description = "sk-1234..."` passes `validate()`. | Extend `_scan_string` calls in `validate()` to recursively scan all string values in `manifest.metadata` (the dict-path `validate_manifest_dict` already does this — port the recursive scan to the dataclass path). Add a test case with a secret marker in `metadata.description`. |
| Warning | WR-01 | packages/solution-loader/src/inkstatute_solution_loader/loader.py | 112 | type-safety-hole | `materialize_for` passes `None` to `MaterializerFn` (typed `Callable[[Solution, Path], ...]`) for materializers without `write_dir` side effect, with `# type: ignore[arg-type]`. The type annotation lies. | Change `MaterializerFn` to `Callable[[Solution, Path | None], ...]` or refactor the None case to not call the materializer at all. |
| Warning | WR-02 | packages/solution-loader/src/inkstatute_solution_loader/loader.py | materialize_for | protocol-drift | `SolutionLoader` Protocol says `materialize_for(self, solution, backend_id) -> BackendSolutionBundle` but `DefaultSolutionLoader.materialize_for` returns `tuple[list[Issue], BackendSolutionBundle | None]` and takes extra `output_dir` param. The conformance test only checks methods are callable, not signature match. | Either update the Protocol to match the implementation (return tuple, optional output_dir), or split into two methods (e.g., `try_materialize_for` vs `materialize_for`). |
| Warning | WR-03 | packages/solution-loader/src/inkstatute_solution_loader/materializer_registry.py | register() | silent-overwrite | `register()` silently overwrites existing registrations — no warning, no error. This is the root cause of CR-01. | At minimum log a warning on duplicate `backend_id`; consider raising if the materializer fn or side_effects differ. |
| Warning | WR-04 | packages/solution-loader/src/inkstatute_solution_loader/loader.py | 86 | assert-for-control-flow | `assert side_effects is not None` used for a runtime invariant. Stripped by `python -O`, leaving `side_effects.side_effect_kinds` to raise `AttributeError` if the invariant breaks. | Replace with explicit `if side_effects is None: return ([Issue(...)], None)` guard. |
| Warning | WR-05 | packages/solution-loader/src/inkstatute_solution_loader/config.py | 55 | dead-config-field | `DefaultSolutionLoaderConfig.allow_unknown_backends` is defined but never read by the loader. The loader always returns `no_materializer_registered` Issue regardless of this flag. | Either wire the flag into `materialize_for` (skip the Issue when `allow_unknown_backends=True`) or remove the field. |
| Warning | WR-06 | packages/solution-loader/src/inkstatute_solution_loader/privacy_scan.py | scan_bundle_dir | silent-degradation | Lazy-import fallback: if `inkstatute_solutions_lawfirm.sanitize` is not importable, `scan_bundle_dir` skips content scanning for text files entirely (only extension-based scanning runs). Plan 13-04 risk note claims the fallback "still flags refused extensions and obvious file-name patterns" — but there is no file-name pattern scanning for text files. A `.md` file containing `sk-...` passes silently if the sanitize module is unavailable. | Either (a) add a minimal inline refusal pattern set in `privacy_scan.py` as a fallback (duplicating a subset of `sanitize.SANITIZE_REFUSE_PATTERNS`), or (b) document that `scan_bundle_dir` requires `inkstatute_solutions_lawfirm` on PYTHONPATH and raise `ImportError` if unavailable. |
| Warning | WR-07 | packages/solution-loader/src/inkstatute_solution_loader/manifest_validator.py | validate() solution_id check | falsy-short-circuit | `if manifest.solution_id and not _SOLUTION_ID_RE.match(...)`: if `solution_id` is empty string or None, the check is skipped (falsy short-circuit). An empty/None `solution_id` should be rejected. | Change to `if not manifest.solution_id or not _SOLUTION_ID_RE.match(manifest.solution_id):` and emit an Issue for empty/None. |
| Info | IN-01 | solutions/lawfirm/manifest.json | output_policy | extra-field | `output_policy` contains `block_meta_leak: true` which is not in Plan 13-02's specified field list (`allow_legal_conclusions`, `require_citation`, `redact_pii`). | Document the extra field in MANIFEST.md or remove it if unused. |
| Info | IN-02 | solutions/demo_non_legal/manifest.json | metadata | extra-field | `metadata.is_non_legal_demo: true` is an extra metadata key not specified in Plan 13-03. | Document or remove. |
| Info | IN-03 | solutions/demo_non_legal/src/inkstatute_solutions_demo_non_legal/__init__.py | exports | missing-export | Plan 13-03 says `__init__.py` should re-export `register_into(registry)` but the implementation does not define `register_into` at all. `solutions_meta.register_demo_non_legal_materializer` provides the equivalent helper. | Either add `register_into` to demo_non_legal for symmetry with lawfirm, or update the plan to reference `solutions_meta.register_demo_non_legal_materializer`. |
| Info | IN-04 | solutions/lawfirm/src/inkstatute_solutions_lawfirm/hermes_materializer.py | 106 | import-in-method | `import json as _json` inside method body; demo_non_legal imports at top. Inconsistent style. | Move import to module top. |
| Info | IN-05 | solutions/lawfirm/src/inkstatute_solutions_lawfirm/hermes_materializer.py | _hash_bundle | hash-scope | `bundle_hash` covers 3 files (SKILL.md.template, SAMPLE_PERSONA.md, tools.json) — SANITIZATION_REPORT.md is written after the hash is computed (correct — can't self-hash), but `file_count: 4` in bundle metadata is slightly misleading. | Document that hash covers all files except SANITIZATION_REPORT.md, or change `file_count` to 3. |
| Info | IN-06 | packages/solution-loader/src/inkstatute_solution_loader/__init__.py | ManifestValidatorIssue | redundant-alias | `ManifestValidatorIssue = Issue` is a redundant alias (same type). | Remove the alias or document why it exists. |

## Key Strengths

- **Stdlib-only constraint satisfied:** All imports in solution-loader, lawfirm, and demo_non_legal packages are stdlib or first-party (`platform_runtime`, `inkstatute_solution_loader`, `inkstatute_solutions_*`). No third-party deps.
- **Manifest neutrality:** `solutions/lawfirm/manifest.json` has legal-specific data only in `industry_context.legal_domain`; `solutions/demo_non_legal/manifest.json` uses `education_domain` with `allow_legal_conclusions: false`. Zero legal-only top-level keys in either manifest.
- **Sanitization atomicity:** Both materializers run a pre-flight sanitize scan; on any refusal, return `(issues, None)` and DO NOT write files. No partial writes.
- **Path-traversal guard:** `DefaultSolutionLoader.materialize_for` rejects `bundle_ref` that resolves outside the caller-provided `output_dir`.
- **Default-off gating:** `SolutionLoaderFeatureFlags.require_enabled()` returns `False` by default; `INKSTATUTE_SOLUTION_LOADER_ENABLED` must be set.
- **Privacy scan coverage:** 9 `TestSolutionPrivacyGate` tests cover each refusal class (secret marker, raw_payload, log/db/media extensions, customer doc, confidential_artifact, missing dir, clean bundle).
- **Composability test structure:** 4 `TestComposability` tests assert same-loader-handles-both, registry known backends, distinct solution_ids, fixture loads.
- **Aggregate evidence pattern:** 24-test `test_phase13_solution_evidence.py` wires all Phase 13 artifacts into a single default-off, sanitized, neutral view (extends Phase 11/12 pattern).

## Top Concerns

- **CR-01 (registry collision) is the most significant finding.** The composability claim — that both lawfirm and demo materializers register side by side — is structurally false under the current `MaterializerRegistry` design (keyed by `backend_id` only). The tests pass because both materializers have identical structure, which masks the wrong-dispatch. If a lawfirm-specific behavior is added to `LawfirmHermesMaterializer` in the future, it would silently never run when both packs are registered. This needs a design decision: either `(backend_id, solution_id)` dispatch, or one-materializer-per-backend with solution-id branching inside the materializer.
- **CR-02 (incomplete secret scan) is a spec violation.** The plan explicitly says "secret marker in any field" but the dataclass-path validator only scans 3 fields. The materializer's defense-in-depth scan catches secrets in bundle content, but a caller relying on `validate()` alone before materialization would miss secrets in `metadata` string values.
- **WR-06 (silent degradation) is a privacy gap.** The privacy scanner's lazy-import fallback skips content scanning for text files if the sanitize module is unavailable. The plan claims a "name-only scan" fallback but the implementation provides no file-name pattern scanning for text files. This is a defense-in-depth gap.

## Findings Detail

### CR-01: Registry collision — wrong materializer dispatched

**Description:** `MaterializerRegistry.register(backend_id, fn, side_effects)` silently overwrites any existing registration for the same `backend_id`. In `solutions_meta.py`, both `register_lawfirm_materializer` and `register_demo_non_legal_materializer` register against `backend_id="hermes"`. When both are called (as in `test_phase13_solution_evidence._build_registry` and `test_demo_non_legal._build_loader`), the second registration overwrites the first. Subsequent `materialize_for(lawfirm_solution, "hermes")` dispatches to `DemoNonLegalHermesMaterializer.materialize`, not `LawfirmHermesMaterializer.materialize`.

**Impact:** The composability tests pass because both materializers share identical structure (same 4-file bundle shape, same `profiles/<solution_id>` path) — the wrong materializer writes the right files to the right path. But the bundle's `materializer` metadata field records the wrong class name, and any future lawfirm-specific behavior in `LawfirmHermesMaterializer` would silently never run when both packs are registered. This contradicts Plan 13-03's explicit claim: "Both packs (lawfirm and demo_non_legal) register into the same MaterializerRegistry without conflict."

**Fix:** Choose one:
1. **(Preferred)** Key the registry by `(backend_id, solution_id)` tuple. Update `MaterializerRegistry.register/get/side_effects_for` to accept both. Update `DefaultSolutionLoader.materialize_for` to dispatch by `(backend_id, solution.solution_id)`. Update composability tests to assert both materializers are retrievable.
2. Raise `ValueError` on duplicate `backend_id` registration with a different `fn` or `side_effects`.
3. Document that one materializer per `backend_id` is the intended model; update the composability test to assert only one materializer is active per backend and remove the "both registered side by side" claim from Plan 13-03.

**Files to modify:** `packages/solution-loader/src/inkstatute_solution_loader/materializer_registry.py`, `packages/solution-loader/src/inkstatute_solution_loader/loader.py`, `packages/contract-test-suite/tests/test_phase13_solution_evidence.py`, `solutions/demo_non_legal/tests/test_demo_non_legal_solution.py`.

### CR-02: Manifest validator doesn't scan metadata string values for secret markers

**Description:** `ManifestValidator.validate()` (dataclass path) calls `_scan_string` on `manifest.solution_id`, `manifest.version`, `manifest.manifest_ref` only. `manifest.metadata` string values (e.g., `metadata.description`, `metadata.persona_ref`, `metadata.compatibility`) are NOT scanned for secret markers. The dict-path `validate_manifest_dict` does scan recursively, but `DefaultSolutionLoader.validate()` uses the dataclass path.

**Impact:** A manifest with `metadata.description = "sk-1234567890..."` passes `DefaultSolutionLoader.validate()` with zero Issues. Plan 13-01 acceptance criterion says "manifest_validator.validate(manifest) returns ... ≥1 Issue for each rejection: ... secret marker in any field." The "any field" claim is not met. The materializer's pre-flight sanitize scan catches secrets in bundle content, but a caller relying on `validate()` alone before materialization would miss secrets in metadata.

**Fix:** In `ManifestValidator.validate()`, after the existing `_scan_string` calls, add a recursive walk over `manifest.metadata` (and any nested dicts/lists) calling `_scan_string` on each string value. Add a test case: `test_secret_marker_in_metadata_description_rejected`.

**Files to modify:** `packages/solution-loader/src/inkstatute_solution_loader/manifest_validator.py`, `packages/solution-loader/tests/test_solution_loader_library.py`.

---

**Verdict:** findings — 2 Critical, 7 Warning, 6 Info. The Critical findings (CR-01 registry collision, CR-02 incomplete secret scan) should be fixed before milestone audit. The Warnings are quality issues that should be tracked. The Info items are minor and can be deferred.