# Phase 123: Engine Supervisor & Real Path - Context

**Gathered:** 2026-08-15
**Status:** Ready for execution
**Requirements:** RTM-01, RTM-02, RTM-06, RTM-07
**Depends on:** Phase 122 全部验收门通过

<domain>
## Phase Boundary

把「一个能装配的引擎目录」变成「一个 app 能驱动的真实引擎」：子进程生命周期、ACP 控制面、凭据注入、对话续接。

**本阶段不做**：不读会话日志（Phase 124）、不接前端（Phase 125）。
本阶段的验收通过 Rust 集成测试完成，不需要 UI。

**本阶段是方案风险闸口。** RTM-07（对话续接回灌）必须用**真实 API key** 实测。
若回灌体验不可接受，触发架构回退评审（备选：引擎常驻方案），**不得在证据不足时进入 Phase 124**。
</domain>

<decisions>
## Implementation Decisions

### 会话模型（V5 定案，不再讨论）

- **一个 app 运行期 = 一个 DSH 引擎子进程**，不是 per-conversation 进程。
  实测依据：一条 ACP 连接可拥有多个会话，各自独立的 prompt 槽、工作区、取消路径与日志目录；
  对其中两个并发 `session/prompt`，各自独立结算。
- **一个对话 = 一个 ACP 会话**，首次发消息时惰性创建，在 app 运行期内保持打开。
- **跨 app 重启的续接 = 回灌**。ACP 明确「Fresh sessions only」，无 load/list/resume/fork。

### ACP 调用形式（实测，务必照做）

| 方法 | JSON-RPC 形式 | 关键约束 |
|---|---|---|
| `initialize` | 请求 | `protocolVersion: 1` |
| `session/new` | 请求 | `cwd` **必须绝对路径**；`mcpServers: []`（非空即拒） |
| `session/prompt` | 请求 | 每会话**单 in-flight**；返回 `{stopReason}` |
| `session/cancel` | **通知（无 `id` 字段）** | **按请求发（带 id）返回 `Method not found` 而静默失败** |
| `session/request_permission` | 服务端→客户端**请求** | 需应答，否则引擎侧挂起 |

### 否决方案（不要重新评估）

- **否决引擎常驻**（跨 app 关闭存活）：破坏零孤儿进程保证，且引擎升级时进程冲突难处理。
- **否决 SDK JSON-RPC 缝**：无权限通道、无取消、无版本协商。

### 硬约束

- **密钥零明文进入 JSON / 日志 / 遥测 / 进程命令行参数。** 只经环境变量注入子进程。
- 进程退出路径必须做零孤儿断言。Windows 用 `tasklist /FI "PID eq <pid>" /FO CSV /NH`
  （**不得用 `output.contains(pid)` 裸匹配**——死 PID `123` 会误匹配活 PID `1234`）。
- 不得修改 `apps/flutter_app/`（冻结，只读参照）。
</decisions>

<code_context>
## 移植参照（只读，不修改）

`apps/flutter_app/lib/engine/dsh_process.dart` 已把生命周期逻辑写得很完整，Rust 侧按其**行为**移植：

- `spawn`：`Process.start` + 环境注入 + stderr 行收集（reference-first，不回显 UI）
- `healthProbe`：`initialize` 握手，断言 `protocolVersion == 1`
- `shutdown`：关 stdin → 等退出（10s）→ 超时 SIGTERM → 再超时（5s）SIGKILL
- `assertNoOrphans`：Windows `tasklist /FI "PID eq <pid>" /FO CSV /NH` 过滤 `INFO:` 行后判空

`apps/flutter_app/lib/security/credential_store.dart` 与 `lib/security/engine_env.dart` 是凭据注入参照。

## 新增文件

```
apps/desktop/src-tauri/src/engine/
    supervisor.rs   # 子进程生命周期（RTM-01）
    acp.rs          # ACP 控制面客户端（RTM-02）
    credentials.rs  # OS 凭据库 + 环境注入（RTM-06）
    replay.rs       # 对话续接回灌（RTM-07）
```

## Cargo 依赖新增

```toml
keyring = "3"                    # OS 凭据库（Windows Credential Manager）
tokio-util = { version = "0.7", features = ["codec"] }
```

## 供应商 → 环境变量映射（与 acp.cordis.yml 的 apiKeyEnv 一致）

| 供应商 id | 环境变量 |
|---|---|
| `deepseek` | `DEEPSEEK_API_KEY` |
| `openai` | `OPENAI_API_KEY` |
| `anthropic` | `ANTHROPIC_API_KEY` |
| `google` | `GOOGLE_API_KEY` |
| `groq` | `GROQ_API_KEY` |
| `xai` | `XAI_API_KEY` |
| `zhipu` | `ZHIPU_API_KEY` |
| `qwen` | `QWEN_API_KEY` |
| `custom` | `CUSTOM_API_KEY` |
</code_context>

<research>
## RTM-07 回灌的量化依据

实测 `request/context` 事件：

```json
{"type":"request/context","seq":9,"data":{"provider":"deepseek-official","model":"deepseek-v4-pro","contextWindow":1000000}}
```

1M 上下文 → 一段法律对话转录（数万 token）仅占数个百分点。
溢出由 `dsh-compaction-basic`（`thresholdRatio: 0.8`）自动处理。

回灌格式建议（首轮提示的前缀，模型侧可见）：

```
[以下是本次对话此前的往来记录，供你恢复上下文。请勿重复回答其中已回答的问题。]

【第 1 轮 · 用户】…
【第 1 轮 · 助手】…
…
[记录结束。以下是用户的新问题。]

<用户本次输入>
```

超过轮数上限时，从最近往前保留，并在开头注明 `[更早的 N 轮记录已省略]`。
</research>

<risks>
## Risks

| # | 风险 | 缓解 | 触发后动作 |
|---|---|---|---|
| 1 | **回灌体验不可接受**（首轮延迟过高 / 模型混淆历史与新问题） | 轮数上限可配；前缀措辞明确划界 | **触发架构回退评审**，评估引擎常驻方案。记入 `123-DECISION.md` |
| 2 | `session/cancel` 写成请求 → 静默失败 | 代码注释 + 单元测试断言发出的帧无 `id` 字段 | — |
| 3 | 权限请求未应答导致引擎挂起 | 应答超时兜底：超时未决则发 `reject-once` | — |
| 4 | Windows 上 kill 后子孙进程残留 | `assertNoOrphans` + 冒烟阶段检查 | — |
| 5 | 密钥出现在 crash dump / 进程列表 | 只经环境变量，不经命令行参数；错误路径不打印 env | — |
</risks>
