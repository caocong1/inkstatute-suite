---
phase: 98
slug: real-index-routing
status: draft
created: 2026-08-10
skip_discuss: false
---

# Phase 98 — Real-Index Routing

## Phase Goal

路由基于 396 个真实 skill 而非 4 条假元数据，且继承两处已在生产验证过的路由产品知识

## Requirements

- **SKILL-07**: `packages/router-service` 数据源从 4 条手写元数据换成真实索引；移植 `lawfirm-profile/scripts/router.py` 的 12 条强信号正则与 0.4 软匹配阈值，行为不回退
- **SKILL-08**: 移植 `lawyer-desktop/src-tauri/src/skills/agent_classifier.rs` 的 Chat / Draft / Evidence 三模式判定与 continue / switch / aside 动作

## Success Criteria

1. `packages/router-service` 的数据源换成真实 skill 索引；RULE / SKILL / HYBRID 三策略与法律风险分级保留且测试全绿
2. `lawfirm-profile/scripts/router.py` 的 12 条强信号确定性正则（法院短信、判决书、新案件、docx 合同等）已移植，且用原 router 的输入输出作为对拍集验证行为不回退
3. 触发短语软匹配阈值 0.4、置信度 <0.6 标歧义、`gate_before` = ask-user-enforcement、`gate_after` = legal-de-ai-polish 的语义保留
4. `lawyer-desktop` 的 Chat / Draft / Evidence 三模式判定与 continue / switch / aside 动作已移植，含 LLM 分类失败时的规则兜底
5. 路由决策产出 `RouteDecision` 契约事件并写决策日志，可用于后续 `route_mismatch` 反馈关联
6. 给定一组真实律师任务样本，路由能命中具体的叶子子技能（而不是只能命中 4 个假 skill 名）

## Codebase Scout Findings

### 1. packages/router-service — Current State (V2, manifest-based)

**Location:** `packages/router-service/src/inkstatute_router_service/`

**Source files:**

| File | Lines | Purpose |
|------|-------|---------|
| `service.py` | 482 | `RouterService` with `decide()`, `_decide_rule()`, `_decide_skill()`, `_decide_hybrid()` |
| `strategies.py` | 33 | `RouterStrategy` enum: `RULE`, `SKILL`, `HYBRID` (router-internal, maps to frozen `RouteMode`) |
| `classifier.py` | 48 | `classify_intent()` — 4 intent categories (factual_qa, drafting, analysis, review) via keyword/regex |
| `legal_risk.py` | 160 | `LegalRiskAssessment`, `LegalRiskClassifierPort`, `KeywordLegalRiskClassifier` (low/medium/high) |
| `model_classifier.py` | 50 | `ModelClassifierPort` Protocol + `ModelClassificationResult` (LLM-based, host-injected) |
| `port.py` | 30 | `RouterPort` Protocol — `decide(context) -> RouteDecision` |
| `tool_resolver.py` | 112 | `resolve_tool_refs()` — joins skill `required_tool_refs` to MCP `capability_refs` |

**Current data flow:**
1. `RouterService.__init__` receives `SkillRegistryPort | None` (defaults to `None`)
2. When `None`, RULE strategy falls back to inline `classify_intent` → `SIMPLE_QA` or `ZERO_MATCH`
3. When provided, RULE strategy calls `registry.search(category=intent)` → first descriptor → `MATCHED`
4. SKILL strategy: `registry.get_skill(skill_id)` or `registry.search(name_substring=first_word)`
5. HYBRID strategy: Rule → Skill → Model cascade with confidence thresholds (≥0.8 matched, 0.5–0.8 clarify, <0.5 fallback) + legal-risk override (high-risk → Hermes)

**Confidence constants (service.py lines 32-41):**
- `_ROUTE_THRESHOLD = 0.8` — direct route
- `_CLARIFY_THRESHOLD = 0.5` — clarify
- `_CONFIDENCE_RULE_WITH_REGISTRY = 0.9`
- `_CONFIDENCE_RULE_NO_REGISTRY = 0.6`
- `_CONFIDENCE_SKILL_EXACT = 1.0`
- `_CONFIDENCE_SKILL_SINGLE = 0.85`
- `_CONFIDENCE_SKILL_AMBIGUOUS = 0.6`

**Key gap:** The current `classify_intent()` has only 4 generic intent categories (factual_qa, drafting, analysis, review) with ~20 keywords total. It has NO domain-specific strong-signal rules. The `SkillRegistryPort.search(category=...)` matches on `metadata["intent"]` which the 4 fake skills had but real skill-index descriptors do NOT have (they have `metadata["skill_type"]`, `metadata["declared_gates"]`, etc. but no `intent` field).

**Tests:** 7 test files in `packages/router-service/tests/`:
- `test_strategies.py`, `test_service.py`, `test_skill_strategy.py`, `test_hybrid_strategy.py`, `test_legal_risk.py`, `test_port.py`, `test_tool_resolver.py`
- Tests use `_FakeSkillRegistry` with inline `NeutralSkillDescriptor` fixtures (not loaded from manifest or index)

### 2. lawfirm-profile/scripts/router.py — 12 Strong-Signal Rules (498 lines)

**Location:** `/home/sorawatcher/workspace/lawfirm-profile/scripts/router.py`

**RouteDecision (router-local, lines 38-53):**
```python
@dataclass
class RouteDecision:
    primary_skill: str | None
    supporting_skills: list[str] = field(default_factory=list)
    gate_before: str | None = None
    gate_after: str | None = None
    skip_clarification: bool = False
    reason: str = ""
    confidence: float = 0.0
    matched_rule: str = ""
    session_id: str = ""
```

**The 12 strong-signal rules (lines 74-203), first-match-wins:**

| # | Rule name | Pattern (summary) | Primary skill | Supporting | gate_before | gate_after | Confidence |
|---|-----------|-------------------|---------------|------------|-------------|------------|------------|
| 1 | `court_sms` | 法院短信/送达/案号/zxfw.court.gov.cn | `legal-court-sms` | — | — | `legal-de-ai-polish` | 0.95 |
| 2 | `judgment_or_transcript` | 判决书/裁定书/庭审笔录 | `legal-litigation-analysis` | — | — | — | 0.95 |
| 3 | `new_case` | 新接/建/立/办/收 + 案子/案件/项目/委托/立案 | `legal-new-case` | `litigation-matter-intake` | `ask-user-enforcement` | — | 0.95 |
| 4 | `docx_contract_review` | .docx/审合同/审查合同/审核合同/帮我.*合同 | `legal-contract-copilot` | — | `ask-user-enforcement` | `legal-de-ai-polish` | 0.95 |
| 5 | `qa_extraction` | 客户咨询.*沉淀/问答对/QA库/知识沉淀 | `legal-qa-extractor` | — | — | — | 0.95 |
| 6 | `polish_draft` | 写完.*起诉状/答辩状/合同/意见书/律师函/AI化表述/去AI腔 | `legal-de-ai-polish` | — | — | — | 0.95 |
| 7 | `ip_infringement` | 侵犯.*商标/专利/著作权/商业秘密/知识产权 | `ip-ip-clearance` | — | — | — | 0.95 |
| 8 | `ip_filing` | 申请.*商标/专利/著作权/版权/登记/注册 | `ip-trademark-search` | — | — | — | 0.95 |
| 9 | `labor_dispute` | 劳动争议/纠纷/仲裁/拖欠工资/违法解除 | `employment-labor-dispute-handling` | — | — | — | 0.95 |
| 10 | `compliance_system` | 上市前合规/合规体系建设/合规审查/差距 | `regulatory-compliance-system` | — | — | — | 0.95 |
| 11 | `opc_counsel` | OPC/一人公司/小微企业/常年顾问/公司设立/股权架构 | `legal-opc-legal-counsel` | — | — | — | 0.95 |

**Note:** The code has 11 `_Rule` entries in `_build_strong_signal_rules()`. The ROADMAP says "12 条" — this likely counts the `factual_short_circuit` rule (step 3 in `route()`) as the 12th.

**Routing flow (route() function, lines 340-428):**
1. Empty/trivially short (<4 chars) → `None` primary, confidence 0.9
2. Strong-signal rules (first match wins) → rule's primary_skill, confidence 0.95
3. Simple factual Q (statute lookup, term definition) → `None` primary, confidence 0.85, `matched_rule="factual_short_circuit"`
4. Soft trigger-phrase matching (threshold ≥0.4) → best match, `gate_before=ask-user-enforcement` (unless score ≥0.7 → skip), `gate_after=legal-de-ai-polish`
5. Ambiguous (below 0.4) → `None` primary, confidence = best_score or 0.0, `matched_rule="ambiguous"`

**Soft matching (_score_skill, lines 230-265):**
- Bag-of-triggers scoring: fraction of triggers found in message, weighted by phrase length (longer = stronger)
- Description bigram bonus: +0.1 per overlapping bigram (capped at 1.0)
- Only `user_facing=True` skills are scored
- Threshold: ≥0.4 → match; ≥0.7 → skip clarification

**Decision logging (_append_decision_log, lines 299-315):**
- Appends JSONL to `~/.hermes/profiles/lawfirm/router_logs/{session_id}.jsonl`
- Each record: decision fields + `timestamp` + `user_msg`
- No-op if `session_id` is empty

**Routing error recording (_record_routing_error, lines 318-337):**
- Appends to `~/.hermes/profiles/lawfirm/data/router_errors.jsonl`
- Records: timestamp, session_id, user_msg, router_primary, router_confidence, router_matched_rule, actual_skill
- Called by `report_routing_error()` — used when user feedback indicates wrong routing

### 3. lawfirm-profile Test Suite (对拍集 / Comparison Test Set)

**Location:** `/home/sorawatcher/workspace/lawfirm-profile/scripts/tests/`

**Test files:**

| File | Purpose | Fixture size |
|------|---------|-------------|
| `test_router.py` | Core routing scenarios (contract review, court SMS, factual Q, new case chain) | 4 test cases |
| `test_eval_router.py` | Eval harness with accuracy threshold ≥75% | 8 fixture cases |
| `integration_test_router.py` | Full chain integration with ≥80% accuracy threshold | 15 fixture cases |
| `test_decision_logging.py` | Decision log JSONL format verification | — |
| `test_routing_feedback.py` | Routing error recording + feedback loop | — |

**Integration fixture (15 cases, lines 26-45 of integration_test_router.py):**
- 7 strong-signal cases (contract, court SMS, new case, judgment, OPC, QA extraction, polish)
- 3 simple factual Qs (statute lookup → None)
- 5 soft-match cases (trademark, labor, compliance, copyright, construction)

**Expected accuracy: ≥80% (≥12/15 correct)**

This is the **对拍集** — the golden fixture set that Phase 98 must use to verify behavior non-regression.

### 4. lawyer-desktop agent_classifier.rs — Three-Mode Detection (691 lines)

**Location:** `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/src/skills/agent_classifier.rs`

**AgentMode enum (lines 6-12):**
```rust
pub enum AgentMode {
    Chat,    // 法律问答
    Draft,   // 文书起草
    Evidence, // 案情分析
}
```

**ClassifyContext (lines 28-44):**
- `user_message: String`
- `has_directory_ref: bool` — whether user attached a case directory
- `has_file_ref: bool` — whether user attached a file
- `directory_aliases: Vec<String>` — alias names for attached directories
- `current_mode: Option<String>` — mode of the committed task (draft/evidence) or None
- `current_task_label: Option<String>` — human label of committed task
- `has_active_document: bool` — whether a document/report already exists

**ClassifyResult (lines 46-61):**
- `mode: AgentMode` — Chat / Draft / Evidence
- `label: String` — short Chinese task label
- `reason: String` — one-sentence reason
- `action: String` — "continue" | "switch" | "aside" (drives switch-confirmation gate)
- `source: String` — "llm" | "fallback"
- `fallback_reason: Option<String>` — error category when fallback used
- `diagnostic: Option<String>` — error detail

**LLM classifier (classify_agent_mode, lines 125-196):**
- System prompt with 10 rules for mode + action classification
- Policy supplement with 5 boundary rules (chat is default, draft only for explicit document requests, evidence only for case-directory-based analysis)
- Temperature 0.0, max_tokens 160, non-streaming
- Returns JSON: `{"mode":"draft|evidence|chat","action":"continue|switch|aside","label":"...","reason":"..."}`

**Retry logic (classify_agent_mode_with_retry, lines 198-218):**
- Fast provider first; if fallback, retry with primary provider
- If both fail, returns the second fallback result

**Fallback rules (fallback_classify, lines 349-376):**
- **No keyword matching on user text** — deliberately structural only
- If `has_active_document` is true: use `current_mode` (keep the committed task's mode), default to Chat if current_mode is unparseable
- If `has_active_document` is false: always `Chat`
- Action is always `"continue"` — fallback must never surprise-switch
- Source is `"fallback"` with error reason

**Action normalization (normalize_action, lines 73-79):**
- "switch" / "切换" → "switch"
- "aside" / "插问" / "提问" → "aside"
- anything else → "continue" (safe default)

**Mode parsing (parse_mode_str, lines 328-345):**
- Handles Chinese aliases: "文书" / "起草" / "文书起草" → Draft; "案情" / "案情分析" / "诉讼" / "证据" → Evidence; "咨询" / "问答" / "法律问答" → Chat
- Also handles English: "draft"/"document"/"doc", "evidence"/"caseanalysis"/"case", "chat"/"qa"/"q&a"

**Action pinning rule (parse_classifier_response, lines 240-245):**
- When `current_mode` is None (no committed task), action is always pinned to "continue" — switch/aside is meaningless without a committed task

**Test cases (lines 468-691):**
- 10 unit tests covering: JSON parsing, mode aliases, action normalization, fallback behavior, retry logic, double-failure degradation, switch/aside detection, invalid JSON/mode handling

### 5. RouteDecision Contract (platform-contract)

**Location:** `packages/platform-contract/src/platform_contract/events.py` (lines 206-222)

**Frozen schema:**
```python
@dataclass(frozen=True, slots=True)
class RouteDecision:
    route_decision_id: str
    turn_id: str
    primary_skill: str | None
    confidence: float
    mode: RouteMode | str          # matched | simple_qa | skipped | zero_match
    created_at: str
    supporting_skills: list[str] = field(default_factory=list)
    gates_before: list[str] = field(default_factory=list)
    gates_after: list[str] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)
    matched_rule: str | None = None
    reason: str | None = None
    route_mismatch: bool | None = None
    industry_context: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)
```

**JSON Schema:** `packages/platform-contract/src/platform_contract/schemas/route_decision.schema.json`

**Key mapping from lawfirm router.py → platform-contract RouteDecision:**

| router.py field | RouteDecision field | Notes |
|----------------|-------------------|-------|
| `primary_skill` | `primary_skill` | Direct |
| `supporting_skills` | `supporting_skills` | Direct |
| `gate_before` | `gates_before` (list) | Single str → list[str] |
| `gate_after` | `gates_after` (list) | Single str → list[str] |
| `skip_clarification` | `metadata["skip_clarification"]` | Not a top-level field |
| `reason` | `reason` | Direct |
| `confidence` | `confidence` | Direct |
| `matched_rule` | `matched_rule` | Direct |
| `session_id` | `metadata["session_id"]` | Not a top-level field |
| — | `route_decision_id` | New (generated) |
| — | `turn_id` | New (from context) |
| — | `mode` | New (RouteMode enum) |
| — | `created_at` | New (timestamp) |
| — | `required_tools` | New (from descriptor) |
| — | `route_mismatch` | New (from feedback) |

**route_mismatch feedback association:**
- `FeedbackEvent.route_mismatch: bool | None` (events.py line 151/173/220)
- `FeedbackEvent.event_type` can be `"route_mismatch"` (enums.py line 136)
- Gateway feedback handler (`services/gateway/src/gateway/feedback.py`) maps `action="route_wrong"` → `event_type="route_mismatch"` with `SkillCandidate`
- `RouteDecision.route_mismatch` can be set to `True` when feedback indicates the route was wrong
- The router's `report_routing_error()` function is the existing pattern for this association

### 6. skill-index.json — The Real Index (from Phase 96)

**IndexRecord fields (packages/skill-index/src/inkstatute_skill_index/index_builder.py lines 40-68):**
- `skill_id`, `name`, `source_repo`, `plugin`, `relative_path`
- `skill_type` ("orchestration" or "leaf"), `parent_skill`, `child_skills`
- `description`, `frontmatter`, `token_estimate`
- `declared_gates`, `referenced_resources`, `practice_profile_dependency`
- `host_assumptions`, `required_scripts`, `license`, `version`
- `content_hash`, `has_local_modification`, `warnings`

**Phase 97 `index_to_descriptors()` (packages/skill-registry/src/inkstatute_skill_registry/mapper.py lines 77-152):**
- Reads `skill-index.json` → list of `NeutralSkillDescriptor`
- Maps: `skill_id`, `name`, `description`, `required_scripts` → `required_tool_refs`
- Metadata dict includes: `token_estimate`, `declared_gates`, `host_assumptions`, `skill_type`, `parent_skill`, `source_repo`, `plugin`
- **No `intent` field** — the current router's `search(category=intent)` will NOT match real descriptors because they have no `metadata["intent"]`

**Phase 97 routing manifest (`produce_routing_manifest()` in three_separation.py):**
- Produces metadata-only JSON with fields: `skill_id`, `name`, `description`, `token_estimate`, `declared_gates`, `host_assumptions`, `required_scripts`, `skill_type`, `parent_skill`
- No body text, no frontmatter raw content
- This is what the router should consume for routing decisions

### 7. SkillRegistryPort Interface

**Location:** `packages/skill-registry/src/inkstatute_skill_registry/registry.py` (lines 16-28)

```python
class SkillRegistryPort(Protocol):
    def list_skills(self) -> list[NeutralSkillDescriptor]: ...
    def get_skill(self, skill_id: str) -> NeutralSkillDescriptor | None: ...
    def search(
        self,
        tag: str | None = None,
        category: str | None = None,
        name_substring: str | None = None,
    ) -> list[NeutralSkillDescriptor]: ...
```

**search() filters (AND logic):**
- `tag` — matches `metadata["risk_level"] == tag` or `tag` in `metadata["tags"]`
- `category` — matches `metadata["intent"] == category`
- `name_substring` — case-insensitive substring on `name`

**Problem:** Real skill-index descriptors have no `metadata["intent"]` and no `metadata["risk_level"]`. The `search(category=...)` and `search(tag=...)` paths will return empty for real skills. The router needs a new search dimension or the descriptors need enriched metadata.

### 8. Legal Risk Grading (Current)

**Location:** `packages/router-service/src/inkstatute_router_service/legal_risk.py`

**Three levels:** `LOW`, `MEDIUM`, `HIGH`

**High-risk keywords (28):** 诉讼, 起诉, 仲裁, 判决, 法律意见, 合规审查, 赔偿, 犯罪, 刑事, 合同审查, 合同起草, 法律风险, 上诉, 抗诉, 立案, 庭审, 证据保全 + English equivalents

**Medium-risk keywords (15):** 合同, 法律, 法规, 条款, 权利, 义务, 违约 + English equivalents

**Usage in HYBRID strategy:** High-risk → forced to Hermes (`_HERMES_SKILL_ID = "hermes"`) regardless of confidence

### 9. lawyer-desktop router.rs — Prompt Assembly (627 lines)

**Location:** `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/src/skills/router.rs`

This file is about **prompt assembly** (not routing decisions) — it builds the system prompt with skill descriptions, research-gate injection, retrieval tool mapping, and citation rules. This is **Phase 102 scope** (CORE-05), NOT Phase 98. Phase 98 only ports the classifier (agent_classifier.rs) and the strong-signal router (router.py).

### 10. Trigger Phrase Soft Matching — Existing Patterns

**lawfirm-profile router.py:**
- `_score_skill()` — bag-of-triggers with phrase-length weighting + description bigram bonus
- Threshold: 0.4 (match), 0.7 (skip clarification)
- `gate_before = "ask-user-enforcement"` (when score < 0.7)
- `gate_after = "legal-de-ai-polish"` (always for soft matches)

**Current router-service:**
- No trigger-phrase matching at all — only 4 generic intent categories
- No 0.4 threshold
- No `gate_before`/`gate_after` semantics (the `gates_before`/`gates_after` fields exist in RouteDecision but are populated from context, not computed by the router)

## Key Decisions (Auto-Selected)

### 1. Router Data Source: skill-index.json via index_to_descriptors + SkillRegistry

[auto] Q: "How to switch router-service from manifest to skill-index.json?" → Selected: "Construct SkillRegistry from `index_to_descriptors(skill_index_path)`, inject into RouterService as `skill_registry`"

**Rationale:** Phase 97 already built `index_to_descriptors()` in `packages/skill-registry/src/inkstatute_skill_registry/mapper.py`. This function reads `skill-index.json` and produces `NeutralSkillDescriptor` records. The `SkillRegistry` class accepts a `list[NeutralSkillDescriptor]` at construction. The router already accepts `SkillRegistryPort` — no interface change needed. The migration is: replace the manifest-based descriptor list with index-based descriptors at the point where `RouterService` is constructed (the host/composition root). The router-service package itself does not need to know about `skill-index.json` — it just receives a `SkillRegistry` populated with real descriptors.

### 2. 12 Strong-Signal Regex Porting: New `strong_signal.py` module in router-service

[auto] Q: "How to port the 12 strong-signal rules from lawfirm-profile/scripts/router.py?" → Selected: "Create `packages/router-service/src/inkstatute_router_service/strong_signal.py` with the 11 `_Rule` entries + factual short-circuit as a pre-router layer"

**Rationale:** The strong-signal rules are deterministic regex patterns that run BEFORE the strategy cascade. They are a separate concern from the existing `classify_intent()` (which has 4 generic categories). The new module:
- Defines `_StrongSignalRule` dataclass (name, pattern, primary, supporting, gate_before, gate_after, skip_clarification, confidence, reason)
- `build_strong_signal_rules() -> list[_StrongSignalRule]` — the 11 rules from router.py
- `match_strong_signal(message: str) -> _StrongSignalRule | None` — first match wins
- `is_simple_factual(message: str) -> bool` — the factual short-circuit patterns (the 12th "rule")
- The `RouterService.decide()` method calls strong-signal matching first, before falling through to the strategy cascade

### 3. 对拍集 (Comparison Test Set): Port lawfirm-profile test fixtures as golden tests

[auto] Q: "How to verify behavior doesn't regress?" → Selected: "Port the 15-case integration fixture + 8-case eval fixture from lawfirm-profile/scripts/tests/ as golden tests in router-service"

**Rationale:** AGENTS.md mandates: "When porting logic from lawyer-desktop (Rust), use the Rust-side test cases as the Python-side golden fixture set." The same principle applies to porting from lawfirm-profile. The test fixtures in `integration_test_router.py` (15 cases, ≥80% accuracy) and `test_eval_router.py` (8 cases, ≥75% accuracy) become the golden test set. These are ported as new test files in `packages/router-service/tests/`:
- `test_strong_signal_golden.py` — 15 integration cases + 8 eval cases
- Each case: `(user_msg, expected_primary_skill)` pair
- Accuracy threshold: ≥80% (matching the original integration test threshold)
- The strong-signal rules must produce the same `primary_skill` for each input

### 4. Three-Mode Detection: New `mode_classifier.py` module in router-service

[auto] Q: "How to port Chat/Draft/Evidence from lawyer-desktop?" → Selected: "Create `packages/router-service/src/inkstatute_router_service/mode_classifier.py` with `AgentMode` enum, `ClassifyContext`, `ClassifyResult`, LLM port + fallback"

**Rationale:** The three-mode detection is a separate concern from skill routing. It classifies the user's message into a mode (Chat/Draft/Evidence) and an action (continue/switch/aside) relative to the current task. This is ported as a new module:
- `AgentMode` enum (Chat, Draft, Evidence) — Python StrEnum
- `ClassifyContext` dataclass (user_message, has_directory_ref, has_file_ref, directory_aliases, current_mode, current_task_label, has_active_document)
- `ClassifyResult` dataclass (mode, label, reason, action, source, fallback_reason, diagnostic)
- `ModeClassifierPort` Protocol — `classify(context: ClassifyContext) -> ClassifyResult`
- `LLMModeClassifier` — calls LLM with the same system prompt + policy supplement, parses JSON response
- `fallback_classify()` — structural-only fallback (no keyword matching on user text, action always "continue")
- `parse_mode_str()` — handles Chinese + English mode aliases
- `normalize_action()` — "switch"/"切换" → switch, "aside"/"插问"/"提问" → aside, else → continue
- Action pinning: when `current_mode` is None, action is always "continue"
- Retry logic: fast provider → primary provider → fallback

### 5. continue/switch/aside Actions: Stored in RouteDecision.metadata

[auto] Q: "How to implement continue/switch/aside actions?" → Selected: "Store `mode`, `action`, `label` in `RouteDecision.metadata` — no new top-level fields (contract freeze)"

**Rationale:** The `RouteDecision` dataclass is frozen (SAFETY-06 contract freeze). Adding new top-level fields would break the 28 existing gates. The three-mode detection results are stored in `metadata`:
- `metadata["agent_mode"]` = "chat" | "draft" | "evidence"
- `metadata["mode_action"]` = "continue" | "switch" | "aside"
- `metadata["mode_label"]` = short Chinese task label
- `metadata["mode_source"]` = "llm" | "fallback"
- `metadata["mode_fallback_reason"]` = error category (when fallback)

### 6. LLM Classification Fallback: Structural-only, action always "continue"

[auto] Q: "What rules when LLM fails?" → Selected: "Port the exact fallback_classify() logic: no keyword matching on user text, use current_mode when has_active_document, else Chat, action always continue"

**Rationale:** The lawyer-desktop fallback is deliberately conservative:
- It does NOT try to infer mode from user text keywords (this is a safety property — a broken LLM should not surprise-switch the user's task)
- When `has_active_document=True`: keep the current committed mode (if parseable), else Chat
- When `has_active_document=False`: always Chat
- Action is always "continue" — fallback must never surprise-switch
- Source is "fallback" with error reason for diagnostics
- This exact logic is ported 1:1 to Python

### 7. RouteDecision Contract: Map router.py fields to frozen RouteDecision, no schema changes

[auto] Q: "How to structure the RouteDecision event?" → Selected: "Map lawfirm router.py fields to existing RouteDecision: gate_before→gates_before list, gate_after→gates_after list, skip_clarification→metadata, session_id→metadata"

**Rationale:** The platform-contract `RouteDecision` is frozen. The mapping is:
- `primary_skill` → `primary_skill` (direct)
- `supporting_skills` → `supporting_skills` (direct)
- `gate_before` (str|None) → `gates_before` (list[str]) — wrap in list if not None
- `gate_after` (str|None) → `gates_after` (list[str]) — wrap in list if not None
- `skip_clarification` (bool) → `metadata["skip_clarification"]` (bool)
- `reason` → `reason` (direct)
- `confidence` → `confidence` (direct)
- `matched_rule` → `matched_rule` (direct)
- `session_id` → `metadata["session_id"]` (str)
- `route_decision_id` → generated UUID or from context
- `turn_id` → from context
- `mode` → derived from confidence + match (matched/simple_qa/zero_match)
- `created_at` → ISO-8601 timestamp
- `required_tools` → from matched descriptor's `required_tool_refs`

### 8. Decision Logging: JSONL append per session, same pattern as router.py

[auto] Q: "Where to log routing decisions?" → Selected: "Port the JSONL append pattern from router.py: per-session JSONL file with decision + timestamp + user_msg"

**Rationale:** The lawfirm-profile router.py already has a working decision logging pattern:
- `_append_decision_log()` appends to `{log_dir}/{session_id}.jsonl`
- Each record: decision fields + `timestamp` + `user_msg`
- No-op when session_id is empty (lets callers opt out)
- The platform version adapts this to log the `RouteDecision` (platform-contract format) instead of the router-local format
- Log directory is configurable (not hardcoded to `~/.hermes/...`)
- The log is used for `route_mismatch` feedback association: when a user reports `route_wrong`, the feedback system can look up the original decision by `turn_id` or `session_id`

### 9. Trigger Phrase Soft Matching: Port _score_skill + 0.4 threshold as new `soft_matcher.py`

[auto] Q: "How to implement 0.4 threshold soft matching?" → Selected: "Port `_score_skill()` and `_best_soft_match()` from router.py as `packages/router-service/src/inkstatute_router_service/soft_matcher.py`"

**Rationale:** The soft matching in router.py uses:
- Bag-of-triggers scoring with phrase-length weighting (longer phrases = stronger signal)
- Description bigram bonus (+0.1 per overlapping bigram, capped at 1.0)
- Only `user_facing=True` skills are scored
- Threshold: ≥0.4 → match; ≥0.7 → skip clarification
- `gate_before = "ask-user-enforcement"` when score < 0.7
- `gate_after = "legal-de-ai-polish"` always for soft matches

The ported module:
- `score_skill(message: str, descriptor: NeutralSkillDescriptor) -> float` — same scoring algorithm
- `best_soft_match(message: str, descriptors: list[NeutralSkillDescriptor], exclude: set[str]) -> tuple[str | None, float, str]` — same best-match logic
- The `host_assumptions` field in real descriptors replaces the `triggers` field from the lawfirm index (host_assumptions contain trigger patterns like `/plugin:skill`)
- Threshold constants: `_SOFT_MATCH_THRESHOLD = 0.4`, `_SKIP_CLARIFICATION_THRESHOLD = 0.7`

### 10. Legal Risk Grading: Preserve existing KeywordLegalRiskClassifier, no changes

[auto] Q: "How to preserve legal risk grading in real-index routing?" → Selected: "Keep existing `legal_risk.py` unchanged — it operates on message text, not skill metadata"

**Rationale:** The `KeywordLegalRiskClassifier` in `legal_risk.py` classifies the user's message text (not the skill descriptor) into low/medium/high risk. It works independently of the skill data source. The HYBRID strategy's legal-risk override (high-risk → Hermes) continues to work as-is. No changes needed.

### 11. Leaf Skill Matching: Use skill_id from real descriptors + host_assumptions for trigger matching

[auto] Q: "How to match to specific leaf sub-skills (not just 4 fake names)?" → Selected: "Strong-signal rules target real skill_ids (e.g., 'legal-court-sms', 'legal-contract-copilot'); soft matching uses host_assumptions as trigger phrases; registry.search uses name_substring on real skill names"

**Rationale:** The 12 strong-signal rules in router.py already target real skill names (e.g., `legal-court-sms`, `legal-contract-copilot`, `legal-new-case`, `ip-ip-clearance`, etc.). These are the actual skill_ids in the real index. The soft matching uses `host_assumptions` (which contain `/plugin:skill` trigger patterns and argument hints) as trigger phrases. The `SkillRegistry.search(name_substring=...)` path works on real skill names. The key change is that the router now has 396 real descriptors to search against, not 4 fake ones.

**Verification (criterion 6):** Given a set of real lawyer task samples (the 15-case integration fixture), the router must produce `primary_skill` values that match real skill_ids in the index — not `case_qa`, `contract_draft`, `litigation_summary`, or `compliance_review` (the 4 fake names).

## Summary

Phase 98 ports two pieces of production-validated routing knowledge into the platform's router-service:
1. **lawfirm-profile/scripts/router.py** → 12 strong-signal regex rules + soft trigger-phrase matching with 0.4 threshold + gate_before/gate_after semantics + decision logging
2. **lawyer-desktop/src-tauri/src/skills/agent_classifier.rs** → Chat/Draft/Evidence three-mode detection + continue/switch/aside actions + LLM fallback rules

The router's data source switches from 4 fake manifest skills to 396 real skill-index descriptors (via Phase 97's `index_to_descriptors()`). The frozen `RouteDecision` contract is preserved — new fields go into `metadata`. The lawfirm-profile test fixtures become the golden 对拍集 for behavior non-regression verification.
