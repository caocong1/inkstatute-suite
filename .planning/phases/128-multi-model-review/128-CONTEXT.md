# Phase 128: Multi-Model Cross-Review & Adversarial Challenge - Context

**Gathered:** 2026-08-16
**Status:** Ready for execution（**在 Phase 127 交付之后**）
**Requirements:** MMR-01..06, GATE-14
**Depends on:** Phase 127 完成（v5.0 核心交付闭环）

<domain>
## Phase Boundary

把 v3.1 Arena 的核心价值——**多个不同厂商的模型互相审查同一份法律意见**——
以增强附加功能的形式重建在 v5.0 架构上。

**业主决定（2026-08-16）：**
- 范围：**交叉互评 + 对抗质询**（原 Mode 3 + Mode 4）。不做 Mode 1 并行、不做 Mode 2 自评迭代。
- 排期：**v5.0 交付之后**，不进核心交付路径。

**本阶段不做**：不做模式选择器（与「零配置」冲突）、不复活 `packages/arena-engine`（Python，
经 v3 Gateway，架构已不适用）、不复活 `services/arena-service`。
</domain>

<decisions>
## 决定性的架构发现（已核实源码）

**多模型互评在 v5.0 里是配置，不是编排代码。** 依据：

`@deepseek-ai/dsh-tool-subagent` 的 Config（源码 `packages/subagent/tool-subagent/src/index.ts:81`）：

```ts
provider: z.string().required(),        // 子代理传输方式（不是 LLM 厂商）
toolName: z.string().default('subagent'),
agentOptions: z.object({ provider, model, maxTokens }),   // ← LLM 厂商与模型，逐实例覆盖
persona: z.string(),
toolFilter: z.object({ allow, deny }),
maxDepth: ...
```

**该插件可注册多次**，每个实例有独立的 `toolName` / `agentOptions` / `persona` / `toolFilter`。
于是"请 GPT 复核"和"请 Claude 挑刺"各是一个模型可调用的工具。
主代理不需要我们写编排——它自己按人设调用这些工具。

配套包全部已在 npm `0.1.0-rc.6`：
`dsh-tool-subagent` · `dsh-subagent` · `dsh-subagent-spawn-in-process` ·
`dsh-subagent-fork-in-process` · `dsh-tool-subagent-report`

LLM 厂商由 `dsh-llm-pi-ai` 提供（Phase 122 已配 8 家 + custom）。

## 必须用 spawn，不能用 fork

| 传输方式 | 行为 | 用于复核 |
|---|---|---|
| `subagent-fork-in-process` | 子代理**继承父会话已完成的全部轮次** | ❌ 复核者会被起草者的推理锚定 |
| `subagent-spawn-in-process` | 子代理**全新会话，不见父历史** | ✅ 新鲜视角 |

原 v3.1 设计对此有明确立场：`packages/arena-engine/tests/test_fresh_context.py`
是一个 AST 门禁，禁止 arena 源码里出现任何 `resume` / `session/resume`——
「Every arena run must use a fresh context」。**这条方法论在 v5 保留。**

案情与初稿经**工具参数显式传入**子代理，而非靠会话继承。

## ACP 的约束（已核实，影响方案形状）

`session/new` **不支持 per-session 模型覆盖**——
`agentOptions(config)`（`packages/acp/acp/src/index.ts:422`）只读全局 config。
因此「一个引擎开多个会话跑不同模型」这条路不通，多模型只能经子代理实现。
这反而是更好的形状：复核是主任务的一部分，不是并列的另一次对话。

## 触发方式（与「零配置」的调和）

**不做模式选择器。** 律师不选模式，两条触发路径：

1. **自动**：预设人设规定——凡将输出 `[HUMAN_REVIEW:]` 级别的高风险结论
   （诉讼时效认定、合同效力、刑责判断、金额 >100 万、行政处罚幅度、
   或任何 unverified 依据支撑的结论）**必须先调用复核工具**。
2. **手动**：会话界面一个「深度复核」按钮，对当前成稿追加一轮互评 + 对抗。

## 与法律护栏的衔接（Phase 126 已建立）

- 复核发现的**未消解分歧**必须落成 `[HUMAN_REVIEW: 模型间存在分歧 —— …]`，
  徽记不可自动消除（沿用 GRD-14）。
- 对抗质询提出的漏洞若未被回应，同样升级为人审标记。
- 复核**不得**放宽引用审查（GRD-12）：复核者自身的引用同样要标等级。

## 复用清单（Phase 125-01 已保留，未删除）

| 资产 | 位置 | 用途 |
|---|---|---|
| `ReviewSummary.tsx` | ui-core/components | 互评结论汇总 |
| `SynthesisViewer.tsx` | ui-core/components | 综合稿呈现 |
| `ParallelStreamPanel.tsx` | ui-core/components | 多路并行进度 |
| `ScoreCard.tsx` | ui-core/components | 评分卡 |
| `SlotStreamView.tsx` | ui-core/components | 单路流式 |
| `ArenaWorkflowCreator.tsx` | ui-core/components | 触发入口（需按新触发方式改造） |
| `reducers/arenaEventReducer.ts` | ui-core/reducers | Arena 事件 → 渲染态 |
| `types/arena.ts` | ui-core/types | 类型契约 |

Arena 事件词汇已在 `packages/platform-sdk-ts/src/events.ts`：
`ArenaWorkflowStarted/Completed` · `ArenaScoreRecorded` · `ArenaReviewCompleted` ·
`ArenaSynthesisStarted/Completed` · `ArenaAdversarialChallengeCompleted` · `ArenaEarlyStopTriggered`

**传输层已在 Phase 125-01 删除**（`arenaStream.ts` / `sseUtils.ts` / `eventStream.ts` 走 Gateway SSE），
本阶段以 Tauri 事件通道重新接入。

## 观测面已就绪

DSH 会话事件词汇含 `subagent/start` · `subagent/end` · `subagent/descriptor`，
Phase 124 的日志尾随器能直接看到子代理活动 —— 不需要新的数据通道。
</decisions>

<risks>
| # | 风险 | 缓解 |
|---|---|---|
| 1 | 每次任务成本与耗时成倍增长（互评 2 路 + 对抗多轮） | 只在高风险结论自动触发；手动入口独立；早停（无新问题即停）；轮数上限默认 2 |
| 2 | 复核用的第二厂商密钥未配置 | 优雅降级：只用已配置厂商；一个厂商也能跑（同厂商不同模型），并在 UI 注明「单模型复核，效力有限」 |
| 3 | 子代理递归失控 | `maxDepth` 显式设 1（复核者不得再起复核者） |
| 4 | 复核者被起草者锚定 | 强制 spawn 而非 fork；门禁静态断言配置里无 fork provider |
| 5 | 分歧被模型自行"和稀泥"抹平 | 综合人设强制：分歧必须逐条列出并标注，不得合并叙述；未消解分歧强制 `[HUMAN_REVIEW:]` |
| 6 | 子代理继承主代理的 fs/bash 工具造成越权 | `toolFilter.allow` 只放行只读检索类工具，禁 bash 与写文件 |
</risks>
