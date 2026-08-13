# Phase 112: DSH Engine Integration (ACP over stdio) - Context

**Gathered:** 2026-08-13
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

建立 V4 的技术地基：Flutter 工程骨架内有一个按契约实现的 Dart ACP v1 客户端和一个受控的 DSH 子进程管理器，用脚本化 mock ACP server 即可端到端冒烟（无需真实模型）；引擎发布产物管线（钉版构建）与 v4 门禁 runner 同日建立。V4-SELECTION §7 的 V1-V5 待验证项在本阶段 RESEARCH 全部闭环。

**Depends on:** Nothing (first v4.0 phase; builds on DSH repo + V4 PRD)
**Requirements:** DSH-01, DSH-02, DSH-03, DSH-04, GATE-01, GATE-02
**UI hint:** no (non-frontend phase — UI-SPEC gate not applicable)

**Success Criteria (what must be TRUE):**

1. `apps/flutter_app/` 工程存在且 `flutter analyze` / `flutter test` 全绿；`packages/acp_client` 为 app 内部 Dart 包（path 依赖），不进 npm 工作区
2. Dart ACP 客户端通过脚本化 mock server fixtures：initialize 握手、session/new（绝对 cwd；additionalDirectories/mcpServers 非空拒绝路径有测试）、session/prompt 单 in-flight 拒绝、session/cancel、session/update 文本块聚合、session/request_permission 策略钩子
3. DSH 子进程管理器：从 `engine\<version>\` spawn ACP 组合成功；`DSH_HOME` 指向 `%LOCALAPPDATA%\InkStatute\runtime\.dsh`；initialize 健康探针通过；app 退出后零孤儿进程（PID 断言测试）；日志 reference-first
4. `scripts/build_dsh_release.sh` 在 `engines/dsh-pin.txt` 钉住的 commit 上构建产出 `engine-<version>.zip` + `engine-manifest.json`（dsh_commit/node_version/sha256/built_at 字段齐全、sha256 可复验）；`engines/acp.cordis.yml` 含批准栈"terminal 默认拒绝"配置
5. 批准安全路径：mock 权限事件下，未知 kind 一律拒绝、terminal/execute_code 渲染用户卡片、无批量批准路径（测试覆盖三态）
6. `scripts/run_v4_gates.py` 存在并接入 CI：dart analyze + flutter test + 引擎清单校验；meta-test 断言每个新 Dart `lib/` 目录有测试覆盖
7. V4-SELECTION §7 的 V1（真实 ACP 全流程）、V2（审批上抛）、V3（skill 目录进前缀）、V4（会话日志路径）、V5（构建后启动形态）全部实测并在 `112-RESEARCH.md` 记录结论；任一证伪即触发 PRD §12.1 回退评审

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

All implementation choices are at Claude's discretion — discuss phase was skipped per user setting (`workflow.skip_discuss=true`). Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

**Binding constraints from AGENTS.md / V4-PRD that plan-phase MUST honor (non-negotiable):**

- 引擎 = DSH；集成缝 = automation-only ACP server（JSON-RPC stdio）。无 WebView。ACP 契约以 DSH `packages/acp/acp/README.md` 为准。
- DSH 钉版本 + 禁自动升级引擎：`engines/dsh-pin.txt` 钉 commit；升级 = 改 pin → `scripts/build_dsh_release.sh` 重建 → 真机回归 → 随 app 版本发布。
- ACP 三个刻意限制由产品吸收：澄清走 `[CLARIFY: …]` 约定文本 + 前置采集（DP-1，引擎组合移除 `ask_user_question`）；工具活动以状态文案呈现（DP-2）；批准卡为唯一交互通道（DP-3）；单 in-flight（DP-4）。
- 批准栈 terminal/execute_code 默认拒绝、上抛用户卡、无批量批准；未知 kind 一律拒绝。
- 单用户、单本地引擎、Windows 优先；无 Gateway、无远程引擎、无多租户。
- 安全：API 密钥只存 OS 凭据库；仓库/日志/遥测/安装包零明文密钥（grep 断言）；引擎日志 reference-first（原始 payload、客户全文不进 app 日志）。
- V4 产品代码 = `apps/flutter_app/`（Dart/Flutter）与 `presets/`、`engines/`、`scripts/build_dsh_release.sh`、`scripts/run_v4_gates.py`。冻结目录（LEG-01 清单：services/gateway、services/wecom-service、services/qqbot-service、services/arena-service、packages/agent-core、packages/arena-engine、packages/acp-client(TS)、packages/ui-core(SolidJS)、apps/web、apps/desktop）零新提交。
- 每个新 Dart `lib/` 目录必须有测试覆盖（v4 门禁 meta-test）。
- 不引入新依赖除非 V4 PRD 或当前 phase plan 要求（Flutter 生态例外：SQLite/drift 等已列入 PRD）。

**Phase 112 是技术风险闸口：** RESEARCH 必须先闭环 V4-SELECTION §7 的 V1-V5。任一证伪触发 PRD §12.1 回退评审（RB1 分步表单澄清 / RB2 尾随日志展示），不得在证据不足时进入 Phase 113。Plan-phase 必须把 V1-V5 实测作为 RESEARCH 工作包的首要交付，并在 PLAN 中显式标注"V1-V5 闭环前不得进入实现波次"。

</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research. Key external references plan-phase should consult:

- **DSH repo** (本机 `/home/sorawatcher/deepseek-harness`): V4 引擎源；ACP 契约以 `packages/acp/acp/README.md` 为准。
- **`docs/requirements/V4-PRD.md`**: 当前产品规格（source of truth）。
- **`.planning/research/V4-SELECTION.md`** §7: V1-V5 待验证项清单。
- **`.planning/research/SUMMARY.md`**: 研究摘要。
- **`lawyer-desktop`** (sibling repo): 前身 Tauri+SolidJS app，V4 仅取设计参照；agent 逻辑退役不迁入。
- **v3.x 冻结目录**（LEG-01 清单）: 零新提交，仅作历史参照。

</code_context>

<specifics>
## Specific Ideas

No specific requirements — discuss phase skipped. Refer to ROADMAP phase description and success criteria.

**Plan-phase should structure work around:**
1. RESEARCH 闭环 V1-V5（首要，阻塞实现波次）
2. Flutter 工程骨架 + `packages/acp_client` Dart 包
3. ACP v1 客户端 + mock fixtures
4. DSH 子进程管理器 + 健康探针 + 零孤儿进程
5. `scripts/build_dsh_release.sh` + `engines/dsh-pin.txt` + `engines/acp.cordis.yml`
6. 批准安全路径三态测试
7. `scripts/run_v4_gates.py` + CI 接入 + meta-test

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped.

</deferred>
