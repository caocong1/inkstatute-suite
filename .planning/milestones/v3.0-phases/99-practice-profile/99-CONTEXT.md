---
phase: 99
slug: practice-profile
status: draft
created: 2026-08-11
skip_discuss: false
---

# Phase 99 — Practice Profile

## Phase Goal

约 50 个依赖 `CLAUDE.md` 执业配置的 skill 能在平台上正确工作，配置成为平台侧的多租户数据而非文件系统里的模板

## Requirements

- **PROF-01**: per-plugin `CLAUDE.md` 执业配置机制升级为平台侧多租户配置（审查立场、升级矩阵、文书风格、管辖识别、交易破坏者），覆盖约 50 个依赖它的 skill
- **PROF-02**: 未配置时降级"临时模式"，并在每个输出上标记
- **PROF-03**: 冷启动访谈可通过统一事件词汇的 `elicitation.requested` 完成配置采集

## Success Criteria

1. 执业配置在平台侧建模并按租户存储：审查立场（甲方/乙方各自的责任限制、违约金、知识产权、数据保护、期限终止、管辖、交易破坏者）、升级矩阵（金额阈值 + 审批层级 + 自动升级触发）、文书风格、管辖识别
2. 执行时执业配置被注入 skill 上下文，覆盖索引中标记了 `practice_profile_dependency` 的全部 skill
3. 未配置时降级"临时模式"：使用通用默认值，且每个输出被标记 `[临时模式]`，有测试断言标记不会遗漏
4. 冷启动访谈可通过 `elicitation.requested` 完成——多轮 2-4 题采集，答案写回租户执业配置
5. 执业配置的读写经 RBAC 授权，跨租户访问被拒
6. 执业配置不含 secrets，且不进入契约事件日志

## Codebase Scout Findings

### 1. CLAUDE.md Practice Profile Files — Source Format

**Location:** `/home/sorawatcher/workspace/ai-for-china-legal/<plugin>/CLAUDE.md`

**Count:** 15 CLAUDE.md files (1 root + 13 plugin-level + 1 shared)

**Structure (from commercial-legal/CLAUDE.md, 257 lines):**

| Section | Content | Key Fields |
|---------|---------|------------|
| `## 我们是谁` | Identity & team | company_name, entity_type, team_size, escalation_contact, monthly_volume, counterparty_type |
| `## 谁在使用` | User role | role (律师/非律师), lawyer_contact |
| `## 可用集成` | Integrations | contract_mgmt, e_signature, doc_storage, wecom/dingtalk |
| `## 审查立场` | Review stance | risk_appetite (保守/平衡/进取), 甲方立场 (7 dimensions), 乙方立场 (7 dimensions) |
| `## 升级矩阵` | Escalation matrix | approval_table (role → amount_limit → escalation_condition), amount_thresholds, auto_escalation_triggers |
| `## 文书风格` | Document style | revision_tone, stakeholder_summary, work_product_location, renewal_reminder_recipient |
| `## 输出` | Output format | work_product_title, reviewer_note_block, silent_mode_rules, decision_tree_template |
| `## 共享护栏` | Shared guardrails | no_silent_fill, timeliness_trigger, legal_fact_verification, source_labels, destination_check, dual_severity, jurisdiction_identification |
| `## 事项工作区` | Matter workspace | enabled (✗/✓) |
| `## 审查过的种子文档` | Seed documents | table of reviewed docs |

**Seven dimensions per side (甲方/乙方):**
1. 责任限制 (liability caps, indirect damages, carveouts, base definition)
2. 违约金 (standard stance, acceptable alternatives, never accept)
3. 知识产权 (ownership, licensing, acceptable alternatives)
4. 数据保护 (compliance requirements, specific requirements)
5. 期限与终止 (standard terms, acceptable alternatives, never accept)
6. 管辖法律与争议解决 (preferred, acceptable, escalate, never accept)
7. 交易破坏者 (the one absolute dealbreaker)

**Each dimension has:** 标准立场, 可接受的备选, 绝不接受

**Litigation-legal CLAUDE.md (153 lines)** has a different structure:
- `## 风险校准` (severity definitions, probability definitions, materiality thresholds)
- `## 利益冲突清除` (conflict clearance method, responsible person)
- `## 外部律师合作` (partner firms, selection criteria, budget approval)
- `## 证据保全` (preservation trigger, scope, refresh cycle)
- `## 和解策略` (settlement authority threshold, approval flow, tendency)

**Key insight:** Each plugin has a different CLAUDE.md structure — the fields are domain-specific. The platform-side model must be flexible enough to accommodate all plugin schemas without hardcoding commercial-legal's structure.

### 2. Practice Profile Dependency in Skill Index

**Location:** `packages/skill-index/src/inkstatute_skill_index/metadata_extractor.py` (lines 105-115)

**Detection markers:**
```python
_PRACTICE_PROFILE_MARKERS: list[str] = [
    "CLAUDE.md",
    "实践配置",
    "审查立场",
    "执业配置",
]
```

**`_check_practice_profile_dependency(body: str) -> bool`** — returns True if any marker is found in the skill body text.

**In skill-index.json:** Each skill record has `practice_profile_dependency: bool` field. The V3-PRD shows it as a string path (`"commercial-legal/CLAUDE.md"`), but the actual implementation uses a boolean.

**Coverage:** ~50 skills have `practice_profile_dependency=True` (per V3-PRD §4.3). These are spread across 13 plugins, each with its own CLAUDE.md.

### 3. Cold-Start Interview Skills

**Location:** `<plugin>/skills/cold-start-interview/SKILL.md` (13 files, one per plugin)

**Commercial-legal cold-start-interview structure (113 lines):**
- Orchestration entry that sequences 5 sub-skills:
  1. `identity-team` — identity, practice environment, team structure, integrations
  2. `review-stance` — risk appetite, 甲方/乙方 dual-stance 6 dimensions, dealbreakers
  3. `escalation-rules` — amount thresholds, risk-level triggers, auto-escalation conditions
  4. `document-style` — output format, tone, citation preferences, bilingual needs
  5. `jurisdiction-profile` — governing law, local regulations, court preferences, special zones

**Each sub-skill can be triggered independently** to update only its section of CLAUDE.md.

**Practice-profile-schema.md** (242 lines, in `<plugin>/skills/_shared/practice-profile-schema.md`):
- Defines the contract between CLAUDE.md and skills
- Field mapping table: interview field → CLAUDE.md section → reading skills
- Skill reading contract: read CLAUDE.md before work, check for [PLACEHOLDER], choose run mode
- Temporary mode defaults defined (see §4 below)
- Legal fact reasonableness checks before writing to config

### 4. Temporary Mode (临时模式) — Existing Specification

**From practice-profile-schema.md §3.2:**

When skills detect CLAUDE.md is missing or contains `[PLACEHOLDER]`:
- Must NOT silently use guessed values
- Must offer two choices: run cold-start-interview OR say "临时模式"
- In temporary mode, tag every output: `[临时模式 — 配置你的档案以获得定制输出]`

**Temporary mode defaults:**

| Field | Default |
|-------|---------|
| 风险偏好 | 平衡型 |
| 执业角色 | 律师 |
| 管辖法律 | 中国大陆法律 |
| 甲方/乙方立场 | 标记常见风险，不偏向任何一方 |
| 升级矩阵 | 不自动升级，提示律师判断 |
| 文书风格 | 半正式，含法条引用，不含案例引用 |

### 5. Tenant Storage — Current Platform Patterns

**Gateway auth (services/gateway/src/gateway/auth.py):**
- `AuthContext` carries `tenant_id: str` — always present (from identity or `default_tenant_id`)
- `GatewayAuth.check_tenant(ctx, resource_tenant_id)` — raises 403 on cross-tenant access
- `GatewayConfig.default_tenant_id = "default"` — single-tenant fallback

**Gateway sessions (services/gateway/src/gateway/sessions.py):**
- `GatewaySession` has `tenant_id`, `user_id`, `conversation_id`, `devices`
- `GatewaySessionManager` uses RBAC `SessionStore` Protocol (in-memory MVP)
- `list_sessions(tenant_id)` filters by tenant

**Gateway runs (services/gateway/src/gateway/runs.py):**
- Run creation carries `tenant_id` from `AuthContext`
- All run operations check tenant ownership

**Pattern:** Tenant-scoped data is stored in-memory keyed by tenant_id. No database is introduced (AGENTS.md: "Do not introduce a new service, database, queue, or runtime dependency unless the V3 PRD or the active GSD plan requires it"). The platform is single-firm scale (≤50 lawyers), so in-memory storage is sufficient.

### 6. RBAC — Current Authorization

**Location:** `packages/rbac/src/rbac/`

**Roles (roles.py):**
```python
class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    LAWYER = "lawyer"
    VIEWER = "viewer"
```

**Identity (identity.py):**
- `Identity(role: Role, tenant_id: str)` — frozen dataclass
- `resolve_identity()` — Bearer token first, session cookie fallback
- When `rbac_enabled=False`, static-token fallback returns `Identity(role=ADMIN, tenant_id="default")`

**Gateway auth methods:**
- `authenticate(headers) -> AuthContext` — never raises, returns authenticated=False on failure
- `require_auth(headers) -> AuthContext` — raises 401 on failure
- `require_role(headers, allowed_roles) -> AuthContext` — raises 403 if role not in allowed_roles
- `check_tenant(ctx, resource_tenant_id)` — raises 403 on cross-tenant access

**For practice profiles:**
- Read: LAWYER, OPERATOR, ADMIN (all authenticated users in the tenant)
- Write: ADMIN, OPERATOR (not LAWYER or VIEWER)
- Cross-tenant: always denied

### 7. Elicitation Protocol — Platform Contract

**Location:** `packages/platform-contract/src/platform_contract/elicitation.py` (189 lines)

**Data structures (unified_events.py):**
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

**Constraints:**
- `validate_question_count(questions)` — enforces 2-4 questions per round
- `format_answer_display(questions, answers)` — formats Q&A for display
- Bidirectional conversion with V2 `RunInterrupt` via `elicitation_to_run_interrupt()` / `run_interrupt_to_elicitation()`

**Gateway elicitation handler (services/gateway/src/gateway/elicitation.py):**
- `POST /v1/runs/{run_id}/elicitation` — accepts clarification card answers
- `GatewayElicitationHandler` stores submissions in-memory keyed by `(run_id, interrupt_id)`
- `handle_submit_elicitation(ctx, run_id, body)` — validates interrupt_id + answers, stores with tenant_id
- Runtime can delegate via `resume_elicitation(run_id, interrupt_id, answers)` if supported

**For cold-start interview:**
- Each interview step (identity-team, review-stance, etc.) maps to one `elicitation.requested` event
- Each event has 2-4 questions (per ASK-USER-PROTOCOL.md constraint)
- Multi-round: 5 steps × 2-4 questions = 10-20 total questions across the full interview
- Answers are collected via `POST /v1/runs/{run_id}/elicitation` and written back to tenant practice profile

### 8. Context Injection — Body Injector

**Location:** `packages/skill-materializer/src/inkstatute_skill_materializer/body_injector.py` (499 lines)

**SkillBodyInjector:**
- Parses SKILL.md into sections by `##` headers
- Assigns priorities: protected (frontmatter + description + first section), high (research-gate/ask-user), medium, low (example/appendix/reference)
- Trims from lowest priority to fit token budget
- `read_skill_body(skill_id, index_path, budget_tokens)` — on-demand body reading for self-built core

**Host assumption rewriter (host_assumption_rewriter.py, 269 lines):**
- Rule 3: `CLAUDE.md` references are flagged as `practice_profile_dependency` but NOT rewritten in text
- The rewriter logs CLAUDE.md references in `RewriteReport` entries with `rule_applied="claude_md_flag"`

**Gap:** The body injector handles skill body text injection but does NOT inject practice profile content. There is no existing mechanism to inject CLAUDE.md practice profile data into the skill execution context. This is what Phase 99 must build.

### 9. HostAssumptionRewriter — CLAUDE.md Flagging

**Location:** `packages/skill-materializer/src/inkstatute_skill_materializer/host_assumption_rewriter.py`

The rewriter already identifies CLAUDE.md references in skill bodies and flags them. This means the materializer is aware of which skills depend on practice profiles. The Phase 96 skill index also records `practice_profile_dependency: bool` per skill.

**What's missing:** The platform needs a runtime component that:
1. Reads the tenant's practice profile
2. Injects it into the skill execution context alongside the skill body
3. Marks outputs with `[临时模式]` when no profile is configured

### 10. Existing Packages — New Package Pattern

**Current packages (20):** acp-client, acp-event-bridge, backends, channel-core, channels, contract-test-suite, mcp-registry, model-gateway, multi-agent-adapter, operator-config, platform-contract, platform-runtime, platform-sdk-ts, rbac, router-service, skill-index, skill-materializer, skill-registry, solution-loader, ui-core

**Pattern for new packages:**
- `packages/<name>/pyproject.toml` — package metadata
- `packages/<name>/src/<package_name>/` — source code
- `packages/<name>/tests/` — test suite
- Must be registered in gate system (V6 from STATE.md: "新包需加 path 变量 + Gate() 条目 + compileall")
- `gate-coverage` meta-test enforces every `packages/*/src` directory is covered

### 11. V3-PRD §5.4 — Practice Profile Requirements

**From V3-PRD line 350-352:**
> `CLAUDE.md` 机制（~50 个 skill 依赖）升级为平台侧多租户配置：审查立场（甲方/乙方）、升级矩阵（金额阈值 + 审批层级）、文书风格、管辖识别、交易破坏者。未配置时降级"临时模式"并在每个输出上标记。冷启动访谈可通过 `elicitation` 完成。

**From V3-PRD line 99:**
> ~50 个 skill 读 per-plugin `CLAUDE.md` 执业配置，未配置时降级"临时模式"

**From V3-PRD line 320:**
> `"practice_profile_dependency": "commercial-legal/CLAUDE.md"` — the PRD shows a string path, but the actual index uses a boolean. The platform-side model should track which plugin's CLAUDE.md each skill depends on.

## Key Decisions (Auto-Selected)

### 1. Practice Profile Data Model: Structured JSON with plugin-specific sections

[auto] Q: "How to model the practice profile data — structured JSON or prose text?" → Selected: "Structured JSON with plugin-specific sections, stored per tenant"

**Rationale:** The original CLAUDE.md files are prose templates with `[PLACEHOLDER]` fields. For platform-side multi-tenant storage, a structured JSON model is needed because: (a) it must be programmatically readable at execution time for context injection, (b) it must support partial updates (individual sections), (c) it must be storable per tenant, (d) the cold-start interview writes structured answers. The model should have a common header (identity, role, integrations) plus a `plugin_configs: dict[str, JsonObject]` map where each key is a plugin name and the value is that plugin's practice profile data. This accommodates the fact that each plugin has a different CLAUDE.md structure (commercial-legal has review-stance with 7 dimensions × 2 sides, litigation-legal has risk calibration and settlement strategy, etc.) without hardcoding any single plugin's schema.

### 2. Tenant Storage: In-memory PracticeProfileStore (Protocol-based)

[auto] Q: "Where to store practice profiles — database, JSON files, or in-memory?" → Selected: "In-memory PracticeProfileStore following the SessionStore pattern"

**Rationale:** The platform is single-firm scale (≤50 lawyers, per AGENTS.md decision 9). All existing tenant-scoped data (sessions, runs, elicitation submissions) uses in-memory storage with Protocol-based interfaces. A `PracticeProfileStore` Protocol with an `InMemoryPracticeProfileStore` implementation follows the same pattern as `SessionStore` / `InMemorySessionStore`. The Protocol allows future swap to DB/Redis without changing call sites. No new runtime dependency is introduced (AGENTS.md coding rule).

### 3. New Package: `packages/practice-profile`

[auto] Q: "Should practice profile logic go in an existing package or a new one?" → Selected: "New package `packages/practice-profile`"

**Rationale:** Practice profile is a distinct concern from skill indexing (skill-index), skill materialization (skill-materializer), routing (router-service), and platform contracts (platform-contract). It needs its own data model, store, injection logic, and interview orchestration. A new package follows the existing pattern (each concern gets its own package with its own gate). The package will depend on `platform-contract` (for elicitation types), `rbac` (for Role checks), and `skill-index` (for querying which skills have `practice_profile_dependency`).

### 4. Context Injection: PracticeProfileInjector in practice-profile package

[auto] Q: "How to inject practice profile into skill context at execution time?" → Selected: "PracticeProfileInjector that renders profile data as a context section prepended to skill body"

**Rationale:** The body_injector (Phase 97) handles skill body text injection with budget trimming. The practice profile injection is a separate concern: it renders the tenant's practice profile as a structured context section (e.g., `## 执业配置\n\n### 审查立场\n...`) and prepends it to the skill body before the body injector runs. The injector checks the skill's `practice_profile_dependency` flag in the index — if True, it fetches the tenant's profile; if no profile exists, it generates temporary mode defaults with `[临时模式]` tag. The injector output includes a `profile_injected: bool` and `temporary_mode: bool` flag for observability.

### 5. Temporary Mode: Default profile with `[临时模式]` tag on every output

[auto] Q: "How to implement 临时模式 with [临时模式] tagging?" → Selected: "Generate default profile from practice-profile-schema defaults, tag all outputs with [临时模式] prefix"

**Rationale:** The practice-profile-schema.md already defines temporary mode defaults (平衡型 risk, 律师 role, 中国大陆法律 jurisdiction, etc.). When `PracticeProfileStore.get(tenant_id, plugin)` returns None, the injector generates a `PracticeProfile` from these defaults with `temporary_mode=True`. The injector adds a `[临时模式]` tag to the context section. The agent core (Phase 100+) will be responsible for including this tag in user-visible output. For Phase 99, the test asserts that: (a) the injector always produces a profile (real or temporary), (b) temporary mode profiles have `temporary_mode=True`, (c) the `[临时模式]` tag is present in the injected context. The output-boundary enforcement of the tag in user-visible text is deferred to the agent core (Phase 100+), but the contract is established here.

### 6. Cold-Start Interview: Multi-round elicitation via elicitation.requested events

[auto] Q: "How to implement multi-round cold-start interview?" → Selected: "ColdStartInterviewOrchestrator that emits elicitation.requested events in sequence, writes answers to PracticeProfileStore"

**Rationale:** The cold-start-interview SKILL.md defines a 5-step interview (identity-team → review-stance → escalation-rules → document-style → jurisdiction-profile). Each step maps to one `elicitation.requested` event with 2-4 questions (per the elicitation contract constraint). The orchestrator: (a) emits the first elicitation event, (b) on answer submission, writes answers to the profile store, (c) emits the next elicitation event, (d) repeats until all steps are complete. The orchestrator is plugin-aware — it uses the plugin's interview definition to determine the question set. For Phase 99, a reference implementation for commercial-legal is built; other plugins follow the same pattern. The interview can be triggered via a Gateway endpoint (`POST /v1/practice-profile/interview`).

### 7. RBAC Authorization: ADMIN/OPERATOR write, all roles read

[auto] Q: "How to enforce RBAC on practice profile read/write?" → Selected: "Write requires ADMIN or OPERATOR role; read allowed for all authenticated roles; cross-tenant always denied"

**Rationale:** Practice profiles contain firm-level configuration (escalation matrices, liability positions) that should be editable by admins and operators but not by individual lawyers. All authenticated users within a tenant can read their firm's profile (needed for skill execution). The Gateway's existing `require_role()` and `check_tenant()` methods enforce this. New Gateway endpoints: `GET /v1/practice-profile` (all roles), `PUT /v1/practice-profile` (ADMIN/OPERATOR only), `POST /v1/practice-profile/interview` (ADMIN/OPERATOR only, starts cold-start interview).

### 8. No Secrets in Practice Profiles: Validation + schema enforcement

[auto] Q: "How to enforce that practice profiles contain no secrets?" → Selected: "Validate profile data on write — reject fields matching secret patterns (API keys, tokens, passwords, AES keys)"

**Rationale:** Practice profiles are business configuration (risk positions, escalation thresholds, document style preferences) — they should never contain secrets. The `PracticeProfileStore.update()` method validates incoming data against a secret-detection regex set (matching patterns like `api_key`, `secret`, `token`, `password`, `aes_key`, `-----BEGIN`). If any field value matches, the write is rejected with a 400 error. Additionally, practice profile data is never included in contract event logs — the injection is a runtime context operation, not a persisted event. The `PracticeProfile` dataclass has no `raw_payload_ref` or event-logging path.

### 9. No Practice Profiles in Contract Event Log: Runtime-only injection

[auto] Q: "How to ensure practice profiles don't enter the contract event log?" → Selected: "Practice profiles are runtime-only context; no RunEvent is emitted for profile injection; profile data stays in PracticeProfileStore"

**Rationale:** Contract events (RunEvent) are the persisted audit trail. Practice profiles are runtime execution context — they are injected into the skill execution context but never serialized into events. The `PracticeProfileInjector.inject()` method returns a context string that is passed to the agent, but no `RunEvent` is created for the injection. The profile data remains in the `PracticeProfileStore` (in-memory). If observability is needed, the injector returns metadata (`profile_injected`, `temporary_mode`, `plugin`) that can be included in run metadata (not in event payloads).

### 10. API Design: Gateway endpoints for practice profile CRUD + interview

[auto] Q: "What's the API for reading/writing practice profiles?" → Selected: "Three Gateway endpoints: GET, PUT, and POST interview"

**Rationale:** Following the existing Gateway pattern (`/v1/sessions`, `/v1/runs`, `/v1/skills`), practice profiles get three endpoints:
- `GET /v1/practice-profile` — returns the tenant's profile (all plugins) or a specific plugin's profile via `?plugin=commercial-legal`
- `PUT /v1/practice-profile` — updates the tenant's profile (full or partial via `plugin` parameter)
- `POST /v1/practice-profile/interview` — starts a cold-start interview run, returns a `run_id` for elicitation event consumption

All endpoints use `require_auth()` + `check_tenant()`. Write endpoints additionally use `require_role((Role.ADMIN, Role.OPERATOR))`. The interview endpoint creates a run that emits `elicitation.requested` events consumable via SSE at `/v1/runs/{id}/events`.

### 11. Coverage: Query skill-index for practice_profile_dependency skills

[auto] Q: "How to cover all skills with practice_profile_dependency?" → Selected: "Query skill-index.json at startup to build a set of skill_ids with practice_profile_dependency=True; injector checks this set"

**Rationale:** The skill index (Phase 96) already records `practice_profile_dependency: bool` per skill. The `PracticeProfileInjector` loads the index at initialization and builds a `set[str]` of skill_ids that depend on practice profiles. At injection time, it checks if the target skill_id is in this set — if yes, it injects the profile; if no, it skips injection. This ensures all ~50 dependent skills are covered without hardcoding skill IDs. A test asserts that the set matches the index's `practice_profile_dependency=True` count.

## Gray Area Count: 11

All 11 gray areas auto-selected with recommended options.
