# Phase 121: Integration Wiring & Real-Path Activation - Context

**Gathered:** 2026-08-14
**Status:** Ready for planning
**Mode:** Auto-generated from milestone audit + user decision

<domain>
## Phase Boundary

闭合 v4.0 审计发现的 5 个集成缺口并激活全部真实路径。审计报告（`.planning/v4.0-MILESTONE-AUDIT.md`）确认所有组件已实现且有 ~560 测试通过，但组件间的"胶水代码"缺失，导致 E2E 流程不可用。

5 个集成缺口：
- INT-01 (CRITICAL): GuardrailIntegrator 未接入 ChatController
- INT-02 (CRITICAL): main.dart 是最小壳，未使用 AppStartup/FirstRunWizard
- INT-03 (CRITICAL): DshProcessManager 未被实例化，引擎未 spawn
- INT-04 (MAJOR): ExportDialog 未接入 ChatView
- INT-05 (MINOR): 便携 Python 下载未自动化

用户明确要求：去掉所有 mock，走真实路径——真实 DSH 引擎 + 真实 DeepSeek API + 真实 Python docx 导出 + 真实内容更新。

</domain>

<decisions>
## Implementation Decisions

### User Decisions (from audit discussion)

1. **全部真实路径**：运行时零 mock。单元测试的 fixtures 保留（测试隔离），但 app 运行时路径全部对接真实组件。
2. **真实 DSH 引擎**：使用 `build_dsh_release.sh` 构建引擎，`DshProcessManager` spawn 真实引擎进程。
3. **真实 DeepSeek API**：API key 存 OS 凭据库，经环境注入引擎。用户已提供 key（需轮换——在对话中明文暴露）。
4. **真实 Python docx 导出**：便携 Python 自动下载，执行 track-changes 脚本。
5. **真实内容更新**：ContentUpdater 对接真实 manifest 源（GitHub Release 或自有源）。

### Claude's Discretion

- main.dart 重写策略：保留现有 ChatView/HomeScreen 作为向导后的目标，新增 AppStartup 门控层
- 集成测试策略：在真实引擎 + 真实 API 路径上写冒烟测试，标注 real-API
- 引擎构建时机：Phase 121 第一步即构建引擎，后续所有工作依赖引擎可用
- API key 处理：**永远不提交到仓库**；帮助用户存入 OS 凭据库；用户需轮换暴露的 key

</decisions>

<code_context>
## Existing Code Insights

### 已实现但未接线的组件

| Component | Location | Status |
|-----------|----------|--------|
| AppStartup | lib/app/app_startup.dart | ✅ Implemented, ❌ not wired to main.dart |
| FirstRunWizard | lib/wizard/first_run_wizard.dart | ✅ Implemented, ❌ not wired |
| CredentialStore | lib/security/credential_store.dart | ✅ Implemented, ❌ not invoked |
| DshProcessManager | lib/engine/dsh_process.dart | ✅ Implemented, ❌ not instantiated |
| GuardrailIntegrator | lib/guardrails/guardrail_integrator.dart | ✅ 6 checkers, ❌ not in ChatController |
| ExportDialog | lib/export/export_dialog.dart | ✅ Implemented, ❌ not in ChatView |
| DocxExporter | lib/export/docx_exporter.dart | ✅ Implemented, ❌ not triggered |
| ContentUpdater | lib/content/content_updater.dart | ✅ Full pipeline, ✅ wired to ContentSettingsPage |
| ChatController | lib/chat/chat_controller.dart | ✅ ACP streaming, ❌ no guardrails |
| ChatView | lib/chat/chat_view.dart | ✅ Renders messages, ❌ no export button |
| main.dart | lib/main.dart | ❌ Minimal shell, needs full rewrite |

### 引擎构建状态

- DSH repo: `/home/sorawatcher/deepseek-harness` (commit 47f943859b)
- Pin file: `engines/dsh-pin.txt` (dsh_commit=47f943859b, node_version=^22.19.0 || >=24.0.0)
- Build script: `scripts/build_dsh_release.sh` (ready, not yet executed)
- Engine zip: **NOT BUILT** — no engine-*.zip in engines/
- ACP config: `engines/acp.cordis.yml` (exists, terminal default deny)

### Mock 使用位置（运行时路径，需移除）

1. `lib/chat/error_mapper.dart:82` — no-op stub (Phase 119 应接线但未接)
2. `lib/engine/dsh_config.dart:94` — mock engine spawn 路径（测试用，运行时应走真实路径）
3. `lib/presets/engine_preset_smoke.dart` — mock LLM adapter（冒烟测试用，可保留为测试工具）

</code_context>

<specifics>
## Specific Ideas

- 引擎构建是 Phase 121 的前置步骤：先 `build_dsh_release.sh` 产出 engine zip，再接线
- main.dart 重写后应支持：首启向导 → 凭据存储 → 引擎 spawn → 健康探针 → ChatView
- GuardrailIntegrator 应在 ChatController._handleUpdate() 中调用，每条 assistant 消息过护栏
- ExportDialog 应从 ChatView 的 AppBar 或消息上下文菜单触发
- 便携 Python 下载应在 build_windows_installer.sh 中自动化（curl 下载 + 解压到 staging）
- E2E 冒烟测试标注 real-API，CI 中无 key 时跳过

</specifics>

<deferred>
## Deferred Ideas

- HG-1/HG-3/HG-4 人工闸门签字仍由律师手动完成（不在本阶段自动化）
- LEG-02 退役执行仍在律师试运行验收后
- v3.x 平台组件移除仍在 Phase 120 验收后

</deferred>
