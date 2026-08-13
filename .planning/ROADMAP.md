# Roadmap: 墨律 InkStatute

## Milestones

- 🔄 **v4.0 Flutter Native + DSH Engine** — Phases 112-120 (started 2026-08-13)
- ✅ **v3.1 Legal AI Arena** — Phases 105-111 (shipped 2026-08-09)
- ✅ **v3.0 Unified Legal Core** — Phases 88-104 (shipped 2026-08-08)
- ✅ **V2 PRD Foundation** — Phases 1-8 (2026-06-30; Phase 5/8 human gates carried)
- ✅ **v1.1 Platform Foundation** — Phases 09-13 (2026-06-30)
- ✅ **v1.2 Conversational Context and Memory Foundation** — Phases 14-19 (2026-07-02)
- ✅ **v1.3 Production Memory System and Evaluation Spikes** — Phases 20-25.1 (2026-07-02)
- ✅ **v1.4 Long-Term Memory Productization** — Phases 26-32 (2026-07-03)
- ✅ **v1.5 V2 Acceptance Closure** — Phases 33-35 (2026-07-03)
- ✅ **v1.6 M2 Multi-Backend & Platform Extensions** — Phases 36-44 (2026-07-04)
- ✅ **v1.7 M3 Platform Extensions** — Phases 45-57.1 (2026-07-06)
- ✅ **v1.8 QQBot Channel Production** — Phases 58-67 (2026-07-09)
- ✅ **v1.9 QQBot Host Composition** — Phases 68-72 (2026-07-10)
- ✅ **v1.10 Operator Config Console** — Phases 73-78.1 (2026-07-12)
- ✅ **v1.11 Product Console** — Phases 79-87 (2026-07-15)

<details>
<summary>✅ v1.x archives (Phases 1-87) — SHIPPED</summary>

All v1.x phase details, requirements, and audits are archived under `.planning/milestones/`.
See `.planning/MILESTONES.md` for the consolidated history.

Carried human gates from v1.x (NOT closed by v3.0 or v3.1):

- Phase 5 live WeCom UAT operator confirmation
- Phase 8 five-workday lawyer trial acceptance
- Operator `--live` QQ OpenAPI acceptance evidence

</details>

---

## 🔄 v4.0 Flutter Native + DSH Engine (STARTED 2026-08-13)

**Milestone Goal:** 一名零技术操作的律师在 Windows 桌面上双击即用：Flutter 原生 app（无 WebView）经 ACP over stdio 驱动本地嵌入的 DeepSeek Harness（DSH）引擎；分域法律预设 + 技能内容包自动更新；四条法律护栏与人审标记不可绕过；Word 原生修订稿一键导出；v3.x 平台整体冻结收敛。

**Source:** `docs/requirements/V4-PRD.md` · **Requirements:** `.planning/REQUIREMENTS.md` · **Research:** `.planning/research/SUMMARY.md` · **Evidence:** `.planning/research/V4-SELECTION.md`

**Stages:**

| 阶段 | Phases | 完成后的状态 |
|---|---|---|
| A DSH 引擎底座 | 112 | Flutter 骨架 + Dart ACP 客户端 + 子进程管理 + 引擎发布脚本，mock 全链路冒烟通过 |
| B 法律预设与能力层 | 113-115 | 分域预设 + dsh 物化管线 + 内容包自动更新可用，token 预算门禁生效 |
| C 客户端与护栏 | 116-118 | 会话 UI / 批准与澄清 / 护栏双层 / Word 导出端到端可用 |
| D 交付与收敛 | 119-120 | 单 exe 安装包 + 三层更新 + 律师试运行验收 + v3.x 冻结收敛 |

**关键路径：** 112 → 113 → 116 → 117 → 119 → 120（118 完成后 119 才可集成导出；120 闭合全部）

**并行机会：** 114/115（技能管线）在 113 之后即可与 116/117 并行；118（docx）依赖 113 与引擎即可，与 116/117 并行；119 依赖 115+116+117+118。

**人工闸门（不得自动关闭）：** HG-1 法律质量（Phase 120）、HG-4 修订稿质量（Phase 118）、HG-3 五工作日/15 真实任务律师试运行（Phase 120）。HG-2（WeCom）与 QQ `--live` 随通道冻结转入 DEFER。

## Phases

### 阶段 A — DSH 引擎底座

- [ ] **Phase 112: DSH Engine Integration (ACP over stdio)** - Flutter 骨架 + Dart ACP v1 客户端 + DSH 子进程管理器 + 引擎发布产物管线 + v4 门禁 runner + 批准安全 (DSH-01..04, GATE-01, GATE-02)

### 阶段 B — 法律预设与能力层

- [ ] **Phase 113: Legal Presets & Domain Presets** - 分域预设（core+四域）+ 人设与护栏提示词基座 + token 预算门禁 (SKL-05..07)
- [ ] **Phase 114: Skill Pipeline — dsh Target** - 语料仓 convert-skills.js 新增 dsh 物化 + 内容包 manifest + 内容门禁 (SKL-01..03)
- [ ] **Phase 115: Skill Content Auto-Update** - app 侧内容包更新器：manifest 比对 + 原子切换 + 回滚 + 离线 (SKL-04)

### 阶段 C — 客户端与护栏

- [ ] **Phase 116: Chat UI & Output Boundary** - Flutter 会话 UI（流式/批准卡/澄清卡/引用/人审徽记）+ 本地会话库 + 输出边界 (APP-01..03, APP-05)
- [ ] **Phase 117: Legal Guardrails** - 六条护栏双层落地（提示词段 + app 呈现/强制） (GRD-01..06)
- [ ] **Phase 118: Word Track-Changes Export** - 变更清单 schema + 便携 Python 确定性 docx 变换 + E2E 金标准 (APP-04, GATE-03)

### 阶段 D — 交付与收敛

- [ ] **Phase 119: First-Run Wizard & Windows Packaging** - 首启向导 + 凭据/模型 + 单 exe 安装包 + 三层更新器 (APP-06, DSH-05, PKG-01, PKG-02)
- [ ] **Phase 120: Convergence & Lawyer Trial** - 遥测 + 离线行为 + v3.x 冻结收敛 + 人工闸门 (PKG-03, PKG-04, LEG-01, LEG-02)

---

## Phase Details

### Phase 112: DSH Engine Integration (ACP over stdio)

**Goal**: 建立 V4 的技术地基：Flutter 工程骨架内有一个按契约实现的 Dart ACP v1 客户端和一个受控的 DSH 子进程管理器，用脚本化 mock ACP server 即可端到端冒烟（无需真实模型）；引擎发布产物管线（钉版构建）与 v4 门禁 runner 同日建立。V4-SELECTION §7 的 V1-V5 待验证项在本阶段 RESEARCH 全部闭环
**Depends on**: Nothing (first v4.0 phase; builds on DSH repo + V4 PRD)
**Requirements**: DSH-01, DSH-02, DSH-03, DSH-04, GATE-01, GATE-02
**Success Criteria** (what must be TRUE):

  1. `apps/flutter_app/` 工程存在且 `flutter analyze` / `flutter test` 全绿；`packages/acp_client` 为 app 内部 Dart 包（path 依赖），不进 npm 工作区
  2. Dart ACP 客户端通过脚本化 mock server fixtures：initialize 握手、session/new（绝对 cwd；additionalDirectories/mcpServers 非空拒绝路径有测试）、session/prompt 单 in-flight 拒绝、session/cancel、session/update 文本块聚合、session/request_permission 策略钩子
  3. DSH 子进程管理器：从 `engine\<version>\` spawn ACP 组合成功；`DSH_HOME` 指向 `%LOCALAPPDATA%\InkStatute\runtime\.dsh`；initialize 健康探针通过；app 退出后零孤儿进程（PID 断言测试）；日志 reference-first
  4. `scripts/build_dsh_release.sh` 在 `engines/dsh-pin.txt` 钉住的 commit 上构建产出 `engine-<version>.zip` + `engine-manifest.json`（dsh_commit/node_version/sha256/built_at 字段齐全、sha256 可复验）；`engines/acp.cordis.yml` 含批准栈"terminal 默认拒绝"配置
  5. 批准安全路径：mock 权限事件下，未知 kind 一律拒绝、terminal/execute_code 渲染用户卡片、无批量批准路径（测试覆盖三态）
  6. `scripts/run_v4_gates.py` 存在并接入 CI：dart analyze + flutter test + 引擎清单校验；meta-test 断言每个新 Dart `lib/` 目录有测试覆盖
  7. V4-SELECTION §7 的 V1（真实 ACP 全流程）、V2（审批上抛）、V3（skill 目录进前缀）、V4（会话日志路径）、V5（构建后启动形态）全部实测并在 `112-RESEARCH.md` 记录结论；任一证伪即触发 PRD §12.1 回退评审

**Plans**: 6 plans
**Wave 1**

- [x] 112-01-PLAN.md — Wave 1 tracer: Flutter skeleton + acp_client + initialize handshake + mock fixture (DSH-01) ✅ 2026-08-13

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 112-02-PLAN.md — Wave 2: Full ACP v1 client method coverage with mock fixtures (DSH-01)
- [ ] 112-03-PLAN.md — Wave 2: Approval security three-state tests (DSH-04)
- [ ] 112-04-PLAN.md — Wave 2: DSH subprocess manager — spawn, health probe, zero orphans (DSH-02)

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 112-05-PLAN.md — Wave 3: Engine release pipeline — dsh-pin.txt + acp.cordis.yml + build_dsh_release.sh (DSH-03)
- [ ] 112-06-PLAN.md — Wave 3: v4 gates runner + CI — dart analyze + flutter test + meta-test (GATE-01, GATE-02)

**UI hint**: no

### Phase 113: Legal Presets & Domain Presets

**Goal**: 建立 V4 能力层的形态：本仓 `presets/` 下产出 legal-core（≤30 核心集）+ 四域预设，人设统一携带护栏提示词基座与澄清约定；token 预算门禁测试红灯即拒发货。分域形态决定 Phase 114 转换器的输出结构，故本阶段先行
**Depends on**: Phase 112
**Requirements**: SKL-05, SKL-06, SKL-07
**Success Criteria** (what must be TRUE):

  1. `presets/legal-core`（≤30 技能）+ `presets/legal-commercial` / `legal-litigation` / `legal-family` / `legal-employment` 各自含 preset.yml（name/description）+ agent.cordis.yml（以 standard 为底、native 呈现、persona、工具集、`customSkillDirs` 指向内容包分域目录）
  2. 预设人设统一包含：research-gate / citation audit（verified/retrieved/unverified）/ ask-user（`[CLARIFY: …]` 约定，缺失事实不得起草）/ de-AI polish / `[HUMAN_REVIEW: …]` 输出约定 / 保密提示 / "先经 skill 工具加载对应技能再动手"
  3. 引擎组合中 ACP 会话移除 `ask_user_question` 工具（澄清走约定文本，PRD DP-1），测试断言该工具不在 ACP 会话工具集
  4. 用 Phase 112 的引擎底座对 legal-core 做一次真实引擎冒烟：挂载 2-3 个技能，确认目录进入模型前缀、按名加载可用（V3 验证项的落地形态）
  5. SKL-07 预算门禁：核心集目录渲染（name+description）长度 ≤ 8,000 字符（可配置），超预算测试红灯；345 技能全量挂载被显式禁止并有无害断言说明
  6. 预设物化脚本：`scripts/materialize_presets.sh` 把 `presets/` 物化到引擎 `~/.agent-presets/<domain>/`（安装时执行）；随附安装目录只读纪律写进脚本注释

**Plans**: TBD (est. 3-4)
**UI hint**: no

### Phase 114: Skill Pipeline — dsh Target

**Goal**: 语料仓 `ai-for-china-legal` 获得一条 `dsh` 物化管线：白名单分域扫描 + 两类语义改写，产出结构稳定的技能树；内容包 manifest 与发布脚本一次成型，内容门禁拦住一切格式漂移。墨律本仓不复制语料
**Depends on**: Phase 113
**Requirements**: SKL-01, SKL-02, SKL-03
**Success Criteria** (what must be TRUE):

  1. `scripts/convert-skills.js --to dsh`：白名单按域扫描（`.qwen/`、`managed-agent-cookbooks/` 等自动产物目录不扫）；frontmatter（name/description）直通；输出 `dist/dsh/<domain>/<skill-name>/SKILL.md`，目录名=技能名且唯一
  2. 两类语义改写有测试：斜杠命令（`/commercial-legal:cold-start-interview`）→ "用 skill 工具按名加载 X 技能"指引；CLAUDE.md 写入指令 → 写 app 数据目录 `practice-profile.md`
  3. `content-manifest.json` 生成器：schema_version / release_version / released_at / min_engine_version / domains:{skills:[{name,sha256}]}；zip 发布脚本（GitHub Release 默认，`CONTENT_RELEASE_URL` 可配自有源）
  4. 内容门禁（`test:compatibility` 扩展）：每个输出 SKILL.md 可解析、frontmatter 合法、无斜杠命令残留、无 "写 CLAUDE.md" 残留；CI 红灯拦截
  5. RESEARCH 结论落 `114-RESEARCH.md`：语料仓（Windows 路径）转换执行方式（Windows CI 或 WSL 桥接）定案并写入发布脚本
  6. 端到端演示：从语料仓源 → dsh 物化 → manifest → zip → 解包到内容包目录，全程脚本化、无手工步骤

**Plans**: TBD (est. 3-4)
**UI hint**: no

### Phase 115: Skill Content Auto-Update

**Goal**: app 侧内容包更新器上线：启动与手动检查两条路径，manifest 比对 → 原子下载解压 → sha256 校验 → current 指针切换，失败自动回滚 last-good，离线降级；全程零用户操作、零重启（DSH skill watcher 生效）
**Depends on**: Phase 113, Phase 114
**Requirements**: SKL-04
**Success Criteria** (what must be TRUE):

  1. 启动时（+设置页手动检查）拉取 `content-manifest.json` 与本地 current 比对；无更新零操作，有更新走下载流程
  2. 原子性：解压到 `skills\<release>\` 临时目录 → 全量 sha256 校验 → 切换 current 指针 → 清理旧版本（保留 last-good）；任一步失败回滚 last-good 并明确提示"技能更新失败，已回退"
  3. 离线/拉取失败：用 last-good 启动，设置页显示"技能更新不可用"；不阻塞会话功能
  4. 更新后零重启验证：技能目录 watcher 在会话中刷新目录（测试：更新前后 skill 目录快照变化且引擎无重启）
  5. RESEARCH 结论落 `115-RESEARCH.md`：GitHub Release 作为内容源在中国大陆网络环境的可用性（含备选自有服务器方案）；更新源 URL 配置化
  6. 安全：manifest 与 zip 签名校验（或 sha256 链式校验），伪造/截断包被拒；降级攻击（更低 release_version）被拒

**Plans**: TBD (est. 3)
**UI hint**: yes

### Phase 116: Chat UI & Output Boundary

**Goal**: 律师看到的产品本体：单一 Flutter 会话 UI 完整渲染已提交文本流、批准卡片、澄清卡片、引用徽记、人审徽记与状态文案；本地会话库落成；输出边界把一切引擎噪声挡在用户视野外。同时完成 R2（澄清体验）与 R3（可见性）两个产品级实测
**Depends on**: Phase 112, Phase 113
**Requirements**: APP-01, APP-02, APP-03, APP-05
**Success Criteria** (what must be TRUE):

  1. `apps/flutter_app/lib/chat/` 为唯一 chat UI 实现；墨律三主题可用（lawyer-desktop 23 组件为设计参照）；`flutter test` 全绿
  2. 流式渲染：agent_message_chunk 增量渲染已提交文本；单 in-flight 时输入禁用并显示"处理中"；取消路径（session/cancel）有 UI 与测试
  3. 批准卡片：`session/request_permission` 渲染为 allow/reject 卡片；未知 kind 拒绝策略生效；无批量批准控件
  4. 澄清卡片：模型输出含 `[CLARIFY: …]` 时渲染澄清卡片，用户补充后作为新 prompt 继续；实测一次完整澄清往返（R2 结论落 `116-RESEARCH.md`，不达标启用 PRD RB1）
  5. 引用/人审渲染：verified/retrieved/unverified 三态徽记与 `[HUMAN_REVIEW: …]` 徽记视觉可辨（截图/组件测试）
  6. 输出边界：非 assistant 已提交文本一律不渲染（DSH meta/system 噪声测试）；错误映射用户可读（引擎未启动/限流/鉴权/超时四类场景测试）；原始堆栈只进本地日志
  7. 本地会话库（SQLite/drift）：会话/消息/引用/审批记录 CRUD、按执业方向分组、删除与导出（隐私验收项）
  8. 可见性实测（R3）：状态文案（"正在检索/起草/复核"）与引用审计联动可用；不达标启用 PRD RB2（尾随会话日志只读展示）并在 RESEARCH 记录

**Plans**: TBD (est. 5-6)
**UI hint**: yes

### Phase 117: Legal Guardrails

**Goal**: 六条护栏以"提示词段 + app 呈现/强制"双层落地，任一层缺失都算护栏绕过（回归测试锁定）；批准栈维持 terminal 默认拒绝；高风险结论恒带人审徽记且不可自动消除
**Depends on**: Phase 116
**Requirements**: GRD-01, GRD-02, GRD-03, GRD-04, GRD-05, GRD-06
**Success Criteria** (what must be TRUE):

  1. research-gate 双层：预设人设已含（Phase 113）；app 侧无 verified 引用时结论区"待核实"标记，测试锁定
  2. citation audit 双层：模型输出引用解析（verified/retrieved/unverified 标记语法）→ 徽记渲染；解析失败的引用落入 unverified，测试锁定
  3. ask-user 双层：`[CLARIFY: …]` 解析（Phase 116 已建）与"未澄清任务锁定"状态机；锁定态下发送新任务被拦截并提示先补充事实
  4. de-AI polish：终稿渲染样式独立；终稿前无 polish 标记的结论被 app 标记"未经润色"
  5. human review：`[HUMAN_REVIEW: …]` 徽记渲染且无任何 UI/API 路径可自动消除；高风险任务类型清单（法律结论/文书对外版）在 app 配置层定义
  6. confidentiality：涉及客户材料的任务入口弹一次性确认（DeepSeek API 传输告知 + 脱敏提醒）；确认记录落本地库
  7. 护栏回归套件：6 条护栏各至少 1 个"绕过尝试"负向测试（如无检索直接结论、无引用输出、缺事实起草、批量批准入口存在性断言）
  8. 真实引擎实测：一条带护栏冲突的法律任务（故意缺关键事实）在真实 DSH 引擎上产出 `[CLARIFY: …]` 而非草稿（real-API 标注）

**Plans**: TBD (est. 4-5)
**UI hint**: yes

### Phase 118: Word Track-Changes Export

**Goal**: 律师一键拿到带 Word 原生修订的 docx：模型产结构化变更清单，app 侧便携 Python 执行 41,185 字节 track-changes 脚本做确定性变换；E2E 与金标准齐备，人工闸门 HG-4 就位
**Depends on**: Phase 113
**Requirements**: APP-04, GATE-03
**Success Criteria** (what must be TRUE):

  1. 变更清单 JSON schema 定义（在契约层）：条款定位、原文、修订文、修订理由、风险等级；schema 校验测试
  2. 便携 Python（Windows embeddable）+ `contract_review_trackchanges.py` 打包进 app；以变更清单为输入、docx 为输出，模型永不直接写 docx 字节（代码断言：导出路径无模型文本直写）
  3. 金标准 fixtures：lawfirm-profile 既有测试用例迁移为 V4 回归；输出 docx 的 track-changes 结构与 fixture 一致
  4. 导出 UX：会话内一键导出 → 用户指定路径 → 成功/失败状态明确；失败不污染会话（输出边界保持）
  5. GATE-03 E2E：mock ACP 全流程（prompt → 流 → 批准卡 → 答复 → committed text）+ 真实引擎路径（real-API 标注）+ docx 金标准，三者入 v4 门禁
  6. RESEARCH 结论落 `118-RESEARCH.md`：embeddable Python 体积与 lxml 依赖兼容性定案；体积超限时降级方案（纯 Python 依赖最小化）定案
  7. **人工闸门 HG-4**：docx 须经律师确认可用于对外谈判——自动化只记录"待确认"状态，不得声称通过

**Plans**: TBD (est. 3-4)
**UI hint**: yes

### Phase 119: First-Run Wizard & Windows Packaging

**Goal**: "电脑白痴双击即用"的交付形态：首启向导（执业方向 → 密钥 → 模型确认）之后零终端零配置；单 exe 安装包与三层更新器（app/引擎/内容包）落地，引擎层禁自动升级
**Depends on**: Phase 115, Phase 116, Phase 117, Phase 118
**Requirements**: APP-06, DSH-05, PKG-01, PKG-02
**Success Criteria** (what must be TRUE):

  1. 首启向导三步走通：执业方向卡片（写默认预设）→ 密钥（预填/一次性粘贴 → OS 凭据库）→ 模型确认；向导完成后任何后续会话不再要求终端/配置
  2. 凭据安全：密钥只进 OS 凭据库，启动时环境注入引擎；仓库/日志/遥测/安装包零明文密钥（全路径 grep 断言）
  3. 密钥轮换入口：业主模式（设置页隐藏入口 + 快捷键），普通用户不可见
  4. 单 exe 安装包：装到 `%LOCALAPPDATA%\InkStatute`，开始菜单/桌面快捷方式；卸载干净（含 runtime 数据保留提示）
  5. 三层更新器：app（安装器自更新）、引擎（zip 原子替换，**禁自动**，仅随 app 版本发布）、内容包（唯一自动层，Phase 115）；启动 manifest 检查、签名校验、回滚路径
  6. 全链路冒烟：干净 Windows 虚拟机安装 → 向导 → 一次真实法律任务（real-API 标注）→ docx 导出 → 重启 app 状态保留
  7. 模型默认：DeepSeek 官方路由（deepseek-v4 系）配置化；供应商/模型可改但只进业主模式

**Plans**: TBD (est. 4-5)
**UI hint**: yes

### Phase 120: Convergence & Lawyer Trial

**Goal**: 交付收口：opt-in 遥测与离线行为就位；v3.x 平台组件冻结标注完成、验收通过后归档退役；三项人工闸门（HG-1 法律质量、HG-4 修订稿质量、HG-3 律师试运行）进入签字流程，自动化永不声称通过
**Depends on**: Phase 119
**Requirements**: PKG-03, PKG-04, LEG-01, LEG-02
**Success Criteria** (what must be TRUE):

  1. 遥测：opt-in、脱敏（无密钥/无客户全文/无原始 payload）；引擎健康探针（initialize 握手）内嵌；业主远程日志路径可用
  2. 离线行为：断网可启动、可看历史、新任务明确提示"需联网"；last-good 引擎+内容包完整可用（PKG-04）
  3. LEG-01 冻结标注：gateway / wecom / qq / arena / agent-core / acp-client(TS) / ui-core(SolidJS) / apps/web / apps/desktop 在 README + MILESTONES 标 frozen；v4 门禁套件不覆盖冻结代码；冻结代码零新提交（收敛后）
  4. LEG-02 收敛：律师试运行验收通过后，移除退役目录；v3.0/v3.1 文档归档 `milestones/`；主线只含 V4 产品代码路径
  5. **人工闸门 HG-3**：五工作日 / 15 真实任务律师试运行记录签字（业主的朋友为试用律师）；HG-1：V4 基线（DSH+分域预设）法律质量经律师抽样确认不低于 lawyer-desktop/Hermes 基线；HG-4 随 Phase 118 验收一并签字
  6. v4 门禁全绿（dart analyze / flutter test / 内容结构 / 引擎清单 / mock E2E / docx 金标准）；真实引擎路径场景六条（PRD §2）全通过
  7. Milestone audit（`/gsd-audit-milestone`）与归档（`/gsd-complete-milestone`）完成

**Plans**: TBD (est. 3-4)
**UI hint**: yes

---

## ✅ v3.1 Legal AI Arena (SHIPPED 2026-08-09)

**Milestone Goal:** 律师可在桌面 app 内创建法律任务，选择多个 ACP 后端 agent 并行处理，每个 agent 自评迭代到满意后交叉评审，最终由独立 session 综合评审意见产出最终版——全程流式可见、法律护栏不绕过。

**Source:** `.planning/REQUIREMENTS.md`（归档待 `/gsd-complete-milestone`）· **Research:** `.planning/research/SUMMARY.md`（已由 v4.0 取代，git 历史保留）

<details>
<summary>v3.1 Phase Details (105-111) — SHIPPED</summary>

### Phase 105: Arena Contract Extension ✅

- **Requirements**: CONTRACT-01..04 — Arena 生命周期事件词汇、数据类、Protocol、Schema 校验与可组合性测试。

### Phase 106: ACP fs Handler ✅

- **Requirements**: FS-01..04, SAFE-05, GATE-04 — fs/read_text_file 入站路由、五重路径沙箱、参考文件注入消毒、Gateway 向后兼容。

### Phase 107: Arena Engine — Modes 1+2 ✅

- **Requirements**: ENGINE-01, ENGINE-02, ENGINE-05..09, SAFE-01..04, SAFE-07 — 并行调度、自评迭代、编排器不产内容、护栏不可绕过、产物持久化、故障恢复、用户停止。

### Phase 108: Arena Engine — Modes 3+4 ✅

- **Requirements**: ENGINE-03, ENGINE-04, SAFE-06 — 交叉评审、对抗竞技、多轮综合、提前停止、跨族评审强制。

### Phase 109: Arena Service ✅

- **Requirements**: SVC-01..08, GATE-05, GATE-06 — 本地 HTTP+SSE 服务、多流复用、输出边界、权限安全、子进程受控、重连、错峰启动。

### Phase 110: Arena UI + Integration ✅

- **Requirements**: UI-01..07, GATE-01..03 — 桌面竞技 UI、多流解复用、状态持久化、gate 更新、端到端集成。

### Phase 111: v3.1 Closure ✅ COMPLETE

- **Requirements**: UI-01..07, GATE-01 (closure) — 桌面 arena 集成、Word 导出端点、FS handler 接线、BackendAdapter 测试回归修复（6 plans，completed 2026-08-09）。

</details>

---

## ✅ v3.0 Unified Legal Core (SHIPPED 2026-08-08)

**Milestone Goal:** 一套法律能力核心，通过同一套事件词汇同时服务所有客户端（web / 桌面 / 移动浏览器 / WeCom / QQ）和所有 agent 后端（Hermes / Codex / Claude Code / 墨律自研），并让 396 个真实法律 skill 首次进入平台。

**Source:** `docs/requirements/V3-PRD.md` · **Evidence:** `.planning/research/V3-SELECTION.md`

<details>
<summary>v3.0 Phase Details (88-104) — SHIPPED</summary>

### Phase 88: Unified Event Contract ✅

- **Requirements**: EVT-01..06 — 13-category unified event vocabulary, ACP-isomorphic, JSON Schema + Python + TypeScript bindings, bot degradation rules, V2 contract preserved.

### Phase 89: ACP Backend Client ✅

- **Requirements**: ACP-01, ACP-02, ACP-03, ACP-06 — Python ACP client driving hermes acp, second backend proof, subprocess lifecycle.

### Phase 90: ACP Event Bridge & Output Boundary ✅

- **Requirements**: ACP-04, ACP-05, ACP-07, SAFE-02, SAFE-03 — Bidirectional ACP↔unified event mapping, output boundary enforced, permission safety defaults.

### Phase 91: Unified Gateway ✅

- **Requirements**: GW-01..06 — Single multi-tenant HTTP+SSE Gateway replacing platform_api + lawyer-web-chat.

### Phase 92: Shared UI Core ✅

- **Requirements**: UI-01, UI-02, UI-03, UI-06 — @inkstatute/ui-core extracted from lawyer-desktop, 23 components, 3 themes, single chat UI implementation.

### Phase 93: Web Client ✅

- **Requirements**: UI-04 — Responsive web client (desktop + mobile browser), full task flow via Gateway.

### Phase 94: Desktop Client ✅

- **Requirements**: UI-05 — Tauri desktop shell reusing ui-core, invoke()→Gateway, offline read-only.

### Phase 95: Bot Channel Degradation ✅

- **Requirements**: BOT-01, BOT-02, BOT-03 — WeCom/QQ as Gateway consumers with non-streaming degradation.

### Phase 96: Real Skill Index ✅

- **Requirements**: SKILL-01..04, SAFE-05 — 396 real legal SKILL.md indexed, read-only, dual-repo merge.

### Phase 97: Skill Materialization ✅

- **Requirements**: SKILL-05, SKILL-06, SKILL-09 — Per-backend materialization, three-way separation, manifest cleanup.

### Phase 98: Real-Index Routing ✅

- **Requirements**: SKILL-07, SKILL-08 — Routing on real skill index, strong-signal rules ported, three-mode detection.

### Phase 99: Practice Profile ✅

- **Requirements**: PROF-01, PROF-02, PROF-03 — CLAUDE.md practice profile multi-tenantized, cold-start interview.

### Phase 100: Agent Core Skeleton ✅

- **Requirements**: CORE-01, CORE-04, CORE-09 — Python async streaming turn loop, context budget, model layer.

### Phase 101: Agent Core Tools ✅

- **Requirements**: CORE-02, CORE-03 — Tool layer + Word-native track-changes docx (41,185 bytes ported).

### Phase 102: Legal Guardrail Port ✅

- **Requirements**: CORE-05..08, SAFE-01, SAFE-04 — Prompt assembly, tool_leak, citation audit, 4 guardrails ported from Rust.
- **Human gate**: HG-1 法律质量（carried to v4.0）

### Phase 103: Dual Entry Points ✅

- **Requirements**: CORE-10 — in-process BackendAdapter + `inkstatute-agent acp` CLI.

### Phase 104: Legacy Convergence ✅

- **Requirements**: CONV-01..05, SAFE-06 — ~10,483 lines retired, gate system updated (34 gates), composability preserved.

**Archive:** [v3.0-ROADMAP.md](milestones/v3.0-ROADMAP.md) | [v3.0-REQUIREMENTS.md](milestones/v3.0-REQUIREMENTS.md) | [v3.0-phases](milestones/v3.0-phases/)

</details>

---

## Progress

### v4.0 Flutter Native + DSH Engine

**Execution Order:** 112 → 113 → 116 → 117 → 119 → 120

**Parallelization opportunities** (for wave-based execution):

- After 113: Phase 114 (skill pipeline) and Phase 115 (auto-update, after 114) run parallel to 116/117
- After 113: Phase 118 (docx) runs parallel to 116/117
- After 115 + 116 + 117 + 118: Phase 119 integrates packaging
- After 119: Phase 120 closes with human gates

| Phase | Stage | Plans Complete | Status | Completed |
|-------|-------|----------------|--------|-----------|
| 112. DSH Engine Integration (ACP over stdio) | A | 0/6 | Planned | — |
| 113. Legal Presets & Domain Presets | B | 0 | Not started | — |
| 114. Skill Pipeline — dsh Target | B | 0 | Not started | — |
| 115. Skill Content Auto-Update | B | 0 | Not started | — |
| 116. Chat UI & Output Boundary | C | 0 | Not started | — |
| 117. Legal Guardrails | C | 0 | Not started | — |
| 118. Word Track-Changes Export | C | 0 | Not started | — |
| 119. First-Run Wizard & Windows Packaging | D | 0 | Not started | — |
| 120. Convergence & Lawyer Trial | D | 0 | Not started | — |

### v3.1 Legal AI Arena — COMPLETE (SHIPPED 2026-08-09)

| Phase | Stage | Plans Complete | Status | Completed |
|-------|-------|----------------|--------|-----------|
| 105. Arena Contract Extension | A | 4/4 | Complete | 2026-08-08 |
| 106. ACP fs Handler | B | 3/3 | Complete | 2026-08-08 |
| 107. Arena Engine — Modes 1+2 | C | 6/6 | Complete | 2026-08-08 |
| 108. Arena Engine — Modes 3+4 | D | 4/4 | Complete | 2026-08-08 |
| 109. Arena Service | E | 6/6 | Complete | 2026-08-08 |
| 110. Arena UI + Integration | F | 5/5 | Complete | 2026-08-09 |
| 111. v3.1 Closure | G | 6/6 | Complete | 2026-08-09 |

### v3.0 Unified Legal Core — COMPLETE

| Phase | Stage | Plans Complete | Status | Completed |
|-------|-------|----------------|--------|-----------|
| 88. Unified Event Contract | A | 6/6 | Complete | 2026-08-07 |
| 89. ACP Backend Client | A | 3/3 | Complete | 2026-08-07 |
| 90. ACP Event Bridge & Output Boundary | A | 4/4 | Complete | 2026-08-07 |
| 91. Unified Gateway | B | 5/5 | Complete | 2026-08-08 |
| 92. Shared UI Core | B | 4/4 | Complete | 2026-08-08 |
| 93. Web Client | B | 4/4 | Complete | 2026-08-08 |
| 94. Desktop Client | B | 4/4 | Complete | 2026-08-09 |
| 95. Bot Channel Degradation | B | 4/4 | Complete | 2026-08-09 |
| 96. Real Skill Index | C | 4/4 | Complete | 2026-08-09 |
| 97. Skill Materialization | C | 4/4 | Complete | 2026-08-10 |
| 98. Real-Index Routing | C | 3/3 | Complete | 2026-08-10 |
| 99. Practice Profile | C | 3/3 | Complete | 2026-08-10 |
| 100. Agent Core Skeleton | D | 4/4 | Complete | 2026-08-11 |
| 101. Agent Core Tools | D | 4/4 | Complete | 2026-08-11 |
| 102. Legal Guardrail Port | D | 5/5 | Complete | 2026-08-08 |
| 103. Dual Entry Points | D | 3/3 | Complete | 2026-08-08 |
| 104. Legacy Convergence | D | 4/4 | Complete | 2026-08-08 |
