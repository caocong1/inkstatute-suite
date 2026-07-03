# Stack Research

**Domain:** V2 Acceptance Closure — requirement traceability, automated gap analysis, acceptance readiness reporting, CI gate completeness verification
**Researched:** 2026-07-03
**Confidence:** HIGH

## Context

The v1.5 milestone is **not** a feature milestone. It is an acceptance-closure milestone: audit all unchecked V2 Active requirements against the shipped codebase, close code gaps, mark validated requirements in `PROJECT.md`, and produce a final V2 acceptance readiness report so that only the Phase 5 live WeCom UAT and Phase 8 five-workday lawyer trial human gates remain.

This means the "stack" question is narrow: what tooling is needed to (a) trace PRD §10 acceptance criteria + `PROJECT.md` Active requirements to concrete code evidence, (b) automatically detect gaps between requirements and shipped code, (c) generate a readiness report, and (d) verify CI gate completeness — **without introducing unnecessary runtime dependencies** into a codebase that has been deliberately kept dependency-free.

## Existing Stack Baseline (DO NOT re-add)

The codebase already runs on a deliberately minimal, stdlib-first stack. Acceptance-closure tooling must fit this pattern, not break it.

| Existing Piece | Location | Role for Acceptance Closure |
|----------------|----------|------------------------------|
| V2 gate runner | `scripts/run_v2_gates.py` | Subprocess-orchestrates 8 gates (platform-contract, wecom-service, hermes-contract-layer, conversation-read-view, feedback-service, phase7-privacy-boundary, contract-test-suite, compileall). Emits `--json-summary`. This is the CI gate surface to extend. |
| Milestone audit checker | `scripts/check_v1_3_verification_artifacts.py` | Precedent for the closure pattern: regex-parses `REQUIREMENTS.md` traceability tables, verifies artifact headers exist, asserts audit frontmatter no longer reports `gaps_found`. Pure stdlib (`re`, `pathlib`, `argparse`). |
| Contract test suite | `packages/contract-test-suite/src/contract_test_suite/` | Already ships `schema_validation.py` (stdlib JSON-Schema subset validator — no `jsonschema` dep), `coverage_report.py` (contract-log coverage + breakage rate), `boundary_checks.py` (AST + import-root scan for industry-neutral composability), `privacy_scan.py` (secret-pattern scan), `event_stream_replay.py` (JSONL replay + seq ordering), `trial_acceptance.py` (Phase 8 evidence-row metrics). These are the evidence producers the gap analyzer invokes. |
| JSON Schema files | `packages/platform-contract/src/platform_contract/schemas/*.schema.json` | 17 schema files. Already validated by the stdlib subset validator. |
| CI workflow | `.github/workflows/v2-contract-gates.yml` | Runs `python scripts/run_v2_gates.py` on Python 3.11 for every push/PR. |
| Python | 3.11 (CI) / 3.14 (local) | `tomllib` is stdlib since 3.11 — usable for reading `pyproject.toml` without a dependency. |

**Key constraint:** `platform-contract`, `contract-test-suite`, and all services declare `dependencies = []` in `pyproject.toml`. The project intentionally avoids `jsonschema`, `PyYAML`, `Jinja2`, and any heavy framework. The AGENTS rule is explicit: *"Do not introduce a new service, database, queue, or runtime dependency unless the V2 PRD or the active GSD plan requires it."* Acceptance-closure tooling is a GSD-plan need, but it is tooling, not a runtime service — so it must stay stdlib-only and live in `scripts/` or a new `tools/` location, not in a shipped package.

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python stdlib only | 3.11+ (CI floor) | All acceptance-closure tooling: traceability parsing, gap analysis, report generation, gate extension | The codebase is deliberately dependency-free. `pathlib`, `re`, `json`, `tomllib`, `argparse`, `dataclasses`, `subprocess`, `ast`, `datetime` cover every need. The existing `run_v2_gates.py` and `check_v1_3_verification_artifacts.py` prove this pattern works for gate orchestration and traceability checks. Adding a library would violate the AGENTS dependency rule and create CI install steps that do not exist today. |
| JSON (not YAML) for traceability manifest | — | Machine-readable mapping of PRD §10 criteria + PROJECT.md Active requirements → code evidence (file paths, test module paths, gate names, schema IDs) | `json` is stdlib. PyYAML is **not** installed and the only YAML file (`V2-ingest-manifest.yaml`) is trivial. A JSON manifest keeps the closure tooling dependency-free and diff-friendly in PRs. |
| Markdown for readiness report | — | Final V2 acceptance readiness report output | The project's source-of-truth artifacts (`PROJECT.md`, `MILESTONE-AUDIT.md`, `VERIFICATION.md`) are all Markdown. A generated `.planning/v2-ACCEPTANCE-READINESS.md` fits the existing artifact convention and needs no template engine. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `tomllib` (stdlib) | 3.11+ | Read `pyproject.toml` `dependencies = []` declarations to prove no runtime deps were silently added during gap closure | Gap-analysis "zero new runtime dependencies" invariant check. Already available — no install. |
| `ast` (stdlib) | — | Parse Python source to verify exported symbols, import roots, and forbidden-field leakage for composability closure | Reuses the exact pattern already in `boundary_checks.py`. The gap analyzer can call `contract_test_suite.boundary_checks` directly rather than re-implementing. |
| `subprocess` (stdlib) | — | Invoke `run_v2_gates.py --json-summary` and individual gate commands from the gap analyzer / report generator | Mirrors `run_v2_gates.py._run_gate`. Lets the closure tooling treat gate results as structured data without importing test modules. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `scripts/audit_v2_requirements.py` (new) | Reads a traceability manifest, verifies each requirement's evidence exists (files, test modules, gate names), invokes the existing contract-test-suite checkers (`boundary_checks`, `privacy_scan`, `coverage_report`, `schema_validation`), and prints a gap list with exit code 0/1. | Pure stdlib. Follow `check_v1_3_verification_artifacts.py` structure: `--mode {traceability,gaps,all}`, dataclass results, `argparse`. Do NOT import test frameworks — use `subprocess` + `ast` + `pathlib` for evidence checks. |
| `acceptance/v2-traceability.json` (new artifact) | Machine-readable manifest: each entry has `requirement_id`, `prd_section`, `project_md_line`, `evidence` (list of `{kind: file|test|gate|schema, path, assertion}`), `status: pending|validated|gap`, `closure_phase`. | Lives at repo root under a new `acceptance/` dir (not `.planning/` so CI can read it without planning-state coupling). JSON so `json.load` works with no dependency. |
| `scripts/generate_v2_readiness_report.py` (new) | Aggregates: (1) `run_v2_gates.py --json-summary` output, (2) `audit_v2_requirements.py` gap list, (3) traceability manifest statuses, (4) coverage/breakage metrics from `contract_test_suite.coverage_report`. Emits `.planning/v2-ACCEPTANCE-READINESS.md`. | Pure stdlib string templates (triple-quoted f-strings). No Jinja2. Report sections mirror PRD §10.1–10.4 so the reader can cross-check each acceptance criterion. |
| `run_v2_gates.py` (extend) | Add a 9th gate `v2-acceptance-traceability` that runs `scripts/audit_v2_requirements.py --mode all`. | One new `Gate(...)` entry in `_gates()`. Keeps CI as a single command. The gate fails (exit 1) if any requirement is `status: gap` or evidence is missing, which is exactly the PRD §10.2 "contract-test-suite in CI main branch stays green" invariant extended to acceptance closure. |

## Installation

```bash
# No installation required. No new packages.
# The acceptance-closure tooling uses only the Python 3.11+ stdlib.

# Verify the existing environment is sufficient:
python3 -c "import json, re, pathlib, argparse, subprocess, ast, tomllib, dataclasses, datetime; print('stdlib OK')"
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Stdlib `json` + custom manifest | `jsonschema` 4.26.0 to validate the traceability manifest itself | Only if the manifest grows complex enough that hand-rolled validation becomes a maintenance burden. For ~15 requirements with a flat schema, stdlib `json.load` + a 20-line `dataclass` validator is sufficient and keeps `dependencies = []`. The project already chose a stdlib JSON-Schema subset validator for the actual contract schemas — the manifest is far simpler. |
| JSON manifest | YAML manifest parsed by PyYAML 6.x | Only if humans will hand-edit the manifest frequently and find JSON's comma/quote noise painful. PyYAML is not installed and would be the first non-stdlib runtime import in the tooling layer. JSON + a small schema comment block is the lower-friction choice given the existing dependency-free stance. |
| Stdlib triple-quoted f-string templates | Jinja2 3.x for readiness report generation | Only if the report template grows to >300 lines with complex conditionals/loops. The readiness report is a fixed-structure document mirroring PRD §10.1–10.4 — a few f-strings and a list comprehension are clearer than introducing a template engine dependency. |
| `subprocess` invocation of `run_v2_gates.py --json-summary` | Importing gate modules directly into the analyzer | Never prefer direct import for the analyzer. `subprocess` keeps the analyzer decoupled from test-module import side effects and matches the existing gate runner's isolation model. Direct import would couple closure tooling to PYTHONPATH wiring that already lives in `run_v2_gates.py`. |
| New `scripts/audit_v2_requirements.py` | Extending `check_v1_3_verification_artifacts.py` | Only if the v1.5 scope were a single milestone's artifact check. V2 acceptance closure spans the entire PRD §10 criteria set and all shipped packages/services, so a dedicated analyzer with a manifest is cleaner than overloading the v1.3-specific checker. Keep the v1.3 script as a precedent reference. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `jsonschema` (runtime dep) | The project deliberately ships a stdlib JSON-Schema subset validator (`schema_validation.py`). Adding `jsonschema` to validate the traceability manifest would be the first runtime dependency in a `dependencies = []` package and sets a precedent that breaks the composability/zero-dep invariant the closure work is supposed to verify. | Stdlib `json` + a `dataclass`-based manifest validator in `scripts/audit_v2_requirements.py`. |
| `PyYAML` | Not installed anywhere. Introducing it just to parse a traceability manifest that could be JSON adds a dependency for no architectural gain. The only existing YAML (`V2-ingest-manifest.yaml`) is consumed by the GSD tooling, not by shipped code. | JSON manifest (`acceptance/v2-traceability.json`). |
| `Jinja2` / `Mako` / any template engine | The readiness report is a fixed-structure Markdown document with ~4 sections. A template engine is overhead that adds a dependency and a learning curve for a document that mirrors PRD §10. | Stdlib f-string templates in `scripts/generate_v2_readiness_report.py`. |
| `rich` / `click` / `typer` | The existing CLI tools (`run_v2_gates.py`, `check_v1_3_verification_artifacts.py`) use bare `argparse` and plain `print`. Introducing a CLI framework would diverge from the established tooling style and add a dependency. | `argparse` + `print`, matching `run_v2_gates.py`. |
| A new `acceptance-service` or `acceptance` Python package with `pyproject.toml` | Acceptance closure is a build-time/CI-time concern, not a shipped runtime component. Packaging it would imply it is part of the V2 platform surface, which it is not. | Scripts in `scripts/` + a data artifact in `acceptance/`. No package, no `pyproject.toml`, no install step. |
| `coverage` / `pytest-cov` for requirement coverage | The PRD's "coverage" metric (§10.2: contract-log coverage ≥ 95%) is about contract-event pairing (`AgentTurn`+`AgentResult`), not line coverage. `contract_test_suite.coverage_report` already computes this. Line coverage would measure the wrong thing. | Existing `coverage_report.py` for contract-log coverage; the traceability manifest for requirement coverage. |
| A new database or state store for traceability | Traceability state is a single JSON file committed to the repo. It changes only when requirements move from `pending` to `validated`. A database would be persistent state for an inherently file-based, review-driven workflow. | `acceptance/v2-traceability.json` committed to git. |

## Stack Patterns by Variant

**If the traceability manifest needs to assert "test module X exists and defines test class Y":**
- Use `ast.parse` on the test file and walk for `ClassDef`/`FunctionDef` nodes.
- This is the same pattern `boundary_checks.py` already uses for import-root scanning.
- Do NOT import the test module (side effects, PYTHONPATH coupling).

**If a requirement's evidence is "gate G passes":**
- Record the gate name in the manifest (`evidence.kind = "gate"`, `path = "contract-test-suite"`).
- The analyzer runs `run_v2_gates.py --list` to confirm the gate exists, then checks the last `--json-summary` result.
- Do NOT re-run the gate inside the analyzer for every requirement — run gates once via `run_v2_gates.py`, then have the analyzer read the summary.

**If a requirement maps to a PRD §10.4 lawyer-trial human gate:**
- Mark `status: "human_gate"` in the manifest, not `pending` or `validated`.
- The analyzer reports human-gate requirements as "remaining human gates" rather than gaps.
- This is how Phase 5 (live WeCom UAT) and Phase 8 (five-workday trial) stay visible in the readiness report without being treated as code gaps.

**If gap closure adds new code to a shipped package:**
- The analyzer's `tomllib`-based dependency check reads every `pyproject.toml` and asserts `dependencies = []` (or the known-allowed list for services that legitimately need `aiohttp`/`hindsight-client`).
- This catches the scenario where gap closure accidentally introduces a runtime dependency, which would itself be a V2 acceptance failure.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| Python 3.11 (CI floor) | `tomllib` (stdlib since 3.11) | The CI workflow pins `python-version: "3.11"`. `tomllib` is available. Do not use 3.12+ stdlib features in closure scripts. |
| Python 3.14 (local dev) | All stdlib modules used | Local dev runs 3.14.6; closure scripts must stay 3.11-compatible since CI is the authority. |
| `run_v2_gates.py` (existing) | New `v2-acceptance-traceability` gate | The gate runner already supports arbitrary `Gate(name, command, pythonpath)` entries. The new gate needs no `pythonpath` (it runs a script, not unittest discovery). |
| `contract-test-suite` checkers | `scripts/audit_v2_requirements.py` | The analyzer can import `contract_test_suite.boundary_checks`, `privacy_scan`, `coverage_report`, `schema_validation` directly since they are stdlib-only and already on the `contract-test-suite` gate's PYTHONPATH. Alternatively invoke via subprocess to stay fully decoupled. |

## Integration with Existing V2 Gate Runner

The closure tooling integrates at three points, all additive:

1. **New gate entry** in `scripts/run_v2_gates.py:_gates()`:
   ```python
   Gate(
       "v2-acceptance-traceability",
       (py, "scripts/audit_v2_requirements.py", "--mode", "all", "--json-summary"),
   ),
   ```
   Placed **before** `compileall` so a traceability failure fails fast. No `pythonpath` needed — the analyzer is a standalone script.

2. **Readiness report generation** runs as a separate script (`scripts/generate_v2_readiness_report.py`) invoked manually at milestone close, NOT as a CI gate. It reads the gate summary JSON (produced by `run_v2_gates.py --json-summary`) plus the traceability manifest and writes `.planning/v2-ACCEPTANCE-READINESS.md`.

3. **Traceability manifest** (`acceptance/v2-traceability.json`) is the single source of truth that both the analyzer and the report generator read. `PROJECT.md` Active-requirement checkboxes are updated to match the manifest's `status` field during the closure milestone — the manifest is authoritative, the markdown checkboxes are the human-readable projection.

## Sources

- `scripts/run_v2_gates.py` — existing gate runner structure, `Gate` dataclass, `--json-summary` format (read in full)
- `scripts/check_v1_3_verification_artifacts.py` — precedent for stdlib-only traceability/audit closure pattern (read in full)
- `packages/contract-test-suite/src/contract_test_suite/` — `schema_validation.py`, `coverage_report.py`, `boundary_checks.py`, `privacy_scan.py`, `event_stream_replay.py`, `trial_acceptance.py` (evidence producers the analyzer invokes)
- `packages/platform-contract/pyproject.toml` — `dependencies = []` invariant
- `packages/contract-test-suite/pyproject.toml` — `dependencies = []` invariant
- `.github/workflows/v2-contract-gates.yml` — CI pins Python 3.11, runs `run_v2_gates.py`
- `docs/requirements/V2-PRD.md` §10 验收标准 (10.1–10.4), §12 开发顺序, §13 遗留风险 — acceptance criteria the traceability manifest must cover
- `.planning/PROJECT.md` — Active requirements list (11 unchecked items) that the manifest maps to evidence
- `.planning/milestones/v1.4-MILESTONE-AUDIT.md` — audit frontmatter format (`status: gaps_found` → `passed`) the readiness report mirrors
- Local environment: Python 3.14.6, no `jsonschema`/`PyYAML`/`Jinja2` installed — confirmed via `pip list` and import probes
- PyPI: `jsonschema` 4.26.0 (Jan 2026), `PyYAML` 6.x — verified latest versions for the "Alternatives Considered" section; recommended NOT to use either

---
*Stack research for: V2 acceptance closure — traceability, gap analysis, readiness reporting, CI gate verification*
*Researched: 2026-07-03*
