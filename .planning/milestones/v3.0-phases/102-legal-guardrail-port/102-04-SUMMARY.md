---
phase: 102-legal-guardrail-port
plan: 04
status: complete
created: 2026-08-08
---

# Plan 102-04 Summary — Guardrails + De-AI Polish + Skill Candidate Safety

## What Was Done

Created `packages/agent-core/src/inkstatute_agent_core/guardrails.py` — the guardrail orchestration module that enforces all four legal guardrails at code level and implements de-AI polish (designed fresh, no Rust source). Also implemented the `skill_candidate.requires_human_review` safety invariant (SAFE-01). All four guardrails have bypass-prevention tests proving code-level enforcement.

## Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `packages/agent-core/src/inkstatute_agent_core/guardrails.py` | 412 | Guardrail orchestration + de-AI polish + skill_candidate safety |
| `packages/agent-core/tests/test_guardrails.py` | 287 | 22 tests — four-guardrail code-level enforcement |
| `packages/agent-core/tests/test_de_ai_polish.py` | 174 | 16 tests — de-AI polish pattern detection + removal |
| `packages/agent-core/tests/test_skill_candidate_safety.py` | 148 | 11 tests — skill_candidate safety invariant |

## Implemented Components

### Four Legal Guardrails (CORE-08, SAFE-04)

1. **`enforce_research_gate(prompt: str) -> None`** — Guardrail 1. Raises `ValueError("System prompt missing research-gate — legal safety violation")` if `"research-gate"` is absent. Non-bypassable: verified across all three modes, with/without loaded research-gate skill, with empty/non-empty retrieval tools.

2. **`enforce_ask_user_mandate(prompt: str, mode: AgentMode) -> None`** — Guardrail 2. Raises `ValueError` for `DRAFT`/`EVIDENCE` modes when `"ask_user"` is absent. Chat (Q&A) mode is exempt by design — Q&A does not mandate `ask_user`.

3. **`enforce_citation_audit(text, retrievals, law_library) -> CitationAudit`** — Guardrail 3 (async coroutine). Always runs; annotation-style (never blocks output). Delegates to `citations.audit()` (Plan 102-03) when the sub-package is importable; falls back to a conservative self-contained extractor so the guardrail is never bypassed. Unverified citations carry a `待律师复核` note on their `CitationAuditItem`.

4. **`de_ai_polish(text: str) -> str`** — Guardrail 4 (designed fresh, no Rust source). Conservative `_AI_PATTERNS` list removes AI self-references (`作为一个AI助手`, `作为一个人工智能`, `请注意，我是AI`), hedging (`根据我的理解`, `据我所知`), and "not legal advice" boilerplate (`以上分析仅供参考，不构成法律建议`, `我无法提供法律建议`). Preserves legal citations, article numbers, and conclusions. Collapses 3+ blank lines; uses `re.IGNORECASE`. `apply_de_ai_polish` is a public alias.

### Guardrail Verification

- **`verify_guardrails(prompt, mode) -> GuardrailResult`** — verifies prompt-level guards (research-gate + ask-user-enforcement). Returns `GuardrailResult(passed, missing_guardrails)`. Post-processing guards (3, 4) are enforced by their functions at runtime.

### Skill Candidate Safety (SAFE-01)

- **`SkillCandidate` dataclass** — `requires_human_review: bool = True` field.
- **`create_skill_candidate(name, description, **kwargs) -> SkillCandidate`** — the ONLY constructor. Always sets `requires_human_review=True`; override to `False` raises `ValueError`. No code path auto-synthesizes or auto-modifies legal conclusion skills.
- **`assert_skill_candidate_safety(candidate: dict) -> None`** — rejects `requires_human_review=False` and missing field (default-deny). Validates external dicts.

### Type Reuse

`CitationAudit` and `CitationAuditItem` are re-exported from the `citations` sub-package (Plan 102-03) when available, so callers use one canonical type. Conservative fallback types are defined for when the sub-package is absent.

## Test Coverage

### test_guardrails.py (22 tests, 23 subtests)
- **Research-gate (4)**: passes when present; raises when missing; `build_system_prompt` always includes it across all modes/gates/tools (subtested); bypass attempt via empty prompt raises.
- **Ask-user-enforcement (7)**: raises for Draft/Evidence without `ask_user`; passes for Chat without `ask_user`; passes for Draft/Evidence with `ask_user`; `build_system_prompt` always includes `ask_user` for Draft/Evidence (subtested); Chat prompt legitimately omits it.
- **Citation audit (5)**: runs and returns `CitationAudit`; unverified citations labelled `待律师复核`; retrieved citations not labelled; never blocks output (empty text → zero counts); always executes for empty input.
- **De-AI polish guardrail (2)**: runs after citation audit (AI patterns removed, citation preserved); `apply_de_ai_polish` alias works.
- **verify_guardrails (5)**: passes when all prompt guards present for Draft; reports missing research-gate; reports missing ask-user for Evidence; Chat does not require ask-user; `build_system_prompt` passes verification for all modes.

### test_de_ai_polish.py (16 tests)
- **Removal (11)**: removes AI-assistant self-reference, bare AI self-reference, 人工智能 self-reference, "请注意我是AI" disclaimer, understanding hedging, "据我所知" hedging, "无法提供法律建议" disclaimer, "仅供参考不构成法律建议" boilerplate, standalone "仅供参考" boilerplate, preserves "无法" meaning when dropping AI self-ref, removes AI-generated trailing disclaimer.
- **Preservation (5)**: clean legal text unchanged; citations + article numbers preserved; legal conclusions preserved; case numbers preserved; conservative set does not alter legal meaning.
- **Formatting (3)**: collapses multiple blank lines; strips leading/trailing whitespace; multiple patterns removed in one pass.

### test_skill_candidate_safety.py (11 tests)
- **create_skill_candidate (5)**: default `requires_human_review=True`; preserves name/description; rejects `False` override; accepts explicit `True`; stores extra kwargs.
- **assert_skill_candidate_safety (4)**: accepts `True`; rejects `False`; rejects missing field (default-deny); rejects empty dict.
- **No auto-synthesis (3)**: directly-built unsafe candidate rejected by safety check; factory never mutates existing skills; factory output always passes safety check.

## Verification

- Targeted tests: `54 passed, 23 subtests passed` (test_guardrails + test_de_ai_polish + test_skill_candidate_safety).
- Full agent-core suite: `721 passed` (635 existing + 86 from 102-03 citations + 54 new).
- V2 gates: all 28 gates green (agent-core: 721 tests OK).

## Design Decisions

1. **De-AI polish is conservative by design** — the pattern set only removes AI self-references, hedging, and "not legal advice" boilerplate. Legal citations, article numbers, and conclusions are never altered. Over-aggressive polishing could alter legal meaning (T-102-15 mitigation).

2. **`enforce_citation_audit` is async** — delegates to the async `citations.audit()` (Plan 102-03). The turn loop (wired in 102-05) awaits it after every final response. A sync fallback runs when the `citations` sub-package is absent so the guardrail is never bypassed.

3. **`CitationAudit`/`CitationAuditItem` re-exported** from `citations` when available — avoids type duplication and ensures the guardrail wrapper and the audit module share one canonical type.

4. **`create_skill_candidate` is the only constructor** — no code path auto-synthesizes skills. `assert_skill_candidate_safety` validates external dicts with default-deny (missing field → rejected).

## What Was NOT Done (per plan / out of scope)

- **Turn loop wiring** (102-05) — `enforce_citation_audit()` and `de_ai_polish()` are not yet called from `turn_loop.py`; that is Plan 102-05.
- **HG-1 (法律质量) is NOT auto-closed** — these tests verify structural guardrail enforcement, not prompt legal quality. A lawyer must sample and confirm the ported guardrails are no worse than current lawyer-desktop / Hermes.

## Success Criteria Met

- [x] guardrails.py exists with all four guardrail enforcement functions + de-AI polish + skill_candidate safety
- [x] `enforce_research_gate()` raises ValueError when research-gate missing (SAFE-04)
- [x] `enforce_ask_user_mandate()` raises ValueError for Draft/Evidence without ask_user (CORE-08)
- [x] `enforce_citation_audit()` always runs audit (SAFE-04, CORE-08)
- [x] `de_ai_polish()` removes AI-characteristic patterns while preserving legal meaning (CORE-08)
- [x] `assert_skill_candidate_safety()` rejects requires_human_review=False (SAFE-01)
- [x] `create_skill_candidate()` always sets requires_human_review=True (SAFE-01)
- [x] No code path auto-synthesizes or auto-modifies legal conclusion skills (SAFE-01)
- [x] All four guardrails have bypass-prevention tests proving code-level enforcement
- [x] No new pip dependencies (stdlib `re` only)
- [x] Full test suite remains green
