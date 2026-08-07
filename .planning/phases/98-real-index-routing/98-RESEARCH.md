# Phase 98 Research — Real-Index Routing

**Phase:** 98 — Real-Index Routing
**Created:** 2026-08-10
**Status:** Complete
**Requirements:** SKILL-07, SKILL-08

---

## 1. packages/router-service — Current Routing Implementation

### 1.1 Source Files

**Location:** `packages/router-service/src/inkstatute_router_service/`

| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | 35 | Re-exports: RouterPort, RouterService, RouterStrategy, classify_intent, tool resolvers, legal risk, model classifier |
| `service.py` | 482 | `RouterService` — concrete `RouterPort` with `decide()`, `_decide_rule()`, `_decide_skill()`, `_decide_hybrid()`, `_run_cascade()`, `_build_decision()` |
| `strategies.py` | 33 | `RouterStrategy` StrEnum: `RULE`, `SKILL`, `HYBRID` (router-internal, maps to frozen `RouteMode`) |
| `classifier.py` | 48 | `classify_intent()` — 4 intent categories (factual_qa, drafting, analysis, review) via keyword/regex |
| `legal_risk.py` | 160 | `LegalRiskAssessment`, `LegalRiskClassifierPort` Protocol, `KeywordLegalRiskClassifier` (low/medium/high) |
| `model_classifier.py` | 50 | `ModelClassifierPort` Protocol + `ModelClassificationResult` (LLM-based, host-injected) |
| `port.py` | 30 | `RouterPort` Protocol — `decide(context) -> RouteDecision` |
| `tool_resolver.py` | 112 | `resolve_tool_refs()`, `resolve_all_tool_refs()` — joins skill `required_tool_refs` to MCP `capability_refs` |

### 1.2 Three Strategies (strategies.py)

```python
class RouterStrategy(StrEnum):
    RULE = "rule"
    SKILL = "skill"
    HYBRID = "hybrid"
```

These are **router-internal strategies** that map onto the frozen `RouteMode` outcome values (`matched`, `simple_qa`, `skipped`, `zero_match`). They are NOT `RouteMode` enum values — adding them would violate SAFETY-06 contract freeze.

- **RULE** — keyword/regex intent classification via `classify_intent()`. If registry is available, looks up skills by intent category. Falls back to `SIMPLE_QA` or `ZERO_MATCH`.
- **SKILL** — stateless Skill Registry lookup. Direct `skill_id` lookup via `get_skill()`, or message-based `search()`.
- **HYBRID** — Rule → Skill → Model cascade with confidence thresholds and legal-risk override (high-risk forced to Hermes).

### 1.3 How Router Currently Gets Skill Data (service.py lines 61-71)

```python
def __init__(
    self,
    skill_registry: "SkillRegistryPort | None" = None,
    strategy: RouterStrategy = RouterStrategy.RULE,
    legal_risk_classifier: LegalRiskClassifierPort | None = None,
    model_classifier: ModelClassifierPort | None = None,
) -> None:
```

The router receives a `SkillRegistryPort` (Protocol) at construction. When `skill_registry` is `None`, the router falls back to inline inference. When provided:
- `registry.search(category=intent)` — RULE strategy (service.py line 87)
- `registry.get_skill(skill_id)` — SKILL strategy (service.py line 154)
- `registry.search(name_substring=first_word)` — message-based search (service.py line 447)

### 1.4 Confidence Constants (service.py lines 32-44)

```python
_ROUTE_THRESHOLD = 0.8          # ≥ 0.8 → route directly (matched)
_CLARIFY_THRESHOLD = 0.5        # 0.5–0.8 → clarify (simple_qa); < 0.5 → fallback (zero_match)

_CONFIDENCE_RULE_WITH_REGISTRY = 0.9
_CONFIDENCE_RULE_NO_REGISTRY = 0.6
_CONFIDENCE_SKILL_EXACT = 1.0
_CONFIDENCE_SKILL_SINGLE = 0.85
_CONFIDENCE_SKILL_AMBIGUOUS = 0.6
_CONFIDENCE_NO_MATCH = 0.0

_HERMES_SKILL_ID = "hermes"     # safe-path backend for high-risk override
```

### 1.5 classify_intent() — 4 Generic Categories (classifier.py)

```python
INTENT_KEYWORDS: dict[str, list[str]] = {
    "factual_qa": ["什么", "是否", "如何", "请问", "查询", "what", "is", "how"],
    "drafting": ["起草", "草拟", "撰写", "draft", "write", "generate"],
    "analysis": ["分析", "总结", "归纳", "analyze", "summarize"],
    "review": ["审查", "审核", "检查", "review", "check", "compliance"],
}
```

**Key gap:** Only 4 generic intent categories with ~20 keywords total. NO domain-specific strong-signal rules. The `search(category=...)` matches on `metadata["intent"]` which the 4 fake skills had but real skill-index descriptors do NOT have.

### 1.6 HYBRID Cascade (service.py lines 228-422)

The `_decide_hybrid()` method:
1. **Legal-risk pre-check** — `classify_legal_risk(message)` → if high-risk, force to Hermes
2. **Rule layer** — `classify_intent()` + `registry.search(category=intent)` → confidence 0.9 (with registry) or 0.6 (without)
3. **Skill layer** — `get_skill(skill_id)` (confidence 1.0) or `search(name_substring)` (confidence 0.85 single, 0.6 ambiguous)
4. **Model layer** — `ModelClassifierPort.classify(context)` → confidence from model
5. **Confidence thresholds** — ≥0.8 matched, 0.5–0.8 simple_qa, <0.5 zero_match

### 1.7 Test Files and Test Count

**Location:** `packages/router-service/tests/`

| Test File | Test Count | Purpose |
|-----------|------------|---------|
| `test_hybrid_strategy.py` | 23 | HYBRID cascade: rule/skill/model layers, legal-risk override, confidence invariants, frozen mode |
| `test_legal_risk.py` | 19 | KeywordLegalRiskClassifier: high/medium/low, Chinese/English, frozen dataclass, protocol conformance |
| `test_strategies.py` | 16 | RouterStrategy enum, classify_intent, RULE strategy RouteMode mapping |
| `test_tool_resolver.py` | 12 | resolve_tool_refs: all/none/partial/dedup, frozen dataclass, preserves skill |
| `test_skill_strategy.py` | 8 | SKILL strategy: exact lookup, search, ambiguous, not-configured, stateless, frozen mode |
| `test_service.py` | 7 | RULE strategy: matched, zero_match, simple_qa, stateless, frozen mode, metadata |
| `test_port.py` | 3 | RouterPort Protocol: is_protocol, satisfies, has decide |
| **Total** | **88** | |

All tests use `_FakeSkillRegistry` with inline `NeutralSkillDescriptor` fixtures (not loaded from manifest or index).

### 1.8 NeutralSkillDescriptor Structure (platform-contract/events.py lines 105-112)

```python
@dataclass(frozen=True, slots=True)
class NeutralSkillDescriptor:
    skill_id: str
    name: str
    description: str | None = None
    input_schema_ref: str | None = None
    output_schema_ref: str | None = None
    required_tool_refs: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)
```

---

## 2. lawfirm-profile/scripts/router.py — 12 Strong-Signal Regex Rules

### 2.1 Full Script Overview (498 lines)

**Location:** `/home/sorawatcher/workspace/lawfirm-profile/scripts/router.py`

**Public API:**
- `route(user_msg: str, skill_index: dict, session_id: str = "") -> RouteDecision`
- `load_skill_index(path: str) -> dict`
- `report_routing_error(user_msg, skill_index, session_id, actual_skill) -> RouteDecision`

**Router-local RouteDecision (lines 38-53):**
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

### 2.2 The 12 Strong-Signal Rules (lines 74-203)

The code has 11 `_Rule` entries in `_build_strong_signal_rules()`. The ROADMAP says "12 条" — the 12th is the `factual_short_circuit` rule (step 3 in `route()`).

**`_Rule` dataclass (lines 59-71):**
```python
@dataclass
class _Rule:
    name: str
    pattern: re.Pattern
    primary: str | None
    supporting: list[str]
    gate_before: str | None = None
    gate_after: str | None = None
    skip_clarification: bool = False
    confidence: float = 0.95
    reason: str = ""
```

| # | Rule name | Regex pattern (summary) | Primary skill | Supporting | gate_before | gate_after | Confidence |
|---|-----------|------------------------|---------------|------------|-------------|------------|------------|
| 1 | `court_sms` | `法院\s*(短信|送达)|送达文书|案号\s*[\(（]?\d{4}[\)）]|zxfw\.court\.gov\.cn|全国法院送达平台` | `legal-court-sms` | — | — | `legal-de-ai-polish` | 0.95 |
| 2 | `judgment_or_transcript` | `判决书|裁定书|庭审笔录|开庭笔录|一审判决|二审判决` | `legal-litigation-analysis` | — | — | — | 0.95 |
| 3 | `new_case` | `新\s*(接|建|立|办|收)\s*(了|一个|起)?\s*(案子|案件|项目|业务|委托)|立案|建项目|接收新业务|刚接了.*案子|我.*接了.*案|接了个案|刚接了个` | `legal-new-case` | `litigation-matter-intake` | `ask-user-enforcement` | — | 0.95 |
| 4 | `docx_contract_review` | `\.docx\s*(合同|文件)?|DOCX\s*合同|合同\s*\.docx|审\s*合同|审查\s*合同|审核\s*合同|合同\s*审查|合同\s*审核|帮我.*合同|合同.*(帮我|需要|想)` | `legal-contract-copilot` | — | `ask-user-enforcement` | `legal-de-ai-polish` | 0.95 |
| 5 | `qa_extraction` | `客户.*咨询.*(沉淀|整理|知识库)|问答对|QA\s*库|知识沉淀` | `legal-qa-extractor` | — | — | — | 0.95 |
| 6 | `polish_draft` | `写完(了)?.*(起诉状|答辩状|合同|意见书|律师函)|AI\s*化表述|去\s*AI\s*腔|去除\s*AI\s*化` | `legal-de-ai-polish` | — | — | — | 0.95 |
| 7 | `ip_infringement` | `侵犯.*(商标|专利|著作权|商业秘密|知识产权)|(商标|专利|著作权).*(侵权|侵犯|抢注|山寨|假冒)|被.*(抢注|仿冒|抄袭)` | `ip-ip-clearance` | — | — | — | 0.95 |
| 8 | `ip_filing` | `申请.*(商标|专利|著作权|版权)|(商标|专利|著作权|版权)\s*(登记|注册|申请)|软件著作权\s*登记` | `ip-trademark-search` | — | — | — | 0.95 |
| 9 | `labor_dispute` | `劳动\s*(争议|纠纷|仲裁)|劳动合同\s*(争议|纠纷)|拖欠.*(工资|加班费|补偿金)|违法\s*解除` | `employment-labor-dispute-handling` | — | — | — | 0.95 |
| 10 | `compliance_system` | `上市\s*(前|合规|辅导)|合规体系\s*(建设|搭建)|合规\s*(审查|自查|检查)|合规差距` | `regulatory-compliance-system` | — | — | — | 0.95 |
| 11 | `opc_counsel` | `OPC|一人公司|小微企业|常年顾问|公司设立|股权架构|公私分离` | `legal-opc-legal-counsel` | — | — | — | 0.95 |
| 12 | `factual_short_circuit` | (see §2.4 below) | `None` | — | — | — | 0.85 |

### 2.3 Routing Flow (route() function, lines 340-428)

1. **Empty/trivially short** (<4 chars) → `None` primary, confidence 0.9, `matched_rule=""`
2. **Strong-signal rules** (first match wins) → rule's primary_skill, confidence 0.95
3. **Simple factual Q** (statute lookup, term definition) → `None` primary, confidence 0.85, `matched_rule="factual_short_circuit"`
4. **Soft trigger-phrase matching** (threshold ≥0.4) → best match, `gate_before=ask-user-enforcement` (unless score ≥0.7 → skip), `gate_after=legal-de-ai-polish`
5. **Ambiguous** (below 0.4) → `None` primary, confidence = best_score or 0.0, `matched_rule="ambiguous"`

### 2.4 Factual Short-Circuit Patterns (lines 208-224)

```python
_FACTUAL_Q_PATTERNS = [
    re.compile(r"《?[\u4e00-\u9fff]+法》?第\s*\d+\s*条.*是什么"),
    re.compile(r"民法典第\s*\d+\s*条"),
    re.compile(r"什么是\s*\S{2,15}"),
    re.compile(r"^.{0,20}(怎么读|什么意思|如何理解|有什么区别)"),
    re.compile(r"^\s*[Qq]:"),  # plain Q: prefix
]

def _is_simple_factual(user_msg: str) -> bool:
    msg = user_msg.strip()
    if not msg:
        return True
    if len(msg) < 12:
        return True
    return any(p.search(msg) for p in _FACTUAL_Q_PATTERNS)
```

### 2.5 Input/Output Format

**Input:** `route(user_msg: str, skill_index: dict[str, dict[str, Any]], session_id: str = "")`

The `skill_index` is a dict mapping skill_name → index entry (from `build_skill_index.build_index`). Each entry has:
```python
{
    "name": str,
    "description": str,
    "argument_hint": str,
    "category": str,
    "triggers": list[str],
    "source": str,
    "user_facing": bool,
    "is_orchestrator": bool,
    "path": str,
}
```

**Output:** `RouteDecision` dataclass (see §2.1 above)

### 2.6 Decision Logging (lines 299-315)

```python
def _append_decision_log(decision: RouteDecision, user_msg: str) -> None:
    if not decision.session_id:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{decision.session_id}.jsonl"
    record = decision.to_dict()
    record["timestamp"] = datetime.now(timezone.utc).isoformat()
    record["user_msg"] = user_msg
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
```

- **Log dir:** `~/.hermes/profiles/lawfirm/router_logs/{session_id}.jsonl`
- No-op if `session_id` is empty
- Each record: decision fields + `timestamp` + `user_msg`

### 2.7 Routing Error Recording (lines 318-337)

```python
def _record_routing_error(decision, user_msg, actual_skill) -> None:
    ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": ...,
        "session_id": decision.session_id,
        "user_msg": user_msg,
        "router_primary": decision.primary_skill,
        "router_confidence": decision.confidence,
        "router_matched_rule": decision.matched_rule,
        "actual_skill": actual_skill,
    }
```

- **Error log:** `~/.hermes/profiles/lawfirm/data/router_errors.jsonl`
- Called by `report_routing_error()` when user feedback indicates wrong routing

---

## 3. lawfirm-profile Test Suite — 对拍集 (Comparison Test Set)

### 3.1 Test Files

**Location:** `/home/sorawatcher/workspace/lawfirm-profile/scripts/tests/`

| File | Test Count | Purpose | Fixture size |
|------|------------|---------|-------------|
| `test_router.py` | 4 | Core routing scenarios (contract review, court SMS, factual Q, new case chain) | 4 test cases |
| `test_eval_router.py` | 3 | Eval harness with accuracy threshold ≥75% | 8 fixture cases |
| `test_build_skill_index.py` | 4 | Skill index builder | — |
| `test_routing_feedback.py` | 2 | Routing error recording + feedback loop | — |
| `test_decision_logging.py` | 1 | Decision log JSONL format verification | — |
| **Total** | **14** | | |

### 3.2 Integration Fixture — 15 Cases (integration_test_router.py lines 26-45)

This is the **对拍集** — the golden fixture set that Phase 98 must use to verify behavior non-regression.

```python
INTEGRATION_FIXTURE: list[tuple[str, str | None]] = [
    # ── Strong signal (7 cases — should all hit dedicated rules) ──
    ("我刚收到一份合同，帮我审一下", "legal-contract-copilot"),
    ("[法院短信] 您有新的送达文书，案号 (2025)京0105民初1234号", "legal-court-sms"),
    ("我新接了一个案子", "legal-new-case"),
    ("判决书已经下来了，帮我分析", "legal-litigation-analysis"),
    ("我是OPC一人公司的创始人", "legal-opc-legal-counsel"),
    ("客户咨询想沉淀到知识库", "legal-qa-extractor"),
    ("写完答辩状了，帮我去掉 AI 腔", "legal-de-ai-polish"),
    # ── Simple factual Qs (3 cases — router should punt) ──
    ("民法典第 1062 条是什么？", None),
    ("什么是公司法人人格否认？", None),
    ("刑法第 13 条讲什么？", None),
    # ── Soft match (5 cases — trigger phrase scoring) ──
    ("对方公司涉嫌侵犯我们的商标权", "ip-trademark-search"),
    ("我有个劳动合同纠纷要处理", "employment-labor-dispute-handling"),
    ("公司要上市前的合规审查", "regulatory-compliance-system"),
    ("我想申请软件著作权登记", "ip-copyright-registration"),
    ("建设工程合同纠纷，对方拖欠工程款", "construction-payment-dispute"),
]
```

**Expected accuracy: ≥80% (≥12/15 correct)**

### 3.3 Eval Fixture — 8 Cases (test_eval_router.py lines 41-50)

```python
fixture = [
    ("我刚收到一份合同，帮我审一下", "legal-contract-copilot"),
    ("[法院短信] 您有新的送达文书，案号 (2025)京0105民初1234号", "legal-court-sms"),
    ("我新接了一个案子", "legal-new-case"),
    ("判决书已经下来了，帮我分析", "legal-litigation-analysis"),
    ("我是OPC一人公司的创始人", "legal-opc-legal-counsel"),
    ("民法典第 1062 条是什么？", None),
    ("写完答辩状了，帮我去掉 AI 腔", "legal-de-ai-polish"),
    ("客户咨询想沉淀到知识库", "legal-qa-extractor"),
]
```

**Expected accuracy: ≥75% (≥6/8 correct)**

### 3.4 How to Create 对拍集 for Phase 98

1. Port the 15-case integration fixture + 8-case eval fixture as golden tests in `packages/router-service/tests/`
2. New test file: `test_strong_signal_golden.py` — each case is a `(user_msg, expected_primary_skill)` pair
3. Accuracy threshold: ≥80% (matching the original integration test threshold)
4. The strong-signal rules must produce the same `primary_skill` for each input
5. The soft-match cases depend on the skill index having trigger phrases — the real index's `host_assumptions` field replaces the lawfirm `triggers` field

---

## 4. lawyer-desktop agent_classifier.rs — Three-Mode Detection

### 4.1 Full Script Overview (691 lines)

**Location:** `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/src/skills/agent_classifier.rs`

### 4.2 AgentMode Enum (lines 6-26)

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AgentMode {
    Chat,    // 法律问答
    Draft,   // 文书起草
    Evidence, // 案情分析
}

impl AgentMode {
    pub fn ui_label(self) -> &'static str {
        match self {
            AgentMode::Chat => "法律问答",
            AgentMode::Draft => "文书起草",
            AgentMode::Evidence => "案情分析",
        }
    }
}
```

### 4.3 ClassifyContext (lines 28-44)

```rust
pub struct ClassifyContext {
    pub user_message: String,
    pub has_directory_ref: bool,         // user attached a case directory
    pub has_file_ref: bool,              // user attached a file
    pub directory_aliases: Vec<String>,  // alias names for attached directories
    pub current_mode: Option<String>,    // mode of committed task (draft/evidence) or None
    pub current_task_label: Option<String>, // human label of committed task
    pub has_active_document: bool,       // document/report already exists
}
```

### 4.4 ClassifyResult (lines 46-61)

```rust
pub struct ClassifyResult {
    pub mode: AgentMode,
    pub label: String,           // short Chinese task label
    pub reason: String,          // one-sentence reason
    pub action: String,          // "continue" | "switch" | "aside"
    pub source: String,          // "llm" | "fallback"
    pub fallback_reason: Option<String>, // error category when fallback used
    pub diagnostic: Option<String>,      // error detail
}
```

### 4.5 LLM Classifier (classify_agent_mode, lines 125-196)

- System prompt with 10 rules for mode + action classification
- Policy supplement with 5 boundary rules:
  1. Chat is default base
  2. Draft only for explicit document requests
  3. Evidence only for case-directory-based analysis
  4. Don't use single word to trigger mode switch
  5. When uncertain, choose chat
- Temperature 0.0, max_tokens 160, non-streaming
- Returns JSON: `{"mode":"draft|evidence|chat","action":"continue|switch|aside","label":"...","reason":"..."}`

### 4.6 Retry Logic (classify_agent_mode_with_retry, lines 198-218)

1. Fast provider first
2. If fallback, retry with primary provider
3. If both fail, returns the second fallback result

### 4.7 Action Normalization (normalize_action, lines 73-79)

```rust
fn normalize_action(raw: Option<&str>) -> String {
    match raw.map(|s| s.trim().to_lowercase()).as_deref() {
        Some("switch") | Some("切换") => "switch".into(),
        Some("aside") | Some("插问") | Some("提问") => "aside".into(),
        _ => "continue".into(),  // safe default
    }
}
```

### 4.8 Mode Parsing (parse_mode_str, lines 328-345)

Handles Chinese + English aliases:
- **Draft:** "draft", "document", "doc", "文书", "起草", "文书起草", "法律文书", "法律文书起草"
- **Evidence:** "evidence", "caseanalysis", "case", "案情", "案情分析", "诉讼", "诉讼方案", "分析", "证据", "证据分析"
- **Chat:** "chat", "qa", "q&a", "咨询", "问答", "法律问答", "法律咨询"

### 4.9 Action Pinning Rule (parse_classifier_response, lines 240-245)

When `current_mode` is `None` (no committed task), action is always pinned to `"continue"` — switch/aside is meaningless without a committed task.

### 4.10 Fallback Rules (fallback_classify, lines 349-376)

**Deliberately structural only — NO keyword matching on user text:**
- If `has_active_document` is true: use `current_mode` (keep committed task's mode), default to Chat if unparseable
- If `has_active_document` is false: always `Chat`
- Action is always `"continue"` — fallback must never surprise-switch
- Source is `"fallback"` with error reason

```rust
fn fallback_classify(ctx: &ClassifyContext, fallback_reason: &str, diagnostic: Option<String>) -> ClassifyResult {
    let mode = if ctx.has_active_document {
        ctx.current_mode.as_deref().and_then(parse_mode_str).unwrap_or(AgentMode::Chat)
    } else {
        AgentMode::Chat
    };
    ClassifyResult {
        label: ctx.current_task_label.clone().filter(|s| !s.trim().is_empty())
            .unwrap_or_else(|| mode.ui_label().to_string()),
        reason: "AI 分类失败，已使用结构性安全默认模式".into(),
        mode,
        action: "continue".into(),  // fallback must never surprise-switch
        source: "fallback".into(),
        fallback_reason: Some(fallback_reason.into()),
        diagnostic,
    }
}
```

### 4.11 Error Diagnostics (classify_error_diagnostic, lines 281-298)

Error categories:
- `auth_failed` — 401/403
- `model_not_found` — 404
- `timeout` — timeout/timed out
- `response_parse_failed` — failed to parse LLM response
- `network_error` — failed to send/DNS/connect
- `request_failed` — other

### 4.12 Test Cases (lines 468-691) — 10 Unit Tests

| Test | Purpose |
|------|---------|
| `parses_classifier_json` | JSON parsing, no committed task → action pinned to continue |
| `aviation_regulatory_risk_question_is_chat_when_llm_classifies_it` | Chat mode for risk analysis |
| `formal_legal_opinion_document_is_draft_when_llm_classifies_it` | Draft mode for formal document |
| `retry_uses_primary_when_fast_classifier_falls_back` | Retry: fast fails → primary succeeds |
| `double_classifier_failure_degrades_to_current_committed_mode` | Double failure → fallback keeps current_mode |
| `parses_switch_action_when_task_committed` | Switch action when task is committed |
| `parses_aside_action_for_mid_draft_question` | Aside action for mid-draft question |
| `unknown_action_degrades_to_continue` | Unknown action → continue (safe default) |
| `parses_qa_mode_alias` | Chinese mode aliases (问答, 法律问答, 文书起草, 案情分析) |
| `parses_llm_chinese_mode_label_for_draft` | Chinese mode label "文书起草" → Draft |
| `fallback_defaults_to_chat_without_current_artifact` | Fallback → Chat when no active document |
| `fallback_does_not_infer_draft_from_user_text` | Fallback does NOT infer from user text keywords |
| `fallback_keeps_invalid_json_diagnostic` | Fallback keeps diagnostic for invalid JSON |
| `fallback_keeps_invalid_mode_diagnostic` | Fallback keeps diagnostic for invalid mode |

### 4.13 Mode Detection in the Platform Codebase

**No existing mode detection in the platform.** Grep for `agent_mode`, `AgentMode`, `mode_classifier`, `mode_detection` in `packages/` and `apps/` found zero implementation files — only planning docs (Phase 94 desktop context, Phase 98 context) and requirement docs. The three-mode detection is a **new port** from lawyer-desktop Rust to Python.

---

## 5. RouteDecision Contract Event

### 5.1 Frozen Schema (platform-contract/events.py lines 206-222)

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

### 5.2 JSON Schema

**Location:** `packages/platform-contract/src/platform_contract/schemas/route_decision.schema.json`

Required fields: `route_decision_id`, `turn_id`, `primary_skill`, `confidence`, `mode`, `created_at`

### 5.3 Field Mapping: lawfirm router.py → platform-contract RouteDecision

| router.py field | RouteDecision field | Notes |
|----------------|-------------------|-------|
| `primary_skill` | `primary_skill` | Direct |
| `supporting_skills` | `supporting_skills` | Direct |
| `gate_before` (str\|None) | `gates_before` (list[str]) | Single str → wrap in list |
| `gate_after` (str\|None) | `gates_after` (list[str]) | Single str → wrap in list |
| `skip_clarification` (bool) | `metadata["skip_clarification"]` | Not a top-level field |
| `reason` | `reason` | Direct |
| `confidence` | `confidence` | Direct |
| `matched_rule` | `matched_rule` | Direct |
| `session_id` | `metadata["session_id"]` | Not a top-level field |
| — | `route_decision_id` | New (generated UUID) |
| — | `turn_id` | New (from context) |
| — | `mode` | New (RouteMode enum) |
| — | `created_at` | New (ISO-8601 timestamp) |
| — | `required_tools` | New (from descriptor's `required_tool_refs`) |
| — | `route_mismatch` | New (from feedback) |

### 5.4 How RouteDecision Is Currently Built (service.py lines 453-482)

```python
def _build_decision(self, context, mode, primary_skill, confidence, ...) -> RouteDecision:
    return RouteDecision(
        route_decision_id=context.get("route_decision_id", ""),
        turn_id=context.get("turn_id", ""),
        primary_skill=primary_skill,
        confidence=confidence,
        mode=mode,
        created_at=context.get("created_at", ""),
        supporting_skills=...,
        gates_before=list(context.get("gates_before", [])),
        gates_after=list(context.get("gates_after", [])),
        required_tools=...,
        matched_rule=matched_rule,
        reason=reason,
        route_mismatch=context.get("route_mismatch"),
        industry_context=dict(context.get("industry_context", {})),
        metadata=metadata_extra if metadata_extra is not None else {},
    )
```

**Key observation:** `gates_before` and `gates_after` are currently populated from context, NOT computed by the router. Phase 98 must make the router compute these from strong-signal rules and soft matching.

---

## 6. Trigger Phrase Soft Matching

### 6.1 lawfirm-profile router.py — _score_skill (lines 230-265)

```python
def _score_skill(msg: str, entry: dict[str, Any]) -> float:
    if not entry.get("user_facing", False):
        return 0.0

    msg_lower = msg.lower()
    triggers = entry.get("triggers", [])
    if not triggers:
        return 0.0

    # Score = fraction of triggers found in msg, weighted by phrase length
    score = 0.0
    max_possible = 0.0
    for trig in triggers:
        weight = min(len(trig), 6) / 6.0  # longer phrases = stronger signal
        max_possible += weight
        if trig in msg:
            score += weight

    if max_possible == 0:
        return 0.0
    raw = score / max_possible

    # Description bonus: if msg contains 2+ bigrams from description
    desc = entry.get("description", "")
    bigrams = _extract_bigrams(desc)
    if bigrams:
        overlap = sum(1 for bg in bigrams if bg in msg)
        if overlap:
            raw = min(1.0, raw + 0.1 * overlap)

    return raw
```

### 6.2 Threshold Semantics

- **0.4** — soft match threshold: `best_score >= 0.4` → match (route to skill)
- **0.7** — skip clarification threshold: `best_score >= 0.7` → `skip_clarification=True`, `gate_before=None`
- **<0.4** — ambiguous: `primary_skill=None`, `matched_rule="ambiguous"`

### 6.3 Gate Semantics

- `gate_before = "ask-user-enforcement"` — when score < 0.7 (clarification needed)
- `gate_after = "legal-de-ai-polish"` — always for soft matches

### 6.4 Current router-service — No Soft Matching

The current `packages/router-service` has:
- NO trigger-phrase matching
- NO 0.4 threshold
- NO `gate_before`/`gate_after` computation (the `gates_before`/`gates_after` fields exist in RouteDecision but are populated from context, not computed by the router)

### 6.5 _best_soft_match (lines 274-293)

```python
def _best_soft_match(user_msg, index, exclude) -> tuple[str | None, float, str]:
    best_name = None
    best_score = 0.0
    best_reason = ""
    for name, entry in index.items():
        if name in exclude:
            continue
        s = _score_skill(user_msg, entry)
        if s > best_score:
            best_score = s
            best_name = name
            best_reason = f"trigger-phrase match on {name} (triggers hit: ...)"
    return best_name, best_score, best_reason
```

### 6.6 Porting to Real Index

The lawfirm `skill_index` has a `triggers` field (extracted by `build_skill_index.py` from `_TRIGGER_PHRASES`). The real `skill-index.json` from Phase 96 does NOT have a `triggers` field — it has `host_assumptions` (which contain `/plugin:skill` trigger patterns and argument hints) and `description`.

**Porting strategy:** Use `host_assumptions` as trigger phrases + `description` for bigram bonus. The `host_assumptions` field contains patterns like `/commercial-legal:contract-review` which can be split to extract skill names as trigger phrases.

---

## 7. Legal Risk Grading

### 7.1 Current Implementation (legal_risk.py)

**Three levels:** `LOW`, `MEDIUM`, `HIGH` (StrEnum)

**High-risk keywords (28):** 诉讼, 起诉, 仲裁, 判决, 法律意见, 合规审查, 赔偿, 犯罪, 刑事, 合同审查, 合同起草, 法律风险, 上诉, 抗诉, 立案, 庭审, 证据保全 + English: litigation, lawsuit, arbitration, judgment, legal opinion, compliance review, criminal, compensation, legal risk, appeal, indictment, trial, evidence preservation

**Medium-risk keywords (15):** 合同, 法律, 法规, 条款, 权利, 义务, 违约 + English: contract, legal, law, regulation, clause, rights, obligations, breach

### 7.2 Grading Logic

1. If any high-risk keyword matches → `HIGH`, `is_high_risk=True`
2. If no high-risk but medium-risk matches → `MEDIUM`, `is_high_risk=False`
3. Otherwise → `LOW`, `is_high_risk=False`

### 7.3 Usage in HYBRID Strategy

High-risk → forced to Hermes (`_HERMES_SKILL_ID = "hermes"`) regardless of confidence. This is a **pre-check** that runs before the cascade.

### 7.4 Phase 98 Scope

**No changes needed.** The `KeywordLegalRiskClassifier` operates on message text, not skill metadata. It works independently of the skill data source. The HYBRID strategy's legal-risk override continues to work as-is.

---

## 8. skill-index.json Consumption

### 8.1 IndexRecord Fields (skill-index/index_builder.py lines 40-68)

```python
@dataclass(frozen=True, slots=True)
class IndexRecord:
    skill_id: str
    name: str
    source_repo: str
    plugin: str | None
    relative_path: str
    skill_type: str          # "orchestration" or "leaf"
    parent_skill: str | None
    child_skills: list[str]
    description: str | None
    frontmatter: dict[str, Any]
    token_estimate: int
    declared_gates: list[str]
    referenced_resources: list[str]
    practice_profile_dependency: bool
    host_assumptions: list[str]
    required_scripts: list[str]
    license: str | None
    version: str | None
    content_hash: str
    has_local_modification: bool
    warnings: list[str]
```

### 8.2 index_to_descriptors() (skill-registry/mapper.py lines 77-152)

Reads `skill-index.json` → list of `NeutralSkillDescriptor`:

```python
def index_to_descriptors(skill_index_path: str | Path) -> list[NeutralSkillDescriptor]:
    # Reads JSON, iterates "skills" array, converts each record
    ...
```

**Field mapping:**
- `skill_id` → `skill_id`
- `name` → `name`
- `description` → `description`
- `required_scripts` → `required_tool_refs`
- Metadata dict: `token_estimate`, `declared_gates`, `host_assumptions`, `skill_type`, `parent_skill`, `source_repo`, `plugin`

**No `intent` field** — the current router's `search(category=intent)` will NOT match real descriptors.

### 8.3 Fields Available for Routing

| Field | Source | Routing use |
|-------|--------|-------------|
| `skill_id` | IndexRecord | Direct skill_id lookup (SKILL strategy) |
| `name` | IndexRecord | Name substring search |
| `description` | IndexRecord | Bigram bonus for soft matching |
| `host_assumptions` | IndexRecord → metadata | Trigger phrases for soft matching |
| `declared_gates` | IndexRecord → metadata | Gate_before/gate_after mapping |
| `skill_type` | IndexRecord → metadata | Filter: only score `leaf` skills for routing |
| `token_estimate` | IndexRecord → metadata | Context budget (not routing) |
| `required_scripts` | IndexRecord → required_tool_refs | Tool resolution |

### 8.4 SkillRegistryPort Interface (registry.py lines 16-28)

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

**Problem:** Real skill-index descriptors have no `metadata["intent"]` and no `metadata["risk_level"]`. The `search(category=...)` and `search(tag=...)` paths return empty for real skills. The router needs a new search dimension or the descriptors need enriched metadata.

### 8.5 How Router-Service Will Consume the Real Index

Per the context auto-selected decision:
1. Construct `SkillRegistry` from `index_to_descriptors(skill_index_path)` at the composition root
2. Inject into `RouterService` as `skill_registry`
3. No interface change needed — the router already accepts `SkillRegistryPort`
4. The router-service package itself does not know about `skill-index.json` — it just receives a `SkillRegistry` populated with real descriptors

---

## 9. route_mismatch Feedback Association

### 9.1 RouteDecision.route_mismatch Field

**Location:** `packages/platform-contract/src/platform_contract/events.py` line 220

```python
route_mismatch: bool | None = None
```

Also present in `FeedbackEvent` (line 151/173) and `AgentResult` (line 220).

### 9.2 FeedbackEvent.route_mismatch

**Location:** `packages/platform-contract/src/platform_contract/enums.py` line 136

```python
ROUTE_MISMATCH = "route_mismatch"  # FeedbackEventType enum
```

### 9.3 Gateway Feedback Handler (services/gateway/src/gateway/feedback.py)

**Flow:**
1. User submits feedback with `action="route_wrong"` via `POST /v1/feedback`
2. `_normalize_action()` maps `"route_mismatch"` → `"route_wrong"` (line 198)
3. `_action_to_event_type("route_wrong")` → `"route_mismatch"` (line 211)
4. `fields_map["route_mismatch"] = True` (line 105)
5. `SkillCandidate` created with `source="route_mismatch"`, `requires_human_review=True`, `metadata.no_auto_modify=True` (lines 106-113)
6. `FeedbackEvent` built with route_mismatch=True

### 9.4 The Feedback Loop

```
User reports route_wrong
    ↓
Gateway feedback handler → FeedbackEvent(route_mismatch=True, SkillCandidate)
    ↓
RouteDecision.route_mismatch can be set to True
    ↓
Router's report_routing_error() pattern (from lawfirm-profile) records:
    timestamp, session_id, user_msg, router_primary, router_confidence,
    router_matched_rule, actual_skill
```

### 9.5 lawfirm-profile report_routing_error (router.py lines 431-444)

```python
def report_routing_error(user_msg, skill_index, session_id, actual_skill) -> RouteDecision:
    decision = route(user_msg, skill_index, session_id=session_id)
    _record_routing_error(decision, user_msg, actual_skill)
    return decision
```

This is the existing pattern for route_mismatch feedback association. Phase 98 ports this as a decision logging + error recording mechanism in the platform.

---

## 10. Leaf Skill Matching

### 10.1 How to Match User Input to Specific Leaf Sub-Skills

**Current problem:** The router can only match to 4 fake skill names (`case_qa`, `contract_draft`, `litigation_summary`, `compliance_review`). Real lawyer tasks need to hit specific leaf sub-skills like `legal-court-sms`, `legal-contract-copilot`, `employment-labor-dispute-handling`, etc.

### 10.2 Three Matching Layers (Phase 98 Design)

1. **Strong-signal rules** — 11 deterministic regex rules that target real skill_ids directly (e.g., `legal-court-sms`, `legal-contract-copilot`, `legal-new-case`, `ip-ip-clearance`). These are first-match-wins with confidence 0.95.

2. **Soft trigger-phrase matching** — Uses `host_assumptions` from real descriptors as trigger phrases + `description` for bigram bonus. Threshold 0.4 for match, 0.7 for skip clarification. This is the fallback when no strong-signal rule matches.

3. **Registry search** — `SkillRegistry.search(name_substring=...)` works on real skill names. The `search(category=...)` path needs a new dimension since real descriptors have no `metadata["intent"]`.

### 10.3 Metadata Available for Matching

| Metadata | Source | Matching use |
|----------|--------|-------------|
| `name` | NeutralSkillDescriptor.name | Name substring search |
| `description` | NeutralSkillDescriptor.description | Bigram bonus for soft matching |
| `host_assumptions` | metadata["host_assumptions"] | Trigger phrases (contains `/plugin:skill` patterns) |
| `skill_type` | metadata["skill_type"] | Filter: only score `leaf` skills for routing (orchestration entries are parent skills) |
| `declared_gates` | metadata["declared_gates"] | Gate_before/gate_after mapping |

### 10.4 How the 396-Skill Index Enables Better Matching

- **396 real skills** vs 4 fake skills → 99x more routing targets
- **~60 orchestration entries** (parent skills) can be filtered out for leaf matching
- **~285 leaf sub-skills** are the actual routing targets
- **host_assumptions** contain `/plugin:skill` trigger patterns that can be parsed into trigger phrases
- **declared_gates** tell the router which gates to apply (research-gate, ask-user-enforcement, legal-de-ai-polish)

---

## 11. New Modules to Create in Phase 98

### 11.1 strong_signal.py

**Purpose:** Port the 11 strong-signal regex rules + factual short-circuit as a pre-router layer.

**Components:**
- `_StrongSignalRule` dataclass (name, pattern, primary, supporting, gate_before, gate_after, skip_clarification, confidence, reason)
- `build_strong_signal_rules() -> list[_StrongSignalRule]` — the 11 rules from router.py
- `match_strong_signal(message: str) -> _StrongSignalRule | None` — first match wins
- `is_simple_factual(message: str) -> bool` — the factual short-circuit patterns (12th "rule")
- `RouterService.decide()` calls strong-signal matching first, before falling through to the strategy cascade

### 11.2 soft_matcher.py

**Purpose:** Port `_score_skill()` and `_best_soft_match()` from router.py.

**Components:**
- `score_skill(message: str, descriptor: NeutralSkillDescriptor) -> float` — same scoring algorithm
- `best_soft_match(message, descriptors, exclude) -> tuple[str | None, float, str]` — same best-match logic
- Threshold constants: `_SOFT_MATCH_THRESHOLD = 0.4`, `_SKIP_CLARIFICATION_THRESHOLD = 0.7`
- Uses `host_assumptions` as trigger phrases (replaces lawfirm `triggers` field)
- Description bigram bonus (+0.1 per overlapping bigram, capped at 1.0)

### 11.3 mode_classifier.py

**Purpose:** Port Chat/Draft/Evidence three-mode detection from agent_classifier.rs.

**Components:**
- `AgentMode` StrEnum (Chat, Draft, Evidence)
- `ClassifyContext` dataclass (user_message, has_directory_ref, has_file_ref, directory_aliases, current_mode, current_task_label, has_active_document)
- `ClassifyResult` dataclass (mode, label, reason, action, source, fallback_reason, diagnostic)
- `ModeClassifierPort` Protocol — `classify(context: ClassifyContext) -> ClassifyResult`
- `LLMModeClassifier` — calls LLM with the same system prompt + policy supplement, parses JSON response
- `fallback_classify()` — structural-only fallback (no keyword matching, action always "continue")
- `parse_mode_str()` — handles Chinese + English mode aliases
- `normalize_action()` — "switch"/"切换" → switch, "aside"/"插问"/"提问" → aside, else → continue
- Action pinning: when `current_mode` is None, action is always "continue"

### 11.4 decision_log.py

**Purpose:** Port JSONL decision logging from router.py.

**Components:**
- `append_decision_log(decision: RouteDecision, user_msg: str, log_dir: Path, session_id: str)` — appends to `{log_dir}/{session_id}.jsonl`
- `record_routing_error(decision, user_msg, actual_skill, error_log: Path)` — appends to error log
- Log directory is configurable (not hardcoded to `~/.hermes/...`)

---

## 12. Key Decisions from Context (Auto-Selected)

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Router data source: skill-index.json via `index_to_descriptors` + `SkillRegistry` | Phase 97 already built `index_to_descriptors()`. No interface change needed — router already accepts `SkillRegistryPort`. |
| 2 | 12 strong-signal rules: new `strong_signal.py` module | Deterministic regex rules run BEFORE strategy cascade. Separate concern from existing `classify_intent()`. |
| 3 | 对拍集: Port 15-case integration + 8-case eval fixtures as golden tests | AGENTS.md mandates using source-side test cases as golden fixture set. |
| 4 | Three-mode detection: new `mode_classifier.py` module | Separate concern from skill routing. Classifies mode + action relative to current task. |
| 5 | continue/switch/aside: stored in `RouteDecision.metadata` | Contract freeze — no new top-level fields. `metadata["agent_mode"]`, `metadata["mode_action"]`, `metadata["mode_label"]`. |
| 6 | LLM fallback: structural-only, action always "continue" | Safety property — broken LLM should not surprise-switch user's task. |
| 7 | RouteDecision mapping: no schema changes | `gate_before`→`gates_before` list, `gate_after`→`gates_after` list, `skip_clarification`→`metadata`, `session_id`→`metadata`. |
| 8 | Decision logging: JSONL append per session | Same pattern as router.py. Log dir configurable. Used for route_mismatch feedback association. |
| 9 | Soft matching: new `soft_matcher.py` with 0.4 threshold | Port `_score_skill()` + `_best_soft_match()`. Uses `host_assumptions` as trigger phrases. |
| 10 | Legal risk grading: keep existing `legal_risk.py` unchanged | Operates on message text, not skill metadata. Independent of skill data source. |
| 11 | Leaf skill matching: strong-signal targets real skill_ids, soft matching uses host_assumptions | 12 strong-signal rules already target real skill names. 396 real descriptors enable specific leaf matching. |

---

## 13. Risks and Mitigations

### 13.1 Soft Matching Trigger Source Change

**Risk:** The lawfirm `skill_index` has a `triggers` field extracted by `build_skill_index.py`. The real `skill-index.json` has `host_assumptions` instead. The soft matching algorithm depends on trigger phrases.

**Mitigation:** Parse `host_assumptions` for `/plugin:skill` patterns and extract skill names as trigger phrases. The `description` bigram bonus still works with the real index's `description` field. Some soft-match test cases may need adjustment if the trigger phrase coverage differs.

### 13.2 search(category=intent) Incompatibility

**Risk:** Real descriptors have no `metadata["intent"]`. The RULE strategy's `search(category=intent)` returns empty for real skills.

**Mitigation:** The strong-signal rules bypass the intent classification entirely (they match on regex patterns, not intent categories). The soft matching uses `host_assumptions` and `description`, not `category`. The `search(name_substring=...)` path still works. The intent-based search path becomes less important with strong-signal + soft matching layers.

### 13.3 Contract Freeze Compliance

**Risk:** Adding new fields to `RouteDecision` would break the 28 existing gates (SAFETY-06).

**Mitigation:** All new data (agent_mode, mode_action, mode_label, skip_clarification, session_id) goes into `metadata` dict. No top-level field changes. The `gates_before`/`gates_after` fields already exist as `list[str]` — the router just needs to populate them from strong-signal rules instead of from context.

### 13.4 Test Fixture Dependency on lawfirm Skill Index

**Risk:** The lawfirm-profile test fixtures depend on `build_index(LAWFIRM_SKILLS_ROOT)` which scans `~/.hermes/profiles/lawfirm/skills/`. This directory may not exist in CI.

**Mitigation:** Port the fixture cases as static `(user_msg, expected_primary_skill)` pairs in `test_strong_signal_golden.py`. The strong-signal rules are pure regex — they don't need the skill index to produce `primary_skill`. The soft-match cases need a fixture skill index with trigger phrases — create inline fixture descriptors.

---

## 14. Summary

Phase 98 ports two pieces of production-validated routing knowledge into the platform's router-service:

1. **lawfirm-profile/scripts/router.py** (498 lines) → 12 strong-signal regex rules + soft trigger-phrase matching with 0.4 threshold + gate_before/gate_after semantics + decision logging
2. **lawyer-desktop/src-tauri/src/skills/agent_classifier.rs** (691 lines) → Chat/Draft/Evidence three-mode detection + continue/switch/aside actions + LLM fallback rules

The router's data source switches from 4 fake manifest skills to 396 real skill-index descriptors (via Phase 97's `index_to_descriptors()`). The frozen `RouteDecision` contract is preserved — new fields go into `metadata`. The lawfirm-profile test fixtures (15 integration cases + 8 eval cases) become the golden 对拍集 for behavior non-regression verification.

**New modules to create:**
- `strong_signal.py` — 11 regex rules + factual short-circuit
- `soft_matcher.py` — trigger-phrase scoring with 0.4/0.7 thresholds
- `mode_classifier.py` — Chat/Draft/Evidence + continue/switch/aside
- `decision_log.py` — JSONL decision logging

**Existing modules unchanged:**
- `legal_risk.py` — operates on message text, not skill metadata
- `strategies.py` — RouterStrategy enum unchanged
- `port.py` — RouterPort Protocol unchanged
- `tool_resolver.py` — tool resolution unchanged
- `model_classifier.py` — ModelClassifierPort unchanged

**Test count impact:**
- Current: 88 tests in 7 files
- Expected after Phase 98: ~130+ tests (88 existing + ~15 golden strong-signal + ~10 soft matching + ~15 mode classifier + ~5 decision logging)
