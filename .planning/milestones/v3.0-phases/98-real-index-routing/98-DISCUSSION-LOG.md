---
phase: 98
slug: real-index-routing
status: draft
created: 2026-08-10
mode: auto
---

# Phase 98 Discussion Log — Real-Index Routing

**Mode:** --auto (all gray areas auto-selected with recommended options)
**Date:** 2026-08-10
**Requirements:** SKILL-07, SKILL-08
**Depends on:** Phase 97 (complete)

---

## Gray Area Analysis

11 gray areas identified, all auto-selected with recommended options.

---

### Gray Area 1: Router Data Source Migration

**Q:** How to switch router-service from 4 fake manifest skills to 396 real skill-index descriptors?

**Options:**
- A) Construct `SkillRegistry` from `index_to_descriptors(skill_index_path)`, inject into `RouterService` as `skill_registry` — **SELECTED**
- B) Have router-service directly read `skill-index.json` (new dependency on skill-index package)
- C) Have router-service read the routing manifest from Phase 97's `produce_routing_manifest()`

**Decision:** A — Use `index_to_descriptors()` (already built in Phase 97) to populate `SkillRegistry`, inject into `RouterService` at the composition root.

**Rationale:** The router already accepts `SkillRegistryPort` — no interface change needed. Phase 97 built `index_to_descriptors()` which reads `skill-index.json` → `NeutralSkillDescriptor` list. The `SkillRegistry` constructor accepts this list. The router-service package stays decoupled from skill-index; the host wires them together. This follows the existing dependency injection pattern and the three-separation principle (router uses metadata only).

**Risk:** The `SkillRegistry.search(category=intent)` path won't match real descriptors because they have no `metadata["intent"]` field. The strong-signal rules bypass this by matching directly to skill_ids. The soft matcher uses `host_assumptions` and `name_substring` instead of `category`. The generic `classify_intent()` 4-category classifier becomes a secondary signal, not the primary routing path.

---

### Gray Area 2: 12 Strong-Signal Regex Porting

**Q:** How to port the 12 strong-signal deterministic regex rules from `lawfirm-profile/scripts/router.py`?

**Options:**
- A) Create new `strong_signal.py` module in router-service with the 11 `_Rule` entries + factual short-circuit — **SELECTED**
- B) Merge the 12 rules into the existing `classifier.py` `classify_intent()` function
- C) Keep the rules in a separate config file (JSON/YAML) loaded at runtime

**Decision:** A — New `strong_signal.py` module, separate from `classifier.py`.

**Rationale:** The strong-signal rules are domain-specific deterministic regex patterns that run BEFORE the strategy cascade. They are a different concern from the generic 4-category intent classifier. Keeping them separate:
- Preserves the existing `classify_intent()` for backward compatibility
- Makes the 12 rules testable in isolation (golden fixture)
- Allows the rules to be versioned and audited independently
- Matches the lawfirm-profile structure (separate `_build_strong_signal_rules()` function)

The 12th "rule" is the `factual_short_circuit` — the `_is_simple_factual()` check for statute lookups and term definitions. This is ported as `is_simple_factual()` in the same module.

**Risk:** The regex patterns contain Chinese characters and legal domain-specific patterns. Must port exactly (not from memory) — copy the regex strings verbatim from `router.py` lines 78-203.

---

### Gray Area 3: 对拍集 (Comparison Test Set) — Behavior Non-Regression

**Q:** How to verify that ported routing behavior doesn't regress?

**Options:**
- A) Port the 15-case integration fixture + 8-case eval fixture from lawfirm-profile as golden tests in router-service — **SELECTED**
- B) Run the lawfirm-profile test suite against the new router-service (cross-repo testing)
- C) Write new test cases from scratch based on the success criteria

**Decision:** A — Port the existing test fixtures as golden tests.

**Rationale:** AGENTS.md mandates: "When porting logic from lawyer-desktop (Rust), use the Rust-side test cases as the Python-side golden fixture set. Do not port by reading and re-writing from memory." The same principle applies to porting from lawfirm-profile. The test fixtures are:
- `integration_test_router.py`: 15 cases (7 strong-signal + 3 factual + 5 soft-match), ≥80% accuracy threshold
- `test_eval_router.py`: 8 cases, ≥75% accuracy threshold
- `test_router.py`: 4 core scenarios (contract, court SMS, factual Q, new case chain)
- `test_decision_logging.py`: decision log JSONL format
- `test_routing_feedback.py`: routing error recording

These are ported as new test files in `packages/router-service/tests/` with the same fixture data and accuracy thresholds.

**Risk:** Some soft-match cases (e.g., "construction-payment-dispute") may not match if the real skill-index doesn't have a skill with that exact name or trigger. The accuracy threshold is ≥80% (12/15), allowing up to 3 failures. The soft-match cases depend on the real index having the expected skills — need to verify skill_ids in the actual `skill-index.json`.

---

### Gray Area 4: Three-Mode Detection (Chat/Draft/Evidence)

**Q:** How to port the three-mode detection from `lawyer-desktop/src-tauri/src/skills/agent_classifier.rs`?

**Options:**
- A) Create new `mode_classifier.py` module in router-service with `AgentMode` enum, `ClassifyContext`, `ClassifyResult`, LLM port + fallback — **SELECTED**
- B) Merge mode detection into the existing `classifier.py` as an extended `classify_intent()`
- C) Put mode detection in a separate package (`packages/mode-classifier/`)

**Decision:** A — New `mode_classifier.py` module in router-service.

**Rationale:** The three-mode detection is a distinct concern from skill routing:
- Skill routing: "which skill should handle this message?" → `RouteDecision.primary_skill`
- Mode detection: "what kind of task is this (chat/draft/evidence) and how does it relate to the current task?" → `ClassifyResult.mode` + `ClassifyResult.action`

Keeping them in the same package but separate modules:
- Mode detection can be used independently of skill routing (e.g., the UI uses it to decide which panel to show)
- The LLM-based classifier is a separate port (`ModeClassifierPort`) from the existing `ModelClassifierPort`
- The fallback logic is ported 1:1 from Rust to Python

**Risk:** The LLM system prompt is in Chinese and contains domain-specific rules. Must port the exact prompt text (CLASSIFIER_SYSTEM + CLASSIFIER_POLICY_SUPPLEMENT) from `agent_classifier.rs` lines 92-123.

---

### Gray Area 5: continue/switch/aside Actions

**Q:** How to implement the continue/switch/aside action semantics?

**Options:**
- A) Store in `RouteDecision.metadata` — no new top-level fields (contract freeze) — **SELECTED**
- B) Add new top-level fields to `RouteDecision` (breaks contract freeze)
- C) Return a separate `ModeDecision` event alongside `RouteDecision`

**Decision:** A — Store mode/action/label in `RouteDecision.metadata`.

**Rationale:** `RouteDecision` is a frozen platform-contract dataclass (SAFETY-06). Adding top-level fields would break 28 existing gates and the JSON Schema. The metadata dict is the designated extension point. Fields:
- `metadata["agent_mode"]` = "chat" | "draft" | "evidence"
- `metadata["mode_action"]` = "continue" | "switch" | "aside"
- `metadata["mode_label"]` = short Chinese task label
- `metadata["mode_source"]` = "llm" | "fallback"

The UI/client can read these from metadata to drive the switch-confirmation gate (when action="switch") or the aside indicator (when action="aside").

**Risk:** Clients must know to look in metadata for mode info. This is documented in the router's docstring and the context file.

---

### Gray Area 6: LLM Classification Fallback Rules

**Q:** What rules apply when the LLM classifier fails?

**Options:**
- A) Port the exact `fallback_classify()` logic: structural-only, no keyword matching, action always "continue" — **SELECTED**
- B) Use a keyword-based fallback that tries to infer mode from user text
- C) Default to Chat always, regardless of current task state

**Decision:** A — Port `fallback_classify()` 1:1 from Rust.

**Rationale:** The lawyer-desktop fallback is deliberately conservative — this is a safety property:
- It does NOT infer mode from user text keywords (a broken LLM should not surprise-switch)
- When `has_active_document=True`: keep `current_mode` (if parseable), else Chat
- When `has_active_document=False`: always Chat
- Action is always "continue" — fallback must never surprise-switch
- Source is "fallback" with error reason for diagnostics

This is a legal safety property: an LLM failure should not cause the user's committed draft task to be silently switched to a different mode.

**Risk:** The fallback uses `parse_mode_str()` which handles Chinese mode aliases. Must port this function exactly (lines 328-345 of agent_classifier.rs).

---

### Gray Area 7: RouteDecision Contract Event

**Q:** How to structure the RouteDecision event when porting from router.py?

**Options:**
- A) Map router.py fields to existing frozen RouteDecision: gate_before→gates_before list, gate_after→gates_after list, skip_clarification→metadata — **SELECTED**
- B) Create a new `LegalRouteDecision` subclass with additional fields
- C) Modify the frozen RouteDecision schema (breaks contract freeze)

**Decision:** A — Map to existing frozen RouteDecision, no schema changes.

**Rationale:** The platform-contract `RouteDecision` (events.py lines 206-222) is frozen. The mapping is straightforward:
- `gate_before` (str|None) → `gates_before` (list[str]) — `[gate_before]` if not None, else `[]`
- `gate_after` (str|None) → `gates_after` (list[str]) — `[gate_after]` if not None, else `[]`
- `skip_clarification` (bool) → `metadata["skip_clarification"]` (bool)
- `session_id` (str) → `metadata["session_id"]` (str)
- New fields: `route_decision_id` (generated), `turn_id` (from context), `mode` (RouteMode), `created_at` (timestamp), `required_tools` (from descriptor)

**Risk:** The `mode` field (RouteMode enum: matched/simple_qa/skipped/zero_match) must be derived from the router.py decision. Mapping:
- `confidence >= 0.8` and `primary_skill is not None` → `matched`
- `confidence >= 0.5` or `primary_skill is None` with reason containing "simple" → `simple_qa`
- `confidence < 0.5` → `zero_match`

---

### Gray Area 8: Decision Logging

**Q:** Where and how to log routing decisions?

**Options:**
- A) Port the JSONL append pattern from router.py: per-session JSONL file with decision + timestamp + user_msg — **SELECTED**
- B) Use the platform's existing contract log (RunEvent/ExecutionTrace)
- C) Log to a database table

**Decision:** A — Port the JSONL append pattern, with configurable log directory.

**Rationale:** The lawfirm-profile router.py already has a working decision logging pattern (`_append_decision_log()`). It's simple, append-only, and per-session. The platform version:
- Uses a configurable log directory (not hardcoded to `~/.hermes/...`)
- Logs the `RouteDecision` in platform-contract format (not router-local format)
- Includes `timestamp` and `user_msg` alongside the decision
- No-op when session_id is empty (opt-out preserved)
- The log enables `route_mismatch` feedback association: when a user reports `route_wrong`, the feedback system can look up the original decision by `turn_id` or `session_id`

**Risk:** The log directory must be configurable, not hardcoded. Use a `RouterLogConfig` dataclass with `log_dir: Path | None` (None = no logging).

---

### Gray Area 9: Trigger Phrase Soft Matching (0.4 Threshold)

**Q:** How to implement the 0.4 threshold soft matching from router.py?

**Options:**
- A) Port `_score_skill()` and `_best_soft_match()` as new `soft_matcher.py` module — **SELECTED**
- B) Use SQLite FTS5 full-text search on skill descriptions
- C) Use embedding-based similarity (out of scope per PROJECT.md)

**Decision:** A — Port the bag-of-triggers scoring algorithm.

**Rationale:** The lawfirm-profile router.py soft matching uses:
- Bag-of-triggers scoring: fraction of triggers found in message, weighted by phrase length (longer = stronger, capped at 6 chars)
- Description bigram bonus: +0.1 per overlapping 2-char bigram (capped at 1.0)
- Only `user_facing=True` skills scored (in real index, this maps to `skill_type == "leaf"` or a similar filter)
- Threshold: ≥0.4 → match; ≥0.7 → skip clarification
- `gate_before = "ask-user-enforcement"` when score < 0.7
- `gate_after = "legal-de-ai-polish"` always for soft matches

The ported module uses `host_assumptions` from real descriptors as trigger phrases (these contain `/plugin:skill` patterns and argument hints). The `description` field provides bigrams for the bonus.

**Risk:** The real skill-index descriptors use `host_assumptions` (list of strings) instead of `triggers` (list of strings). The scoring algorithm is the same but the input field is different. Need to extract trigger-like phrases from `host_assumptions` (e.g., parse `/plugin:skill` patterns into skill names).

---

### Gray Area 10: Legal Risk Grading Preservation

**Q:** How to preserve legal risk grading in real-index routing?

**Options:**
- A) Keep existing `legal_risk.py` unchanged — it operates on message text, not skill metadata — **SELECTED**
- B) Extend the legal risk classifier with skill-specific risk levels from the index
- C) Replace keyword-based grading with an LLM-based risk classifier

**Decision:** A — No changes to `legal_risk.py`.

**Rationale:** The `KeywordLegalRiskClassifier` classifies the user's message text (not the skill descriptor) into low/medium/high risk. It works independently of the skill data source. The HYBRID strategy's legal-risk override (high-risk → forced to Hermes) continues to work as-is. The 28 high-risk keywords and 15 medium-risk keywords are domain-specific and already validated in production.

**Risk:** None — this is a no-change decision.

---

### Gray Area 11: Leaf Skill Matching (Not 4 Fake Names)

**Q:** How to ensure routing hits specific leaf sub-skills (not just 4 fake skill names)?

**Options:**
- A) Strong-signal rules target real skill_ids; soft matching uses host_assumptions; registry.search uses name_substring on real names — **SELECTED**
- B) Add an `intent` field to real descriptors to make `search(category=...)` work
- C) Build a separate skill matching service that maps messages to skill_ids

**Decision:** A — Use real skill_ids in strong-signal rules, host_assumptions for soft matching, name_substring for registry search.

**Rationale:** The 12 strong-signal rules already target real skill names (`legal-court-sms`, `legal-contract-copilot`, `legal-new-case`, `ip-ip-clearance`, etc.). These are actual skill_ids in the real index. The soft matcher uses `host_assumptions` (trigger patterns) from real descriptors. The `SkillRegistry.search(name_substring=...)` works on real skill names. The key change is that the router now has 396 real descriptors to search against, not 4 fake ones.

**Verification (criterion 6):** The 15-case golden fixture tests assert that `primary_skill` matches real skill_ids (e.g., `legal-court-sms`, not `case_qa`). This is the direct verification that leaf skill matching works.

**Risk:** Some skill names in the golden fixture may not exist in the real index (e.g., `construction-payment-dispute`, `ip-copyright-registration`). Need to verify these against the actual `skill-index.json` and either (a) confirm they exist, or (b) adjust the expected values to the closest real skill_id. The ≥80% accuracy threshold allows up to 3 mismatches.

---

## Summary of Decisions

| # | Gray Area | Decision | Module/File |
|---|-----------|----------|-------------|
| 1 | Router data source migration | `index_to_descriptors()` → `SkillRegistry` → `RouterService` | Composition root (host) |
| 2 | 12 strong-signal regex porting | New `strong_signal.py` module | `packages/router-service/src/inkstatute_router_service/strong_signal.py` |
| 3 | 对拍集 comparison test set | Port 15+8 case fixtures as golden tests | `packages/router-service/tests/test_strong_signal_golden.py` |
| 4 | Three-mode detection | New `mode_classifier.py` module | `packages/router-service/src/inkstatute_router_service/mode_classifier.py` |
| 5 | continue/switch/aside actions | Store in `RouteDecision.metadata` | `service.py` (metadata population) |
| 6 | LLM classification fallback | Port `fallback_classify()` 1:1 | `mode_classifier.py` |
| 7 | RouteDecision contract | Map to frozen RouteDecision, no schema changes | `service.py` (`_build_decision()`) |
| 8 | Decision logging | JSONL append per session, configurable log dir | New `decision_log.py` or in `service.py` |
| 9 | Trigger phrase soft matching | Port `_score_skill()` as `soft_matcher.py` | `packages/router-service/src/inkstatute_router_service/soft_matcher.py` |
| 10 | Legal risk grading | No changes to `legal_risk.py` | — |
| 11 | Leaf skill matching | Real skill_ids in rules, host_assumptions for soft match | `strong_signal.py` + `soft_matcher.py` |

---

## Estimated Plan Structure

Based on the gray area analysis, Phase 98 likely needs 3 plans:

1. **98-01: Strong-signal rules + soft matcher + data source migration** — Port the 12 strong-signal rules, soft trigger-phrase matching, factual short-circuit; wire router to real skill-index via `index_to_descriptors()`; golden fixture tests (15+8 cases)
2. **98-02: Three-mode detection + continue/switch/aside** — Port `agent_classifier.rs` as `mode_classifier.py`; LLM port + fallback; action normalization; mode parsing; store in RouteDecision.metadata
3. **98-03: Decision logging + RouteDecision mapping + phase completion** — JSONL decision log; router.py → RouteDecision field mapping; route_mismatch feedback association; full gate suite; phase completion

---

## Open Questions (Deferred to Plan Phase)

1. **skill-index.json location:** Where is the generated `skill-index.json` stored? Need to confirm the path for the composition root to load it. (Likely `packages/skill-index/data/skill-index.json` or a configurable path.)
2. **host_assumptions as triggers:** The real index stores `host_assumptions` (list of strings with `/plugin:skill` patterns), not `triggers`. Need to verify that the soft matcher can extract useful trigger phrases from `host_assumptions`.
3. **Golden fixture skill_ids:** Some expected skill_ids in the lawfirm-profile test fixtures (e.g., `construction-payment-dispute`, `ip-copyright-registration`) may not exist in the real index. Need to verify against actual `skill-index.json` and adjust if needed.
4. **LLM mode classifier integration:** The mode classifier requires an LLM provider. In the platform, this would be injected via the model gateway. Need to define the `ModeClassifierPort` integration point.
5. **Gate registration:** If new test files are added to `packages/router-service/tests/`, the existing `router-service` gate should pick them up automatically (no new gate needed). Verify gate count stays at 36.
