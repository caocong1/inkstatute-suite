# Requirements: 墨律 InkStatute — v5.0 Tauri Shell + DSH Three-Plane Integration

**Defined:** 2026-08-15
**Core Value:** 一名零技术操作的律师在 Windows 桌面上双击即用：Tauri + SolidJS app 经 ACP over stdio 驱动本地嵌入的 DSH 引擎，工具调用与思考过程可见，分域法律技能随内容包自动更新，四条法律护栏与人审标记不可绕过，引擎半自动更新且失败自动回滚。

**Predecessor:** v4.0 Flutter Native + DSH Engine（开发侧技术闭环 2026-08-15；产品层被 V5 推翻，`apps/flutter_app` 冻结不删）

## v5.0 Requirements

规格真源：`docs/requirements/V5-PRD.md`；选型证据：`.planning/research/V5-SELECTION.md`（11 项本机实测）。
Traceability 见文末。**每条需求恰好映射一个 roadmap phase（122–127）。**

### ENG — 引擎装配与更新

- [ ] **ENG-01**: 引擎 pin 从 git commit 改为 npm 精确版本——`engines/dsh-pin.txt` 记录 `dsh_version=0.1.0-rc.6` + 15 个组合包清单 + `node_version`；**禁止使用 dist-tag**（`latest` 指向旧版 `0.0.1-rc.1`）；退役 `scripts/build_dsh_release.sh` 的 pnpm-deploy 符号链接手术
- [ ] **ENG-02**: `engine-lock.json` 生成脚本——从 pin 文件执行 `npm install` 产出 lockfile v3，裁剪 `node-pty/prebuilds` 非目标平台目录，附加 `engine_version` / `compatible_app_range` / `cordis_config_sha256` 字段；产物约 40KB，是引擎更新的唯一分发单元
- [ ] **ENG-03**: Rust 侧 lockfile 装配器——按 lockfile `packages` 路径逐包下载 tarball、校验 sha512 `integrity`、解包铺平到目标目录（实测树全平、零嵌套 `node_modules`）；registry 基址可配（默认 `registry.npmmirror.com`，回退 `registry.npmjs.org`）；**运行时不依赖 npm**
- [ ] **ENG-04**: ACP 组合配置修正——`persistenceRoot` 改为 `!!js process.env.DSH_HOME + '/sessions'`（`${DSH_HOME}` 不被 Cordis 展开，V4 缺陷 D1）；新增 `packChunks: false` + `persistenceCompression: none`（观测面前提）；供应商块改用 `@deepseek-ai/dsh-llm-pi-ai`，`apiKeyEnv` 为凭据引用
- [ ] **ENG-05**: 引擎半自动更新器——七步流程（取版本 → 兼容闸 → 下载校验 → 铺树 → **冒烟** → 指针切换 → 回滚）；版本目录 `engine\<version>\` + 单行指针 `engine\current`；**冒烟通过前指针一次都不动**；旧版本保留一代

### RTM — Rust 引擎主管（三面接入）

- [ ] **RTM-01**: DSH 子进程生命周期——从 `engine\current` 指向的目录 spawn `node.exe`；`DSH_HOME` 指向 `%LOCALAPPDATA%\InkStatute\runtime\.dsh`；`initialize` 握手健康探针；stdin 关闭 → 等待退出 → 超时 SIGTERM → 再超时 SIGKILL；**零孤儿进程断言**（Windows 用 `tasklist /FI "PID eq <pid>" /FO CSV /NH`）
- [ ] **RTM-02**: 控制面 ACP 客户端——NDJSON JSON-RPC 帧收发；`initialize` / `session/new`（绝对 cwd，`mcpServers: []`）/ `session/prompt`（每会话单 in-flight）/ **`session/cancel` 必须作为通知发送（无 `id`，按请求发返回 Method not found）** / `session/request_permission` 应答；**一个 app 运行期一个引擎进程、一个对话一个 ACP 会话**
- [ ] **RTM-03**: 观测面日志尾随器——尾随 `<persistenceRoot>/--<规范化 cwd>--/<sessionId>/session.jsonl`（明文 NDJSON，`seq` 连续）；解析 14 种事件类型与 7 种 chunk 类型；断行/半行安全（只处理完整行）；文件轮转与首次创建延迟容错
- [ ] **RTM-04**: 历史面只读查询——`<persistenceRoot>/session-query.db` 以只读模式打开；`persisted_sessions` 供会话列表，`persisted_docs`（FTS5 unicode61）供全文搜索；**app 侧永不写入该库**
- [ ] **RTM-05**: 事件映射器——DSH 会话事件 → `RunEventEnvelope`（15 种统一 `event_type`，见 V5-PRD §5）；`seq` 单调递增；经 Tauri event channel 推送前端；已提交文本经 ACP 与日志双通道到达时以日志为准、ACP 为校验
- [ ] **RTM-06**: 凭据与供应商——密钥存 OS 凭据库（Windows Credential Manager）；spawn 时按当前供应商注入对应环境变量（`DEEPSEEK_API_KEY` / `OPENAI_API_KEY` / …）；**密钥零明文进入 JSON / 日志 / 遥测 / 进程参数**
- [ ] **RTM-07**: 对话续接（回灌）——重开旧对话时创建新 ACP 会话，把此前成稿往来作为首轮提示的上下文前缀回灌；轮数上限可配（默认 20），超出从最近往前截断并注明省略；依据实测 `contextWindow: 1000000`

### UIW — 前端接线

- [ ] **UIW-01**: Tauri 事件传输层——`apps/desktop/src/hooks/useEventStream.ts` 从 Gateway SSE 改为 Tauri `listen()` 订阅；**`packages/ui-core/src/event-reducer.ts` 与全部 ui-core 组件零改动**
- [ ] **UIW-02**: V3 平台耦合裁剪——移除 `config/gateway.ts` · `config/arena.ts` · `contexts/AuthContext.tsx` · `contexts/ConnectionContext.tsx` · `pages/ArenaPage.tsx` · `lib/upload.ts` · `lib/runBuilder.ts` · `commands/offline_cache.rs`；`packages/platform-sdk-ts` 只保留 `src/events.ts`
- [ ] **UIW-03**: ui-core Arena 组件裁剪——移除 `ArenaWorkflowCreator` · `ParallelStreamPanel` · `ScoreCard` · `SynthesisViewer` · `ReviewSummary` · `reducers/arenaEventReducer.ts` · `stores/arenaStream.ts` · `types/arena.ts` 及其测试；`src/index.ts` 同步收敛导出
- [ ] **UIW-04**: 设置面板移植——从 `lawyer-desktop/src/components/settings/SettingsPanel.tsx`（963 行）移植，砍掉 sync / skillopt 页签，保留 LLM 供应商 / 技能 / 文件 / 关于；接 `RTM-06` 凭据命令
- [ ] **UIW-05**: 工作区外壳——移植 `lawyer-desktop` 的 `Workspace.tsx`（左右分栏可调宽度）+ `App.tsx` 路由 + `index.css`；`ConversationDrawer` 数据源改为 `RTM-04` 历史面

### GRD — 法律护栏（沿用 v4.0 GRD-01..06，呈现层重做）

- [ ] **GRD-11**: research-gate 可核验化——工具时间线直接显示检索工具是否被调用；无 verified 引用时结论区渲染「待核实」标记
- [ ] **GRD-12**: citation audit——引用标注 verified / retrieved / unverified 三类徽记，unverified 视觉警示；复用 `ui-core/src/utils/citationAudit.ts`
- [ ] **GRD-13**: ask-user 强制——模型输出 `[CLARIFY: …]` 块 → 映射为 `elicitation.requested` → 渲染 `ClarificationCard`；未澄清任务锁定
- [ ] **GRD-14**: de-AI polish + human review——终稿过润色段；`[HUMAN_REVIEW: …]` 徽记不可自动消除；批准栈无任何放行路径
- [ ] **GRD-15**: 批准卡片——`session/request_permission` → `permission.requested` → 用户卡片 allow-once / reject-once；**无批量批准入口**；未知 kind 一律拒绝
- [ ] **GRD-16**: 输出边界与保密——只渲染已提交 assistant 文本，DSH meta/system 噪声永不出现；错误映射用户可读（引擎未启动/限流/鉴权/超时）；原始堆栈只进本地日志；上传前脱敏提醒

### SKL — 技能与内容包（沿用 v4.0 管线）

- [ ] **SKL-11**: 分域预设挂载——`presets/<domain>/` 物化到 `runtime\.dsh\.agent-presets\`；`skills.filesystem.customSkillDirs` 指向内容包分域目录；LLM 自动判断法律领域，用户不选执业方向
- [ ] **SKL-12**: 内容包自动更新——沿用 V4 `content-manifest.json` + sha256 + 原子切换 + 回滚；**兼容性判据从字符串相等改为 semver 范围比较**（DSH 已启用 semver）
- [ ] **SKL-13**: token 预算门禁——核心集目录渲染（name+description）长度 ≤ 预算（默认 8,000 字符）；超预算回归测试红灯、拒绝发货

### PKG — 打包交付

- [ ] **PKG-11**: 便携 Node 运行时——随包带 `node.exe`（官方 win-x64，v24 LTS）；引擎 spawn 用绝对路径，**禁止依赖系统 Node**（V4 缺陷 D3）
- [ ] **PKG-12**: 字体本地化——移除 `ui-core/src/themes/molv-tokens.css` 的 Google Fonts `@import`（中国大陆不可达，V4 缺陷 D2）；字体子集随包分发或降级到系统 CJK 字体栈
- [ ] **PKG-13**: Windows 单 exe 安装包——Tauri build + `node.exe` + 引擎基线树 + 内容包基线 + 预设；装到 `%LOCALAPPDATA%\InkStatute`；快捷方式；零命令行
- [ ] **PKG-14**: 首启向导——供应商卡片 → 密钥（存 OS 凭据库）→ 模型确认；之后零终端零配置文件
- [ ] **PKG-15**: App 层更新器——`tauri-plugin-updater`，替换 lawyer-desktop 遗留的占位公钥 `dW5zZXQtcmVwbGFjZS13aXRoLXNpZ25lci1wdWJrZXk=` 为真实签名公钥

### GATE — 门禁

- [ ] **GATE-11**: 引擎装配门禁——从空目录出发，Rust 装配器铺出的引擎完成 `initialize` → `session/new`；会话日志落在 `DSH_HOME` 下且为明文 NDJSON；密钥零明文残留（grep 断言）
- [ ] **GATE-12**: 事件映射门禁——用真实录制的 `session.jsonl` 作 fixture 喂进 `event-reducer.ts`，断言 `RenderState` 正确；流式正文 / 工具时间线 / 进度步骤三者同时正常
- [ ] **GATE-13**: 更新回滚门禁——故意投一个坏包（sha512 不符 / 冒烟失败），断言 `current` 指针未移动、旧引擎仍可用、用户无感

## Non-Goals（v5.0 明确不做）

- Word 原生修订导出（V4 APP-04）、便携 Python、track-changes 脚本、`docx-rs`、`pdf-extract`
- 内嵌文档编辑（DocPreview 只读）
- Gateway / WeCom / QQ / Arena / 管理台 / 多租户 / 远程引擎
- 自研 agent loop 的任何投入
- 移动端
- 复活 `apps/flutter_app`（冻结保留作 Rust 侧移植参照，不删除、不投入）

## Traceability

| Requirement | Phase | Status |
|---|---|---|
| ENG-01 | 122 | Pending |
| ENG-02 | 122 | Pending |
| ENG-03 | 122 | Pending |
| ENG-04 | 122 | Pending |
| GATE-11 | 122 | Pending |
| RTM-01 | 123 | Pending |
| RTM-02 | 123 | Pending |
| RTM-06 | 123 | Pending |
| RTM-07 | 123 | Pending |
| RTM-03 | 124 | Pending |
| RTM-04 | 124 | Pending |
| RTM-05 | 124 | Pending |
| GATE-12 | 124 | Pending |
| UIW-01 | 125 | Pending |
| UIW-02 | 125 | Pending |
| UIW-03 | 125 | Pending |
| UIW-04 | 125 | Pending |
| UIW-05 | 125 | Pending |
| GRD-11 | 126 | Pending |
| GRD-12 | 126 | Pending |
| GRD-13 | 126 | Pending |
| GRD-14 | 126 | Pending |
| GRD-15 | 126 | Pending |
| GRD-16 | 126 | Pending |
| SKL-11 | 126 | Pending |
| SKL-12 | 126 | Pending |
| SKL-13 | 126 | Pending |
| ENG-05 | 127 | Pending |
| PKG-11 | 127 | Pending |
| PKG-12 | 127 | Pending |
| PKG-13 | 127 | Pending |
| PKG-14 | 127 | Pending |
| PKG-15 | 127 | Pending |
| GATE-13 | 127 | Pending |

**Coverage:**

- v5.0 requirements: 34 total (5 ENG + 7 RTM + 5 UIW + 6 GRD + 3 SKL + 5 PKG + 3 GATE)
- Mapped to phases: 34 (100%)
- Unmapped: 0 ✅

**Phase distribution:**

| Phase | Requirements | Count |
|-------|-------------|-------|
| 122 引擎装配管线换血 | ENG-01..04, GATE-11 | 5 |
| 123 引擎主管与真实链路 | RTM-01, RTM-02, RTM-06, RTM-07 | 4 |
| 124 观测面·历史面·事件映射 | RTM-03..05, GATE-12 | 4 |
| 125 前端接线与裁剪 | UIW-01..05 | 5 |
| 126 护栏与技能能力层 | GRD-11..16, SKL-11..13 | 9 |
| 127 打包与三层更新 | ENG-05, PKG-11..15, GATE-13 | 7 |
| **Total** | | **34** |

**Distribution rationale:**

- **122 先行**：引擎装配是所有后续阶段的物理前提，且是最容易验证的一环（不需要 UI、不需要真 key）。
- **123 在动 UI 之前**：RTM-07（对话续接回灌）是唯一可能推翻方案的环节——若回灌体验不可接受，备选方案是更大的架构决定，越早知道越好。故要求本阶段用**真实 API key** 实测。
- **124 与 125 拆开**：124 交付「事件正确到达前端」（可用 fixture 验证，不依赖 UI），125 交付「UI 正确渲染」。拆开后 GATE-12 可在无 UI 状态下亮灯。
- **126 合并 GRD 与 SKL**：护栏的呈现依赖技能预设里的提示词段，两者同阶段落地才能双层同时验证。
- **127 收口**：引擎更新器（ENG-05）与打包同阶段，因为二者共享版本目录与指针机制。

---
*Requirements defined: 2026-08-15*
*Last updated: 2026-08-15 — v5.0 milestone opened, 0/34 complete*
