# InkStatute Agent Instructions

## Project Source Of Truth

- **Current product specification: `docs/requirements/V5-PRD.md`.**
- Selection evidence and research: `.planning/research/V5-SELECTION.md`（选型证据）与 `.planning/research/SUMMARY.md`（研究摘要）。
- V1/V2/V3/V4 均退役为历史文档：`docs/requirements/V3-PRD.md`、`docs/requirements/V4-PRD.md` 只读，不作为当前约束。
- This repo implements **V5**: Tauri 2 + SolidJS app（装配 `packages/ui-core` 墨律三主题）经 ACP over stdio 驱动本地嵌入 DeepSeek Harness（DSH）引擎，Windows 桌面双击即用。
- 三层分工：
  - **引擎层** — DSH（钉版本 `engines/dsh-pin.txt`，按 `engines/engine-lock.json` 在本地 npm 锁文件铺平装配）。agent loop / 工具注册表 / 批准栈 / 技能系统 / 会话持久化 / 子代理 / 工作流全部继承，禁止在墨律侧重实现。
  - **能力层** — `ai-for-china-legal` 为唯一语料事实源（只读物化，`dsh` target）；本仓 `presets/<domain>/` 为分域预设源；内容包独立版本化、唯一自动更新层。
  - **产品层** — `apps/desktop/`（Tauri 2 + SolidJS，Windows 优先）：会话 UI、批准卡、澄清卡、引用/人审徽记、三层更新器、零操作安装。
- **v3.x / v4.x 平台冻结（LEG-01）**：`services/gateway`、`services/wecom-service`、`services/qqbot-service`、`services/arena-service`、`packages/agent-core`、`packages/arena-engine`、`packages/acp-client`(TS)、`apps/web`、`apps/flutter_app` — 冻结，不新开工、不进 v5 交付物。`packages/ui-core`(SolidJS) 与 `apps/desktop` 在 v5.0 复活为核心资产；`packages/ui-core/src/event-reducer.ts` 不得改动。

## GSD Continuation Protocol

- When the user says "continue", "继续开发", "resume", or asks what is next, first run or follow `$gsd-resume-work`.
- For hands-free progression, use `$gsd-autonomous` (current milestone is v5.0, Phases 122–127).
- Treat `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, `.planning/V5-EXECUTION-GUIDE.md`, and phase artifacts as the persistent project memory.
- Do not skip GSD safety gates: unresolved checkpoints, failed verification, or missing summaries must be handled before advancing.
- **Phase 123 是方案风险闸口**：RTM-07（对话续接回灌）必须用**真实 API key** 实测。若回灌体验不可接受，触发架构回退评审（备选：引擎常驻方案）。不得在证据不足时进入 124。
- Human gates must never be auto-close. See "Human Gates" below.

## Current Milestone: v5.0 Tauri Shell + DSH Three-Plane Integration (Phases 122–127)

| Stage | Phases | State after completion |
|---|---|---|
| A 引擎底座换血 | 122 | npm lockfile 装配替代 zip 管线；ACP 配置缺陷修复；空目录能装出可启动引擎 |
| B 真实链路打通 | 123-124 | 引擎主管 + 三面接入 + 事件映射；真 key 跑通问答；fixture 门禁亮灯 |
| C 产品外壳 | 125-126 | ui-core 接线 + 裁剪 + 设置面板 + 护栏双层 + 技能能力层 |
| D 交付 | 127 | 单 exe 安装包 + 三层更新 + 回滚门禁 |

**Critical path:** 122 → 123 → 124 → 125 → 126 → 127（严格串行）。

## Binding Architecture Decisions

Do not relitigate these without an explicit user decision. Full rationale in `.planning/PROJECT.md` Key Decisions and `docs/requirements/V5-PRD.md`.

1. **引擎 = DSH；集成缝 = automation-only ACP server（JSON-RPC stdio）**。ACP 契约以 DSH `packages/acp/acp/README.md` 为准。
2. **三面接入**：ACP stdio 做控制面；会话 JSONL 日志做观测面；`session-query.db` 做历史面。
3. **会话模型**：一个 app 运行期一个引擎子进程；一个对话一个 ACP 会话；跨 app 重启用**回灌**续接。
4. **DSH 钉 npm 精确版本，禁 dist-tag**。升级 = 更新 `engines/dsh-pin.txt` →  regenerated `engines/engine-lock.json` → Rust 装配器 → 冒烟闸 → 指针切换。
5. **技能语料唯一事实源 = `ai-for-china-legal`**。只读物化：`convert-skills.js` 新增 `dsh` target；本仓永不复制语料、永不写回语料仓。
6. **内容包 = 唯一自动更新层**（manifest + sha256 + 原子切换 + 回滚）；app 与引擎层禁自动。
7. **分域预设 + token 预算门禁**：legal-core ≤30 + 四域；默认会话只挂所选分域目录；目录渲染 ≤8,000 字符（可配置），超预算拒绝发货。**禁全量挂载 345 技能。**
8. **护栏双层（预设提示词段 + app 呈现/强制）**，任一层缺失即算绕过（回归锁定）。批准栈 terminal/execute_code 默认拒绝、上抛用户卡、无批量批准。
9. **Word 原生修订导出（APP-04）已放弃**。`docx-rs`、`pdf-extract`、便携 Python、track-changes 脚本已从 `apps/desktop/src-tauri` 移除。
10. **自研 agent core（`packages/agent-core`）与 lawyer-desktop agent 逻辑退役**。`lawyer-desktop` 仅作 UI 设计参照；`packages/ui-core` 是 lawyer-desktop UI 的像素级移植。
11. **单用户、单本地引擎、Windows 优先**。无 Gateway、无远程引擎、无多租户；移动端推迟。

## Related Repositories (siblings of this repo)

| Repo | Role |
|---|---|
| `deepseek-harness` | V5 引擎 npm 发布源（本地仅作只读参照；构建改走 npm lockfile）。 |
| `ai-for-china-legal` | 345 个 SKILL.md，唯一语料事实源。`convert-skills.js` 加 `dsh` target。 |
| `legal-skills` | 66 个 SKILL.md（46 带 .py），许可逐 skill 声明：约 42 个 MIT、19 个 CC BY-NC 4.0（2026-10-15 核实）。DEFER-01：按 skill 逐个评估后另议，v5 不并入。 |
| `lawyer-desktop` | 前身（Tauri 2.11 + SolidJS）。V5 UI 移植源；agent 逻辑（router/classifier/tool_leak）退役。 |
| `lawyer-ai` | OpenCode 原型，搁置，不迁入。 |

## Implementation Priorities

Follow the roadmap phase order. Within a phase:

1. `apps/desktop/src-tauri/`：引擎装配、ACP 控制面、子进程主管、事件/历史读写；Tauri command 在 Phase 127 接入。
2. `packages/ui-core/`：V5 产品 UI 唯一实现；任何新 UI 面不得复制渲染逻辑。`packages/ui-core/src/event-reducer.ts` 不得改动。
3. `engines/`：钉版 `dsh-pin.txt` + `engine-lock.json` + `acp.cordis.yml` 是装配与配置源；任何引擎改动走 `gen-engine-lock.mjs` + 冒烟闸。
4. `presets/<domain>/`：分域预设源；Phase 126 决定 `dsh` 物化输出结构。
5. `scripts/gates/v5/run-gates.mjs`：v5 门禁（cargo check/test、引擎装配、真实 engine 冒烟、配置校验、密钥扫描）在 Phase 122 建立，此后每个 phase 自证全绿。
6. 护栏（Phase 126）在 UI 接线（Phase 125）之后，但 schema 与提示词段可在 Phase 126 冻结。
7. Phase 127 收敛最后：单 exe、三层更新、回滚门禁。

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
| HG-1 法律质量 | V5 基线（DSH + 分域预设）须由律师抽样确认不低于 lawyer-desktop/Hermes 基线 | 127 |
| HG-3 律师试运行 | 五工作日 / 15 真实任务 | 127 |
| HG-2 真机通道 | Live WeCom UAT — DEFERRED（通道随 v3.x 平台冻结） | — |
| — | Operator `--live` QQ OpenAPI acceptance — DEFERRED（同上） | — |

> HG-4（修订稿质量）随 APP-04 放弃而**关闭**，不再是待办闸门。

## Coding Rules

- Keep changes scoped to the active GSD phase and its plan.
- V5 产品代码 = `apps/desktop/`、`packages/ui-core/`、`presets/`、`engines/`、`scripts/gates/v5/`、`scripts/gen-engine-lock.mjs`。冻结目录（LEG-01 清单）与 `apps/flutter_app` 零新提交，改动即违规。
- Add tests before or with behavior changes: Rust 单测/集成测、内容结构测试、gate 脚本。
- Prefer structured parsers and schema validators over ad hoc string parsing（变更清单 JSON、manifest、`[CLARIFY:]`/`[HUMAN_REVIEW:]` 块解析）。
- 不引入新依赖除非 V5 PRD 或当前 phase plan 要求。
- 引擎侧任何改动 = 改 `engines/acp.cordis.yml` 或 `engines/dsh-pin.txt`，再走 `scripts/gen-engine-lock.mjs` + `scripts/gates/v5/run-gates.mjs` 冒烟闸；禁止改随附安装目录内容。
- 更新 GSD artifacts when implementation decisions change（PROJECT.md / STATE.md / 当前 phase 的 CONTEXT 与 SUMMARY）。
