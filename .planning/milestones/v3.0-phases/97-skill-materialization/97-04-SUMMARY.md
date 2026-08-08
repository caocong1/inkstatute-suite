# Plan 97-04 Summary — CLI + E2E Tests + Three-Separation Verification + Phase Completion

**Plan**: 97-04 — CLI + e2e tests + three-separation verification + phase completion
**Phase**: 97 (skill-materialization)
**Wave**: 3 (depends on 97-01, 97-02, 97-03 — all complete)
**Requirements**: SKILL-05, SKILL-06, SKILL-09
**Status**: COMPLETE

## Tasks Executed

| Task | Description | Commit | Result |
|------|-------------|--------|--------|
| 97-04-01 | Implement CLI entry point (materialize, inject-body, routing-manifest) | `ffba975` | PASS |
| 97-04-02 | Verify gate registration (done in 97-01) + fix gateway test_gate_count 31→36 | `7b3cd6c` | PASS |
| 97-04-03 | Hermes ACP integration test (materialize → hermes acp --check) | `0e5aad6` | PASS |
| 97-04-04 | Three-separation e2e verification (15 tests) | `585d6ea` | PASS |
| 97-04-05 | Run full gate suite — all 36 gates green | (verification) | PASS |
| 97-04-06 | Phase 97 completion — SUMMARY.md, STATE.md, ROADMAP.md, REQUIREMENTS.md | (this commit) | PASS |

## What Was Built

### CLI Entry Point (Task 97-04-01)

**Files modified:**
- `packages/skill-materializer/src/inkstatute_skill_materializer/cli.py` — Full CLI implementation replacing the stub. Three subcommands:
  - `materialize --target hermes|acp --index <path> --output <path> [--profile <name>]` — Materializes skills to Hermes profile or ACP agent skills layout
  - `inject-body --skill-id <id> --index <path> --budget <tokens> [--chars-per-token <n>]` — Reads a skill body on-demand and applies budget-constrained trimming, prints JSON summary
  - `routing-manifest --index <path> --output <path>` — Produces a metadata-only routing manifest
- `packages/skill-materializer/src/inkstatute_skill_materializer/__main__.py` — Updated to match skill-index pattern (sys.exit(main()))

**New test file:**
- `packages/skill-materializer/tests/test_cli.py` — 17 CLI smoke tests:
  - Help tests (5): no-command, --help, materialize --help, inject-body --help, routing-manifest --help
  - Error handling (2): invalid --target, missing required args
  - Materialize Hermes (2): produces profile layout, custom profile name
  - Materialize ACP (1): produces Claude Code plugin layout with plugin.json + rewrite-report.json
  - Inject-body (2): returns JSON summary, skill-not-found error
  - Routing-manifest (2): produces JSON, no body fields
  - Index-not-found (3): error handling for all three subcommands

### Gate Registration Verification (Task 97-04-02)

The `skill-materializer` gate was already registered in plan 97-01 (commit `e998ccb`). This task verified all acceptance criteria:
- `skill_materializer_src` path variable exists in `scripts/run_v2_gates.py`
- `Gate("skill-materializer", ...)` entry exists with correct PYTHONPATH
- `packages/skill-materializer/src` is in the compileall paths
- `test_audit_v2_requirements.py` has `assertIn("skill-materializer", gate_names)` and `assertEqual(len(gate_names), 36)`
- `gate-coverage` meta-test passes (auto-discovers `packages/skill-materializer/src`)
- `python scripts/run_v2_gates.py --list` shows 36 gates including `skill-materializer`

**Fix applied:** Updated `services/gateway/tests/test_integration.py` `test_gate_count_is_31` → `test_gate_count_is_36` (the test was still expecting 31 gates from before Phase 96/97 additions).

### Hermes ACP Integration Test (Task 97-04-03)

**New test file:**
- `packages/skill-materializer/tests/test_hermes_acp_integration.py` — 3 integration tests:
  - `test_materialized_profile_loadable_by_hermes` — Materializes 3 fixture skills to a temp Hermes profile, sets `HERMES_HOME`, runs `hermes acp --check`, asserts exit code 0. This is the **实测验证** (empirical verification) for success criterion 1.
  - `test_materialized_skills_have_skill_md` — Verifies each materialized skill directory has a loadable SKILL.md
  - `test_does_not_modify_source_repos` — Verifies source repo file hashes are unchanged after materialization (read-only enforcement)

The test skips with `unittest.SkipTest` if the `hermes` binary is not found in PATH.

### Three-Separation E2E Verification (Task 97-04-04)

**New test file:**
- `packages/skill-materializer/tests/test_e2e_three_separation.py` — 15 end-to-end tests with 5 fixture skills (varying token estimates, some with scripts/, some with host assumptions):

  **Routing manifest (3 tests):**
  - No body/content/raw_text/frontmatter fields in any record
  - Contains all 5 skills from fixture index
  - No body text from source SKILL.md files appears in manifest

  **Hermes materialization (2 tests):**
  - Symlinks point to source repo paths (not routing manifest)
  - Each materialized skill has a loadable SKILL.md

  **ACP materialization (3 tests):**
  - Rewritten SKILL.md files differ from source (host assumptions rewritten)
  - Non-rewritten skills are symlinked (zero-copy)
  - Rewrite report exists with total_rewrites > 0

  **Body injection with budget (3 tests):**
  - Injection with budget=5000 stays within budget
  - Skills larger than budget have non-empty trimmed_sections
  - Protected sections (frontmatter, description) are preserved

  **Tool dependencies metadata-only (2 tests):**
  - required_scripts is a list of string names, not file contents
  - No body text from source appears in routing manifest

  **Self-built core path (2 tests):**
  - read_skill_body() works without any materialization step
  - read_skill_body() reads from source path in index, not from materialized output

  **Full flow integration (1 test):**
  - Complete pipeline: index → routing manifest → on-demand body read → trimmed injection, with determinism verification

### Full Gate Suite (Task 97-04-05)

All 36 gates green:
- skill-materializer: 127 tests (92 from 97-01/97-02 + 17 CLI + 3 Hermes integration + 15 e2e)
- All other gates: no regressions
- compileall: all source files compile including packages/skill-materializer/src
- gate-coverage: all packages/*/src and services/*/src covered

## Acceptance Criteria Results

### Task 97-04-01: CLI entry point
- [x] `python -m inkstatute_skill_materializer materialize --target hermes --index <path> --output <path>` runs the Hermes materializer
- [x] `python -m inkstatute_skill_materializer materialize --target acp --index <path> --output <path>` runs the ACP materializer
- [x] `python -m inkstatute_skill_materializer inject-body --skill-id <id> --index <path> --budget <tokens>` runs the body injector and prints the result
- [x] `python -m inkstatute_skill_materializer routing-manifest --index <path> --output <path>` produces the metadata-only routing manifest
- [x] `--help` shows usage for each subcommand
- [x] Invalid arguments produce clear error messages with non-zero exit code
- [x] CLI smoke tests pass (17 tests)

### Task 97-04-02: Gate registration
- [x] `skill_materializer_src` path variable exists in `scripts/run_v2_gates.py`
- [x] `Gate("skill-materializer", ...)` entry exists with correct PYTHONPATH
- [x] `packages/skill-materializer/src` in compileall paths
- [x] `test_audit_v2_requirements.py` gate count assertion is 36
- [x] `assertIn("skill-materializer", gate_names)` present
- [x] `gate-coverage` meta-test passes
- [x] `python scripts/run_v2_gates.py --list` shows 36 gates including `skill-materializer`

### Task 97-04-03: Hermes ACP integration test
- [x] Test creates temp directory, materializes fixture skills to `temp_dir/profiles/test/skills/`, sets `HERMES_HOME=temp_dir`, runs `hermes acp --check`
- [x] Test asserts `hermes acp --check` exits 0 (profile is loadable)
- [x] Test skips with `unittest.SkipTest` if `hermes` binary not found in PATH
- [x] Test cleans up temp directory after execution
- [x] Test does NOT modify any source repo files (read-only vendoring)
- [x] Integration test is part of the `skill-materializer` gate

### Task 97-04-04: Three-separation e2e verification
- [x] Test loads fixture skill-index.json with 5 skills (varying token estimates, some with scripts/, some with host assumptions)
- [x] Test produces routing manifest and asserts: no `body`, `content`, `raw_text`, or `frontmatter` fields
- [x] Test materializes to Hermes layout and asserts: symlinks point to source repo paths
- [x] Test materializes to ACP layout and asserts: rewritten SKILL.md files differ from source, non-rewritten skills are symlinked
- [x] Test injects body with `budget_tokens=5000` and asserts: `injected_token_estimate <= 5000`, `trimmed_sections` non-empty for skills > budget
- [x] Test asserts: `required_scripts` is a list of script names (strings), not contents
- [x] Test asserts: `read_skill_body()` reads directly from source path without materialization

### Task 97-04-05: Full gate suite
- [x] `python scripts/run_v2_gates.py` exits 0 (all 36 gates green)
- [x] `python scripts/run_v2_gates.py --list` shows 36 gates
- [x] `gate-coverage` meta-test passes
- [x] `compileall` gate passes (all source files compile)
- [x] No regressions in any pre-existing gate

### Task 97-04-06: Phase 97 completion
- [x] `STATE.md` `stopped_at` updated to "Phase 97 complete"
- [x] `STATE.md` progress counts updated (completed_plans += 1 → 47, completed_phases += 1 → 10)
- [x] `ROADMAP.md` Phase 97 marked `[x]` complete
- [x] `REQUIREMENTS.md` SKILL-05, SKILL-06, SKILL-09 marked `[x]` Complete
- [x] `REQUIREMENTS.md` traceability table updated for SKILL-05, SKILL-06, SKILL-09
- [x] Next command points to `/gsd-plan 98` for Phase 98

## Phase 97 Success Criteria Verification

All 6 success criteria from ROADMAP.md verified:

1. **物化器能把语料落到 Hermes profile 布局（symlink 优先、脚本类 copy），且 `hermes acp` 能加载物化产物中的 skill（实测验证，不是推断）** — VERIFIED by `test_hermes_acp_integration.py::test_materialized_profile_loadable_by_hermes` which materializes fixture skills and runs `hermes acp --check` (exit 0).

2. **物化器能把语料落到 ACP agent skills 布局，并按目标后端改写宿主假设** — VERIFIED by `test_e2e_three_separation.py::test_acp_rewritten_skills_differ_from_source` which asserts rewritten SKILL.md differs from source, trigger patterns and ask_user are rewritten.

3. **自研 core 路径不需物化——直接读索引 + 按需读正文** — VERIFIED by `test_e2e_three_separation.py::test_on_demand_body_read_without_materialization` and `test_on_demand_body_read_uses_source_path` which assert read_skill_body() works without any materialization step.

4. **元数据 / 正文 / 工具依赖三分离在代码中体现** — VERIFIED by `test_e2e_three_separation.py` tests: routing manifest has no body fields, bodies read on-demand from source, required_scripts is metadata-only string list.

5. **正文注入受上下文预算约束** — VERIFIED by `test_e2e_three_separation.py::test_body_injection_within_budget` (injected <= 5000) and `test_body_injection_trims_large_skills` (trimmed_sections non-empty).

6. **`solutions/lawfirm/manifest.json` 不再包含 4 条手写 skill 元数据** — VERIFIED in plan 97-03 (commit `f608431`), all affected gates green.

## Deviations

1. **Gate registration already done in 97-01**: The `skill-materializer` gate was registered in plan 97-01 (commit `e998ccb`) because the `gate-coverage` meta-test enforces that every `packages/*/src` directory must be covered by a gate. This task verified the registration is correct and fixed the cascading `test_gate_count_is_31` test in the gateway integration tests.

2. **Gateway test_gate_count_is_31 → 36**: The `test_gate_count_is_31` test in `services/gateway/tests/test_integration.py` was still expecting 31 gates (from before Phase 96/97 additions). Updated to `test_gate_count_is_36` to match the current 36-gate count. This was a pre-existing issue noted as a deviation in 97-03.

3. **Routing manifest size comparison adjusted**: The initial e2e test asserted the routing manifest is smaller than source SKILL.md files. This holds for real-world skills (2K-20K tokens) but not for tiny fixture skills where JSON overhead exceeds body size. Changed to verify no body text from source appears in the manifest instead.

## Self-Check: PASSED

- [x] All tasks executed and committed (6 tasks, 4 commits + 1 verification + 1 this commit)
- [x] All acceptance criteria PASS
- [x] CLI implemented (materialize, inject-body, routing-manifest subcommands)
- [x] E2e tests pass (Hermes + ACP materialization, 15 e2e + 3 integration tests)
- [x] Three-separation verified in e2e (routing manifest no bodies, on-demand body read, tools metadata-only)
- [x] All 6 success criteria verified
- [x] 36 gates green
- [x] SKILL-05, SKILL-06, SKILL-09 marked complete
- [x] Phase 97 marked complete in STATE.md and ROADMAP.md
- [x] SUMMARY.md with Self-Check: PASSED
