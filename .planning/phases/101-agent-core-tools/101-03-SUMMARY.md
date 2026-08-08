# Plan 101-03 Summary: Word Track-Changes Document Generation

**Phase**: 101 (agent-core-tools)
**Wave**: 2
**Requirements**: CORE-03 (Word native track-changes docx — import TrackChangesBuilder, don't rewrite)
**Status**: COMPLETE — Self-Check: PASSED

## What Was Done

### Task 101-03-01: Adapt TrackChangesBuilder for injectable review items

**Deviation**: The plan called for modifying `contract_review_trackchanges.py` to
parameterize `process()` with an optional `review_items` parameter. However, the
script lives in the sibling `lawfirm-profile` repository, and the pre-write code
guard blocks edits to files outside the active project root
(`inkstatute-suite`). 

**Resolution**: Instead of modifying the original script, the `document_generate`
tool uses a monkey-patching approach:
1. Loads the module via `importlib.util.spec_from_file_location()`
2. Temporarily replaces `module.REVIEW_ITEMS` with the injected items
3. Temporarily replaces `module.REVIEWER` if a custom reviewer is provided
4. Calls `builder.process()` (which iterates over the now-patched `REVIEW_ITEMS`)
5. Restores the original `REVIEW_ITEMS` and `REVIEWER` in a `finally` block

This achieves the same effect as parameterizing `process()` without modifying
the original file. The approach is safe because:
- The patch is scoped to a single `process()` call (try/finally restoration)
- The original script's `main()` entry point is unaffected
- The module is loaded fresh each time (no cross-contamination between calls)

### Task 101-03-02: Implement document_generate tool

Created `packages/agent-core/src/inkstatute_agent_core/tools/document_generate.py`:

- `create_document_generate_tool(sandbox, emitter, script_path)` factory
- Lazy-imports `TrackChangesBuilder` via `importlib` (package importable without lxml)
- Validates input/output paths via `PathSandbox`
- Constructs `TrackChangesBuilder(input_docx_path)`, calls `process()`, calls `save()`
- Emits `artifact.created` with `kind=ArtifactKind.TRACKCHANGES_DOCX`
- `Artifact` has UUID `artifact_id`, `file://` URI, correct MIME type
- `ToolResult.metadata` includes `artifact_id`, `output_path`, `review_results`
- `DOCUMENT_GENERATE_TOOL_DEFINITION` — OpenAI function-calling format, name=`generate_review_docx`

### Task 101-03-03: OOXML track-changes verification

Created `packages/agent-core/tests/test_trackchanges_verification.py` — 15 tests
verifying the generated docx contains native Word track changes OOXML elements:

- `<w:ins>` elements with `w:author` and `w:date` attributes
- `<w:del>` elements with `w:author` and `w:date` attributes
- `<w:delText>` elements (deleted text)
- `word/comments.xml` exists with `<w:comment>` elements
- `<w:commentRangeStart>`, `<w:commentRangeEnd>`, `<w:commentReference>`
- `[Content_Types].xml` has `Override` for `/word/comments.xml`
- `word/_rels/document.xml.rels` has `Relationship` targeting `comments.xml`
- Default reviewer "乙方律师审查" appears in output
- Artifact kind is `trackchanges_docx`, URI is `file://` reference

### Task 101-03-04: Register in builtin_registry

Extended `packages/agent-core/src/inkstatute_agent_core/tools/builtin_registry.py`:
- Added `trackchanges_script_path` parameter
- Registers `generate_review_docx` when `emitter` is provided
- Updated `tools/__init__.py` re-exports

### Task 101-03-05: All 38 gates green

`python scripts/run_v2_gates.py` exits 0 — all 38 gates pass.

## Commits

| Hash | Description |
|------|-------------|
| `41a476a` | feat(101-03): document_generate tool — Word track-changes docx generation |
| `a56fd55` | feat(101-03): register document_generate in builtin_registry + re-exports |

## Files Created (3)
- `packages/agent-core/src/inkstatute_agent_core/tools/document_generate.py`
- `packages/agent-core/tests/test_document_generate_tool.py` (16 tests)
- `packages/agent-core/tests/test_trackchanges_verification.py` (15 tests)

## Files Modified (3)
- `packages/agent-core/src/inkstatute_agent_core/tools/builtin_registry.py` (additive — document_generate registration)
- `packages/agent-core/src/inkstatute_agent_core/tools/__init__.py` (re-exports)
- `packages/agent-core/tests/test_builtin_registry.py` (4 new tests)

## Test Counts
- **35 new tests** (16 document_generate + 15 trackchanges verification + 4 builtin_registry)
- **522 total agent-core tests** (487 from 101-01/101-02 + 35 new)
- **All 38 gates green**

## Acceptance Criteria

- [x] `create_document_generate_tool(sandbox, emitter, script_path)` returns a callable
- [x] Handler lazy-imports `TrackChangesBuilder` via `importlib`
- [x] If lazy import fails, returns error `ToolResult` (not a crash)
- [x] Handler calls `TrackChangesBuilder()`, `process()`, `save()`
- [x] Handler does NOT rewrite TrackChangesBuilder — imports and calls it
- [x] `artifact.created` emitted with `kind="trackchanges_docx"` and `file://` URI
- [x] `Artifact` has UUID `artifact_id`, correct MIME type, URI (no raw content)
- [x] Input/output paths validated via `PathSandbox`
- [x] `ToolResult.metadata` includes `artifact_id`, `output_path`, `review_results`
- [x] `DOCUMENT_GENERATE_TOOL_DEFINITION` is valid OpenAI format with `name="generate_review_docx"`
- [x] Tests cover: successful generation, artifact event, path validation, missing file, lazy import failure, empty review items, comment-only items
- [x] Generated docx is valid zip with `word/document.xml`
- [x] OOXML track-changes verified: `w:ins`, `w:del`, `w:delText`, `w:comment`, comment range markers
- [x] `[Content_Types].xml` has Override for comments.xml
- [x] `word/_rels/document.xml.rels` has Relationship targeting comments.xml
- [x] `create_builtin_registry()` registers `generate_review_docx` when emitter provided
- [x] All 38 gates green

## Deviations

1. **Task 101-03-01**: Original script not modified (sibling repo, blocked by pre-write guard).
   Used monkey-patching of `module.REVIEW_ITEMS` instead. Functionally equivalent —
   the tool injects review items at call time without modifying the original file.

## Human Gates

- **HG-4 (修订稿质量)**: NOT auto-closed. The verification test checks OOXML structure
  (w:ins, w:del, w:comment elements), not lawyer usability. A lawyer must confirm the
  generated docx is usable for external negotiation.
