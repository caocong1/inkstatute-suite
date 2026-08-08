---
phase: 102
slug: legal-guardrail-port
status: complete
created: 2026-08-08
review_depth: standard
---

# Phase 102 — Code Review

## Summary

Phase 102 ports the legal guardrail subsystem from the Rust `lawyer-desktop` to the Python `agent-core`. The port covers prompt assembly (CORE-05), tool leak detection (CORE-06), citation audit (CORE-07), four guardrails (CORE-08), and skill_candidate safety (SAFE-01). The code is well-structured, faithfully ports the Rust logic with golden fixture tests, and the 310 Phase 102 tests all pass.

**One Critical finding** was identified: the SAFE-01 safety invariant in `create_skill_candidate()` can be bypassed with falsy non-`False` values (`0`, `None`, `""`, `[]`). The guard check uses `is False` (identity) instead of a truthiness check, so `requires_human_review=0` silently produces a candidate with `requires_human_review=False`. This is a legal safety-critical defect.

Three Warning-level findings relate to: (1) `emit_citation_recorded` double-buffering (side-channel + direct yield), (2) error tool results being collected as retrieval evidence, and (3) the turn loop not enforcing prompt-level guardrails (research-gate, ask-user) at runtime. Several Info-level suggestions are also documented.

## Findings

### Critical

#### C-1: SAFE-01 bypass — `create_skill_candidate` accepts falsy non-`False` values for `requires_human_review`

**File:** `guardrails.py:381`
**Severity:** Critical
**Requirement:** SAFE-01

The factory's guard check uses identity comparison against `False`:

```python
if kwargs.get("requires_human_review") is False:
    raise ValueError(...)
requires_human_review = bool(kwargs.pop("requires_human_review", True))
```

The `is False` check only catches the exact singleton `False`. Any other falsy value (`0`, `None`, `""`, `[]`) passes the guard, then `bool()` converts it to `False`, producing a `SkillCandidate` with `requires_human_review=False` — directly violating SAFE-01.

**Verified by execution:**
```
BUG: created with requires_human_review=False (input was 0)
BUG: created with requires_human_review=False (input was None)
BUG: created with requires_human_review=False (input was empty string)
BUG: created with requires_human_review=False (input was [])
```

**Fix:** Change the guard to reject all falsy values:
```python
if not kwargs.get("requires_human_review", True):
    raise ValueError(...)
```

Or strictly require `True`:
```python
if kwargs.get("requires_human_review", True) is not True:
    raise ValueError(...)
```

**Note:** `assert_skill_candidate_safety()` (line 362) correctly uses `not candidate.get("requires_human_review", False)`, so the external-dict check is sound. The bypass is only in the factory constructor.

### Warning

#### W-1: `emit_citation_recorded` uses side-channel buffer but turn loop yields directly — fragile design

**File:** `event_emitter.py:456`, `turn_loop.py:374`
**Severity:** Warning

`emit_citation_recorded()` appends the event to `_side_channel_events` (like `emit_artifact_created` and `emit_elicitation_requested`), but the turn loop at `turn_loop.py:374` yields the return value directly:

```python
yield emitter.emit_citation_recorded(citation_audit.items)
```

The side-channel copy is never drained (the turn loop returns after the final round). Currently no double-emission occurs, but this is fragile: if a future code path drains the side channel after the citation audit, the `citation.recorded` event would be emitted twice (same event object, same seq). The `artifact.created` and `elicitation.requested` events are correctly drained from the side channel during tool execution (line 237), but `citation.recorded` is not — it's in the final round.

**Fix:** Either (a) remove the `self._side_channel_events.append(event)` line from `emit_citation_recorded` since the turn loop yields it directly, or (b) have the turn loop drain the side channel instead of yielding directly, for consistency with the other side-channel events.

#### W-2: Error tool results collected as retrieval evidence for citation audit

**File:** `turn_loop.py:256, 320, 458-483`
**Severity:** Warning

When a tool execution fails (either via `result.error` or an exception), the error content is appended to `current_messages` as a tool result message, and the tool name is appended to `tool_result_names`. The `_collect_retrieval_evidence()` function then collects these error messages as retrieval evidence:

```
Retrievals: [('legal_search', 'Error: connection failed')]
```

The citation audit searches for citation fragments in all retrieval evidence, including error messages. While error messages are unlikely to contain exact citation text (so false "retrieved" status is improbable), this is not clean — error results should not be treated as retrieval evidence.

**Fix:** In `_collect_retrieval_evidence()`, skip tool result messages whose content starts with `"Error:"`, or track error status alongside tool results and exclude them from retrieval evidence collection.

#### W-3: Turn loop does not enforce prompt-level guardrails (research-gate, ask-user) at runtime

**File:** `turn_loop.py`
**Severity:** Warning
**Requirement:** SAFE-04

The turn loop enforces Guardrails 3 (citation audit) and 4 (de-AI polish) at runtime — they always execute before `message.completed`. However, Guardrails 1 (research-gate) and 2 (ask-user) are only enforced at prompt assembly time via `build_system_prompt()` + `enforce_research_gate()` / `enforce_ask_user_mandate()`. The turn loop itself never calls these enforcement functions (confirmed: `enforce_research_gate`, `enforce_ask_user_mandate`, and `verify_guardrails` do not appear in `run_turn` source).

If `run_turn()` is called directly with messages that don't include a system prompt containing the research-gate section, the turn loop will proceed without error. The guardrails are non-bypassable only if the integration layer always uses `build_system_prompt()` — but there is no runtime assertion in the turn loop to verify this.

**Fix:** Consider adding an optional `mode: AgentMode | None = None` parameter to `run_turn()`. When provided, the turn loop could extract the system prompt from `messages[0]` and call `verify_guardrails()` at startup, raising `ValueError` if guardrails are missing. When `None` (testing/fixture mode), the check is skipped.

#### W-4: `_run_citation_audit` always passes `None` for law_library — "verified" status never achieved in turn loop

**File:** `turn_loop.py:499`
**Severity:** Warning

The turn loop's `_run_citation_audit()` hardcodes `None` for the `law_library` parameter:

```python
return await _audit(text, retrievals, None)
```

This means the citation audit in the turn loop can only produce "retrieved" or "unverified" statuses — never "verified" (which requires a local law library lookup). The `LawLibrary` protocol and the full verification path exist in `citations/verify.py` but are never exercised in production. This is a known limitation (the law library integration is a future phase), but it should be documented.

**Fix:** Add a `law_library` parameter to `run_turn()` (defaulting to `None`) and pass it through to `_run_citation_audit()`, so future phases can wire in the library without modifying the turn loop.

### Info

#### I-1: Fallback citation audit in `guardrails.py` is dead code

**File:** `guardrails.py:48-57, 174-242, 264-266`

The `_CITATIONS_AVAILABLE` flag is always `True` now that the `citations` sub-package exists. The fallback `_fallback_citation_audit()` function and the fallback `CitationAudit` / `CitationAuditItem` dataclasses are never used. This is 80+ lines of dead code. Consider removing it or marking it with `# pragma: no cover` and a comment that it's retained for defensive fallback.

#### I-2: Fallback case-number regex only matches fullwidth brackets

**File:** `guardrails.py:168-170`

`_FALLBACK_CASE_NUMBER_RE` uses `（(\d{4})）` (fullwidth only), while the full extractor in `extract.py:80-82` matches both fullwidth and halfwidth via `[（(]\d{4}[）)]`. This discrepancy is moot (the fallback is dead code), but if the fallback were ever re-activated, it would miss halfwidth case numbers.

#### I-3: `normalize_tool_name` bidirectional fallback is aggressive

**File:** `tool_leak.py:247-249`

The bidirectional fallback `if known in n or n in known` can cause aggressive matches. For example, `normalize_tool_name("re")` returns `"read_chunk"` because `"re" in "read_chunk"` is `True`. Similarly, `normalize_tool_name("ask")` returns `"ask_user"`. This matches the Rust behavior and is acceptable for leak-parse recovery (where names are mangled), but could cause surprising behavior if used outside that context.

#### I-4: `_DB_CASE_ID_RE` only matches single-digit third segment

**File:** `extract.py:84`

The pattern `\d{4}-\d{2}-\d-\d{3}-\d{3}` requires exactly one digit in the third segment. DB case IDs like `2024-10-2-358-001` match, but a hypothetical `2024-10-12-358-001` would not. This matches the Rust source pattern. If the case ID format ever expands, this regex would need updating.

#### I-5: `de_ai_polish` leaves orphaned "我" after removing "作为一个AI"

**File:** `guardrails.py:281, 294`

When processing `"我作为一个AI，无法..."`, the pattern at line 281 removes `"作为一个AI，"`, leaving `"我无法..."`. The pattern at line 294 (`"我(?:是|作为一个)AI...无法" → "无法"`) was intended to handle this case but doesn't fire because the `"作为一个AI"` part is already removed. The result `"我无法访问外部数据库。"` is grammatically acceptable but leaves an orphaned "我". The test passes because it only checks `assertNotIn("我作为一个AI", result)` and `assertIn("无法访问外部数据库。", result)`, not the absence of "我".

#### I-6: Citation audit runs on pre-polish content; user sees polished content

**File:** `turn_loop.py:366, 379`

The citation audit (line 366) runs on `full_content` before `de_ai_polish` (line 379) modifies it. The `citation.recorded` event and audit metadata reflect pre-polish content. Since `de_ai_polish` is designed to preserve legal citations, the audit results remain valid for the polished output. This is a reasonable design choice (audit the generated content, polish for display), but worth documenting.

#### I-7: Leak retry consumes a turn from `max_turns` budget

**File:** `turn_loop.py:134, 348-355`

Each leak retry increments the `for _round in range(config.max_turns)` counter. With `max_turns=10` and `max_leak_retries=3`, up to 3 rounds could be consumed by leak retries, leaving only 7 for actual tool-calling work. This matches the Rust behavior (`MAX_LEAK_RETRIES` in `chat.rs:36`), but if the model frequently leaks, the effective turn budget is reduced.

#### I-8: `assert_skill_candidate_safety` is stricter than `create_skill_candidate` — inconsistency

**File:** `guardrails.py:362, 381`

`assert_skill_candidate_safety()` uses `not candidate.get("requires_human_review", False)` (rejects all falsy values), while `create_skill_candidate()` uses `kwargs.get("requires_human_review") is False` (only rejects `False`). This inconsistency is the root cause of C-1. After fixing C-1, both checks should use the same logic.

## File-by-File Analysis

### tool_leak.py

**Lines:** 429 | **Ported from:** `tool_leak.rs` (392 lines)

Faithful port of the Rust tool-leak detection module. The 20+ leak marker patterns, full-width character normalization (U+FF5C → `|`, U+2581 → `_`), two-phase sanitization, fuzzy tool-name normalization, and embedded tool-call parsing are all ported correctly. The golden fixture test (`REAL_DSML_LEAK`) is byte-identical to the Rust source.

**Correctness:**
- `contains_tool_leakage()`: All 20+ markers from Rust are present. Markdown tables with `|` separators are correctly NOT flagged (verified by test). HTML formatting tags (`<br>`, `<table>`, `<strong>`) are correctly NOT flagged.
- `sanitize_assistant_content()`: Two-phase approach (block removal + line filtering) works correctly. Phase 1b (unclosed `<invoke>` removal) correctly handles the edge case of no closing tag by looking for the next `<invoke` block or removing to end of string.
- `normalize_tool_name()`: Substring heuristics and bidirectional fallback match Rust. See I-3 for aggressive matching note.
- `parse_embedded_tool_calls()`: Correctly parses invoke blocks, extracts parameters, converts numeric params to `int`, and generates UUID-based IDs. Only accepts tools in `KNOWN_TOOLS` or starting with `mcp_`.

**No bugs found.** One Info-level note (I-3) about aggressive bidirectional matching.

### prompt_assembler.py

**Lines:** 362 | **Ported from:** `router.rs` (627 lines)

Faithful port of the prompt assembly logic. Three modes (Chat/Draft/Evidence) each get distinct base prompts. The research-gate, retrieval tool mapping, citation writing spec, skill descriptions, and active skill body are injected in every mode.

**Correctness:**
- `build_system_prompt()`: Pipeline is correct — mode prompt → research-gate → retrieval mapping → citation spec → skill descriptions → active skill. The research-gate is always injected (fallback or custom), satisfying SAFE-04.
- `build_retrieval_tool_mapping()`: Correctly emits honest degradation text when no tools are available. Known tools get mapped descriptions; unknown tools get generic descriptions based on name analysis.
- `is_retrieval_tool()` / `is_retrieval_tool_name()`: Correctly identifies retrieval tools by direct name match, MCP prefix + fragment match, or description text analysis.
- All three mode prompts contain the required `ask_user` mandate for Draft/Evidence and omit it for Chat (by design).

**No bugs found.** Clean, well-documented port.

### citations/extract.py

**Lines:** 193 | **Ported from:** `extract.rs` (284 lines)

Faithful port of the citation extraction module. Six compiled regex patterns extract law articles, interpretations, state council decrees, case numbers, and DB case IDs.

**Correctness:**
- `_LAW_ARTICLE_RE`: Correctly matches `《法名》第N条` with enumeration expansion (`、和及与`). Handles `之N` suffixes (e.g., 第二百八十七条之一).
- `_INTERPRETATION_RE`: Correctly matches `法释〔YYYY〕N号` with optional adjacent `《name》`. Bracket variants (`[`, `（`, `(`) are all matched.
- `_CASE_NUMBER_RE`: Matches both fullwidth and halfwidth brackets. Case-type suffixes cover all major Chinese court case types. See I-4 for DB case ID limitation.
- `_normalize_doc_number()`: Correctly normalizes bracket variants for deduplication.
- Deduplication by `(kind, source, reference)` with first-occurrence ordering is correct.

**No bugs found.** One Info-level note (I-4) about DB case ID pattern.

### citations/verify.py

**Lines:** 397 | **Ported from:** `verify.rs` (250 lines)

Faithful port of the three-state citation verification module. The `LawLibrary` protocol is well-designed as an optional dependency — when `None`, all lookups fail and the verifier falls back to retrieval evidence.

**Correctness:**
- `verify_law_article()`: Correctly tries library lookup first (→ "verified" or "law_found_article_missing"), then falls back to retrievals (→ "retrieved" or "unverified"). Non-current status notes are correctly generated.
- `verify_interpretation()`: Correctly tries doc-number lookup, then name-based lookup, then retrieval fallback. The "按名称匹配" note for name-based matches is appropriate.
- `verify_case()`: Synchronous (no library lookup) — correctly tries both fullwidth and halfwidth bracket forms against retrievals.
- `verify_items()`: Correctly dispatches by kind. The async/sync mix (law and interpretation are async, case is sync) is handled correctly — `verify_case` is not awaited.
- Error handling: All library lookups are wrapped in `try/except Exception` that degrades to `None`, ensuring the audit never fails.

**No bugs found.** Clean, defensive implementation.

### citations/__init__.py

**Lines:** 97 | **Ported from:** `mod.rs` (55 lines)

The `audit()` async function correctly composes `extract_citations()` and `verify_items()`, and aggregates counts. The `CitationAudit` dataclass with `items`, `total`, `verified`, `retrieved`, `unverified` fields is well-structured.

**No bugs found.** Clean orchestration layer.

### guardrails.py

**Lines:** 413 | **Designed fresh** (no Rust source for guardrails orchestration + de-AI polish)

Implements the four guardrails at code level and the SAFE-01 skill_candidate safety invariant.

**Critical issue (C-1):** `create_skill_candidate()` has a bypassable `is False` check — see C-1 above.

**Other observations:**
- `enforce_research_gate()` and `enforce_ask_user_mandate()`: Simple, correct assertion functions. Chat mode is correctly exempt from ask-user.
- `enforce_citation_audit()`: Correctly delegates to `citations.audit()` when available. The fallback is dead code (I-1).
- `de_ai_polish()`: Conservative pattern set that preserves legal citations, article numbers, and conclusions. The 12 patterns cover AI self-references, hedging, and "not legal advice" boilerplate. See I-5 for orphaned "我" note.
- `verify_guardrails()`: Correctly checks prompt-level guards (1 and 2). Guards 3 and 4 are runtime-enforced, not prompt-checkable.
- `assert_skill_candidate_safety()`: Correctly uses `not` (rejects all falsy) — stricter than the factory's `is False` (I-8).

### turn_loop.py (modified)

**Lines:** 511 | **Modified in Phase 102** (guardrail pipeline wiring)

The turn loop correctly wires in the Phase 102 guardrails:
1. **Leak detection + retry** (lines 347-357): After streaming, checks `contains_tool_leakage()`. If leaked and retries remain, discards the response and retries (does NOT append leaked content to history). When exhausted, sanitizes via `sanitize_assistant_content()`.
2. **Citation audit** (lines 363-374): Collects retrieval evidence from tool results, runs `_run_citation_audit()`, emits `citation.recorded` event, and attaches audit summary to `message.completed` metadata.
3. **De-AI polish** (line 379): Runs `de_ai_polish()` on the final content before emitting `message.completed`.

**Warning findings:**
- W-2: Error tool results collected as retrieval evidence.
- W-3: No runtime enforcement of prompt-level guardrails (research-gate, ask-user).
- W-4: `law_library` always `None` — "verified" status never achieved.

**Correctness of existing (non-102) code:** The tool execution, error recovery, heartbeat, and turn limit logic are unchanged from Phase 100 and remain correct. The `_collect_retrieval_evidence()` helper correctly pairs tool result messages with tool names by insertion order.

### event_emitter.py (modified)

**Lines:** 460 | **Modified in Phase 102** (added `emit_citation_recorded`)

The new `emit_citation_recorded()` method (lines 420-457) converts `CitationAuditItem` objects to `CitationRecord` objects (with `source` and `status` only), builds a `CitationRecordedPayload`, and emits a `citation.recorded` event.

**Warning finding:**
- W-1: The method appends to `_side_channel_events` but the turn loop yields the return value directly, creating a fragile double-buffer situation.

**Correctness:** The source fallback (`item.source if item.source else item.reference`) correctly handles bare case numbers with empty source. The method correctly increments seq and updates last_event_time via `_emit()`.

### config.py (modified)

**Lines:** 82 | **Modified in Phase 102** (added `max_leak_retries`)

The new `max_leak_retries` field (default 3, matching Rust `MAX_LEAK_RETRIES`) is correctly validated in `__post_init__` with `if self.max_leak_retries < 0: raise ValueError`. The value `0` is allowed (immediate sanitization on first leak, no retries).

**No bugs found.** Clean, minimal addition.

## Test Quality Assessment

The Phase 102 test suite is comprehensive and well-organized:

- **Golden fixture tests** (`test_tool_leak.py`, `test_prompt_assembler.py`, `test_citation_extract.py`, `test_citation_verify.py`): Port all Rust test cases with byte-identical inputs. The `REAL_DSML_LEAK` constant is verbatim from the Rust source. These are the strongest tests in the suite.
- **Guardrail enforcement tests** (`test_guardrails.py`, `test_de_ai_polish.py`, `test_skill_candidate_safety.py`): Verify each guardrail is enforced at code level, including bypass attempts.
- **E2E integration tests** (`test_e2e_guardrail_pipeline.py`): Verify the guardrails are correctly wired into `run_turn()` with fixture providers (no external LLM calls). Tests leak retry, citation audit, de-AI polish, and retrieval evidence collection.
- **Success criteria meta-test** (`test_phase102_success_criteria.py`): Maps each SC to verifying tests and checks key assertions inline. Includes the HG-1 reminder (not auto-closable).

**Test gap:** The SAFE-01 bypass (C-1) is not caught by any test. `test_skill_candidate_safety.py` only tests `requires_human_review=False` (the exact `False` value), not other falsy values like `0` or `None`. A regression test should be added for these bypass attempts after fixing C-1.

## Verdict

**Findings found.** One Critical finding (C-1: SAFE-01 bypass) must be fixed before proceeding. The fix is a one-line change in `guardrails.py:381`. Three Warning findings should be addressed but are not blocking. The port is otherwise faithful, well-tested, and structurally sound.
