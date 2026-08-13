# Project Research Summary: Flutter Native + DSH Engine

**Domain:** 单用户 Windows 桌面法律助手：Flutter 原生 UI 经 ACP over stdio 驱动嵌入的 DeepSeek Harness（DSH）引擎，法律技能随版本化内容包自动更新
**Researched:** 2026-08-13
**Overall confidence:** HIGH

> 前里程碑研究摘要（v3.1 Legal AI Arena，2026-08-08）已随 v3.1 归档（git 历史保留；归档待 `/gsd-complete-milestone` 收尾）。

## Executive Summary

V4 把墨律重新定义为「法律能力包 + 律师可用外壳，套在 DSH 引擎上」。执行核心全面外包给 DSH（agent loop、工具注册表、批准栈、技能系统、会话持久化、子代理、工作流全部继承），墨律只保留三类真正属于它的资产：**法律技能语料（ai-for-china-legal 345 个 SKILL.md）、法律护栏（research-gate / citation audit / ask-user / de-AI polish / 人审标记）、律师可用性（Flutter 原生 UI、零操作安装、三层更新）**。V3 平台（gateway / wecom / qq / arena / 自研 Python core / Tauri 桌面）整体冻结，不再投入。

集成缝选定为 DSH 的 automation-only ACP server（JSON-RPC stdio）：文本 prompt 进、已提交 assistant 文本出、一次性批准卡为唯一交互通道。该缝的三个刻意限制（无 elicitation、无工具流、无 transcript replay）由产品侧约定吸收：澄清走 `[CLARIFY: …]` 标记文本 + 前置结构化采集；工具活动以状态文案呈现；批准卡由 app 策略化处理（未知 kind 拒绝、terminal 默认拒绝、无批量批准）。用户明确否决 WebView，`dsh web` 浏览器面与 Typert RPC 协议面均不在考虑范围。

技能管线是一条低风险增量：DSH 技能格式（目录 + SKILL.md + name/description frontmatter）与语料仓现格式同构；语料仓已有的 `convert-skills.js --to kimi|opencode|standalone` 多端物化管线增加 `dsh` target，仅需两类语义改写（斜杠命令 → 按名加载技能；CLAUDE.md 写入 → 会话配置事实源文件）。内容包独立版本化（manifest + sha256 + 原子切换 + 回滚），是三层更新中唯一自动的一层；DSH 的 skill-filesystem watcher 使技能更新无需重启。

风险最大的两点均有既定对策：DSH pre-release 兼容性 → 钉 commit、禁自动升级引擎、升级前真机回归；345 技能 token 成本 → 分域预设 + 核心集 ≤30 个 + 目录渲染长度预算门禁（超预算拒绝发货）。

## Key Findings

**引擎：** DSH ACP server 契约逐文件核实（initialize 仅 baseline 能力；session/new 要求绝对 cwd；单 in-flight prompt；`session/update` 只发已提交文本；断开零孤儿进程）。运行组合以 `examples/acp-agent/cordis.yml` 为模板，`provider`/`model` 必填，叶层供给沙箱/批准/fs/技能。

**预设：** Agent preset = 目录（preset.yml + agent.cordis.yml）挂单会话 scope；用户自创预设放 `${DSH_HOME}/.agent-presets/<id>/`；随附目录升级覆盖。V4 分域预设以 standard 为底、native 呈现；`cordis` 预设的 `customSkillDirs` 挂载写法即模板。

**技能：** 目录清单（name+description）进模型前缀 → 全量挂载不可行；模型经 `skill` 工具按名加载；`skill-filesystem` 自带 watcher → 内容包更新零重启。

**护栏：** 双层执行——预设提示词段（模型侧）+ app 呈现/强制（渲染侧），任一层缺失即绕过。批准栈 terminal 默认拒绝，经 ACP 上抛用户卡。

**docx：** 模型产 JSON 变更清单，app 侧便携 Python 执行 41,185 字节 `contract_review_trackchanges.py` 做确定性变换——可审计、可测试、模型不碰 docx 字节。

## Implications for Roadmap

- Phase 112（DSH 引擎底座）是技术风险闸口：V4-SELECTION §7 的 V1-V5 待验证项全部在该阶段 RESEARCH 闭环，任一项证伪即回退 PRD §12.1。
- Phase 113 先于 114：预设形态（分域目录 + customSkillDirs 挂载）决定转换器输出结构。
- Phase 116 承担两个产品级实测：澄清体验（R2）与可见性（R3），不达标启用 RB1/RB2。
- 引擎升级纪律（钉版 + 真机回归 + 禁自动）写入发布脚本与 CI，不靠自觉。

## Open Questions

- 语料仓转换器是否由 CI 在 Windows 侧跑（业主语料仓在 Windows 路径），或由 WSL 桥接执行——Phase 114 RESEARCH 定。
- GitHub Release 作为内容包源是否满足业主网络环境（中国大陆下载稳定性）——Phase 115 RESEARCH 定，必要时业主自有服务器。
- 便携 Python（Windows embeddable）打包体积与 docx 脚本依赖（lxml）兼容性——Phase 118 RESEARCH 定。
