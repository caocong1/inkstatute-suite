# Milestone Context: v4.0 Flutter Native + DSH Engine

**Created:** 2026-08-13
**Milestone:** v4.0 · Phases 112-120
**Spec:** `docs/requirements/V4-PRD.md`（权威）· **Evidence:** `.planning/research/V4-SELECTION.md` · **Summary:** `.planning/research/SUMMARY.md`

## Goals

1. 交付一个"电脑白痴双击即用"的 Windows 单文件安装包：安装 → 首启向导（执业方向 + 密钥 + 模型）→ 直接对话，之后零终端、零配置。
2. 引擎能力全部来自嵌入的钉版 DSH：Flutter 原生 app（**无 WebView**）经 ACP over stdio 驱动；agent loop / 工具 / 批准栈 / 技能系统 / 会话持久化 / 子代理 / 工作流零自研。
3. 法律能力包首次真正进入产品：`ai-for-china-legal` 经新增 `dsh` 物化 target → 分域预设（legal-core ≤30 + commercial/litigation/family/employment）→ 内容包启动时自动更新（唯一自动更新层）。
4. 六条法律护栏（research-gate / citation audit / ask-user / de-AI polish / human review / confidentiality）以"预设提示词段 + app 呈现/强制"双层落地，任一层缺失即算绕过。
5. Word 原生修订 docx 一键导出：模型产 JSON 变更清单，app 侧便携 Python 执行 41,185 字节 `contract_review_trackchanges.py`。
6. v3.x 平台整体冻结（LEG-01），律师试运行验收后退役（LEG-02）。

## Non-Goals (V4)

- 不用 WebView / 不嵌入 `dsh web` / 不复刻 Tauri 版。
- 不做 Gateway / WeCom / QQ / Arena / 管理台；不做自研 loop 任何后续投入。
- 不并 `legal-skills`（DEFER-01）；不全量挂载 396 技能（token 预算门禁）。
- 不做多用户 / 远程引擎 / 移动端；引擎层禁自动升级。

## Architecture (one paragraph)

单用户本地架构：`apps/flutter_app`（Flutter，含内部 Dart 包 `packages/acp_client`）spawn `engine\<version>\` 里的 DSH ACP 组合（`engines/acp.cordis.yml`），`DSH_HOME=%LOCALAPPDATA%\InkStatute\runtime\.dsh`；预设由本仓 `presets/<domain>/` 物化，技能内容包由更新器原子切换到 `skills\<release>\`；便携 Python 只做 docx 确定性变换；API 密钥从 OS 凭据库注入。分层与数据布局见 PRD §3。

## Key integration contract (already decided — do not relitigate)

- ACP 面 = 文本 in / 已提交文本 out / 一次性批准卡（DSH `packages/acp/acp/README.md` 已逐条核实）。
- DP-1 澄清走 `[CLARIFY: …]` 约定文本 + 前置采集（引擎移除 `ask_user_question`）。
- DP-2 工具活动不可见为接受取舍（状态文案 + 引用审计）。
- DP-3 批准卡唯一交互通道；terminal/execute_code 默认拒绝、上抛用户卡、无批量批准。
- DP-4 每会话单 in-flight prompt，UI 对齐禁用输入。
- 回退方案：RB1（分步表单）、RB2（尾随会话日志只读展示）——见 PRD §12.1，触发条件 = Phase 116 实测不达标。

## Phase list (112-120)

| Phase | 阶段 | 一句话 |
|---|---|---|
| 112 DSH Engine Integration (ACP over stdio) | A | Dart ACP 客户端 + 子进程管理 + 引擎发布管线 + v4 门禁；V1-V5 研究闭环 |
| 113 Legal Presets & Domain Presets | B | presets/ 五域 + 护栏提示词基座 + token 预算门禁 |
| 114 Skill Pipeline — dsh Target | B | 语料仓 convert-skills.js 加 dsh 物化 + manifest + 内容门禁 |
| 115 Skill Content Auto-Update | B | app 内容包更新器（原子切换/回滚/离线） |
| 116 Chat UI & Output Boundary | C | 会话 UI + 本地库 + 输出边界 + R2/R3 实测 |
| 117 Legal Guardrails | C | 六条护栏双层 + 绕过回归 |
| 118 Word Track-Changes Export | C | 变更清单 schema + 便携 Python docx + E2E 金标准 |
| 119 First-Run Wizard & Windows Packaging | D | 首启向导 + 单 exe + 三层更新 |
| 120 Convergence & Lawyer Trial | D | 遥测/离线 + v3.x 冻结收敛 + HG-1/HG-4/HG-3 |

## Critical constraints inherited from v3.x (still binding)

- 批准请求永不服务端默认放行；引用审计不可绕过；高风险结论永不自动定稿；敏感全文不进日志（reference-first）。
- 密钥/令牌/客户材料永不进仓库与日志。
- 人工闸门不得由自动化声称通过（HG-1 / HG-4 / HG-3）。
- 新代码必须带测试与门禁（v4 门禁 runner `scripts/run_v4_gates.py`，Phase 112 建立）。
