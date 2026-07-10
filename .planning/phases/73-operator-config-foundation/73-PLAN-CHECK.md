# Plan Check — Phase 73: Operator Config Foundation

**Checker:** gsd-plan-checker
**Date:** 2026-07-10
**Iteration:** 1
**Plans checked:** 73-01-PLAN.md, 73-02-PLAN.md, 73-03-PLAN.md
**Phase requirements:** CFG-01, CFG-02, CFG-03
**Result:** ISSUES FOUND — 2 blocker(s), 3 warning(s)

---

## Goal-Backward Analysis

**Phase goal (ROADMAP.md):** Operators have an InkStatute-owned, refs-only config authority that is off by default and never treats Hermes filesystem paths as config source of truth.

**What must be TRUE:**
1. Persist channel/provider/catalog/vision config in a refs-only InkStatute store
2. `operator_config_enabled` OFF by default; mutate refuses writes
3. Validators reject Hermes `~/.hermes` / profile paths as authority

**Plan mapping (intent coverage — sound):**

| Success criterion | Covering plans/tasks | Status |
|-------------------|----------------------|--------|
| SC-1 refs-only persist | 01 schemas/secrets → 02 validate → 03 atomic store | Covered in plan intent |
| SC-2 flag OFF refuse | 03 Task 1 flag + Task 2 `save` gate + `test_flag_gate.py` | Covered in plan intent |
| SC-3 Hermes ban | 02 `validate.py` + `test_hermes_banlist.py` | Covered in plan intent |

**Verdict on substance:** The three-wave split (schemas → validators → store+flag+gate) correctly delivers CFG-01..03 without Phase 74 HTTP / 75–78 scope bleed. Execution is blocked until Nyquist VALIDATION.md exists and RESEARCH open questions are marked resolved.

---

## Dimension Results

### Dimension 1: Requirement Coverage — PASS

| Requirement | Plans | Tasks | Status |
|-------------|-------|--------|--------|
| CFG-01 | 01, 02, 03 | schemas/secrets, validate planted-secret, store persist | COVERED |
| CFG-02 | 03 | flag default False + save refuse + test_flag_gate | COVERED |
| CFG-03 | 02 | Hermes ban-list + negative matrix | COVERED |

All three IDs appear in plan frontmatter `requirements` fields. CFG-02 REQUIREMENTS wording ("mutate endpoints") is correctly interpreted as package mutate path per RESEARCH (HTTP = Phase 74).

### Dimension 2: Task Completeness — PASS

All three plans: `verify.plan-structure` → `valid: true`, 0 errors.

| Plan | Tasks | Files+Action+Verify+Done |
|------|-------|--------------------------|
| 01 | 3 | All present; TDD behaviors specific |
| 02 | 2 | All present |
| 03 | 3 | All present (Task 3 has action/verify/done; no empty fields) |

### Dimension 3: Dependency Correctness — PASS

```
73-01 (wave 1, depends_on: [])
73-02 (wave 2, depends_on: [73-01])
73-03 (wave 3, depends_on: [73-01, 73-02])
```

Acyclic; wave numbers consistent; no forward-only references.

### Dimension 4: Key Links Planned — PASS

Critical wiring present in must_haves + task actions:
- schemas ↔ channel/provider `*_ref` naming
- `validate_document` → `normalize_config_secret_ref`
- Hermes ban-list → document before store
- `OperatorConfigStore.save` → `require_enabled("operator_config_enabled")` then `validate_document` then `os.replace`
- V2 gate → `packages/operator-config/src`

### Dimension 5: Scope Sanity — WARNING

| Plan | Tasks | Files | Status |
|------|-------|-------|--------|
| 01 | 3 | 8 | OK |
| 02 | 2 | 4 | OK |
| 03 | 3 | 10 | WARNING (files at warning threshold) |

Plan 03 packs flag + store + gate + gitignore + admin regression — acceptable but tight.

### Dimension 6: Verification Derivation — PASS

must_haves truths are operator-observable (refs-only docs, flag refuse, Hermes reject, atomic round-trip, gate coverage). Artifacts and key_links map to those truths.

### Dimension 7: Context Compliance — PASS

Locked decisions honored:
- Secrets as refs only (01/02/03)
- No new SPA/DB/queue (atomic JSON file)
- `operator_config_enabled` default OFF (03)
- Never Hermes as config authority (02)

Deferred CFG-F01..F03 / HTTP / catalog content / vision runtime excluded. Discretion areas (API shape, issue-list vs raise) left to executor — OK.

### Dimension 7b: Scope Reduction — PASS

Deferred items (`vision_routing_enabled`, catalog vendor JSON, admin PUT) are explicit later-phase boundaries from RESEARCH/CONTEXT, not silent reductions of locked Phase 73 decisions.

### Dimension 7c: Architectural Tier Compliance — PASS

Matches RESEARCH Architectural Responsibility Map: library package for schemas/validate/store; platform-runtime for flag; no browser/HTTP mutate in Phase 73.

### Dimension 8: Nyquist Compliance — FAIL (BLOCKER)

`workflow.nyquist_validation: true` in `.planning/config.json`.

**Check 8e:** `73-VALIDATION.md` **not found** under `.planning/phases/73-operator-config-foundation/`.

Per gate rules: BLOCKING FAIL — skip 8a–8d until VALIDATION.md exists.

**Revision:** Create `73-VALIDATION.md` from RESEARCH Validation Architecture + plan `<automated>` commands (mirror `72-VALIDATION.md` structure). Map CFG-01..03 → test files already named in plans. Mark Wave 0 as in-plan TDD (tests created with implementation; no separate Wave 0 plan required if documented).

### Dimension 9: Cross-Plan Data Contracts — PASS

Pipeline is compatible: schemas (01) → validate (02) → gated persist (03). No conflicting sanitize/strip vs parse assumptions. Store must not bypass validate (explicitly planned).

### Dimension 10: .cursor/rules/ Compliance — SKIPPED

No `.cursor/rules/` directory. AGENTS.md constraints (no new DB/queue, secrets as refs, Hermes boundary) are respected by plans.

### Dimension 11: Research Resolution — FAIL (BLOCKER)

`73-RESEARCH.md` has `## Open Questions` **without** `(RESOLVED)` suffix. Four questions have Recommendations but lack inline `RESOLVED:` markers.

Plans already follow the recommendations (schema-only catalog; shape-only secrets; defer `vision_routing_enabled`; skip etag). Mark the section resolved to clear the gate.

### Dimension 12: Pattern Compliance — WARNING

PATTERNS.md File Classification uses different test filenames than plans:
- PATTERNS: `test_schemas_refs.py` / `test_validate_hermes_ban.py` / `test_store_flag_gate.py`
- Plans: `test_schemas.py` + `test_secret_refs.py` / `test_hermes_banlist.py` / `test_store.py` + `test_flag_gate.py`

Also PATTERNS `__init__` export names (`ModelCatalogDoc`, `VisionRoutingDoc`) differ from plan names (`CatalogSelectionDoc`, `VisionPolicyDoc`).

Plans do reference correct analogs in actions. Align PATTERNS.md names with plans (or vice versa) before execute to avoid executor confusion.

---

## Structured Issues

```yaml
issues:
  - plan: null
    dimension: nyquist_compliance
    severity: blocker
    description: "73-VALIDATION.md missing while workflow.nyquist_validation is true. Dimension 8 Check 8e fails; 8a–8d skipped."
    fix_hint: "Write .planning/phases/73-operator-config-foundation/73-VALIDATION.md from RESEARCH Validation Architecture + each plan task <automated> command. Document Wave 0 as in-plan TDD stubs (test_* files created in 01–03). Set nyquist_compliant after map is complete."

  - plan: null
    dimension: research_resolution
    severity: blocker
    description: "73-RESEARCH.md ## Open Questions is not marked (RESOLVED); Q1–Q4 lack inline RESOLVED markers."
    fix_hint: "Rename to ## Open Questions (RESOLVED). Annotate each question RESOLVED with the choice already reflected in plans (catalog schema-only; shape-only secret refs; defer vision_routing_enabled to 77; skip etag)."

  - plan: "73-03"
    dimension: scope_sanity
    severity: warning
    description: "Plan 03 modifies 10 files (warning threshold) across flag, store, gate, gitignore, and admin regression."
    metrics:
      tasks: 3
      files: 10
    fix_hint: "Optional: split gate registration + gitignore into a thin 73-04, or leave as-is if executor keeps context tight."

  - plan: null
    dimension: pattern_compliance
    severity: warning
    description: "PATTERNS.md test/export names diverge from PLAN.md filenames and schema type names."
    fix_hint: "Update PATTERNS.md File Classification + __init__ export example to match plan names (test_schemas.py, test_secret_refs.py, test_hermes_banlist.py, test_store.py, test_flag_gate.py, CatalogSelectionDoc, VisionPolicyDoc)."

  - plan: "73-03"
    dimension: nyquist_compliance
    severity: warning
    description: "Task 1 verify uses `cmd_a 2>/dev/null || cmd_b` fallback; first failure (including real test failure) falls through to second invocation."
    task: 1
    fix_hint: "Prefer a single discover command: PYTHONPATH=packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests -p 'test_feature_flags.py' -q"
```

---

## Recommendation

**Do not execute yet.** Return to planner with 2 blockers:

1. Add `73-VALIDATION.md` (Nyquist gate).
2. Mark RESEARCH Open Questions as `(RESOLVED)` with inline resolutions matching current plan choices.

After those land, re-run plan-checker. Substance of 73-01/02/03 is otherwise ready for `/gsd-execute-phase 73`.

**Options:**
1. Planner revises artifacts only (VALIDATION + RESEARCH markers + optional PATTERNS align) — preferred; no plan split required.
2. If VALIDATION cannot be authored in this loop, re-run `/gsd-plan-phase 73 --research` validation-strategy step then re-check.
