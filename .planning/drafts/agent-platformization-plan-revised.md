# Agent Platformization Plan (Revised)

> 范围：从 V2 现状过渡到「平台 + 解决方案包」形态的下一里程碑规划。本计划复审并替换上一版架构重构草案，编号沿用 V2 GSD 体系（Phase 09–13 / M0–M4 对外标识）。

---

## 1. 复审结论（对原草案的明确修正）

原草案在抽象层、契约扩展和阶段目标上方向正确，但以下问题必须在本里程碑解决，否则会让「平台化」变成重新命名而不是真的解耦。

### 1.1 必须修正的事实性错误

1. **Hermes 端点真实情况**（已通过源码核对 `gateway/platforms/api_server.py`）：
   - `/v1/runs`、`/v1/runs/{id}/events`、`/v1/runs/{id}/approval`、`/v1/runs/{id}/stop` 已存在；
   - `/v1/responses` 已存在（OpenAI Responses 风格，stateful via `previous_response_id`）；
   - `/v1/chat/completions` 已存在，但本身**仍是 opt-in session via header**，默认无状态；
   - 没有 `/v1/runs` 之外真正「异步、独立 cancel/approval」的更高层抽象，原草案描述准确，但应明确 `/v1/runs` 才是唯一与平台 AsyncTaskState 对得上的源。
2. **V2 现状并非「Plan Mode 阻止落地」**：`.planning/`、`packages/platform-contract/`、`packages/contract-test-suite/`、`services/hermes-contract-layer/`、`services/wecom-service/`、`services/feedback-service/`、`services/conversation-read-view/`、`scripts/run_v2_gates.py`、`scripts/inkstatute_wecom_live_bridge.py` 全部存在；`Phase 1–7` 完成，`Phase 8` = `human_needed`（08-04 已部署，等待 live UAT）。
3. **现行 WeCom 服务并非「最小可用」**：08-04 已经实现 `task_flow`、`active_task_router`、`delivery_guard`、`runtime_audit`、`output_policy`、`agent_backend`、`sender`、`normalization`、`idempotency`、`owned_notices`。原草案把它定位为「纯通道薄壳」是失实的。

### 1.2 原草案隐藏的债务

- 把「方案包」当作一等公民时，`lawfirm` 解决方案包与 `REQ-agent-backend-adapter-contract` 的 `mode=hermes` 描述边界不清——同一组事实既是解决方案配置又是后端模式，命名重叠会污染 ContractTestSuite 的非法律组合测试。
- 12 个主题的「共识日志」是「Codex fallback」，不是真实多人决策记录。原草案把这条写进 ADR 等价物，等于在没有锁的前提下把观点沉淀为结论。修订版只承认其作为「讨论证据包」，不作为锁定决策。
- TypeScript 在 M2 进入的范围（公共 API facade、生成 SDK、Web/Admin、客户端）会触发新一轮身份/会话/隐私契约。原草案把它描述为「API 表面变化」，但没说清楚契约扩展会不会反过来影响 Phase 8 trial acceptance 数据收集。
- 原草案没有把 `audit-trail` 与 `runtime_audit` 区分开：`runtime_audit.py`（08-04 现存）只审计运行时是否送出了错误 `completed`；真正的「blocked/rewritten output-policy audit」属于 `output_policy` 的 M0 验收。
- 「方案包私有」与「私有运行时审计」混在一起：原草案说「runtime audit 留在仓库外」，但 `scripts/inkstatute_wecom_live_bridge.py` + `runtime_audit.py` 实际都在仓内可见（除原始 payload 不入库）。修订版对「仓库边界」给出明确清单。

### 1.3 保留并加重的正确决策

- V2 契约不破坏：保留 `AgentTurn / AgentResult / FeedbackEvent / ExecutionTrace / RouteDecision`。
- WeCom 服务不能回退到 Hermes gateway 路径——这是 Phase 5.5 已经落地的硬约束。
- 「方案包」是描述 `lawfirm` 怎么用平台的可移植制品，不是平台核心的代码耦合点。
- `M0` 必须先固化现网 WeCom 行为再做任何重构——不接受「重构打破线上」。

---

## 2. 新里程碑定位

### 2.1 一句话定义

把 V2 的「合同 + 单一后端 + 单通道适配」沉淀为「**多通道 / 多后端 / 多解决方案**的薄平台」，并把 `lawfirm` 重写为第一个**解决方案包**，平台核心从此与具体后端、具体业务解耦。

### 2.2 与 V2 的边界

- 平台核心**不再**包含 `lawfirm` 任何字段；
- 平台核心**不再**包含 Hermes 任何具体路径、profile 结构、hook 名；
- 平台核心**只**暴露通道、后端、存储、策略、观测、solution-package 加载六类接口；
- V2 契约仍然向下兼容：所有新契约以「附加」方式进入，不修改既有 JSON Schema。

### 2.3 不在本里程碑

- Web/Tauri/Electron/Flutter 客户端 UI 实现——只暴露 SDK / API。
- 完整 Multi-Agent Runtime（独立 runtime），仅以适配器协议形态存在。
- 完整安全平台（加密、租户隔离、RBAC、WORM、密钥轮换）。
- 自动法律技能合成或对高风险法律结论的自动改写（既有约束保持）。

---

## 3. 平台核心结构（修订版六大块）

| 模块 | 职责 | 不负责 |
|------|------|--------|
| Contracts | JSON Schema + Python / TS 类型 + 事件关系图 | 业务字段、解决方案配置 |
| Channel adapters | 协议归一化（WeCom / QQBot / WeChat / Feishu / Web API / Webhook / WebSocket / SSE） | 业务语义、Agent 推理 |
| Agent backend adapters | `submit_run / get_run / stream_events / cancel_run / submit_approval` + 工具/工件/会话能力声明 | 通道 IO、合规改写 |
| Solution package loader | 加载 `lawfirm` 等方案包：prompts / skills / MCP refs / output policy / eval fixtures / bootstrap manifest / 后端适配器配置 | 实际部署、外部副作用 |
| Storage / Read models | 契约日志 + 只读视图（沿用 V2 read APIs） | 写权威业务库 |
| Observability / Privacy / Audit | 运行时审计、blocked/rewritten 留痕、关系完整性、覆盖率 | 业务分析 |

**Hermes 在本里程碑里被降级为「一个后端适配器 + 一个兼容 SDK 路径」，不再特殊。**

---

## 4. 新契约（仅追加、不破坏）

保留：`AgentTurn`、`AgentResult`、`FeedbackEvent`、`ExecutionTrace`、`RouteDecision`、`AgentAdapterManifest`。

新增（JSON Schema 增量；TypeScript 由生成器产出）：

- `ChannelMessage` / `ChannelDelivery`：通道归一化输入与发送回执；
- `Run` / `RunEvent` / `RunStep`：`/v1/runs` 形状的平台表示；
- `ToolCall` / `Approval` / `Artifact`：工具调用、审批、工件引用；
- `Session` / `Tenant` / `Workspace`：多租户与会话（与 Hermes session 解耦）；
- `SolutionPackage` / `SolutionPackageManifest`：方案包描述；
- `BotInstance` / `ChannelBinding`：机器人实例与通道绑定（注入 secret）。

每个新契约遵守 V2 既有约束：
- 行业特定字段只能在 `industry_context` 或方案包 `metadata` 中；
- 所有敏感字段继续 `raw_payload_ref` 化；
- 顶层禁止 `lawfirm` / `Hermes` / `WeCom` 等专有命名。

---

## 5. Hermes 适配策略（修订）

把 Hermes 当成与「Codex / provider-model」并列的普通后端，不再保留任何特殊代码路径。

- **能力探测先行**：在 `agent_backend` 加载阶段，发起一次只读 `GET /v1/runs/{id}` 与 `OPTIONS`-式探测，返回能力清单 `submit_run / get_run / stream_events / cancel_run / submit_approval / artifact_refs / session_memory / parallel_tasks`。
- **首选 `/v1/runs`**：异步任务、取消、审批、SSE 事件都来自这条路径；明确这就是与平台 `Run` / `RunEvent` / `AsyncTaskState` 对得上的唯一 Hermes 入口。
- **`/v1/responses`**：保留作为兼容客户端（Open WebUI 等）的入口；不作为主要 run 路径。
- **`/v1/chat/completions`**：仅在 fallback 或简答场景使用；本身默认无状态，因此不能承担 `cancel_run / submit_approval` 等需要状态的能力。
- **subprocess oneshot（08-04 live bridge）**：在适配器未通过能力探测或平台要求最低可用语义时，作为**降级路径**保留；它的功能集必须被显式标注为「无 cancel / 无 update / 无并行」，任何控制平面话术不得越过这个集合。
- **Hermes 版本与 hook 兼容矩阵**：从原草案继承，但补充：探测结果与版本矩阵只要有一个失配，平台立刻切到 oneshot 并在审计日志中记录 `mode=hermes_oneshot_fallback, reason=...`。

---

## 6. 阶段路线（M0–M4 / Phase 09–13）

### M0 / Phase 09：固化现网 WeCom 行为（**禁止重构**）

- **唯一目标**：在原架构不动的状态下跑通 live UAT，完成 Phase 8 验收。
- 验收：fresh live UAT 通过——quick ACK、阶段化进度、明确 final/timeout/failure、不出现假 `completed`、无 Hermes 元信息泄漏、对运行中任务的追问有即时响应。
- 风险：重构破坏现网。缓解：本期**只读现有代码**，任何改动必须以新增文件落地、不改 `task_flow` / `delivery_guard` / `output_policy` 的现有签名。
- 测试：`python scripts/run_v2_gates.py --json-summary` + live UAT 清单。
- 隐私：runtime 审计保留在仓内可见（08-04），原始 payload 不入库；本里程碑起为后续 M1 准备 privacy scan baseline。
- 回滚：保留 08-04 live bridge + oneshot 路径；如有任何问题直接切回。
- **不做**：不引入新契约、不引入解决方案包加载器、不动 Hermes 适配。

### M1 / Phase 10：抽取平台边界（**docs + 新增包，不删旧**）

- 目标：在 `packages/platform-contract` 之上建立「平台核心」接口边界，**不**删除 V2 任何契约或服务代码。
- 验收：
  - 新增 `packages/platform-core/`（仅 contracts + 接口 + fixture）；
  - 既有 `ChannelMessage / ChannelDelivery / Run / RunEvent / RunStep / ToolCall / Approval / Artifact / Session / Tenant / Workspace / SolutionPackage / SolutionPackageManifest / BotInstance / ChannelBinding` 在 `platform-core` 以 JSON Schema + Python 类型落地；
  - `lawfirm` 作为方案包描述（manifest + prompts/profile + skills + MCP refs + output policy + eval fixtures + bootstrap），其仓库位置 `solutions/lawfirm/` 与平台核心物理隔离；
  - 顶层命名规则扫描：仓内 `platform-core/` 与 `services/*` 中不允许出现 `lawfirm` / `wecom` / `hermes` 等专有命名；违例列入 CI。
- 风险：过度建模。缓解：每个新契约必须有 ≥1 个非法律合成 fixture 通过 contract-test-suite。
- 测试：schema validation、非法律 fixture（金融 / 工程 / 教育）、专有命名扫描。
- 隐私：方案包 manifest 中只允许引用 secret 名，不允许存明文。
- 回滚：`packages/platform-contract/` 与 `services/*` 维持 V2 行为不变。

### M2 / Phase 11：正式 Run Runtime + 平台 API

- 目标：平台 Run API 暴露 `create / poll / stream / cancel / approval / artifact refs`；后端适配器协议 v1 发布。
- 验收：
  - `platform-core` 实现 `RunRuntime` 接口（Python 优先，TS 由生成器产出）；
  - Hermes 适配器实现 v1 并通过能力探测；探测失败时 fallback 到 oneshot 并记录原因；
  - `/v1/runs` 与 `/v1/runs/{id}/events` 路径在适配器与平台 API 之间有明确一一对应；
  - 公共 API facade 暴露 `POST /v1/platform/runs`、`GET /v1/platform/runs/{id}`、`GET /v1/platform/runs/{id}/events`；
  - 多租户 ID（`tenant_id` / `workspace_id` / `session_id`）在 Run 路径上全程存在；
- 风险：Hermes API 表面变化。缓解：能力探测矩阵 + 适配器契约测试 + API parity fixture。
- 测试：探测矩阵、适配器契约、parity fixture、auth 路径。
- 隐私：所有 Run 日志只存 `raw_payload_ref`，原始 payload 入私有存储；auth token 不入日志。
- 回滚：禁用 API-server lane，回退 oneshot。
- **TS 进入条件**：M2 末产出 generated SDK + 公共 API 的 OpenAPI；不再进入业务逻辑。

### M3 / Phase 12：多通道与客户端嵌入

- 目标：WeCom 仍是 first-class，但通道适配器变为「一个接口、多实现」。
- 验收：
  - WeCom 适配器作为既实现搬到 `platform-core/channels/wecom/`，与 V2 `services/wecom-service` 在同一接口下提供；
  - Web API / SSE 通道提供至少 1 个新通道适配器 fixture（不需要 production-grade，但需要 e2e 通过）；
  - 至少 1 个非 WeCom 通道（首选 Web API + SSE）通过 contract-test-suite；
  - 客户端（Web / Tauri / Electron / Flutter）只通过平台 API/SDK 接入；本地 runtime 仅在显式要求时启用；
- 风险：通道抽象泄漏协议细节。缓解：通道适配器禁止直接调用后端，只能通过 platform-core 暴露接口。
- 测试：每个通道必须具备「发送去重 / 反馈去重 / 幂等键」fixture。
- 隐私：channel secret 仅在 `ChannelBinding` 中按通道隔离；不得跨通道泄漏。
- 回滚：per-channel feature flags；任意通道失败不影响其它通道。

### M4 / Phase 13：多解决方案包

- 目标：把 `lawfirm` 沉淀为方案包范式，再造一个**非法律** demo 方案包验证平台不变。
- 验收：
  - `solutions/lawfirm/` 完整方案包（prompts / profile / skills / MCP refs / output policy / eval fixtures / bootstrap manifest / 后端适配器配置 / secrets template）；
  - `solutions/demo_non_legal/`（例如「内部研发助手」或「学生问答」）跑通 platform-core 而**不**触碰平台代码；
  - 方案包 manifest 元数据 schema 锁定；
  - solution-package privacy scan（bundle 内禁止：secret、log、DB、raw payload）；
  - 平台核心代码对比 M0 仍为「零新增法律字段」；
- 风险：方案包变成隐藏 fork。缓解：composability gate + boundary gate，方案包只允许通过 manifest + 资源文件影响平台，不得改平台代码。
- 测试：composability、boundary、privacy scan。
- 隐私：方案包 bundle 不含 secret / log / DB / 原始 payload；发布清单必须可审计。
- 回滚：把 `lawfirm` 标记为 compatibility-only，不阻塞后续方案包。

---

## 7. 测试与门禁

- 阶段前后都跑 `python scripts/run_v2_gates.py --json-summary`；
- 新增 contract test：所有新 schema 必跑；
- 新增 adapter 能力探测矩阵测试；
- 新增 channel normalization / delivery / idempotency fixture；
- 新增 run event replay、approval / cancel 路径测试；
- 新增 multi-tenant ID 一致性测试；
- 新增 solution-package privacy scan（拒绝 secret / log / DB / 原始 payload）；
- Phase 8 trial acceptance 的「live gates」继续保留：fixture 不能替代 live 验收。

---

## 8. 仓库与隐私边界（修订）

| 内容 | 仓库可见性 |
|------|------------|
| `packages/platform-contract/`（V2 契约） | 在仓 |
| `packages/platform-core/`（新增） | 在仓 |
| `services/wecom-service/`、`services/hermes-contract-layer/` 等运行时 | 在仓（但原始 payload 不入库） |
| `solutions/<name>/` 方案包（不含 secret） | 在仓 |
| `solutions/<name>/secrets.template` | 在仓（仅占位符） |
| runtime audit（blocked/rewritten 摘要） | 在仓 |
| 原始 WeCom payload、log、DB、用户文件、secret | **不入仓** |
| customer legal payloads、完整身份证号 / 手机号 / 银行号 | **不入仓**，只 `raw_payload_ref` |
| Phase 8 trial evidence（运行数据） | 仅 trial evidence template 在仓；真实 metric 由律师人工汇总 |

---

## 9. 决策记录（替代原 12 主题「共识日志」）

- 原草案里所谓的「Codex 12-topic fallback consensus」**不作为锁定决策**，仅作讨论证据包保留为 `docs/architecture/agent-platform-consensus-log-draft.md`。
- 本计划实际锁定以下决策（须在 ADR 文件中以 ADR-0001 等独立归档）：
  1. V2 契约不破坏，新增走附加 schema；
  2. 平台核心只含 contracts / channel adapters / backend adapters / solution loader / storage-read / observability-privacy-audit 六块；
  3. Hermes 是后端适配器之一，不再特殊；`/v1/runs` 是与平台 Run 对得上的唯一 Hermes 路径；
  4. `lawfirm` 迁移为方案包，平台代码不再出现 `lawfirm` 字段；
  5. 隐私边界以「原始 payload 不入库」为硬约束，runtime audit 与 blocked/rewritten 留痕保留；
  6. TypeScript 仅作为 SDK / OpenAPI 生成器进入业务逻辑。

---

## 10. 风险与回滚一览

| 风险 | 触发条件 | 回滚动作 |
|------|----------|----------|
| M0 重构破坏现网 | live UAT 出现 Phase 8 已有指标回退 | 立刻冻结 M1，重启 08-04 live bridge |
| Hermes API 表面变化 | 能力探测失败或 `/v1/runs` 行为变化 | 切 oneshot fallback，记录 reason |
| 方案包变成隐藏 fork | boundary gate / privacy scan 失败 | 把方案包降级为 compatibility-only |
| TS 进入影响数据收集 | M2 末 SDK 生成结果与契约不一致 | 阻断 M3，回退到 Python-only |
| 多租户隔离穿透 | tenant / workspace ID 一致性测试失败 | 禁用 API-server lane |
| 通道抽象泄漏 | 通道适配器直接访问后端 | per-channel feature flag 关闭该通道 |

---

## 11. 假设与先决条件

- 用户仍接受 V2 阶段延续的 GSD 编号，因此沿用 Phase 09–13 / M0–M4 双编号；
- 平台化为 docs-only milestone（M0 阶段除外）：M1 不修改运行时，只新增包与 manifest；
- `lawfirm` 方案包所需 prompts / skills / MCP refs 来自 V2 既有产物，不要求外部输入；
- Hermes 在本里程碑期间保持可用，且 `/v1/runs` 路径不被 Hermes 端破坏；
- TypeScript 引入仅限 SDK / OpenAPI / 公共 API facade，不涉及任何 V2 现有 Python 服务代码改动。

---

## 12. 与原草案逐条对照（修订摘要）

| 原草案条目 | 修订结论 |
|------------|----------|
| 「Plan Mode 阻止落地」 | 错误：V2 已落地，本里程碑是 docs + 新增包 |
| 「12-topic Codex consensus」 | 不作为锁定决策，改为 ADR 单独归档 |
| 「M0 重新稳定现网 WeCom」 | 接受，但严格禁止重构，仅 live UAT |
| 「TypeScript M2 进入业务」 | 修订：仅 SDK / OpenAPI / 公共 API facade |
| 「Hermes 端点描述」 | 准确，补充 `/v1/chat/completions` 默认无状态与 `/v1/runs` 的唯一 run 地位 |
| 「lawfirm 是方案包」 | 接受，但要求平台代码零新增法律字段、专有命名扫描 |
| 「runtime audit 留仓库外」 | 修订：审计摘要留仓，原始 payload 与 secret 留仓外 |
| 「通道抽象包含 WeChat / Feishu」 | 修订：M3 不要求生产落地 Feishu / WeChat，仅要求 fixture 与接口稳定 |

---

*本计划为 GSD 下一里程碑的 docs-only 草案；Phase 09 进入前需在仓外 review，确认后再以 ADR + Phase 计划文件落地。*