# Phase 124: Observation & History Planes - Context

**Gathered:** 2026-08-15
**Status:** Ready for execution
**Requirements:** RTM-03, RTM-04, RTM-05, GATE-12
**Depends on:** Phase 123 全部通过，且 `123-DECISION.md` 结论为「回灌方案验证通过」

<domain>
## Phase Boundary

补齐 ACP 丢掉的那些数据：工具调用、推理、流式增量、会话列表、全文搜索。
交付「事件正确到达前端」——**用 fixture 验证，不依赖 UI**。UI 渲染在 Phase 125。

**本阶段不做**：不改 `packages/ui-core` 任何文件、不动前端组件。
</domain>

<decisions>
## Implementation Decisions

### 三面分工（已定案）

| 面 | 数据源 | 用途 |
|---|---|---|
| 控制面（Phase 123 已做） | ACP stdout | prompt / cancel / permission |
| **观测面（本阶段）** | `session.jsonl` 明文 NDJSON | tool / reasoning / streaming / step |
| **历史面（本阶段）** | `session-query.db` SQLite 只读 | 会话列表 / 全文搜索 |

### 为什么不用 ACP 拿这些

ACP 源码显式丢弃：「Emit only committed assistant text. Raw chunks, reasoning, tools, plans, titles,
and retry markers are presentation or trace data and stay off the automation wire.」

### 为什么不自写 DSH 插件

官方持久化插件已经在写这些数据（Phase 122 已把配置改成明文 NDJSON），读文件即可。
自写插件会引入需随 DSH 版本维护的 TypeScript 资产。

### 双通道去重规则

已提交的 assistant 文本会经**两条**通道到达：ACP 的 `agent_message_chunk` 与日志的 `assistant/message`。
**以日志为准**（它带 `seq`，可排序、可去重），ACP 侧仅用于交叉校验与断连兜底。
</decisions>

<code_context>
## 日志路径推导（实测确认）

```
<sessionsRoot>/--<规范化 cwd>--/<sessionId>/session.jsonl
```

- `sessionsRoot` = `paths::sessions_root()` = `<dsh_home>/sessions`
- 规范化 cwd：路径分隔符替换为 `-`，首尾各加 `--`。
  实测样例：cwd `/private/tmp/.../scratchpad/ws2`
  → 目录名 `--private-tmp-claude-502--Users-dongli-...-scratchpad-ws2--`
- **规范化是有损的**（分隔符替换 + 长度截断），不同 cwd 可能落进同一项目目录，
  但 sessionId 子目录唯一。**因此定位日志必须用 sessionId 逐项匹配，不要反解 cwd。**

**稳妥做法**：在 `sessionsRoot` 下按 `*/{sessionId}/session.jsonl` 通配查找，
命中唯一即用；未命中则等待（惰性物化 —— `session/new` 后无 append 则不写文件）。

## 实测事件样本（一次失败轮次的完整 14 行）

```jsonc
{"type":"session","version":0,"id":"...","createdAt":1786767750643,"cwd":"/abs/ws","delegationDepth":0}
{"type":"agent/inbox/spliced","seq":0,"time":...,"data":{"target":"next-turn","inserted":[{...role:"user"}]}}
{"type":"turn/start","seq":1,"time":...,"data":{"turn":1}}
{"type":"agent/inbox/spliced","seq":2,...}
{"type":"step/start","seq":3,"time":...,"data":{"turn":1,"step":1}}
{"type":"user/message","seq":4,"time":...,"data":{"content":[{"type":"text","text":"..."}],"role":"user","id":"..."},"surfaceOp":"append"}
{"type":"user/message","seq":5,...}   // 运行时上下文快照（系统注入，不渲染）
{"type":"user/message","seq":6,...}   // 技能清单 system-reminder（系统注入，不渲染）
{"type":"session/title","seq":7,"time":...,"data":{"title":"...","messageSeqs":[4],"source":{"kind":"fallback"}}}
{"type":"request/header","seq":8,"time":...,"data":{"header":{"config":{"provider":"...","model":"...","maxTokens":256000,"reasoningEffort":"max"},"system":"..."}}}
{"type":"request/context","seq":9,"time":...,"data":{"provider":"...","model":"...","contextWindow":1000000}}
{"type":"assistant/chunk","seq":10,"time":...,"data":{"turn":1,"step":1,"chunk":{"type":"finish","reason":{...}}}}
{"type":"step/end","seq":11,"time":...,"data":{"turn":1,"step":1}}
{"type":"turn/end","seq":12,"time":...,"data":{"turn":1,"reason":{"kind":"error","error":{...}}}}
```

**注意 seq 5、6 两条 `user/message` 是系统注入的**（运行时上下文快照、技能清单）。
渲染时必须过滤，否则用户会看到一大段 system-reminder。
判据：`data.source.kind == "user"` 才是真实用户消息；系统注入的没有该字段或 kind 不同。

## chunk 类型（源码 `packages/llm/llm/src/types.ts:291`）

```
block-start | text-delta | reasoning-delta | tool-call-delta | block-end | usage | finish
```

## 目标事件词汇（`packages/platform-sdk-ts/src/events.ts`，零 import 纯类型模块）

```
session.started · message.delta · message.completed · thought.delta
tool_call.started · tool_call.delta · tool_call.completed
plan.updated · phase.changed · elicitation.requested · permission.requested
artifact.created · citation.recorded · run.state_changed · error
```

信封：

```ts
interface RunEventEnvelope {
  event_id: string; run_id: string; event_type: string;
  occurred_at: string; seq: number;
  payload?: UnifiedEventPayload; metadata?: Record<string, unknown>;
}
```

## 新增文件

```
apps/desktop/src-tauri/src/engine/
    tailer.rs     # 日志尾随器（RTM-03）
    history.rs    # 只读历史查询（RTM-04）
    mapper.rs     # 事件映射器（RTM-05）
```
</code_context>

<risks>
| # | 风险 | 缓解 |
|---|---|---|
| 1 | 日志文件惰性物化，`session/new` 后不存在 | 尾随器容忍文件缺失，轮询等待（上限 30s），期间不报错 |
| 2 | 读到半行（写入中途） | 只处理以 `\n` 结尾的完整行；不完整尾部留在缓冲 |
| 3 | 系统注入的 `user/message` 被当成用户消息渲染 | 按 `data.source.kind == "user"` 过滤；有专门测试 |
| 4 | 日志写入延迟 200ms（`writeBatchMaxDelayMs`） | 可接受；如需更低可在 cordis 配置下调 |
| 5 | 明文 NDJSON 体积增长 | 本阶段测量单会话量级并记录，保留期策略在 Phase 127 定 |
| 6 | `session-query.db` 被 app 误写坏 | 只读模式打开（SQLite URI `?mode=ro`），并有测试断言写入被拒 |
</risks>
