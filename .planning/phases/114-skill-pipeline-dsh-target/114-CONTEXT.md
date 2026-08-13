---
phase: 114-skill-pipeline-dsh-target
milestone: v4.0
created: 2026-08-14
mode: auto
prior_phase: 113-legal-presets-domain-presets
requirements: SKL-01, SKL-02, SKL-03
---

# Phase 114: Context — Skill Pipeline — dsh Target

## Phase goal

语料仓 `ai-for-china-legal` 获得一条 `dsh` 物化管线：白名单分域扫描 + 两类语义改写，产出结构稳定的技能树；内容包 manifest 与发布脚本一次成型，内容门禁拦住一切格式漂移。墨律本仓不复制语料。

## Locked decisions (from prior phases, PRD, AGENTS.md)

1. **语料仓唯一事实源 = `ai-for-china-legal`**（Windows 路径 `C:\Users\sorawatcher\workspace\ai-for-china-legal`，本机 WSL 路径 `/home/sorawatcher/workspace/ai-for-china-legal`）。只读物化，本仓永不复制语料、永不写回语料仓。
2. **物化输出结构由 Phase 113 预设形态决定**：`presets/<domain>/skills/<skill-name>/SKILL.md`，目录名=技能名，frontmatter `name`/`description` 直通。
3. **`customSkillDirs` 指向 `~/.agent-presets/<domain>/skills`** — Phase 114 物化输出必须对齐此路径（内容包解包后由 Phase 115 更新器切换 current 指针）。
4. **token 预算门禁 ≤8,000 字符**（Phase 113 `BudgetGate`）— Phase 114 物化后的 legal-core catalog 必须在此预算内。
5. **DSH 钉版本 + 禁自动升级引擎** — 内容包 `min_engine_version` 字段对齐 `engines/dsh-pin.txt`。
6. **V3.x 平台冻结** — `convert-skills.js` 现有 target（kimi/opencode/standalone）保留不动；新增 `dsh` target 不修改现有 target 行为。
7. **两类语义改写**（PRD SKL-01）：
   - 斜杠命令（`/commercial-legal:cold-start-interview`）→ "用 skill 工具按名加载 X 技能"指引
   - CLAUDE.md 写入指令 → 写 app 数据目录 `practice-profile.md`
8. **内容门禁扩展 `test:compatibility`** — 不新建独立 CI；在语料仓现有脚本上扩展。

## Gray areas (auto-resolved)

### [auto] GA-1: 物化执行环境 — WSL 桥接 vs Windows CI

**Question:** 语料仓在 Windows 路径，墨律本仓在 WSL。物化脚本在哪运行？

**Selected:** WSL 桥接（本机开发）+ 脚本跨平台兼容（生产 CI）

**Rationale:** `convert-skills.js` 是 Node.js 脚本，跨平台。本机 WSL 可直接访问 `/home/sorawatcher/workspace/ai-for-china-legal`。发布脚本用 `CONTENT_RELEASE_URL` 环境变量配置目标源，不硬编码路径。CI 可在 Linux runner 上运行。

### [auto] GA-2: 白名单分域映射

**Question:** 语料仓 13 个插件 → 墨律 5 个域（legal-core + 4 域）如何映射？

**Selected:** 显式映射表，多对一

**Rationale:** 语料仓插件 → 墨律域映射：
- `commercial-legal` → `legal-commercial`
- `litigation-legal` → `legal-litigation`
- `family-legal` → `legal-family`
- `employment-legal` → `legal-employment`
- `legal-core` ← 从四域中标记为"核心"的技能子集（frontmatter `core: true` 或显式清单）
- 其余插件（ai-governance, construction-legal, criminal-compliance, data-compliance, ip-legal, law-student, legal-aid, regulatory-legal）→ V4.0 不物化（deferred to later milestone）

映射表在 `convert-skills.js` 的 `dsh` target 中硬编码，可配置。

### [auto] GA-3: 子技能处理

**Question:** 语料仓技能有子技能目录（如 `contract-review/risk-identification/SKILL.md`）。DSH 技能系统是扁平的 `<skill-name>/SKILL.md`。如何处理？

**Selected:** 子技能提升为顶层技能，名称用 `<parent>-<child>` 连接

**Rationale:** DSH `customSkillDirs` 扫描一层子目录找 `SKILL.md`。子技能提升为 `contract-review-risk-identification/SKILL.md` 保持扁平结构。frontmatter `name` 字段保留原名（`risk-identification`），目录名用连接形式保证唯一性。

### [auto] GA-4: manifest 发布渠道

**Question:** `content-manifest.json` + zip 发布到哪？

**Selected:** GitHub Release 默认 + `CONTENT_RELEASE_URL` 可配

**Rationale:** PRD SKL-02 明确。发布脚本生成 zip + manifest，上传 GitHub Release。app 侧更新器（Phase 115）从 `CONTENT_RELEASE_URL` 拉取。本阶段不实现上传逻辑（需要 GH token），只生成本地产物 + 发布脚本骨架。

### [auto] GA-5: 内容门禁实现方式

**Question:** `test:compatibility` 扩展是改语料仓的 `package.json` script，还是新建独立脚本？

**Selected:** 新建 `scripts/test-dsh-output.js` + 在 `package.json` 的 `test:compatibility` 中链式调用

**Rationale:** 不修改现有 `test:compatibility` 行为（避免破坏 kimi/opencode/standalone 测试）。新增 `test:dsh` script，`test:compatibility` 改为 `test:compatibility && test:dsh`（或保持独立，由 CI workflow 并行调用）。

### [auto] GA-6: 物化产物在本仓的存放位置

**Question:** `dist/dsh/<domain>/` 产物是否提交到墨律本仓？

**Selected:** 不提交；物化产物在语料仓 `dist/dsh/` 生成，打包为 zip 后发布。墨律本仓只保留 manifest schema 定义 + 发布脚本 + 门禁测试引用

**Rationale:** AGENTS.md 明确"本仓永不复制语料"。物化在语料仓侧完成，墨律本仓只消费 zip 包（Phase 115 更新器）。

## Deferred ideas

- 其余 8 个语料仓插件（ai-governance 等）的 dsh 物化 → 后续 milestone
- 子技能保留嵌套结构（DSH 未来支持嵌套技能目录时再评估）
- 物化时的 token 预算自动裁剪 → Phase 115 更新器侧处理

## Downstream guidance

### For researcher (114-RESEARCH.md)

1. 检查 `ai-for-china-legal/scripts/convert-skills.js` 现有结构，确定 `dsh` target 的最小侵入式扩展点
2. 检查语料仓 5 个目标域的技能数量 + 子技能数量，估算 legal-core 候选集规模（≤30 约束）
3. 检查语料仓 SKILL.md 中斜杠命令和 CLAUDE.md 引用的具体模式，确定两类语义改写的正则/解析策略
4. 检查 DSH skill loader 对 `customSkillDirs` 的扫描行为，确认扁平结构假设
5. 确认 `engines/dsh-pin.txt` 当前版本，对齐 `min_engine_version`
6. 检查 `scripts/test_materialize_presets.sh`（Phase 113）是否可复用于 Phase 114 端到端演示

### For planner

1. Plans 应覆盖：convert-skills.js dsh target → manifest 生成器 → zip 发布脚本 → 内容门禁 → 端到端演示
2. 所有改动在语料仓 `ai-for-china-legal` 侧；墨律本仓只加 manifest schema 定义 + 引用测试
3. 端到端演示必须脚本化：语料仓源 → dsh 物化 → manifest → zip → 解包验证
4. 不修改 `convert-skills.js` 现有 target（kimi/opencode/standalone）行为
5. CI 集成：语料仓 `.github/workflows/` 新增 dsh 物化 + 门禁 job（或扩展现有 workflow）

## Success criteria (from ROADMAP.md)

1. `scripts/convert-skills.js --to dsh`：白名单按域扫描；frontmatter 直通；输出 `dist/dsh/<domain>/<skill-name>/SKILL.md`
2. 两类语义改写有测试：斜杠命令 → skill 工具加载指引；CLAUDE.md 写入 → `practice-profile.md`
3. `content-manifest.json` 生成器：schema_version / release_version / released_at / min_engine_version / domains:{skills:[{name,sha256}]}
4. 内容门禁：每个输出 SKILL.md 可解析、frontmatter 合法、无斜杠命令残留、无 CLAUDE.md 残留
5. RESEARCH 结论落 `114-RESEARCH.md`：WSL 桥接定案
6. 端到端演示：源 → dsh 物化 → manifest → zip → 解包，全程脚本化
