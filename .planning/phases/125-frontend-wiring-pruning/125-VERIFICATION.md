# Phase 125 Verification

**Date:** 2026-08-16
**Phase:** 125 — Frontend Wiring & V3 Pruning
**Status:** ✅ All automated gates passed; Task 5 manual check deferred to Phase 127

## Verification Results

### 1. Package type checks and tests

```bash
cd packages/ui-core && bunx tsc --noEmit && bunx vitest run
```
- tsc: 0 errors
- vitest: 15 files, 186 tests, 0 failures

```bash
cd apps/desktop && bunx tsc --noEmit && bunx vitest run
```
- tsc: 0 errors
- vitest: 6 files, 36 tests, 0 failures

### 2. Rust check and tests

```bash
cd apps/desktop/src-tauri && cargo check && cargo test
```
- cargo check: green
- cargo test: 85 tests pass (71 unit + 8 ACP + 2 history + 1 mapper + 3 credentials), 5 ignored (real-engine)

### 3. V5 gates

```bash
node scripts/gates/v5/run-gates.mjs
```
- `[PASS] engine-assembly`
- `[PASS] event-mapping`
- 2 passed, 0 failed

### 4. Design system fidelity

```bash
diff <(tr -d '\r' < /Users/dongli/Workspace/lawyer-desktop/src/components/settings/SettingsPanel.css) \
     apps/desktop/src/components/SettingsPanel.css
```
- PASS: byte-identical (LF-normalized)

```bash
diff <(tr -d '\r' < /Users/dongli/Workspace/lawyer-desktop/src/themes/molv-tokens.css) \
     packages/ui-core/src/themes/molv-tokens.css
```
- PASS: identical (LF-normalized)

### 5. Reducer and component immutability

```bash
git diff --quiet pre-125-pruning HEAD -- packages/ui-core/src/event-reducer.ts
```
- PASS: reducer untouched

```bash
for f in ChatPanel DocPreview ConversationDrawer TitleBar HomePage MentionComposer CitationPanel AgentTracePanel MessageFeedback WorkflowProgressSteps ClarificationCard; do
  git diff --quiet pre-125-pruning HEAD -- "packages/ui-core/src/components/$f.tsx"
done
```
- PASS: all 11 ui-core components untouched

### 6. Security constraints

```bash
grep -rn 'get_provider_key\|read_key' apps/desktop/src-tauri/src/commands/credentials.rs
```
- PASS: no output (no key read command)

### 7. Pruning stats

```
git diff --stat pre-125-pruning HEAD -- apps/desktop packages/ui-core
```
- 54+ files changed
- ~7,545 lines deleted (V3 pruning)
- ~1,200 lines added (V5 engine commands, settings, workspace, transport)

### 8. Manual UI check (Task 5)

**Deferred to Phase 127** — requires `bunx tauri dev` with real engine assembly and API key. The 6 manual checks:
1. HomePage renders with correct font/colors
2. Settings tabs work, keys can be entered, connection test returns Chinese result
3. Sending a message streams text, tool timeline, and progress steps
4. Stop interrupts immediately
5. Three theme variants work
6. Conversation drawer lists history sessions

## Phase 125 Completion

All automated verification checks pass. Phase 125 is complete pending the manual UI check, which is deferred to Phase 127 integration testing where a real engine will be available.

**Phase 126 may proceed.**
