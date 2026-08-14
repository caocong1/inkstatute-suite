---
phase: 113
slug: legal-presets-domain-presets
created: 2026-08-14
milestone: v4.0
depends_on: 112
requirements: [SKL-05, SKL-06, SKL-07]
---

# Phase 113 — Context

## Goal

建立 V4 能力层的形态：本仓 `presets/` 下产出 legal-core（≤30 核心集）+ 四域预设，人设统一携带护栏提示词基座与澄清约定；token 预算门禁测试红灯即拒发货。分域形态决定 Phase 114 转换器的输出结构，故本阶段先行。

## Requirements

- **SKL-05**: 分域预设——本仓 `presets/<domain>/`（legal-core ≤30 技能核心集 + legal-commercial / legal-litigation / legal-family / legal-employment 首批四域）；以 standard 为底、native 呈现；`customSkillDirs` 指向内容包分域目录；安装时物化到引擎 `.agent-presets/`
- **SKL-06**: 预设人设与护栏提示词基座——research-gate / citation audit / ask-user（`[CLARIFY:]` 约定）/ de-AI polish / `[HUMAN_REVIEW:]` 输出约定 / 保密提示全部入预设人设；先加载对应技能再动手
- **SKL-07**: token 预算门禁——默认会话只挂所选分域目录；核心集目录渲染（name+description）长度 ≤ 预算（默认 8,000 字符，可配置）；超预算回归测试红灯、拒绝发货

## Success Criteria

1. `presets/legal-core`（≤30 技能）+ `presets/legal-commercial` / `legal-litigation` / `legal-family` / `legal-employment` 各自含 preset.yml（name/description）+ agent.cordis.yml（以 standard 为底、native 呈现、persona、工具集、`customSkillDirs` 指向内容包分域目录）
2. 预设人设统一包含：research-gate / citation audit（verified/retrieved/unverified）/ ask-user（`[CLARIFY: …]` 约定，缺失事实不得起草）/ de-AI polish / `[HUMAN_REVIEW: …]` 输出约定 / 保密提示 / "先经 skill 工具加载对应技能再动手"
3. 引擎组合中 ACP 会话移除 `ask_user_question` 工具（澄清走约定文本，PRD DP-1），测试断言该工具不在 ACP 会话工具集
4. 用 Phase 112 的引擎底座对 legal-core 做一次真实引擎冒烟：挂载 2-3 个技能，确认目录进入模型前缀、按名加载可用（V3 验证项的落地形态）
5. SKL-07 预算门禁：核心集目录渲染（name+description）长度 ≤ 8,000 字符（可配置），超预算测试红灯；345 技能全量挂载被显式禁止并有无害断言说明
6. 预设物化脚本：`scripts/materialize_presets.sh` 把 `presets/` 物化到引擎 `~/.agent-presets/<domain>/`（安装时执行）；随附安装目录只读纪律写进脚本注释

## Locked Decisions (from AGENTS.md / V4-PRD)

- 引擎 = DSH；集成缝 = automation-only ACP server（JSON-RPC stdio）。无 WebView。
- DSH 钉版本 + 禁自动升级引擎：`engines/dsh-pin.txt` 钉 commit。
- ACP 三个刻意限制由产品吸收：澄清走 `[CLARIFY: …]` 约定文本 + 前置采集（DP-1，引擎组合移除 `ask_user_question`）；工具活动以状态文案呈现（DP-2）；批准卡为唯一交互通道（DP-3）；单 in-flight（DP-4）。
- 批准栈 terminal/execute_code 默认拒绝、上抛用户卡、无批量批准；未知 kind 一律拒绝。
- 技能语料唯一事实源 = `ai-for-china-legal`（只读物化，`dsh` target）；本仓永不复制语料、永不写回语料仓。
- 内容包 = 唯一自动更新层（manifest + sha256 + 原子切换 + 回滚）；app 与引擎层禁自动。
- 分域预设 + token 预算门禁：legal-core ≤30 + 四域；默认会话只挂所选分域目录；目录渲染 ≤8,000 字符（可配置），超预算拒绝发货。**禁全量挂载 345 技能。**
- 护栏双层（预设提示词段 + app 呈现/强制），任一层缺失即算绕过（回归锁定）。
- V4 产品代码 = `apps/flutter_app/`（Dart/Flutter）与 `presets/`、`engines/`、`scripts/`。冻结目录（LEG-01 清单）零新提交。
- 每个新 Dart `lib/` 目录必须有测试覆盖（v4 门禁 meta-test）。

## Phase 112 Foundation (available for reuse)

- `apps/flutter_app/packages/acp_client` — Dart ACP v1 client (initialize, session/new, session/prompt, session/cancel, session/update, session/request_permission)
- `apps/flutter_app/lib/engine/` — DSH subprocess manager (spawn, health probe, shutdown, zero-orphan)
- `engines/dsh-pin.txt` — DSH commit pin (`47f943859b`)
- `engines/acp.cordis.yml` — ACP composition with terminal-default-deny approval stack
- `scripts/run_v4_gates.py` — V4 gates runner (dart analyze + flutter test + engine manifest + mock E2E + meta-test)
- `scripts/build_dsh_release.sh` — Engine release pipeline

## DSH Preset Architecture (verified from DSH repo)

- Preset = directory with one `agent.cordis.yml`
- DSH ships 4 presets: `standard`, `code`, `cordis`, `minimal` at `apps/cli/config/agent-presets/`
- `standard` preset is the base (full coding agent with persona, tools, skills, plan mode)
- `customSkillDirs` config field on `@deepseek-ai/dsh-skill-filesystem` plugin adds custom skill roots
- `@deepseek-ai/dsh-persona` plugin provides the agent persona text
- `@deepseek-ai/dsh-tool-ask-user` plugin provides the `ask_user_question` tool (MUST be removed for V4 — DP-1)
- Skills discovered from `customSkillDirs` directories; catalog (name+description) rendered into model prefix as `<available_skills>`
- Skill loading by name via `skill` tool

## V4 Guardrail Prompt Segments (PRD §7)

| Guardrail | Prompt segment content |
|---|---|
| research-gate | 结论前必须检索现行法规/司法解释，未检索不得结论 |
| citation audit | 输出引用必须标注 verified / retrieved / unverified |
| ask-user | 关键事实缺失不得起草，输出 `[CLARIFY: …]` 块 |
| de-AI polish | 终稿过一道去 AI 腔润色段 |
| human review | 高风险结论恒带 `[HUMAN_REVIEW: …]` |
| confidentiality | 上传前脱敏提醒、DeepSeek API 传输告知 |

## Out of Scope

- Skill content materialization pipeline (Phase 114)
- Content package auto-update (Phase 115)
- Chat UI / guardrail app-side enforcement (Phase 116/117)
- Word export (Phase 118)
- Windows packaging (Phase 119)

## Claude's Discretion

All implementation choices are at Claude's discretion — discuss phase was skipped per user setting (`workflow.skip_discuss=true`).
