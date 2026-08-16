# 实践配置文件契约（Practice Profile Schema）

> 本文件定义 commercial-legal 插件的实践配置文件契约：字段定义、存储位置、技能读取规则，以及与 `commercial-legal/CLAUDE.md` 实践配置模板的映射关系。
>
> **所有商事合同技能通过本契约读取个性化配置。** 冷启动访谈子技能按本契约填充配置文件。

---

## 一、配置文件是什么

### 真相来源

实践配置文件的真相来源是 **`commercial-legal/CLAUDE.md`**（散文形式）。该文件：

- 由 `/commercial-legal:cold-start-interview` 冷启动访谈生成和更新
- 可由律师直接编辑（无需重新运行访谈）
- 为所有商事合同技能提供个性化设置的读取来源

### 架构决策（Discretion 选择）

**决策：不引入与现有体系冲突的新配置文件格式。**

背景：`02-CONTEXT.md` 提到配置可为 `.claude-plugin/profile.json` 或类似。但现有体系已用 `commercial-legal/CLAUDE.md`（散文模板）+ 冷启动访谈输出 YAML 双轨。

**选择理由：**

1. `commercial-legal/CLAUDE.md` 已是律师可直接阅读和编辑的人类友好格式，散文胜于 JSON/YAML 用于表达「立场」与「为什么」
2. Claude 的实践配置文件读取本质是文本理解，不需要机器解析的结构化格式
3. 引入 `profile.json` 会产生双重真相来源，维护成本高且容易产生不一致
4. 现有 `contract-review` 编排入口已从 `commercial-legal/CLAUDE.md` 读取配置，模式已验证可行

**结论：** `commercial-legal/CLAUDE.md` 是唯一真相来源。冷启动访谈产出的 YAML 示例仅作为「完整配置示意」，访谈实际填充 `commercial-legal/CLAUDE.md` 的占位符字段。

---

## 二、字段映射表

以下映射表将五个访谈子技能的收集字段，对应到 `commercial-legal/CLAUDE.md` 的章节，并标注哪些技能读取该字段。

### 2.1 身份与团队（identity-team 子技能）

| 访谈字段 | 配置模板章节 | 读取技能 |
|---------|------------|---------|
| 公司/律所名称、实体类型 | `## 我们是谁` → 公司名称、实体类型 | contract-review, contract-drafting, liability-analysis |
| 合同团队规模 | `## 我们是谁` → 合同团队规模 | contract-review (升级路由) |
| 最终升级联系人 | `## 我们是谁` → 最终升级联系人 | contract-review (升级矩阵), escalation-rules |
| 每月处理合同数量 | `## 我们是谁` → 每月处理合同数量 | 参考值，暂无技能直接读取 |
| 主要交易对手类型 | `## 我们是谁` → 主要交易对手类型 | contract-review (风险识别), negotiation-points |
| 合同管理系统 | `## 可用集成` → 合同管理系统 | output-formatting (导出路由) |
| 执业环境（律所/公司法务） | `## 谁在使用` → 角色 | 所有技能（工作产物标题选择） |
| 律师联系人 | `## 谁在使用` → 律师联系人 | 非律师模式时提示 |

### 2.2 审查立场（review-stance 子技能）

| 访谈字段 | 配置模板章节 | 读取技能 |
|---------|------------|---------|
| 风险偏好（保守/平衡/进取） | `## 审查立场` → 整体风险偏好（顶层） | contract-review (所有子技能), liability-analysis |
| 甲方：责任限制立场 | `## 审查立场` → `### 甲方立场` → `#### 责任限制` | risk-identification, clause-revision |
| 甲方：违约金立场 | `## 审查立场` → `### 甲方立场` → `#### 违约金` | risk-identification, clause-revision |
| 甲方：知识产权立场 | `## 审查立场` → `### 甲方立场` → `#### 知识产权` | risk-identification, clause-revision |
| 甲方：数据保护立场 | `## 审查立场` → `### 甲方立场` → `#### 数据保护` | risk-identification, clause-revision |
| 甲方：期限与终止立场 | `## 审查立场` → `### 甲方立场` → `#### 期限与终止` | risk-identification, clause-revision |
| 甲方：管辖与争议解决 | `## 审查立场` → `### 甲方立场` → `#### 管辖法律与争议解决` | risk-identification, jurisdiction-profile |
| 甲方：交易破坏者 | `## 审查立场` → `### 甲方立场` → `#### 交易破坏者` | risk-identification (优先标记) |
| 乙方：责任限制立场 | `## 审查立场` → `### 乙方立场` → `#### 责任限制` | risk-identification, clause-revision |
| 乙方：违约金立场 | `## 审查立场` → `### 乙方立场` → `#### 违约金` | risk-identification, clause-revision |
| 乙方：知识产权立场 | `## 审查立场` → `### 乙方立场` → `#### 知识产权` | risk-identification, clause-revision |
| 乙方：数据保护立场 | `## 审查立场` → `### 乙方立场` → `#### 数据保护` | risk-identification, clause-revision |
| 乙方：期限与终止立场 | `## 审查立场` → `### 乙方立场` → `#### 期限与终止` | risk-identification, clause-revision |
| 乙方：管辖与争议解决 | `## 审查立场` → `### 乙方立场` → `#### 管辖法律与争议解决` | risk-identification, jurisdiction-profile |
| 乙方：交易破坏者 | `## 审查立场` → `### 乙方立场` → `#### 交易破坏者` | risk-identification (优先标记) |

### 2.3 升级规则（escalation-rules 子技能）

| 访谈字段 | 配置模板章节 | 读取技能 |
|---------|------------|---------|
| 金额阈值（各层级） | `## 升级矩阵` → `### 审批权限` 表格 + `### 美元阈值` | contract-review (入口护栏), escalation-rules |
| 审批人姓名/角色/联系方式 | `## 升级矩阵` → `### 审批权限` 表格 | contract-review (升级路由), negotiation-points |
| 自动升级触发条件 | `## 升级矩阵` → `### 自动升级触发条件` | risk-identification (交易破坏者检测), contract-review |
| 风险等级升级规则 | `## 升级矩阵` → `### 审批权限` 需升级条件列 | risk-identification (🔴标记), contract-review |

### 2.4 文书风格（document-style 子技能）

| 访谈字段 | 配置模板章节 | 读取技能 |
|---------|------------|---------|
| 修订语气（正式/半正式/简洁） | `## 文书风格` → 修订语气 | clause-revision, output-formatting |
| 利益相关者摘要要求 | `## 文书风格` → 利益相关者摘要 | output-formatting |
| 工作产物存放位置 | `## 文书风格` → 工作产物存放位置 | output-formatting |
| 续约提醒联系人 | `## 文书风格` → 续约/期限提醒发送给 | output-formatting |
| 默认输出格式 | `## 输出` → `### 工作产物标题` | output-formatting |
| 是否含法条引用 | `## 输出` 风格偏好（访谈补充） | legal-basis, output-formatting |
| 是否含案例引用 | `## 输出` 风格偏好（访谈补充） | legal-basis, output-formatting |
| 是否双语输出 | `## 输出` 风格偏好（访谈补充） | output-formatting |

### 2.5 管辖法律（jurisdiction-profile 子技能）

| 访谈字段 | 配置模板章节 | 读取技能 |
|---------|------------|---------|
| 主要管辖法律 | `## 共享护栏` → `### 管辖识别` | risk-identification, legal-basis, liability-analysis |
| 地方性法规关注范围 | `## 共享护栏` → `### 管辖识别` → 经济特区/民族自治/自贸区 | legal-basis, jurisdiction-profile |
| 法院管辖偏好 | `## 审查立场` 各方 → `#### 管辖法律与争议解决` | risk-identification, clause-revision |
| 行业特殊要求 | `## 共享护栏` → 时效性触发（行业法规） | risk-identification, legal-basis |

---

## 三、技能读取契约

### 3.1 技能读取时机

**在执行任何实质性工作之前**，每个技能（或其编排入口）必须：

1. 读取 `commercial-legal/CLAUDE.md`
2. 检查关键字段是否已填充（不含 `[PLACEHOLDER]`）
3. 根据检查结果选择运行模式

### 3.2 配置缺失或含占位符时的处理

当技能检测到 `commercial-legal/CLAUDE.md` 缺失或含 `[PLACEHOLDER]` 时，**不得静默使用猜测值**，须按以下逻辑处理：

**提示词（标准格式）：**

> 我注意到你还没有配置你的实践档案——这是让我根据你的执业立场、升级规则和文书风格来定制输出的关键。
>
> **两个选择：**
> - 运行 `/commercial-legal:cold-start-interview`（约 5 分钟）来配置你的档案，然后我会根据你的真实审查立场进行工作。
> - 说 **「临时模式」**，我会使用通用默认值——中国法律体系、中等风险偏好、律师角色、无特定审查立场——并在每个输出上标记 `[临时模式 — 配置你的档案以获得定制输出]`。

**临时模式默认值：**

| 字段 | 临时模式默认值 |
|-----|-------------|
| 风险偏好 | 平衡型 |
| 执业角色 | 律师 |
| 管辖法律 | 中国大陆法律 |
| 甲方/乙方立场 | 标记常见风险，不偏向任何一方 |
| 升级矩阵 | 不自动升级，提示律师判断 |
| 文书风格 | 半正式，含法条引用，不含案例引用 |

### 3.3 甲方/乙方立场选择

对于每次合同审查，技能须在阅读合同前确认立场：

1. **从合同文本推断**：若协议标题或主体描述明显（如购货合同、服务采购合同），自动推断
2. **不明显时询问**：「在这个协议中，[机构名称/团队] 是哪一方——甲方（买方/委托方）还是乙方（卖方/受托方）？」
3. **确认后加载对应立场**：从 `## 审查立场` 的 `### 甲方立场` 或 `### 乙方立场` 读取对应字段

立场确认后，审查中的所有「标准立场」「可接受备选」「绝不接受」均来自该方立场。

---

## 四、重跑 / 编辑 / 版本控制

### 4.1 重跑访谈

律师可随时重新运行完整访谈或任一子技能：

- **完整重跑**：`/commercial-legal:cold-start-interview` — 按 identity-team → review-stance → escalation-rules → document-style → jurisdiction-profile 顺序填充全部字段
- **部分更新**：单独触发某一子技能，只更新配置文件的对应章节
  - `/commercial-legal:identity-team` — 仅更新「我们是谁/谁在使用/可用集成」
  - `/commercial-legal:review-stance` — 仅更新「审查立场」
  - `/commercial-legal:escalation-rules` — 仅更新「升级矩阵」
  - `/commercial-legal:document-style` — 仅更新「文书风格/输出」
  - `/commercial-legal:jurisdiction-profile` — 仅更新「共享护栏/管辖识别」

### 4.2 直接编辑

律师可直接编辑 `commercial-legal/CLAUDE.md`，无需重跑访谈。编辑后即时生效，下次技能调用自动读取新值。

### 4.3 版本控制

- `commercial-legal/CLAUDE.md` 纳入 git 版本控制（与代码同仓库）
- 支持通过 git 查看历史版本：`git log --oneline commercial-legal/CLAUDE.md`
- 支持通过 git diff 查看变更：`git diff HEAD~1 commercial-legal/CLAUDE.md`
- **回滚方式**：`git checkout <commit-hash> -- commercial-legal/CLAUDE.md`

### 4.4 配置迁移

当本 schema 版本升级（字段新增或更名）时：
- 新字段默认值为 `[PLACEHOLDER]`，不影响现有字段的正常读取
- 技能向后兼容：遇到未知字段时跳过，不报错

---

## 五、法律事实合理性检查

本节复用 `commercial-legal/CLAUDE.md` 的「验证用户陈述的法律事实」与「时效性触发」规则。

### 5.1 适用范围

在访谈子技能将字段写入配置文件**之前**，对以下类型的用户口述内容进行合理性检查：

- 具体法规条款号（如「民法典第 584 条」）
- 具体金额阈值（如「升级阈值是 ¥500 万」）
- 具体期限或百分比（如「违约金不超过合同价款的 30%」）
- 引用司法解释条文或政策文件

### 5.2 合理性检查规则

**规则 1：条文号核查**

当用户口述条文号时，与训练知识中的该条文内容交叉核对。若发现潜在不一致：

> 你提到 X 条款要求 Y；我的理解是该条款规定的是 Z。请确认哪个写入配置文件？`[前提 flagged — 需验证]`

**规则 2：阈值合理性**

当用户口述升级阈值或违约金比率时，检查是否符合常见市场惯例和法规上限。若超出合理范围（如「违约金上限设为合同总价的 200%」），提示：

> 你设置的违约金上限（200%）明显高于市场惯例（通常为 30%~100%）。依据《民法典》第 585 条，超过实际损失 30% 的违约金条款可能被法院调整。请确认是否要按此填入配置？`[前提 flagged — 需验证]`

**规则 3：时效性标记**

对于任何涉及具体法规适用的配置字段，若规则 `[时效性 flagged]` 适用（距最后更新日期超过 6 个月），在字段值后附加标记：

> `[时效性 flagged — 需验证最新法规]`

**规则 4：矛盾回答澄清**

若用户在同一访谈会话中提供矛盾的立场（如先说「进取型」后对所有条款都要求「绝不让步」），在写入前澄清：

> 你的风险偏好设置为「进取型」，但你的交易破坏者清单涵盖了 [N] 项，超出进取型的典型范围。这是否准确？请确认风险偏好设置。

### 5.3 写入前确认流程

对于所有 `[前提 flagged — 需验证]` 标记的字段：

1. 显示检测到的潜在问题
2. 提供两个选项：(a) 按用户口述写入（保留 `[前提 flagged — 需验证]` 标注）；(b) 按建议值修改后写入
3. 不得静默写入未经确认的存疑值

---

## 六、schema 与 CLAUDE.md 模板章节对照

| schema 字段组 | `commercial-legal/CLAUDE.md` 章节 | 对应访谈子技能 |
|-------------|----------------------------------|--------------|
| 我们是谁、谁在使用、可用集成 | `## 我们是谁`、`## 谁在使用`、`## 可用集成` | identity-team |
| 风险偏好、甲方立场（全维度）、乙方立场（全维度） | `## 审查立场` | review-stance |
| 升级矩阵（金额/风险/自动触发）、审批人 | `## 升级矩阵` | escalation-rules |
| 文书风格、输出格式、工作产物标题 | `## 文书风格`、`## 输出` | document-style |
| 管辖识别、时效性触发、验证规则 | `## 共享护栏` | jurisdiction-profile |
| 事项工作区、种子文档 | `## 事项工作区`、`## 审查过的种子文档` | 不由访谈填充，律师直接编辑 |
