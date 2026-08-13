---
phase: 113-legal-presets-domain-presets
reviewed: 2026-08-13T18:45:27Z
depth: standard
files_reviewed: 38
files_reviewed_list:
  - apps/flutter_app/lib/presets/preset_reader.dart
  - apps/flutter_app/lib/presets/budget_gate.dart
  - apps/flutter_app/lib/presets/engine_preset_smoke.dart
  - presets/legal-core/agent.cordis.yml
  - presets/legal-core/preset.yml
  - presets/legal-commercial/agent.cordis.yml
  - presets/legal-commercial/preset.yml
  - presets/legal-litigation/agent.cordis.yml
  - presets/legal-litigation/preset.yml
  - presets/legal-family/agent.cordis.yml
  - presets/legal-family/preset.yml
  - presets/legal-employment/agent.cordis.yml
  - presets/legal-employment/preset.yml
  - presets/legal-core/skills/citation-check/SKILL.md
  - presets/legal-core/skills/contract-review/SKILL.md
  - presets/legal-core/skills/legal-research/SKILL.md
  - presets/legal-commercial/skills/commercial-due-diligence/SKILL.md
  - presets/legal-commercial/skills/contract-drafting/SKILL.md
  - presets/legal-commercial/skills/shareholder-agreement/SKILL.md
  - presets/legal-litigation/skills/civil-lawsuit-prep/SKILL.md
  - presets/legal-litigation/skills/court-filing/SKILL.md
  - presets/legal-litigation/skills/evidence-organization/SKILL.md
  - presets/legal-family/skills/child-custody/SKILL.md
  - presets/legal-family/skills/divorce-settlement/SKILL.md
  - presets/legal-family/skills/inheritance-dispute/SKILL.md
  - presets/legal-employment/skills/employment-contract/SKILL.md
  - presets/legal-employment/skills/labor-dispute/SKILL.md
  - presets/legal-employment/skills/severance-negotiation/SKILL.md
  - scripts/materialize_presets.sh
  - scripts/test_materialize_presets.sh
  - apps/flutter_app/test/presets/preset_reader_test.dart
  - apps/flutter_app/test/presets/budget_gate_test.dart
  - apps/flutter_app/test/presets/budget_enforcement_test.dart
  - apps/flutter_app/test/presets/domain_presets_budget_test.dart
  - apps/flutter_app/test/presets/domain_presets_structure_test.dart
  - apps/flutter_app/test/presets/legal_core_structure_test.dart
  - apps/flutter_app/test/presets/engine_preset_smoke_test.dart
  - apps/flutter_app/test/presets/fixtures/synthetic_345_skills/.gitkeep
findings:
  critical: 0
  warning: 4
  info: 3
  total: 7
status: findings_found
---

# Phase 113: Code Review Report

**Reviewed:** 2026-08-13T18:45:27Z
**Depth:** standard
**Files Reviewed:** 38
**Status:** issues_found

## Summary

Phase 113 delivers 5 legal presets (legal-core + 4 domains), a PresetReader YAML parser, a BudgetGate token-budget enforcer, an engine smoke-test utility, and a materialization script. The guardrail completeness (all 6 segments + skill-loading directive) is verified present in every preset's persona. No `tool-ask-user` plugin row exists in any composition (DP-1 satisfied). `customSkillDirs` correctly points to each domain's materialized path. The 345-skill full-mount prohibition is explicitly tested. No frozen directories were modified. No secrets committed.

Four warnings were found: (1) the plan-mode section in all 5 presets still references the removed `ask_user_question` tool, creating contradictory guidance; (2) the materialization script's rm-then-mv sequence is not truly atomic despite the header claim; (3) the budget gate's `~` expansion uses `HOME` only, which is unset on Windows (the primary target platform), risking a false green light; (4) the engine smoke test never drains stderr, which can block the engine process on pipe-buffer fill.

## Warnings

### WR-01: Plan-mode section references removed `ask_user_question` tool in all 5 presets

**File:** `presets/legal-core/agent.cordis.yml:153,157` (same lines in all 5 presets)
**Issue:** The `plan-mode` config section (copied verbatim from the DSH `standard` preset) contains prose that instructs the model to use `ask_user_question`:
- Line 153: "Use ask_user_question only for user-owned choices or material ambiguity that inspection cannot answer."
- Line 157: "Do not paste the final plan as a plain reply or ask 'should I proceed?' through prose or ask_user_question."

The `tool-ask-user` plugin row has been removed from the composition (DP-1), so `ask_user_question` is not in the tool catalog. The persona (lines 46) establishes `[CLARIFY: …]` as the V4 clarification mechanism. These plan-mode instructions contradict the persona: they tell the model to use a tool that does not exist, creating conflicting guidance about how to handle ambiguity. If the model follows the plan-mode instruction, it will attempt to call `ask_user_question` and receive a tool-not-found error.
**Fix:** Replace `ask_user_question` references in the plan-mode section with the `[CLARIFY:]` convention. For example:
```yaml
        section: |
              Resolve discoverable facts by inspection. Use [CLARIFY: …] only for user-owned choices or material ambiguity that inspection cannot answer. Do not ask the user where code lives or how current behavior works when you can find out.
              ...
              Do not paste the final plan as a plain reply or ask "should I proceed?" through prose or [CLARIFY: …]. If review rejects it, incorporate the feedback and present again.
```

### WR-02: `materialize_presets.sh` rm-then-mv is not atomic; cross-filesystem staging breaks atomicity

**File:** `scripts/materialize_presets.sh:47-59`
**Issue:** The script header (lines 11-14) claims "atomic overwrite via staging + rename," but the implementation is:
```bash
staging=$(mktemp -d)           # creates in $TMPDIR (typically /tmp)
cp -r "$domain_dir." "$staging/"
rm -rf "$target"               # window: target missing
mv "$staging" "$target"        # may be cross-filesystem copy+delete
```
Two problems: (1) `rm -rf "$target"` followed by `mv` leaves a window where the target directory does not exist — if the process is interrupted (SIGKILL, power loss) between these operations, the preset directory is lost. (2) `mktemp -d` creates the staging directory in `$TMPDIR` (default `/tmp`), while the target is in `$HOME` — these are typically on different filesystems, so `mv` falls back to a recursive copy+delete, which is itself non-atomic and can leave partial state if interrupted.
**Fix:** Create the staging directory on the same filesystem as the target, and use `mv` (rename) for true atomicity:
```bash
staging=$(mktemp -d "$DEST/.tmp.XXXXXX")   # same filesystem as $DEST
cp -r "$domain_dir." "$staging/"
if [[ -d "$target" ]]; then
  chmod -R u+w "$target" 2>/dev/null || true
fi
mv "$staging" "$target"        # atomic rename on same filesystem
```
If the old target must be removed first (e.g., `mv` to existing dir merges on some systems), use a two-step rename: `mv "$staging" "$target.new" && rm -rf "$target" && mv "$target.new" "$target"` — still not fully atomic, but the `mv` rename is. Alternatively, use `rsync --delete` for atomic-ish replacement.

### WR-03: BudgetGate `~` expansion uses `HOME` only — broken on Windows (primary target)

**File:** `apps/flutter_app/lib/presets/budget_gate.dart:72`
**Issue:** The `~` expansion logic is:
```dart
final home = Platform.environment['HOME'] ?? '~';
```
AGENTS.md decision 10 states "Windows 优先" (Windows first). On Windows, the home directory is in the `USERPROFILE` environment variable, not `HOME` (which is typically unset outside Git Bash/WSL). When `HOME` is unset, `home` falls back to the literal `'~'`, so `dir.replaceAll('~', '~')` is a no-op. The path `~/.agent-presets/legal-core/skills` is not expanded and does not exist, so `dirObj.existsSync()` returns false (line 78) and the directory is silently skipped. The gate returns `skillCount: 0, totalChars: 0, passed: true` — a false green light with zero skills scanned. DSH itself uses Node.js `os.homedir()` which respects `USERPROFILE` on Windows, so the Dart gate's expansion is inconsistent with the engine's.
**Fix:**
```dart
final home = Platform.environment['HOME'] ??
    Platform.environment['USERPROFILE'] ??
    '~';
```

### WR-04: Engine smoke test never drains stderr — pipe buffer fill can block engine

**File:** `apps/flutter_app/lib/presets/engine_preset_smoke.dart:317-327`
**Issue:** The `_driveAcpSession` method listens to `process.stdout` but never consumes `process.stderr`. The comment on line 317 says "collect stderr for diagnostics" but no stderr subscription exists. On the real engine path, if DSH writes warnings/errors to stderr, the OS pipe buffer (typically 64 KB on Linux) can fill up, causing the engine process to block on its next stderr write. This blocks the engine indefinitely, causing the ACP session to time out. The `_waitForResponse` polling loop would then throw `TimeoutException`, which is caught and returns `null` (structural fallback) — masking the real cause.
**Fix:** Add a stderr drain:
```dart
final stderrBuffer = <String>[];
process.stderr
    .transform(utf8.decoder)
    .transform(const LineSplitter())
    .listen((line) {
  stderrBuffer.add(line);
});
```
Then include `stderrBuffer.join('\n')` in the error details or the `SmokeResult.details` for diagnostics.

## Info

### IN-01: `PresetReader.parseComposition` only captures top-level plugin IDs, not nested group plugins

**File:** `apps/flutter_app/lib/presets/preset_reader.dart:50,111-137`
**Issue:** The docstring for `PresetComposition.pluginIds` (line 50) says "All plugin `id` values in the composition, in document order." However, the parser only iterates the top-level YAML list (line 111). Group nodes (`planning`, `compaction`, `delegation`) have nested `config` lists containing additional plugin rows (e.g., `plan-mode`, `compaction-basic`, `tool-subagent-control`). These nested IDs are not captured. `hasPlugin('plan-mode')` returns false even though `plan-mode` is in the composition. This is not a functional bug for the current tests (which only check top-level plugins like `persona`, `skill-filesystem`, `tool-ask-user`), but the docstring is misleading.
**Fix:** Either recurse into group `config` lists to capture nested IDs, or update the docstring to say "All top-level plugin `id` values."

### IN-02: Engine smoke test hardcodes developer-machine-specific paths

**File:** `apps/flutter_app/lib/presets/engine_preset_smoke.dart:74-78`
**Issue:** The DSH bin path and root are hardcoded:
```dart
static const String _dshBinPath =
    '/home/sorawatcher/deepseek-harness/packages/examples/acp-demo/lib/bin.js';
static const String _dshRoot = '/home/sorawatcher/deepseek-harness';
```
These paths only exist on the developer's machine. In CI or other environments, the real engine path always fails (bin file not found), so the test silently falls back to structural verification. This is acceptable behavior (the fallback is by design), but the hardcoded paths make the real-engine path non-portable. Consider deriving the DSH root from an environment variable (e.g., `DSH_ROOT`) or a config file.
**Fix:** Read from environment with fallback:
```dart
static final String _dshRoot =
    Platform.environment['DSH_ROOT'] ?? '/home/sorawatcher/deepseek-harness';
```

### IN-03: `_stripJsTags` regex requires a space after `!!js`

**File:** `apps/flutter_app/lib/presets/preset_reader.dart:259`
**Issue:** The regex `!!js [^\n]*` requires a literal space after `!!js`. If a YAML file ever uses `!!js` without a trailing space (e.g., `!!js"expression"` or `!!js'expression'`), the tag would not be stripped and `loadYaml` would throw. DSH's current formatting always includes a space, so this is not a live bug, but it is a minor robustness gap.
**Fix:** Use `!!js\s+[^\n]*` or `!!js[^\n]*` to be more permissive.

---

_Reviewed: 2026-08-13T18:45:27Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
