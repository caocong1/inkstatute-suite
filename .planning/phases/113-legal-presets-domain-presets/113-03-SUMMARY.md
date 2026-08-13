---
phase: 113-legal-presets-domain-presets
plan: 03
type: summary
created: 2026-08-14
---

# Plan 113-03 Summary — materialization script + token budget enforcement tests

## What was accomplished

Created the preset materialization script (`scripts/materialize_presets.sh`) that installs `presets/<domain>/` to `~/.agent-presets/<domain>/` atomically with read-only permissions, along with a smoke test script. Created the token budget enforcement test suite (`apps/flutter_app/test/presets/budget_enforcement_test.dart`) that locks the SKL-07 gate: legal-core catalog passes under 8000 chars (green), a synthetic 345-skill catalog is rejected (red), the budget is configurable, and the 345-skill full mount prohibition is explicitly asserted with a descriptive message.

### Task 1: materialize_presets.sh + test_materialize_presets.sh

- Created `scripts/materialize_presets.sh`:
  - `set -euo pipefail` strict mode.
  - Installs each `presets/<domain>/` to `~/.agent-presets/<domain>/` atomically (staging temp dir + `mv` rename).
  - Marks installed files read-only (`chmod -R a-w`) AFTER the move (mv needs write permission on the staging dir to update its `..` entry).
  - Restores write permissions on old target before `rm -rf` (read-only dirs block content deletion).
  - Read-only discipline documented in script comments: installed files are read-only, all customization goes through `presets/` source, upgrade = re-run the script, never edit installed files directly.
  - Supports `PRESETS_SRC` and `DEST` env var overrides for testing.
  - Resolves `PRESETS_SRC` relative to repo root if not absolute.
- Created `scripts/test_materialize_presets.sh`:
  - Smoke test using temp directories for `PRESETS_SRC` and `DEST` (never touches real `~/.agent-presets/`).
  - Creates a minimal test preset with `preset.yml` + `SKILL.md`, runs materialization, verifies files exist, verifies read-only enforcement (write should fail), verifies atomic re-run (idempotent overwrite).
  - `trap cleanup EXIT` ensures temp dirs are cleaned up.

### Task 2: Budget enforcement tests (TDD)

- Created `apps/flutter_app/test/presets/budget_enforcement_test.dart` with 4 test groups (9 tests total):
  - **Budget enforcement — legal-core green light**: legal-core 3-skill catalog passes under 8000 char budget (`passed == true`, `skillCount == 3`, `totalChars <= 8000`).
  - **Budget enforcement — synthetic 345-skill red light**: 345 synthetic SKILL.md files generated at test time in a temp directory; catalog fails under 8000 char budget (`passed == false`, `skillCount == 345`, `totalChars > 8000`).
  - **Budget enforcement — configurable budget**: same legal-core catalog passes at 8000, fails at 50, fails at 1; different budgets produce different pass/fail for the same catalog (proves the parameter controls the threshold).
  - **345-skill full mount prohibition**: explicit assertion that mounting all 345 skills is forbidden by SKL-07 and AGENTS.md decision 6, with a descriptive message explaining why. Also asserts the prohibition holds at the default budget (8000).
- Synthetic 345-skill catalog generated in `setUpAll()` via `Directory.systemTemp.createTempSync('synthetic_345')`, cleaned up in `tearDownAll()` with `chmod -R u+w` before deletion.
- Created `apps/flutter_app/test/presets/fixtures/synthetic_345_skills/.gitkeep` as a placeholder (actual 345 files are generated at test time, not committed).

## Files created/modified

### Created
- `scripts/materialize_presets.sh` (executable, 67 lines)
- `scripts/test_materialize_presets.sh` (executable, 83 lines)
- `apps/flutter_app/test/presets/budget_enforcement_test.dart` (197 lines, 9 tests)
- `apps/flutter_app/test/presets/fixtures/synthetic_345_skills/.gitkeep`

### Modified
- None (no existing files changed, no frozen directories touched)

## Test results

- **Budget enforcement tests**: 9 tests, all pass
  - legal-core green light: 2 tests (passes under 8000, totalChars positive)
  - synthetic 345-skill red light: 2 tests (fails under 8000, explicitly forbidden)
  - configurable budget: 3 tests (passes at 8000, fails at 50, fails at 1, same totalChars)
  - 345-skill prohibition: 2 tests (forbidden by SKL-07 + AGENTS.md decision 6, enforced at default budget)
- **Full flutter test suite**: 132 tests (131 pass + 1 skip), all pass
- **dart analyze**: No issues found
- **materialize_presets.sh smoke test**: PASS (file materialization, read-only enforcement, atomic re-run)

## V4 gate results

| Gate | Status | Message |
|------|--------|---------|
| dart-analyze | PASS | No issues found |
| flutter-test | PASS | All tests passed |
| engine-manifest | SKIP | Pin + cordis valid; engine-manifest.json not found (build engine first) |
| mock-e2e | PASS | All mock E2E tests passed |
| meta-test | PASS | All lib/ directories have test coverage |
| docx-golden | SKIP | docx golden not active until Phase 118 |

**All V4 gates passed.**

## Deviations from the plan

1. **Read-only marking order**: The plan's template marked the staging directory read-only BEFORE the `mv` (`chmod -R a-w "$staging"` then `mv "$staging" "$target"`). This fails on Linux because `mv` needs write permission on the moved directory to update its `..` entry. Fixed by marking read-only AFTER the move (`mv` first, then `chmod -R a-w "$target"`). Atomicity is preserved — the staging + rename is still atomic; only the read-only marking is deferred to after the move.

2. **Old target removal**: The plan's template used `rm -rf "$target"` directly. This fails on the second run because read-only directories block `rm` from deleting their contents. Fixed by restoring write permissions (`chmod -R u+w "$target"`) before `rm -rf` when the old target exists.

3. **PRESETS_SRC path resolution**: Added logic to resolve `PRESETS_SRC` relative to the repo root (via `SCRIPT_DIR`/`REPO_ROOT`) when it is not absolute, so the script works correctly regardless of the caller's working directory.

## Verification status

- [x] `scripts/materialize_presets.sh` exists, is executable, installs presets atomically with read-only permissions
- [x] `scripts/test_materialize_presets.sh` exists, is executable, passes smoke test
- [x] Script comments document the read-only discipline (read-only, atomic, never edit installed files)
- [x] Script supports `PRESETS_SRC` and `DEST` env var overrides
- [x] Materialization is atomic (staging temp dir + rename)
- [x] Installed files are read-only (`chmod -R a-w`)
- [x] Re-running the script overwrites atomically
- [x] Budget enforcement: legal-core ≤ 8000 chars → green (passed=true, skillCount=3)
- [x] Budget enforcement: synthetic 345-skill catalog → red (passed=false, totalChars > 8000)
- [x] Budget enforcement: budget is configurable (8000 → green, 50 → red, 1 → red)
- [x] 345-skill full mount prohibition assertion exists with descriptive message
- [x] Synthetic 345-skill catalog generated at test time in temp directory (not committed)
- [x] `flutter analyze` exits 0
- [x] `flutter test` exits 0
- [x] V4 gates all pass
- [x] No frozen directory modified
- [x] No real skill content from ai-for-china-legal (synthetic dummy SKILL.md files only)
- [x] No modifications to presets/legal-core/ or presets/legal-*/ (owned by Plans 113-01/113-02)
