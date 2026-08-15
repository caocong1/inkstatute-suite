# Phase 126: Guardrails & Capability Layer - Context

**Gathered:** 2026-08-15
**Status:** Ready for execution
**Requirements:** GRD-11..16, SKL-11..13
**Depends on:** Phase 125 全部通过（含真机核对 6 项）

<domain>
## Phase Boundary

把「能对话的外壳」变成「能做法律工作且不可绕过护栏的产品」：分域预设挂载、内容包更新、护栏双层落地。

**护栏双层缺一即视为绕过**：
- **模型侧**：预设人设的提示词段（research-gate / citation audit / ask-user / de-AI polish / human review / 保密）
- **渲染侧**：app 的呈现与强制（徽记、卡片、锁定、无放行路径）

**本阶段合并 GRD 与 SKL 的原因**：护栏的模型侧就写在技能预设的人设里，两者同阶段才能双层同时验证。
</domain>

<decisions>
## 沿用 v4.0 的成果（不重做）

| 资产 | 位置 | v5 处置 |
|---|---|---|
| 分域预设 | `presets/legal-core` / `legal-commercial` / `legal-litigation` / `legal-family` / `legal-employment` | 沿用，物化目标改为 `<dsh_home>/.agent-presets/` |
| dsh 物化管线 | `ai-for-china-legal/scripts/convert-skills.js --to dsh` | 沿用 |
| 内容包 manifest | `content-manifest.json`（schema_version / release_version / min_engine_version / domains） | 沿用，**兼容性判据改 semver** |
| 内容更新逻辑 | `apps/flutter_app/lib/content/`（manifest_schema / hash_verifier / zip_extractor / content_updater） | **行为参照**，Rust 侧重写 |
| 护栏逻辑 | `apps/flutter_app/lib/guardrails/`（6 个 checker） | **行为参照**，映射到事件层 + ui-core 组件 |

`apps/flutter_app` 冻结：**只读参照，不得修改。**

## v5 的变化

1. **LLM 自动判断法律领域**——用户不再选执业方向。
   首启向导只问供应商与密钥。分域预设的选择由模型按问题内容自行加载技能，
   `customSkillDirs` 挂**全部已启用分域**，靠 token 预算门禁（SKL-13）控制目录规模。
2. **research-gate 可核验化**（GRD-11）：v4 只能从文本推断模型是否检索过；
   v5 有 `tool/call` 时间线，可直接看检索工具是否被调用。
3. **兼容性判据改 semver**：v4 的 `isCompatibleWith` 是 `engineVersion == minEngineVersion` 字符串相等，
   DSH 已启用 semver（`0.1.0-rc.6`），改为范围比较。

## 护栏在事件层的落点

| 护栏 | 模型侧（预设人设） | 渲染侧（app） | 事件来源 |
|---|---|---|---|
| GRD-11 research-gate | "未检索现行法规不得下结论" | 无 verified 引用时结论区"待核实"标记 | `tool_call.started/completed` |
| GRD-12 citation audit | "引用必标 verified/retrieved/unverified" | 三类徽记，unverified 视觉警示 | `citation.recorded`（正文扫描派生） |
| GRD-13 ask-user | "关键事实缺失输出 `[CLARIFY: …]`" | ClarificationCard，未澄清任务锁定 | `elicitation.requested`（文本约定派生） |
| GRD-14 de-AI polish + human review | "终稿过润色段；高风险恒带 `[HUMAN_REVIEW: …]`" | 独立样式 + 徽记不可消除 | 正文扫描派生 |
| GRD-15 批准卡片 | 引擎批准栈 `policy: ask` | allow-once / reject-once，**无批量入口** | `permission.requested`（ACP） |
| GRD-16 输出边界 + 保密 | 保密提示入人设 | 只渲染已提交文本；上传前脱敏提醒 | 映射器过滤 |

## 复用的既有实现

`packages/ui-core/src/utils/citationAudit.ts`（124 行）已实现引用分类，直接用。
`packages/ui-core/src/components/ClarificationCard.tsx` 已存在，直接用。
`packages/ui-core/src/types/workflow.ts` 的 `ClarificationRequest` / `ClarificationQuestion` 是既定契约。
</decisions>

<risks>
| # | 风险 | 缓解 |
|---|---|---|
| 1 | 348 技能目录 token 爆炸 | SKL-13 预算门禁：目录渲染 ≤ 8,000 字符，超预算测试红灯拒绝发货 |
| 2 | 模型不自觉加载技能 | 人设强制"先加载对应技能再动手"；核心集常驻目录 |
| 3 | `[CLARIFY:]` 解析误伤正文 | 解析器要求块状格式且有闭合；有针对性的负例测试 |
| 4 | 护栏只做了渲染侧、模型侧漏配 | 门禁同时断言两侧：预设文件含护栏段 + 渲染组件存在 |
| 5 | 内容源在中国大陆不可达 | 内容源可配；失败保持 last-good 且不阻塞启动 |
</risks>
