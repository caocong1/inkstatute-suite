# Phase 99 Research — Practice Profile

**Phase:** 99 — Practice Profile
**Created:** 2026-08-11
**Status:** Complete
**Requirements:** PROF-01, PROF-02, PROF-03

---

## 1. CLAUDE.md Practice Profile Files — Source Format

### 1.1 File Inventory

**Location:** `/home/sorawatcher/workspace/ai-for-china-legal/<plugin>/CLAUDE.md`

**Count:** 15 CLAUDE.md files (1 root + 13 plugin-level + 1 shared)

| File | Lines | Plugin | Domain |
|------|-------|--------|--------|
| `CLAUDE.md` (root) | 54 | — | Project-level guidance, naming conventions, validation |
| `commercial-legal/CLAUDE.md` | 257 | 商事合同 | Contract review, drafting, liability |
| `litigation-legal/CLAUDE.md` | 153 | 诉讼仲裁 | Litigation, arbitration, evidence preservation |
| `employment-legal/CLAUDE.md` | 137 | 劳动人事 | Labor law, employment, dismissal |
| `data-compliance/CLAUDE.md` | 254 | 数据合规 | PIPL, DSL, CSL, cross-border, PIA |
| `ip-legal/CLAUDE.md` | 299 | 知识产权 | Trademark, patent, copyright, clearance |
| `shared/CLAUDE.md` | 58 | Shared | Research-gate, shared templates, cross-plugin refs |
| `ai-governance/CLAUDE.md` | — | AI 治理 | Algorithm filing, deep synthesis |
| `construction-legal/CLAUDE.md` | — | 建设工程 | Construction disputes, payment |
| `criminal-compliance/CLAUDE.md` | — | 刑事合规 | Criminal compliance, risk |
| `family-legal/CLAUDE.md` | — | 婚姻家事 | Family law, divorce, inheritance |
| `legal-aid/CLAUDE.md` | — | 法律援助 | Legal aid, pro bono |
| `legal-builder-hub/CLAUDE.md` | — | 社区技能中心 | Skill building, community |
| `law-student/CLAUDE.md` | — | 法考培训 | Bar exam, legal education |
| `regulatory-legal/CLAUDE.md` | — | 监管合规 | Regulatory compliance |

### 1.2 Common Structure Across All Plugin CLAUDE.md Files

Every plugin-level CLAUDE.md follows this pattern:

```markdown
# <plugin-name> — 实践配置文件模板

> 本文件由 `/<plugin>:cold-start-interview` 冷启动访谈生成和更新。

## 我们是谁          ← Identity & team
## 谁在使用          ← User role (律师/非律师)
## 可用集成          ← Integrations
## <domain-specific> ← Review stance / compliance stance / IP stance
## 风险校准          ← Risk calibration (some plugins)
## 升级矩阵          ← Escalation matrix
## 文书风格          ← Document style
## 输出              ← Output format, work product titles
## 共享护栏          ← Shared guardrails (no-silent-fill, timeliness, etc.)
## 事项工作区        ← Matter workspace (enabled/disabled)
## 审查过的种子文档  ← Seed documents table
```

### 1.3 Commercial-Legal CLAUDE.md — Detailed Structure (257 lines)

**This is the most complex and serves as the reference template.**

#### `## 我们是谁` (Identity & Team)

| Field | Type | Example Values |
|-------|------|---------------|
| 公司名称 | string | [PLACEHOLDER] |
| 实体类型 | enum | 有限责任公司 / 股份有限公司 / 合伙企业 / 个人独资企业 / 其他 |
| 合同团队规模 | string | [PLACEHOLDER] |
| 最终升级联系人 | string | [PLACEHOLDER] |
| 每月处理合同数量 | string | [PLACEHOLDER] |
| 主要交易对手类型 | enum | 大客户 / 中小企业 / 个人 / 混合 |
| 合同管理系统 | string | [PLACEHOLDER] |
| 最大痛点 | string | [PLACEHOLDER] |
| 执业环境 | enum | 公司法务 / 律所 / 政府法务 / 其他 |

#### `## 谁在使用` (User Role)

| Field | Type | Example Values |
|-------|------|---------------|
| 角色 | enum | 律师 / 非律师但有律师可咨询 / 非律师且无律师可咨询 |
| 律师联系人 | string | [PLACEHOLDER] |

> If role is non-lawyer: all outputs are research for lawyer review, not conclusions. Pauses before legal-consequence actions.

#### `## 可用集成` (Integrations)

| Field | Type |
|-------|------|
| 合同管理系统 | enum (已连接/未连接/不适用) |
| 电子签名 | enum (已连接/未连接/不适用) |
| 文档存储 | string |
| 企业微信/钉钉 | enum (已连接/未连接/不适用) |

#### `## 审查立场` (Review Stance) — 7 Dimensions × 2 Sides

**整体风险偏好:** [保守型 / 平衡型 / 进取型]

**甲方立场 (买方/委托方) and 乙方立场 (卖方/受托方) — each has 7 dimensions:**

| Dimension | Chinese | Fields per dimension |
|-----------|---------|---------------------|
| 责任限制 | 责任限制 | 直接赔偿上限, 间接/后果性损害 (排除/capped/不设限), 接受的例外(carveouts), 基数定义, 可接受的备选, 绝不接受 |
| 违约金 | 违约金 | 标准立场, 可接受的备选, 绝不接受 |
| 知识产权 | 知识产权 | 标准立场, 可接受的备选, 绝不接受 |
| 数据保护 | 数据保护 | 标准立场, 具体要求, 可接受的备选 |
| 期限与终止 | 期限与终止 | 标准立场, 可接受的备选, 绝不接受 |
| 管辖法律与争议解决 | 管辖法律与争议解决 | 首选, 可接受, 需升级, 绝不接受 |
| 交易破坏者 | 交易破坏者 | 绝对不可接受的条款 (single field) |

**Total fields in 审查立场:** 1 (risk_appetite) + 2 sides × 7 dimensions × ~4 fields = ~57 fields

#### `## 升级矩阵` (Escalation Matrix)

**审批权限 table:**

| 角色 | 可独立审批金额上限 | 需升级条件 |
|------|-------------------|-----------|
| 助理/初级律师 | ¥[PLACEHOLDER] | 超过金额上限或有关键问题 |
| 主办律师 | ¥[PLACEHOLDER] | 超过金额上限或有交易破坏者 |
| 法务总监/合伙人 | 无上限 | — |

**金额阈值:** 3 threshold values (助理/主办/总监)

**自动升级触发条件:** List of conditions (无限责任条款, 知识产权全部转让, 管辖法律为境外法律, etc.)

#### `## 文书风格` (Document Style)

| Field | Example |
|-------|---------|
| 修订语气 | 温和但有立场，优先保留对方框架做最小修改 |
| 利益相关者摘要 | 写给业务负责人，控制在 200 字以内 |
| 工作产物存放位置 | [PLACEHOLDER] |
| 续约/期限提醒发送给 | [PLACEHOLDER] |

#### `## 输出` (Output Format)

- **工作产物标题:** Two variants (律师角色 vs 非律师角色)
- **审查者注释块:** Markdown template with date, statute sources, reading scope, severity counts, timeliness
- **静默模式规则:** External deliverables need privilege scrubbing
- **下一步决策树模板:** 5 options (起草修订版, 升级, 获取更多事实, 观望等待, 其他)

#### `## 共享护栏` (Shared Guardrails)

| Guardrail | Description |
|-----------|-------------|
| 无静默补充原则 | Don't fill gaps with guesses; report and ask |
| 时效性触发 | Flag `[时效性 flagged]` if >6 months since last update |
| 验证用户陈述的法律事实 | Cross-check user-stated statute numbers before writing to config |
| 来源标签规范 | `[法宝]`, `[法规网站]`, `[网络搜索 — 需验证]`, `[模型知识 — 需验证]`, `[用户提供]` |
| 目的地检查 | Check privilege circle before output |
| 双重严重性 | Legal risk + commercial friction per issue |
| 管辖识别 | 经济特区, 民族自治地方, 自贸区, 港澳台 — flag `[管辖 flagged]` |

### 1.4 Plugin-Specific Variations

**Litigation-legal (153 lines)** — replaces 审查立场 with:
- `## 风险校准` — severity definitions (极高/高/中/低), probability definitions (>70%/30-70%/<30%), materiality thresholds
- `## 利益冲突清除` — clearance method, responsible person, parallel entry policy
- `## 外部律师合作` — partner firms, selection criteria, budget approval
- `## 证据保全` — preservation trigger, scope, refresh cycle, notification template
- `## 和解策略` — settlement authority threshold, approval flow, tendency

**Employment-legal (137 lines)** — replaces 审查立场 with:
- `## 审查立场` → 雇佣审查 (试用期, 工时制度, 社会保险, 竞业限制) + 解雇审查 (法定解除情形, 经济补偿)
- `## 风险校准` — 4-level risk (🔴🟠🟡🟢)

**Data-compliance (254 lines)** — replaces 审查立场 with:
- `## 合规立场` — 敏感数据政策, 跨境政策, 数据安全立场
- `## 风险校准` — 4-level risk with PIPL/DSL/CSL penalty references
- Industry-specific regulator table (金融/医疗/汽车/教育/互联网/电信/能源)

**IP-legal (299 lines)** — replaces 审查立场 with:
- `## 维权与申请立场` — 商标策略, 专利策略, 著作权策略, 清权严格度
- IP组合概况 (商标/专利/著作权/字号与域名)
- 维权/异议/诉讼触发 table with time limits

**Key insight:** Each plugin has a **domain-specific** CLAUDE.md structure. The common sections are: 我们是谁, 谁在使用, 可用集成, 升级矩阵, 文书风格, 输出, 共享护栏, 事项工作区, 审查过的种子文档. The domain-specific section (审查立场/合规立场/维权与申请立场/风险校准) varies significantly per plugin.

---

## 2. Practice Profile Dependency in Skill Index

### 2.1 Detection Logic

**Location:** `packages/skill-index/src/inkstatute_skill_index/metadata_extractor.py` (lines 105-115)

```python
_PRACTICE_PROFILE_MARKERS: list[str] = [
    "CLAUDE.md",
    "实践配置",
    "审查立场",
    "执业配置",
]

def _check_practice_profile_dependency(body: str) -> bool:
    """Return True if body references CLAUDE.md or practice-profile concepts."""
    return any(marker in body for marker in _PRACTICE_PROFILE_MARKERS)
```

The detector scans skill body text for 4 markers. If any marker is found, the skill's `practice_profile_dependency` is set to `True` in the index.

### 2.2 Index Record Structure

**Location:** `packages/skill-index/src/inkstatute_skill_index/index_builder.py` (lines 40-68)

```python
@dataclass(frozen=True, slots=True)
class IndexRecord:
    skill_id: str
    name: str
    source_repo: str
    plugin: str | None
    relative_path: str
    skill_type: str  # "orchestration" or "leaf"
    parent_skill: str | None
    child_skills: list[str]
    description: str | None
    frontmatter: dict[str, Any]
    token_estimate: int
    declared_gates: list[str]
    referenced_resources: list[str]
    practice_profile_dependency: bool  # ← This field
    host_assumptions: list[str]
    required_scripts: list[str]
    license: str | None
    version: str | None
    content_hash: str
    has_local_modification: bool
    warnings: list[str]
```

### 2.3 Actual Dependency Count (Live Index Scan)

**Scanned:** `ai-for-china-legal` (338 skills) + `legal-skills` (51 skills) = 389 total

| Repo | Total Skills | `practice_profile_dependency=True` |
|------|-------------|-----------------------------------|
| ai-for-china-legal | 338 | 334 |
| legal-skills | 51 | 3 |
| **Total** | **389** | **337** |

**Note:** The V3-PRD and ROADMAP say "约 50 个" (about 50), but the actual scan shows 337 skills with `practice_profile_dependency=True`. This is because the marker `"审查立场"` appears in many skill bodies that reference the practice profile concept, not just the ~50 skills that directly read CLAUDE.md. The detection is broad — it catches any skill that mentions "审查立场" or "CLAUDE.md" or "实践配置" or "执业配置" in its body text.

**legal-skills with dependency:** `legal-contract-copilot`, `legal-project-init`, `legal-skill-manager`

**Implication for Phase 99:** The injector must check the `practice_profile_dependency` flag from the index, but the actual number of skills that need profile injection is much larger than 50. The platform-side model must be efficient enough to handle 337+ dependent skills.

---

## 3. Cold-Start Interview Skills

### 3.1 Interview Orchestration Structure

**Location:** `<plugin>/skills/cold-start-interview/SKILL.md` (13 files, one per plugin)

**Commercial-legal cold-start-interview (113 lines):**

Orchestrates 5 sub-skills in sequence:

| Step | Sub-skill | Collects | CLAUDE.md Section |
|------|-----------|----------|-------------------|
| 1 | `identity-team` | Identity, practice environment, team structure, integrations | `## 我们是谁`, `## 谁在使用`, `## 可用集成` |
| 2 | `review-stance` | Risk appetite, 甲方/乙方 dual-stance 7 dimensions, dealbreakers | `## 审查立场` |
| 3 | `escalation-rules` | Amount thresholds, risk-level triggers, auto-escalation conditions | `## 升级矩阵` |
| 4 | `document-style` | Output format, tone, citation preferences, bilingual needs | `## 文书风格`, `## 输出` |
| 5 | `jurisdiction-profile` | Governing law, local regulations, court preferences, special zones | `## 共享护栏` → `### 管辖识别` |

**Each sub-skill can be triggered independently** to update only its section.

**Order rationale:** Identity first (establishes context) → Review stance second (most critical) → Escalation rules third (depends on team hierarchy) → Document style fourth (independent) → Jurisdiction last (supplementary).

### 3.2 Practice Profile Schema

**Location:** `<plugin>/skills/_shared/practice-profile-schema.md` (13 files)

**Commercial-legal practice-profile-schema.md (242 lines):**

Defines the contract between CLAUDE.md and skills:

1. **Truth source:** `commercial-legal/CLAUDE.md` is the single source of truth (prose format, not JSON/YAML)
2. **Field mapping table:** Interview field → CLAUDE.md section → reading skills
3. **Skill reading contract:** Read CLAUDE.md before work, check for `[PLACEHOLDER]`, choose run mode
4. **Temporary mode defaults** (see §4 below)
5. **Legal fact reasonableness checks** before writing to config
6. **Schema versioning:** New fields default to `[PLACEHOLDER]`, backward compatible

### 3.3 Mapping to Elicitation Protocol

Each interview step maps to one `elicitation.requested` event:
- 5 steps × 2-4 questions = 10-20 total questions across the full interview
- Answers collected via `POST /v1/runs/{run_id}/elicitation`
- Answers written back to tenant practice profile

---

## 4. Temporary Mode (临时模式) — Existing Specification

### 4.1 Specification (from practice-profile-schema.md §3.2)

When skills detect CLAUDE.md is missing or contains `[PLACEHOLDER]`:

1. **Must NOT silently use guessed values**
2. **Must offer two choices:**
   - Run `/commercial-legal:cold-start-interview` (~5 minutes) to configure
   - Say "临时模式" to use generic defaults
3. **In temporary mode, tag every output:** `[临时模式 — 配置你的档案以获得定制输出]`

### 4.2 Temporary Mode Defaults

| Field | Default Value |
|-------|---------------|
| 风险偏好 | 平衡型 |
| 执业角色 | 律师 |
| 管辖法律 | 中国大陆法律 |
| 甲方/乙方立场 | 标记常见风险，不偏向任何一方 |
| 升级矩阵 | 不自动升级，提示律师判断 |
| 文书风格 | 半正式，含法条引用，不含案例引用 |

### 4.3 Implementation Notes

- The `[临时模式]` tag must appear on **every output** when in temporary mode
- The tag is: `[临时模式 — 配置你的档案以获得定制输出]`
- Tests must assert the tag is never omitted in temporary mode
- The agent core (Phase 100+) is responsible for including this tag in user-visible output
- Phase 99 establishes the contract: the injector produces the tag in the context section

---

## 5. Tenant Storage — Current Platform Patterns

### 5.1 Tenant Schema

**Location:** `packages/platform-contract/src/platform_contract/schemas/tenant.schema.json`

```json
{
  "required": ["tenant_id", "name", "created_at"],
  "properties": {
    "tenant_id": { "type": "string" },
    "name": { "type": "string" },
    "status": { "type": "string" },
    "default_workspace_id": { "type": "string" },
    "created_at": { "$ref": "common.schema.json#/$defs/datetime" },
    "metadata": { "$ref": "common.schema.json#/$defs/metadata" }
  }
}
```

### 5.2 Gateway Auth & Tenant Patterns

**Location:** `services/gateway/src/gateway/auth.py` (154 lines)

```python
@dataclass(frozen=True, slots=True)
class AuthContext:
    identity: Identity | None
    authenticated: bool
    tenant_id: str          # ← Always present (from identity or default)
    error: str | None
```

**Key methods:**
- `authenticate(headers) -> AuthContext` — never raises, returns `authenticated=False` on failure
- `require_auth(headers) -> AuthContext` — raises 401 on failure
- `require_role(headers, allowed_roles) -> AuthContext` — raises 403 if role not allowed
- `check_tenant(ctx, resource_tenant_id)` — raises 403 on cross-tenant access

**Default tenant:** `GatewayConfig.default_tenant_id = "default"` — single-tenant fallback when auth is disabled.

### 5.3 Session Storage Pattern

**Location:** `services/gateway/src/gateway/sessions.py` (179 lines)

```python
@dataclass
class GatewaySession:
    session_id: str
    tenant_id: str
    user_id: str
    conversation_id: str
    created_at: int
    expires_at: int
    devices: list[str] = field(default_factory=list)
```

`GatewaySessionManager` uses RBAC `SessionStore` Protocol (in-memory MVP). `list_sessions(tenant_id)` filters by tenant.

### 5.4 Storage Pattern Summary

All tenant-scoped data uses **in-memory storage** with Protocol-based interfaces:
- `SessionStore` Protocol → `InMemorySessionStore` implementation
- `GatewayElicitationHandler._submissions` — dict keyed by `(run_id, interrupt_id)` with `tenant_id`
- No database introduced (AGENTS.md: "Do not introduce a new service, database, queue, or runtime dependency")

**For practice profiles:** A `PracticeProfileStore` Protocol with `InMemoryPracticeProfileStore` implementation follows the same pattern. The Protocol allows future swap to DB/Redis without changing call sites.

---

## 6. RBAC — Current Authorization Model

### 6.1 Roles

**Location:** `packages/rbac/src/rbac/roles.py` (23 lines)

```python
class Role(str, Enum):
    ADMIN = "admin"       # Full access to all admin API endpoints
    OPERATOR = "operator" # Operational endpoints (sessions, tasks, feedback, health)
    LAWYER = "lawyer"     # Read-only case data (sessions, tasks)
    VIEWER = "viewer"     # Read-only case data (sessions, tasks)
```

### 6.2 Identity Resolution

**Location:** `packages/rbac/src/rbac/identity.py` (129 lines)

```python
@dataclass(frozen=True, slots=True)
class Identity:
    role: Role
    tenant_id: str
```

`resolve_identity()` — Bearer token first (HMAC-SHA256 with role+tenant claims), session cookie fallback. When `rbac_enabled=False`, static-token fallback returns `Identity(role=ADMIN, tenant_id="default")`.

### 6.3 Gateway Auth Methods

**Location:** `services/gateway/src/gateway/auth.py`

| Method | Behavior |
|--------|----------|
| `authenticate(headers)` | Returns `AuthContext` (never raises) |
| `require_auth(headers)` | Raises 401 `GatewayAuthError` on failure |
| `require_role(headers, allowed_roles)` | Raises 403 if role not in `allowed_roles` |
| `check_tenant(ctx, resource_tenant_id)` | Raises 403 on cross-tenant access |

### 6.4 Practice Profile RBAC Design

| Operation | Allowed Roles | Cross-tenant |
|-----------|--------------|--------------|
| Read profile | ADMIN, OPERATOR, LAWYER, VIEWER | Always denied |
| Write profile | ADMIN, OPERATOR | Always denied |
| Start interview | ADMIN, OPERATOR | Always denied |

---

## 7. Elicitation Protocol — Platform Contract

### 7.1 Data Structures

**Location:** `packages/platform-contract/src/platform_contract/unified_events.py` (lines 93-114)

```python
@dataclass(frozen=True, slots=True)
class ElicitationOption:
    label: str
    value: str

@dataclass(frozen=True, slots=True)
class ElicitationQuestion:
    id: str
    question: str
    allow_multiple: bool = False
    options: list[ElicitationOption] = field(default_factory=list)

@dataclass(frozen=True, slots=True)
class ElicitationRequestedPayload:
    interrupt_id: str
    intro: str
    questions: list[ElicitationQuestion]
    resume_state_ref: str | None = None
    expires_at: str | None = None
    metadata: JsonObject = field(default_factory=dict)
```

### 7.2 JSON Schema

**Location:** `packages/platform-contract/src/platform_contract/schemas/elicitation_requested.schema.json`

- `questions` array: `minItems: 2`, `maxItems: 4` (enforces 2-4 question constraint)
- Each question has `id`, `question`, optional `allow_multiple`, optional `options` array
- Each option has `label` and `value` (both strings)

### 7.3 Elicitation Contract Functions

**Location:** `packages/platform-contract/src/platform_contract/elicitation.py` (189 lines)

| Function | Purpose |
|----------|---------|
| `elicitation_to_run_interrupt(payload, run_id, session_id, created_at)` | Convert `ElicitationRequestedPayload` → V2 `RunInterrupt` |
| `run_interrupt_to_elicitation(interrupt)` | Convert V2 `RunInterrupt` → `ElicitationRequestedPayload` |
| `validate_question_count(questions)` | Raise `ValueError` if not 2-4 items |
| `format_answer_display(questions, answers)` | Format numbered Q&A display per ASK-USER-PROTOCOL.md |

### 7.4 Gateway Elicitation Handler

**Location:** `services/gateway/src/gateway/elicitation.py` (91 lines)

```python
class GatewayElicitationHandler:
    def __init__(self, runtime: object | None = None):
        self._submissions: dict[tuple[str, str], dict[str, Any]] = {}

    def handle_submit_elicitation(self, ctx, run_id, body) -> JsonObject:
        # Validates interrupt_id + answers
        # Stores submission with tenant_id
        # Delegates to runtime.resume_elicitation() if supported
        return {"status": "submitted", "run_id": run_id, "interrupt_id": interrupt_id}
```

**Endpoint:** `POST /v1/runs/{run_id}/elicitation` — accepts clarification card answers, stores in-memory keyed by `(run_id, interrupt_id)` with `tenant_id`.

### 7.5 Multi-Round Interview Flow

For cold-start interview via elicitation:

```
1. POST /v1/practice-profile/interview → creates run, returns run_id
2. Run emits elicitation.requested (step 1: identity-team, 2-4 questions)
3. Client renders clarification card (ui-core)
4. User submits answers → POST /v1/runs/{run_id}/elicitation
5. Handler stores answers, delegates to runtime.resume_elicitation()
6. Answers written to PracticeProfileStore
7. Run emits elicitation.requested (step 2: review-stance, 2-4 questions)
8. Repeat for steps 3-5
9. Interview complete → profile stored in PracticeProfileStore
```

---

## 8. Skill Context Injection — Body Injector & Profile Injection

### 8.1 SkillBodyInjector (Phase 97)

**Location:** `packages/skill-materializer/src/inkstatute_skill_materializer/body_injector.py` (499 lines)

**Purpose:** Budget-constrained skill body injection with section-priority trimming.

**Section priority assignment:**
- **Protected** (never trimmed): frontmatter + description + first `##` section
- **High**: sections containing "research-gate" or "ask-user" in header
- **Low**: sections containing "example", "appendix", or "reference" in header
- **Medium**: all other sections

**Trim algorithm:**
1. Parse SKILL.md into sections by `##` headers
2. Assign priorities
3. While `injected_token_estimate > budget_tokens`: remove lowest-priority section with most tokens
4. If protected sections alone exceed budget, raise `SkillBodyBudgetError`

**On-demand body reading:**
```python
def read_skill_body(skill_id, index_path, budget_tokens, chars_per_token=4) -> SkillBodyInjectionResult:
    # Load index → find record → resolve source path → read SKILL.md → apply budget trimming
```

### 8.2 HostAssumptionRewriter — CLAUDE.md Flagging

**Location:** `packages/skill-materializer/src/inkstatute_skill_materializer/host_assumption_rewriter.py` (269 lines)

**Rule 3:** `CLAUDE.md` references are flagged as `practice_profile_dependency` in the `RewriteReport` but **NOT rewritten** in the text. The rewriter logs entries with `rule_applied="claude_md_flag"`.

This means the materializer is already aware of which skills depend on practice profiles. The skill index also records `practice_profile_dependency: bool` per skill.

### 8.3 Gap: No Practice Profile Injection Exists

The body injector handles skill body text injection but does **NOT** inject practice profile content. There is no existing mechanism to inject CLAUDE.md practice profile data into the skill execution context.

**What Phase 99 must build:**

A `PracticeProfileInjector` that:
1. Checks the skill's `practice_profile_dependency` flag in the index
2. If True, fetches the tenant's practice profile from `PracticeProfileStore`
3. If no profile exists, generates temporary mode defaults with `[临时模式]` tag
4. Renders the profile as a structured context section (e.g., `## 执业配置\n\n### 审查立场\n...`)
5. Prepends the context section to the skill body before the body injector runs
6. Returns metadata: `profile_injected: bool`, `temporary_mode: bool`, `plugin: str`

**Injection flow:**
```
1. Router selects skill_id
2. PracticeProfileInjector.inject(skill_id, tenant_id) → context_section
3. SkillBodyInjector.inject(skill_body_text) → trimmed_body
4. Final context = context_section + trimmed_body
5. Agent core receives final context for execution
```

---

## 9. No Secrets Enforcement

### 9.1 Existing Secret Detection — privacy_scan.py

**Location:** `packages/acp-event-bridge/src/inkstatute_acp_event_bridge/privacy_scan.py` (396 lines)

**Secret patterns (11 compiled regex):**

| Rule ID | Pattern |
|---------|---------|
| `secret_like` | `\b(?:access|refresh|api|client|encoding)[_-]?(?:token|key|secret)\b` |
| `secret_assignment` | `\b(?:token|secret|key)\s*[:=]` |
| `internal_path` | `(?:^|\s)(?:/[^ \n\t]+){2,}` |
| `windows_path` | `[a-z]:\\[^ \n\t]+` |
| `provider_leak` | `\b(?:model[:\s]|provider[:\s]|api[_-]?key|quota|token[_\s-]?usage)(?!\w)` |
| `api_error` | `\b(?:api key invalid|quota exceeded|rate limit retry|insufficient quota)\b` |
| `hermes_home_path` | `/home/[^/]+/\.hermes` |
| `hermes_dot_path` | `\.hermes[^/]` |
| `acp_env_secret` | `\b(?:HERMES_HOME|ACP_[A-Z_]+|AGENT_[A-Z_]+)\s*[:=]\s*\S+` |
| `acp_debug` | `\b(?:acp:|agent-client-protocol:)` |
| `profile_path` | `\bprofile path\b` |
| `env_secret_combo` | `\benv\b.*\b(?:secret|token|key)\b` |

**Key principle:** The scanner **never** includes the actual matched secret text in any finding — only the pattern name, field path, and audit metadata (hash prefix + length).

### 9.2 Operator Config Secret References

**Location:** `packages/operator-config/src/inkstatute_operator_config/secrets.py` (62 lines)

`normalize_config_secret_ref(raw, field)` validates reference shapes:
- Accepts `None`/blank, `env:NAME`, bare env-key identifiers, `secret://` paths
- Rejects other strings fail-closed without echoing the rejected value
- `InvalidSecretRefError` — message has no secret material

### 9.3 Practice Profile Secret Validation Design

For practice profiles, the `PracticeProfileStore.update()` method must:
1. Validate incoming data against a secret-detection regex set (reuse patterns from `privacy_scan.py`)
2. Check for patterns like `api_key`, `secret`, `token`, `password`, `aes_key`, `-----BEGIN`
3. If any field value matches, reject the write with a 400 error
4. Never echo the matched secret text in the error message

**Validation patterns for practice profiles (subset):**
```python
_PRACTICE_PROFILE_SECRET_PATTERNS = [
    re.compile(r"(?:api[_-]?key|access[_-]?token|secret[_-]?key)\s*[:=]", re.IGNORECASE),
    re.compile(r"-----BEGIN\s+(?:RSA\s+)?(?:PRIVATE\s+)?KEY-----"),
    re.compile(r"\b(?:password|passwd|pwd)\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\b(?:aes[_-]?key|encoding[_-]?aes[_-]?key)\b", re.IGNORECASE),
]
```

---

## 10. No Practice Profiles in Contract Event Log

### 10.1 Contract Event Log Pattern

**Location:** `packages/platform-contract/src/platform_contract/events.py`

`RunEvent` is the persisted audit trail. Events carry `payload` and `metadata`. The privacy scanner enforces:
- Sensitive content fields must use `raw_payload_ref` (hash + length) instead of full text
- `EVENT_TYPES_REQUIRING_RAW_PAYLOAD_REF`: `message.completed`, `tool_call.completed`, `artifact.created`, `citation.recorded`
- Elicitation and permission events are exempt (content needed for real-time interaction)

### 10.2 Practice Profile Exclusion Design

Practice profiles are **runtime-only context** — they are injected into the skill execution context but **never serialized into events**.

**Enforcement mechanisms:**
1. `PracticeProfileInjector.inject()` returns a context string + metadata, but **no `RunEvent` is created** for the injection
2. Profile data remains in `PracticeProfileStore` (in-memory)
3. The injector returns metadata (`profile_injected`, `temporary_mode`, `plugin`) that can be included in **run metadata** (not in event payloads)
4. The privacy scanner (`privacy_scan.py`) would catch any accidental leakage of profile content into events

**If observability is needed:** The injector's metadata can be logged to run metadata (a separate channel from event payloads), but the full profile text is never included.

---

## 11. Practice Profile Field Inventory — Detailed

### 11.1 Common Header Fields (All Plugins)

| Field Group | Fields |
|-------------|--------|
| Identity | org_name, entity_type, team_size, escalation_contact, monthly_volume, max_pain_point |
| User Role | role (律师/非律师), lawyer_contact |
| Integrations | contract_mgmt, e_signature, doc_storage, wecom_dingtalk |
| Escalation Matrix | approval_table (role → amount_limit → escalation_condition), amount_thresholds, auto_escalation_triggers |
| Document Style | revision_tone, stakeholder_summary, work_product_location, renewal_reminder_recipient |
| Output | work_product_title (lawyer/non-lawyer), reviewer_note_block, silent_mode_rules, decision_tree_template |
| Shared Guardrails | no_silent_fill, timeliness_trigger, legal_fact_verification, source_labels, destination_check, dual_severity, jurisdiction_identification |
| Matter Workspace | enabled (bool) |
| Seed Documents | table of reviewed docs |

### 11.2 Commercial-Legal Domain Fields

| Field Group | Fields |
|-------------|--------|
| Risk Appetite | risk_appetite (保守型/平衡型/进取型) |
| 甲方立场 × 7 dimensions | 责任限制 (6 fields), 违约金 (3), 知识产权 (3), 数据保护 (3), 期限与终止 (3), 管辖法律与争议解决 (4), 交易破坏者 (1) |
| 乙方立场 × 7 dimensions | Same as 甲方, different values |
| Escalation | 3-tier approval table, 3 amount thresholds, 4+ auto-escalation triggers |

### 11.3 Litigation-Legal Domain Fields

| Field Group | Fields |
|-------------|--------|
| Risk Calibration | severity_definitions (4 levels), probability_definitions (3 levels), materiality_thresholds (3) |
| Conflict Clearance | clearance_method, responsible_person, parallel_entry_policy |
| External Counsel | partner_firms, selection_criteria, budget_approval |
| Evidence Preservation | trigger_method, scope, refresh_cycle, notification_template |
| Settlement Strategy | authority_threshold, approval_flow, tendency |

### 11.4 Data-Compliance Domain Fields

| Field Group | Fields |
|-------------|--------|
| Compliance Stance | overall_preference (保守/平衡/进取) |
| Sensitive Data Policy | internal_threshold, consent_method, minimization_stance, minor_data, biometric_stance |
| Cross-Border Policy | allow_export, preferred_path, localization_stance, recipient_blacklist, important_data_stance |
| Data Security | classification_strategy, important_data_identification, level_protection_grading |
| Industry Regulator | industry → regulator → special_concerns table |

### 11.5 IP-Legal Domain Fields

| Field Group | Fields |
|-------------|--------|
| IP Portfolio | trademarks (count, classes, pending, well_known, territories), patents (invention, utility, design, core_field), copyrights (registered, software, main_type), trade_name, domains |
| Enforcement Stance | overall_stance (进取/平衡/防御) |
| Trademark Strategy | registration_scope, similarity_tolerance, opposition_tendency, invalidation_tendency, well_known_stance, overseas_layout |
| Patent Strategy | type_preference, enforcement_tendency, fto_strictness, design_around_tendency, invalidation_tendency |
| Copyright Strategy | registration_stance, software_registration_stance, enforcement_priority, authorization_stance |
| Clearance Strictness | risk_tolerance (4 levels), clearance_scope, conclusion_thresholds (3) |

### 11.6 Jurisdiction Identification (All Plugins)

| Jurisdiction Type | Markers |
|-------------------|---------|
| 经济特区 | 深圳、珠海、汕头、厦门、海南 — 特别立法权 |
| 民族自治地方 | 自治条例和单行条例 |
| 自贸区 | 特别规定 |
| 港澳台 | 适用不同法域 |
| 法院层级 | 基层法院/中院/高院/最高院 + 专门法院 (海事/知识产权/金融) |
| 仲裁机构 | CIETAC, BAC, SHIAC, SCIA, 其他地方仲裁委员会 |

When special jurisdiction is involved, mark `[管辖 flagged — 需验证特别规定]`.

---

## 12. Existing Packages & New Package Pattern

### 12.1 Current Package Inventory (20 packages)

`acp-client`, `acp-event-bridge`, `backends`, `channel-core`, `channels`, `contract-test-suite`, `mcp-registry`, `model-gateway`, `multi-agent-adapter`, `operator-config`, `platform-contract`, `platform-runtime`, `platform-sdk-ts`, `rbac`, `router-service`, `skill-index`, `skill-materializer`, `skill-registry`, `solution-loader`, `ui-core`

### 12.2 New Package Pattern

**For `packages/practice-profile`:**

```
packages/practice-profile/
├── pyproject.toml          # Package metadata
├── src/
│   └── inkstatute_practice_profile/
│       ├── __init__.py     # Re-exports
│       ├── model.py        # PracticeProfile dataclass, TemporaryMode defaults
│       ├── store.py        # PracticeProfileStore Protocol + InMemoryPracticeProfileStore
│       ├── injector.py     # PracticeProfileInjector
│       ├── interview.py    # ColdStartInterviewOrchestrator
│       ├── secret_guard.py # Secret detection on write
│       └── defaults.py     # Temporary mode default values
└── tests/
    ├── test_model.py
    ├── test_store.py
    ├── test_injector.py
    ├── test_interview.py
    ├── test_secret_guard.py
    └── test_phase99_success_criteria.py
```

**Dependencies:**
- `platform-contract` — for `ElicitationRequestedPayload`, `ElicitationQuestion`, `ElicitationOption`
- `rbac` — for `Role` checks
- `skill-index` — for querying `practice_profile_dependency` skills

**Gate registration:** Must add path variable + `Gate()` entry + `compileall` check (per STATE.md V6 gate system). `gate-coverage` meta-test enforces every `packages/*/src` directory is covered.

### 12.3 Gateway Endpoints

Following the existing Gateway pattern (`/v1/sessions`, `/v1/runs`, `/v1/skills`):

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/v1/practice-profile` | GET | `require_auth()` + `check_tenant()` | Returns tenant's profile (all plugins or `?plugin=X`) |
| `/v1/practice-profile` | PUT | `require_role((ADMIN, OPERATOR))` + `check_tenant()` | Updates tenant's profile |
| `/v1/practice-profile/interview` | POST | `require_role((ADMIN, OPERATOR))` + `check_tenant()` | Starts cold-start interview run |

---

## 13. Phase 98 Research Context (Predecessor Phase)

### 13.1 Phase 98 Completion Summary

**Location:** `.planning/phases/98-real-index-routing/98-03-SUMMARY.md`

Phase 98 completed with:
- 169 router-service tests passed (123 existing + 19 decision log + 27 success criteria)
- All 36 gates green
- RouteDecision contract frozen — no new top-level fields
- Integration accuracy: 12/15 = 80% (≥80% threshold met)
- 12 strong-signal regex rules ported from `lawfirm-profile/scripts/router.py`
- Chat/Draft/Evidence three-mode detection ported from `lawyer-desktop/agent_classifier.rs`

### 13.2 Router Service State (Post-Phase 98)

The router now uses the real skill index (not 4 fake skills). Key components:
- `RouterService` with RULE/SKILL/HYBRID strategies
- 12 strong-signal regex rules (court_sms, judgment, new_case, docx_contract_review, etc.)
- Soft trigger-phrase matching (threshold 0.4)
- Chat/Draft/Evidence mode detection with LLM fallback
- Decision logging (JSONL per session)
- `route_mismatch` feedback association

**For Phase 99:** The router selects skills, then the practice profile injector provides context for those skills. The router does not need to be aware of practice profiles — injection happens after routing.

---

## 14. Summary of Key Findings

### 14.1 What Exists

| Component | Location | Status |
|-----------|----------|--------|
| CLAUDE.md templates | `ai-for-china-legal/<plugin>/CLAUDE.md` (15 files) | ✅ Read-only source |
| Practice profile schema | `<plugin>/skills/_shared/practice-profile-schema.md` (13 files) | ✅ Defines field mapping |
| Cold-start interview skills | `<plugin>/skills/cold-start-interview/SKILL.md` (13 files) | ✅ 5-step orchestration |
| `practice_profile_dependency` flag | `skill-index/metadata_extractor.py` | ✅ Boolean per skill |
| HostAssumptionRewriter CLAUDE.md flag | `skill-materializer/host_assumption_rewriter.py` | ✅ Rule 3: flag only, no rewrite |
| SkillBodyInjector | `skill-materializer/body_injector.py` | ✅ Budget-constrained body injection |
| Elicitation contract | `platform-contract/elicitation.py` | ✅ 2-4 questions, bidirectional RunInterrupt |
| Gateway elicitation handler | `gateway/elicitation.py` | ✅ POST /v1/runs/{id}/elicitation |
| RBAC roles | `rbac/roles.py` | ✅ ADMIN/OPERATOR/LAWYER/VIEWER |
| Gateway auth | `gateway/auth.py` | ✅ require_auth, require_role, check_tenant |
| Privacy scanner | `acp-event-bridge/privacy_scan.py` | ✅ 11 secret patterns, reference-first |
| Tenant schema | `platform-contract/schemas/tenant.schema.json` | ✅ tenant_id, name, status, metadata |

### 14.2 What Phase 99 Must Build

| Component | Purpose |
|-----------|---------|
| `packages/practice-profile` | New package for practice profile model, store, injector, interview |
| `PracticeProfile` dataclass | Structured model with common header + `plugin_configs: dict[str, JsonObject]` |
| `PracticeProfileStore` Protocol | In-memory store keyed by `(tenant_id, plugin)` |
| `InMemoryPracticeProfileStore` | MVP implementation following SessionStore pattern |
| `PracticeProfileInjector` | Renders profile as context section, prepends to skill body |
| `ColdStartInterviewOrchestrator` | Multi-round elicitation, writes answers to store |
| `secret_guard.py` | Secret detection on profile write (reuse privacy_scan patterns) |
| Temporary mode defaults | 6 default values from practice-profile-schema.md §3.2 |
| Gateway endpoints | GET/PUT `/v1/practice-profile`, POST `/v1/practice-profile/interview` |
| Gate registration | New gate for `packages/practice-profile` |

### 14.3 Key Design Decisions (from 99-CONTEXT.md)

1. **Structured JSON** with plugin-specific sections (not prose) — for programmatic readability, partial updates, per-tenant storage
2. **In-memory PracticeProfileStore** — Protocol-based, follows SessionStore pattern, no new DB dependency
3. **New package** `packages/practice-profile` — distinct concern, own gate
4. **PracticeProfileInjector** — renders profile as context section prepended to skill body
5. **Temporary mode** — default profile with `[临时模式]` tag, `temporary_mode=True` flag
6. **Multi-round elicitation** — 5 steps × 2-4 questions, answers written to store
7. **RBAC** — ADMIN/OPERATOR write, all roles read, cross-tenant always denied
8. **No secrets** — validate on write, reject patterns matching API keys/tokens/passwords
9. **No event log** — runtime-only context, no RunEvent for injection, metadata in run metadata only
10. **3 Gateway endpoints** — GET, PUT, POST interview
11. **Coverage** — query skill-index at startup for `practice_profile_dependency=True` skills

### 14.4 Risk Areas

1. **337 skills with dependency (not 50)** — the marker detection is broad; the injector must be efficient
2. **Plugin-specific schemas** — each plugin has different domain fields; the model must be flexible (`plugin_configs: dict[str, JsonObject]`)
3. **Temporary mode tag enforcement** — the agent core (Phase 100+) must include `[临时模式]` in user-visible output; Phase 99 establishes the contract but cannot enforce output-level tagging
4. **Interview orchestration** — the cold-start interview requires a run that emits elicitation events; the run lifecycle must be managed (create, emit, collect, resume, complete)
5. **Gate system** — new package must be registered in the gate system without breaking existing 36 gates
