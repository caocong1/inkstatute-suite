# Requirements: 墨律 InkStatute — v4.0 Flutter Native + DSH Engine

**Defined:** 2026-08-13
**Core Value:** 一名零技术操作的律师在 Windows 桌面上双击即用：Flutter 原生 app 经 ACP over stdio 驱动本地嵌入的 DSH 引擎，分域法律技能随内容包自动更新，四条法律护栏与人审标记不可绕过，Word 原生修订稿一键导出。

## v4.0 Requirements

每条需求恰好映射一个 roadmap phase（112–120）。规格真源：`docs/requirements/V4-PRD.md`；选型证据：`.planning/research/V4-SELECTION.md`。Traceability 见文末。

### DSH — 引擎接入

- [ ] **DSH-01**: Dart ACP v1 客户端（`apps/flutter_app/packages/acp_client`）——JSON-RPC stdio 帧收发、`initialize` 握手（仅 baseline 能力）、`session/new`（绝对 cwd；`additionalDirectories`/`mcpServers` 非空即拒）、`session/prompt`（单 in-flight）、`session/cancel`、`session/update` 文本块聚合、`session/request_permission` 策略钩子；以脚本化 mock ACP server（fixtures）完整测试，无需真实模型
- [ ] **DSH-02**: DSH 子进程管理器——从捆绑引擎目录 spawn ACP 组合；`DSH_HOME` 指向 `%LOCALAPPDATA%\InkStatute\runtime\.dsh`；API 密钥经环境注入（不落盘明文）；initialize 握手健康探针；app 退出优雅关停；零孤儿进程断言
- [ ] **DSH-03**: 引擎发布产物管线（`scripts/build_dsh_release.sh` + `engines/dsh-pin.txt` + `engines/acp.cordis.yml`）——钉 commit 构建 → `engine-<version>.zip`（便携 Node + 构建产物 + ACP 组合 + 预设物化）→ `engine-manifest.json` {dsh_commit, node_version, sha256, built_at}；**引擎禁自动升级**，升级须真机回归后随 app 版本发布
- [ ] **DSH-04**: 批准安全——引擎批准栈 terminal/execute_code 默认拒绝并上抛 `session/request_permission`；app 策略：未知 kind 一律拒绝、已知 kind 渲染用户卡片、无批量批准入口；mock 权限事件测试全路径
- [x] **DSH-05**: 凭据与模型——密钥存 OS 凭据库、启动时注入；模型/供应商默认（DeepSeek 官方路由）可配；密钥轮换入口（业主模式）；日志与遥测零明文密钥

### SKL — 技能管线

- [ ] **SKL-01**: 语料仓 `scripts/convert-skills.js` 新增 `--to dsh`——白名单按域扫描（不扫 `.qwen/` 等自动产物目录）；frontmatter 直通；两类语义改写：斜杠命令 → skill 工具按名加载指引、CLAUDE.md 写入目标 → app 数据目录 `practice-profile.md`；输出 `dist/dsh/<domain>/<skill-name>/SKILL.md`
- [ ] **SKL-02**: 内容包格式与发布——`content-manifest.json` {schema_version, release_version, released_at, min_engine_version, domains:{skills:[{name,sha256}]}}；convert → manifest → zip → release（GitHub Release 默认，可配自有源）纯脚本流水线
- [ ] **SKL-03**: 语料仓内容门禁——`test:compatibility` 扩展断言 dsh 输出：每个 SKILL.md 可解析、frontmatter 合法、无斜杠命令残留、目录名=技能名唯一
- [ ] **SKL-04**: app 技能更新器——启动 + 手动检查拉 manifest；版本比对；原子下载解压到 `skills\<release>\`；sha256 校验失败回滚 last-good；current 指针切换；离线用 last-good；更新全程零用户操作、零重启
- [ ] **SKL-05**: 分域预设——本仓 `presets/<domain>/`（legal-core ≤30 技能核心集 + legal-commercial / legal-litigation / legal-family / legal-employment 首批四域）；以 standard 为底、native 呈现；`customSkillDirs` 指向内容包分域目录；安装时物化到引擎 `.agent-presets/`
- [ ] **SKL-06**: 预设人设与护栏提示词基座——research-gate / citation audit / ask-user（`[CLARIFY:]` 约定）/ de-AI polish / `[HUMAN_REVIEW:]` 输出约定 / 保密提示全部入预设人设；先加载对应技能再动手
- [ ] **SKL-07**: token 预算门禁——默认会话只挂所选分域目录；核心集目录渲染（name+description）长度 ≤ 预算（默认 8,000 字符，可配置）；超预算回归测试红灯、拒绝发货

### APP — Flutter 产品

- [x] **APP-01**: Flutter 工程骨架（`apps/flutter_app/`，Windows 桌面优先）——单一 chat UI 实现；墨律三主题以 lawyer-desktop 23 组件为设计参照（不逐字复制）
- [x] **APP-02**: 会话 UI——已提交文本流式渲染、批准卡片、澄清卡片（解析 `[CLARIFY:]`）、引用徽记（verified/retrieved/unverified）、人审徽记（`[HUMAN_REVIEW:]`）、状态文案（工具活动不可见为接受取舍，PRD DP-2）；单 in-flight 时输入禁用
- [x] **APP-03**: 本地会话库（SQLite/drift）——会话/消息/引用/审批记录；按执业方向分组；删除与导出
- [x] **APP-04**: Word 原生修订导出——模型产结构化变更清单 JSON（schema 本阶段定义）；app 侧便携 Python 执行 `contract_review_trackchanges.py` 确定性变换；输出 docx 到用户路径；金标准 fixtures 取 lawfirm-profile；模型永不直接写 docx 字节
- [x] **APP-05**: 输出边界——只渲染已提交 assistant 文本；DSH meta/system 噪声永不出现；错误映射用户可读（引擎未启动/限流/鉴权/超时）；原始堆栈只进本地日志
- [x] **APP-06**: 首启向导——执业方向卡片（设默认预设）→ 密钥（预填或一次性粘贴，存 OS 凭据库）→ 模型确认；之后零终端零配置文件

### GRD — 法律护栏

- [x] **GRD-01**: research-gate——未检索现行法规/司法解释不得下结论；app 侧无 verified 引用时结论区"待核实"标记
- [x] **GRD-02**: citation audit——引用必标 verified / retrieved / unverified；三类徽记渲染，unverified 视觉警示
- [x] **GRD-03**: ask-user 强制——关键事实缺失不得起草；模型输出 `[CLARIFY: …]` 块；app 渲染澄清卡片；未澄清任务锁定
- [x] **GRD-04**: de-AI polish——终稿过润色段；独立样式呈现
- [x] **GRD-05**: human review——高风险结论恒带 `[HUMAN_REVIEW: …]`；徽记不可自动消除；批准栈无任何放行路径
- [x] **GRD-06**: 保密——上传前脱敏提醒；DeepSeek API 传输告知；客户材料任务入口一次性确认；本地默认

### PKG — 打包交付

- [x] **PKG-01**: Windows 单 exe 安装包——Flutter build + 引擎 zip + 便携 Python + 初始内容包 + 预设；装到 `%LOCALAPPDATA%\InkStatute`；开始菜单/桌面快捷方式；零命令行
- [x] **PKG-02**: 三层更新器——app（安装器）/ 引擎（zip 原子替换，禁自动）/ 内容包（唯一自动层）；启动 manifest 检查；签名校验；回滚
- [x] **PKG-03**: 健康/崩溃遥测——opt-in、脱敏上传；引擎健康探针（initialize 握手）内嵌；业主远程日志路径
- [x] **PKG-04**: 离线行为——last-good 引擎+内容可启动、可看历史；新任务需联网并明确提示

### LEG / GATE — 收敛与门禁

- [x] **LEG-01**: v3.x 平台冻结——gateway / wecom / qq / arena / agent-core / acp-client(TS) / ui-core(SolidJS) / apps/web / apps/desktop 标注 frozen（README + MILESTONES），不进 V4 交付物与 V4 gate 套件，不新开工；移除仅在 Phase 120 验收后
- [x] **LEG-02**: 收敛——律师试运行验收后移除退役目录；v3.0/v3.1 文档归档到 `milestones/`；主线只含 V4 产品代码路径
- [ ] **GATE-01**: v4 门禁 runner（`scripts/run_v4_gates.py`）——dart analyze + flutter test + 内容结构测试 + 引擎清单校验，接 CI
- [ ] **GATE-02**: 覆盖门禁——每个新 Dart `lib/` 目录有测试覆盖；meta-test 在 v4 runner 内
- [x] **GATE-03**: E2E——mock ACP 全流程（prompt → 流 → 批准卡 → 答复 → committed text）+ 真实引擎路径（DeepSeek API，标注 real-API）+ docx 导出金标准

## Future Requirements (post-v4.0)

- **FUTURE-01**: legal-skills 语料并入（DEFER-01，许可评估后）
- **FUTURE-02**: 流式工具事件接入（DSH 侧能力出现后）
- **FUTURE-03**: DSH ACP 暴露 elicitation 后的原生澄清卡
- **FUTURE-04**: 多用户/远程引擎（DSH 部署形态演进后重估）
- **FUTURE-05**: v3.x 平台资产复活评估（多律所场景）
- **FUTURE-06**: Code Mode（PTC 呈现）作为可选预设给进阶用户

## Out of Scope

| Feature | Reason |
|---------|--------|
| WebView / `dsh web` 嵌入 | 用户明确否决；Flutter 选型意义即原生 UI |
| Gateway / WeCom / QQ / Arena / 管理台 | 单用户交付错配；LEG-01 冻结 |
| 自研 agent loop 后续投入 | 引擎 = DSH，军备竞赛结论（PRD §0.1） |
| 全量挂载 396 技能 | token 预算（SKL-07） |
| 移动端 | 沿用 V3 决定推后 |
| ACP v2 特性 | draft 且破坏性变更，锁 v1（继承 V3） |
| 引擎自动升级 | pre-release 兼容风险（DSH-03） |
| 模型直写 docx 字节 | 确定性变换在 app 侧（APP-04） |
| 批量批准 / 服务端默认放行 | 红线继承 V3（DSH-04） |
| 复制技能语料进本仓 | 只读物化，语料仓唯一事实源（继承 V3） |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DSH-01 | 112 | In progress (tracer complete in 112-01; full coverage in 112-02) |
| DSH-02 | 112 | Not started |
| DSH-03 | 112 | Not started |
| DSH-04 | 112 | Not started |
| GATE-01 | 112 | Not started |
| GATE-02 | 112 | Not started |
| SKL-05 | 113 | Not started |
| SKL-06 | 113 | Not started |
| SKL-07 | 113 | Not started |
| SKL-01 | 114 | Not started |
| SKL-02 | 114 | Not started |
| SKL-03 | 114 | Not started |
| SKL-04 | 115 | Not started |
| APP-01 | 116 | Not started |
| APP-02 | 116 | Not started |
| APP-03 | 116 | Not started |
| APP-05 | 116 | Not started |
| GRD-01 | 117 | Not started |
| GRD-02 | 117 | Not started |
| GRD-03 | 117 | Not started |
| GRD-04 | 117 | Not started |
| GRD-05 | 117 | Not started |
| GRD-06 | 117 | Not started |
| APP-04 | 118 | Not started |
| GATE-03 | 118 | Not started |
| APP-06 | 119 | Not started |
| DSH-05 | 119 | Not started |
| PKG-01 | 119 | Not started |
| PKG-02 | 119 | Not started |
| PKG-03 | 120 | Not started |
| PKG-04 | 120 | Not started |
| LEG-01 | 120 | Not started |
| LEG-02 | 120 | Not started |

**Coverage:**

- v4.0 requirements: 33 total (5 DSH + 7 SKL + 6 APP + 6 GRD + 4 PKG + 2 LEG + 3 GATE)
- Mapped to phases: 33 (100%)
- Unmapped: 0 ✅

**Phase distribution:**

| Phase | Requirements | Count |
|-------|-------------|-------|
| 112 DSH Engine Integration | DSH-01..04, GATE-01, GATE-02 | 6 |
| 113 Legal Presets & Domain Presets | SKL-05..07 | 3 |
| 114 Skill Pipeline — dsh Target | SKL-01..03 | 3 |
| 115 Skill Content Auto-Update | SKL-04 | 1 |
| 116 Chat UI & Output Boundary | APP-01..03, APP-05 | 4 |
| 117 Legal Guardrails | GRD-01..06 | 6 |
| 118 Word Track-Changes Export | APP-04, GATE-03 | 2 |
| 119 First-Run Wizard & Windows Packaging | APP-06, DSH-05, PKG-01, PKG-02 | 4 |
| 120 Convergence & Lawyer Trial | PKG-03, PKG-04, LEG-01, LEG-02 | 4 |
| **Total** | | **33** |

**Distribution rationale:**

- DSH 需求集中在 112（引擎底座），凭据/向导归 119（与打包同阶段验证交付路径）。
- SKL 按管线顺序切分：预设（113）→ 物化（114）→ 更新（115）；SKL-07 预算门禁与预设同阶段（113），因为预算由预设形态决定。
- GRD 全部归 117（护栏阶段统一双层落地），与 116（UI）解耦、与 118（docx）解耦。
- GATE-01/02 随 112 建立 v4 门禁体系；GATE-03（E2E 与金标准）归 118，覆盖全链路。

---
*Requirements defined: 2026-08-13*
*Last updated: 2026-08-13 after roadmap creation (33/33 mapped, 100% coverage)*
