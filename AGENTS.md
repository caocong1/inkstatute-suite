# InkStatute Agent Instructions

## Project Source Of Truth

- **Current product specification: `docs/requirements/V4-PRD.md`.**
- Selection evidence and research: `.planning/research/V4-SELECTION.md`（选型证据）与 `.planning/research/SUMMARY.md`（研究摘要）。
- V1/V2/V3 均退役为历史文档：`docs/requirements/V3-PRD.md`、`docs/requirements/V2-PRD.md` 只读，不作为当前约束。
- This repo implements V4: **Flutter 原生桌面 app（无 WebView）+ 嵌入 DeepSeek Harness（DSH）引擎，经 ACP over stdio 驱动。** 墨律只做三件事：法律能力包（分域预设 + 技能内容包）、法律护栏（双层）、律师可用性（UI/打包/更新）。执行核心零自研。
- 三层分工：
  - **引擎层** — DSH（钉版本 `engines/dsh-pin.txt`，随安装包分发）。agent loop / 工具注册表 / 批准栈 / 技能系统 / 会话持久化 / 子代理 / 工作流全部继承，禁止在墨律侧重实现。
  - **能力层** — `ai-for-china-legal` 为唯一语料事实源（只读物化，`dsh` target）；本仓 `presets/<domain>/` 为分域预设源；内容包独立版本化、唯一自动更新层。
  - **产品层** — `apps/flutter_app/`（Flutter，Windows 优先）：会话 UI、批准卡、澄清卡、引用/人审徽记、Word 导出、三层更新器、零操作安装。
- **v3.x 平台冻结（LEG-01）**：`services/gateway`、`services/wecom-service`、`services/qqbot-service`、`services/arena-service`、`packages/agent-core`、`packages/arena-engine`、`packages/acp-client`(TS)、`packages/ui-core`(SolidJS)、`apps/web`、`apps/desktop` — 不新开工、不进 V4 交付物、不进 v4 门禁；Phase 120 验收后退役（LEG-02）。

## GSD Continuation Protocol

- When the user says "continue", "继续开发", "resume", or asks what is next, first run or follow `$gsd-resume-work`.
- For hands-free progression, use `$gsd-autonomous` (current milestone is v4.0, Phases 112–120).
- Treat `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, and phase artifacts as the persistent project memory.
- Do not skip GSD safety gates: unresolved checkpoints, failed verification, or missing summaries must be handled before advancing.
- **Phase 112 是技术风险闸口**：其 RESEARCH 必须先闭环 `V4-SELECTION.md` §7 的 V1-V5，任一证伪触发 PRD §12.1 回退评审（RB1/RB2），不得在证据不足时进入 Phase 113。
- Human gates must never be auto-closed. See "Human Gates" below.

## Current Milestone: v4.0 Flutter Native + DSH Engine (Phases 112–120)

| Stage | Phases | State after completion |
|---|---|---|
| A DSH 引擎底座 | 112 | Dart ACP 客户端 + 子进程管理 + 引擎发布管线 + v4 门禁，mock 冒烟通过 |
| B 法律预设与能力层 | 113-115 | 分域预设 + dsh 物化管线 + 内容包自动更新，token 预算门禁生效 |
| C 客户端与护栏 | 116-118 | 会话 UI / 护栏双层 / Word 导出端到端可用 |
| D 交付与收敛 | 119-120 | 单 exe 安装包 + 三层更新 + 律师试运行 + v3.x 冻结收敛 |

**Critical path:** 112 → 113 → 116 → 117 → 119 → 120（114/115 与 118 在 113 后并行）。

## Binding Architecture Decisions

Do not relitigate these without an explicit user decision. Full rationale in `.planning/PROJECT.md` Key Decisions and `docs/requirements/V4-PRD.md`.

1. **引擎 = DSH；集成缝 = automation-only ACP server（JSON-RPC stdio）**。用户明确否决 WebView；`dsh web` 的浏览器面/Typert 协议不在范围。ACP 契约以 DSH `packages/acp/acp/README.md` 为准。
2. **ACP 三个刻意限制由产品吸收**：澄清走 `[CLARIFY: …]` 约定文本 + 前置采集（DP-1，引擎组合移除 `ask_user_question`）；工具活动以状态文案呈现（DP-2）；批准卡为唯一交互通道（DP-3）；单 in-flight（DP-4）。回退方案 RB1/RB2 见 PRD §12.1。
3. **DSH 钉版本 + 禁自动升级引擎**。DSH 为 pre-release；升级 = 更新 `engines/dsh-pin.txt` → `scripts/build_dsh_release.sh` 重建 → 真机回归（Phase 118 GATE-03 真机路径 + 一轮真实法律任务）→ 随 app 版本发布。
4. **技能语料唯一事实源 = `ai-for-china-legal`**（Windows 路径 `C:\Users\sorawatcher\workspace\ai-for-china-legal`）。只读物化：`convert-skills.js` 新增 `dsh` target；本仓永不复制语料、永不写回语料仓。
5. **内容包 = 唯一自动更新层**（manifest + sha256 + 原子切换 + 回滚）；app 与引擎层禁自动。
6. **分域预设 + token 预算门禁**：legal-core ≤30 + 四域；默认会话只挂所选分域目录；目录渲染 ≤8,000 字符（可配置），超预算拒绝发货。**禁全量挂载 345 技能。**
7. **护栏双层（预设提示词段 + app 呈现/强制）**，任一层缺失即算绕过（回归锁定）。批准栈 terminal/execute_code 默认拒绝、上抛用户卡、无批量批准。
8. **docx 确定性变换在 app 侧**：模型产 JSON 变更清单，便携 Python 执行 `lawfirm-profile/scripts/contract_review_trackchanges.py`（41,185 字节资产复用）；模型永不直接写 docx 字节。
9. **自研 agent core（`packages/agent-core`）与 lawyer-desktop agent 逻辑退役**。不迁入、不再投入；lawyer-desktop 仅作 UI 设计参照。
10. **单用户、单本地引擎、Windows 优先**。无 Gateway、无远程引擎、无多租户；移动端推迟。

## Related Repositories (siblings of this repo)

| Repo | Role |
|---|---|
| `deepseek-harness` | V4 引擎源（本机 `/home/sorawatcher/deepseek-harness`）。钉 commit 构建；升级必须真机回归。 |
| `ai-for-china-legal` | 345 个 SKILL.md，唯一语料事实源。`convert-skills.js` 加 `dsh` target（Phase 114）。 |
| `legal-skills` | 51 个 SKILL.md（37 带 .py，CC-BY-NC）。DEFER-01：许可评估后另议，V4 不并入。 |
| `lawfirm-profile` | `scripts/contract_review_trackchanges.py` 是 V4 docx 导出复用资产（Phase 118）。 |
| `lawyer-desktop` | 前身（Tauri 2.11 + SolidJS）。V4 只取设计参照；agent 逻辑（router/classifier/tool_leak）退役。 |
| `lawyer-ai` | OpenCode 原型，搁置，不迁入。 |

## Implementation Priorities

Follow the roadmap phase order. Within a phase:

1. `apps/flutter_app/packages/acp_client`（Dart）：ACP v1 客户端与 mock fixtures 先行，一切会话能力建立其上。
2. `scripts/build_dsh_release.sh` + `engines/`：钉版构建管线与 ACP 组合是 Phase 112 交付物，任何引擎升级走它。
3. `presets/<domain>/`：预设形态（Phase 113）决定 `dsh` 物化输出结构（Phase 114），顺序不可倒。
4. `apps/flutter_app/lib/chat/`：chat UI 单一实现；任何新 UI 面不得复制渲染逻辑。
5. `scripts/run_v4_gates.py`：v4 门禁（dart analyze + flutter test + 内容结构 + 引擎清单 + mock E2E + docx 金标准）在 Phase 112 建立，此后每个 phase 自证全绿。
6. 护栏（Phase 117）与导出（Phase 118）在 UI（Phase 116）之后接线，但需求与 schema 可在前期 phase 冻结。
7. Phase 120 收敛最后：退役只在律师试运行验收通过后执行（LEG-02）。

## Safety And Privacy

- Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads.
- API 密钥只存 OS 凭据库，启动时经环境注入引擎；仓库/日志/遥测/安装包零明文密钥（grep 断言）。
- 引擎日志 reference-first：原始 payload、客户全文不进 app 日志与遥测。
- **Output boundary**：app 只渲染 ACP `session/update` 的已提交 assistant 文本；DSH meta/system 噪声与原始堆栈永不进用户界面。
- **Permission safety**：`session/request_permission` 的 terminal / execute_code 类请求默认拒绝或渲染用户卡片；**永远没有批量批准路径**；未知 kind 一律拒绝。
- **Legal guardrails are non-bypassable**: research-gate、citation audit（verified/retrieved/unverified）、ask-user（`[CLARIFY:]` 未澄清不得起草）、de-AI polish、`[HUMAN_REVIEW:]` 恒人审。双层任一缺失 = 绕过（负向回归测试）。
- 高风险法律结论永不自动定稿；`requires_human_review` 恒为 true 的呈现不可被 UI/API 消除。
- 客户材料经 DeepSeek API 传输前必须用户确认（GRD-06 一次性确认 + 脱敏提醒）。
- 更新面安全：内容包 manifest 与产物签名/哈希校验；拒绝伪造、截断与降级包。

## Human Gates (never auto-close, never claim as passed)

| Gate | Content | Phase |
|---|---|---|
| HG-1 法律质量 | V4 基线（DSH + 分域预设）须由律师抽样确认不低于 lawyer-desktop/Hermes 基线 | 120 |
| HG-4 修订稿质量 | Word 原生修订 docx 须由律师确认可用于对外谈判 | 118 |
| HG-3 律师试运行 | 五工作日 / 15 真实任务 | 120 |
| HG-2 真机通道 | Live WeCom UAT — DEFERRED（通道随 v3.x 平台冻结） | — |
| — | Operator `--live` QQ OpenAPI acceptance — DEFERRED（同上） | — |

## Coding Rules

- Keep changes scoped to the active GSD phase and its plan.
- V4 产品代码 = `apps/flutter_app/`（Dart/Flutter）与 `presets/`、`engines/`、`scripts/build_dsh_release.sh`、`scripts/run_v4_gates.py`。冻结目录（LEG-01 清单）零新提交，改动即违规。
- Add tests before or with behavior changes: Dart 单测（mock ACP fixtures）、内容结构测试、docx 金标准。
- Prefer structured parsers and schema validators over ad hoc string parsing（变更清单 JSON、manifest、`[CLARIFY:]`/`[HUMAN_REVIEW:]` 块解析）。
- 不引入新依赖除非 V4 PRD 或当前 phase plan 要求（Flutter 生态例外：SQLite/drift 等已列入 PRD）。
- 每个新 Dart `lib/` 目录必须有测试覆盖（v4 门禁 meta-test）。
- 引擎侧任何改动 = 改 `engines/acp.cordis.yml` 或 `presets/` 源，再走 `build_dsh_release.sh` + 真机回归；禁止改随附安装目录内容。
- 更新 GSD artifacts when implementation decisions change（PROJECT.md / STATE.md / 当前 phase 的 CONTEXT 与 SUMMARY）。
