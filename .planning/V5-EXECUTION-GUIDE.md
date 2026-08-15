# v5.0 自主执行指南

**给自主执行 agent 的唯一入口文档。开始任何工作前先完整读完本文件。**

---

## 0. 一句话目标

把 `apps/desktop`（Tauri 2 + SolidJS）与 `packages/ui-core`（墨律 UI）接上本地嵌入的 DSH 引擎，
交付一个中国律师在 Windows 上双击就能用的法律助手。

**最终验收 = PRD §2 的七个场景在干净 Windows 机器上全部可演示。**

---

## 1. 读文档的顺序

| # | 文档 | 作用 |
|---|---|---|
| 1 | 本文件 | 规则与顺序 |
| 2 | `docs/requirements/V5-PRD.md` | 需求真源。**有疑问以它为准** |
| 3 | `.planning/research/V5-SELECTION.md` | 11 项本机实测证据。**已验证的事实不要重新调研** |
| 4 | `.planning/REQUIREMENTS.md` | 41 条需求与 phase 映射 |
| 5 | `.planning/ROADMAP.md` | 7 个 phase 的目标（122–127 核心 + 128 增强） |
| 6 | `.planning/phases/<phase>/<phase>-CONTEXT.md` | 执行某 phase 前必读 |
| 7 | `.planning/phases/<phase>/<phase>-NN-PLAN.md` | 逐个 task 执行 |

---

## 1.5 环境准备（Phase 0 — 动任何代码之前先做，且必须成功）

```bash
cd /Users/dongli/Workspace/inkstatute-suite

# 1. 装依赖（bun workspaces，约 560 包 / 20 秒）
bun install

# 2. !!! 构建 ui-core !!! 这一步不做，apps/desktop 会有 9 个测试文件直接崩
cd packages/ui-core && bun run build && cd ../..
```

**为什么第 2 步是必须的**：`packages/ui-core/package.json` 的 `main`/`module`/`exports`
全部指向 `dist/`，而 `dist/` 不在仓库里。不构建的话，`apps/desktop` 里任何
`import ... from "@inkstatute/ui-core"` 都会报
`Failed to resolve entry for package "@inkstatute/ui-core"`。

**推论：只要改动了 `packages/ui-core/src/`，就必须重新 `bun run build`，
否则 `apps/desktop` 那侧看到的还是旧产物。** Phase 125 删 Arena 之后尤其要记得重建。

### 已核实的基线状态（2026-08-15，动手前的真实起点）

| 检查 | 结果 |
|---|---|
| `cargo check`（apps/desktop/src-tauri） | ✅ 通过，3 个 unused import 警告 |
| `cargo test` | ✅ 23 passed |
| `packages/ui-core` `vitest run` | ✅ 16 文件 / 200 tests passed |
| `packages/ui-core` `tsc --noEmit` | ⚠️ **5 个 error，全部在 Arena 测试文件里** |
| `apps/desktop` `tsc --noEmit` | ✅ 干净 |
| `apps/desktop` `vitest run` | ✅ 16 文件 / 108 tests passed（**前提：ui-core 已构建**） |

**那 5 个类型错误的处置**（2026-08-16 因保留 Arena 而变更）：
它们分布在 `test_arena_workflow_creator.tsx`(1)、`test_parallel_stream_panel.tsx`(1)、
`test_synthesis_viewer.tsx`(3)。这些测试**不再被删除**（Phase 128 要用 Arena 呈现层），
因此 **Phase 125-01 Task 1 必须就地把这 5 个错误修干净**：
前两个是 mock 缺字段（补 `title`/`sections`、补 `ToolCallCompletedPayload` 必填项），
后三个是元组索引越界（加长度断言或 `?.`）。

### ⚠️ Phase 127 需要 Windows 环境（当前不具备）

当前开发机是 **macOS**，CI 的两个 workflow（`v2-contract-gates.yml`、`v4-gates.yml`）都是
`runs-on: ubuntu-latest`。**Tauri 无法从 macOS 交叉编译出 Windows MSVC 目标。**

Phase 122–126 全部可以在 macOS 上完成（Rust 逻辑、事件映射、前端、护栏都是平台无关的，
引擎装配器把 `target_platform` 当数据处理）。**只有 Phase 127 卡住**：

| Phase 127 任务 | macOS 上可否 |
|---|---|
| 127-01 字体本地化 | ✅ 可以（真机字体核对需 Windows） |
| 127-01 Node 运行时获取 | ✅ 可以（脚本按 `target_platform` 下载 win-x64） |
| 127-02 引擎更新器 + GATE-13 | ✅ 可以（逻辑与门禁平台无关） |
| **127-03 Windows 单 exe 打包** | ❌ **必须 Windows** |
| **127-03 七场景真机演练** | ❌ **必须 Windows** |

**执行到 Phase 127 前必须由业主提供其一：**
1. 一台 Windows 机器 / 虚拟机（最直接）
2. 在 `.github/workflows/` 加一个 `runs-on: windows-latest` 的构建 workflow

**不要试图在 macOS 上"绕过"打包**（比如产出 .app 或 .dmg 冒充交付物）——
交付目标明确是 Windows 单 exe。走到这一步就停下来找业主。

### 在 Windows 机器上执行 Phase 127 的准备（2026-08-16 补）

Phase 122–126 在 macOS 上完成，Phase 127 转到 Windows。**换机后必须先做这四步**：

```powershell
# 1. 克隆并装依赖
git clone https://github.com/caocong1/inkstatute-suite.git
cd inkstatute-suite
bun install
cd packages\ui-core; bun run build; cd ..\..

# 2. 存 API 密钥（Mac 上的凭据不会跟过来）
cargo build --manifest-path apps\desktop\src-tauri\Cargo.toml --bin store-key
# 交互式（Windows 终端可直接粘贴）：
.\apps\desktop\src-tauri\target\debug\store-key.exe deepseek

# 3. 确认基线
cargo test --manifest-path apps\desktop\src-tauri\Cargo.toml -- --test-threads=1
node scripts\gates\v5\run-gates.mjs        # 期望 4 passed, 0 failed

# 4. 开工
# /gsd-execute-phase 127
```

**本文件第 5 节的仓库路径是 macOS 的**（`/Users/dongli/Workspace/...`），
在 Windows 上一律替换为你的克隆位置。其中：
- `lawyer-desktop` / `deepseek-harness` / `ai-for-china-legal` 三个只读参照仓
  **Phase 127 用不到**，不必克隆。127 只需要本仓。
- 引擎装配走 npm，不需要 DSH 源码。

**Windows 上不会有钥匙串弹窗**——凭据管理器按用户而非按二进制授权，
macOS 那套 `#[cfg(debug_assertions)]` 的 dev 文件回退在 Windows 上同样生效
（落在 `%USERPROFILE%\.inkstatute\dev-credentials.json`），两条路都不弹窗。

**Phase 127 交付前记得吊销旧 key**：`sk-6f15…` 曾在对话中明文出现，换新 key 后用
上面第 2 步的命令重存即可。

在 Phase 125-01 之前，`packages/ui-core` 的 `tsc --noEmit` 验收标准是
**「错误数 ≤ 5 且全部位于上述三个 Arena 测试文件」**，不是「零错误」。
Phase 125-01 之后必须是零错误。

---

## 2. 执行顺序（严格串行，不得并行、不得跳过）

```
122 引擎装配管线换血        ← 从这里开始
 ↓  验收门：node scripts/gates/v5/run-gates.mjs 绿 + 空目录能装出可启动引擎
123 引擎主管与真实链路
 ↓  验收门：123-DECISION.md 写明「回灌方案验证通过」  ★ 人工闸门
124 观测面·历史面·事件映射
 ↓  验收门：GATE-12 绿 + ui-core 零改动
125 前端接线与裁剪
 ↓  验收门：三包类型检查+测试全绿 + 真机 6 项核对  ★ 人工核对
126 护栏与技能能力层
 ↓  验收门：4 道门禁绿 + 无批量批准路径
127 打包与三层更新
 ↓  验收门：6 道门禁绿 + 七场景真机演练  ★ 人工闸门
━━ v5.0 核心交付完成 ━━
128 多模型互评（增强附加功能，不在关键路径）
 ↓  验收门：7 道门禁绿 + 双厂商密钥端到端 + 6 项人工验收
完成 → /gsd-complete-milestone
```

**每个 plan 末尾的 `<verification>` 块是硬门槛。未全绿不得进入下一个 plan。**

---

## 3. 绝对禁止（违反即返工）

1. **不得修改 `apps/flutter_app/`。** 它是冻结资产，只作为 Rust 侧移植的行为参照读取。
2. **不得修改 `/Users/dongli/Workspace/lawyer-desktop/`。** 另一个仓库，只读移植源。
3. **不得修改 `packages/ui-core/src/event-reducer.ts`。** 多个 plan 的验证块里有 `git diff --quiet` 断言。
4. **不得修改 ui-core 组件源码。** 唯一允许的 ui-core 改动是：
   Phase 125-01 删除 Arena **传输层**（`arenaStream.ts` / `sseUtils.ts` / `eventStream.ts`）
   并就地修 3 个保留测试的类型错误；Phase 127-01 的字体族四行；
   Phase 128-03 对 `ArenaWorkflowCreator` 的改造。
   **Arena 的 6 个呈现组件 + `arenaEventReducer.ts` + `types/arena.ts` 一律保留**——
   Phase 128 的多模型互评要用（业主 2026-08-16 决定）。
5. **不得把 API 密钥写进任何文件、日志、遥测、命令行参数。** 只经环境变量注入子进程，只存 OS 凭据库。
6. **不得使用 npm dist-tag。** `@deepseek-ai/dsh-*` 的 `latest` 指向旧版 `0.0.1-rc.1`。永远写精确版本号。
7. **不得在引擎冒烟通过前写 `engine/current` 指针。** GATE-13 会用坏包验证这一点。
8. **不得给批准卡片加"总是允许/批量批准/记住选择"入口。** 法律护栏硬约束。
9. **不得用 `skip` / `ignore` / `@ts-ignore` / `as any` / 空 catch 绕过失败的测试。** 修根因。
10. **不得声称人工闸门通过。** HG-1（律师法律质量抽样）与 HG-3（五工作日试运行）保持 DEFERRED。

---

## 4. 已验证的事实（不要重新调研，直接用）

| 事实 | 值 |
|---|---|
| DSH npm 版本 | `0.1.0-rc.6`（16 个包，见 `engines/dsh-pin.txt`） |
| 引擎装配 | 87 包 / 9 秒 / 85MB；裁 node-pty 非目标平台后约 42MB |
| lockfile 结构 | v3，**196 条，含 3 条嵌套 node_modules**，100% 带 resolved + sha512 |
| ACP 握手 | `initialize` → `{"protocolVersion":1,"agentInfo":{"name":"deepseek-harness-acp"}}` |
| **`session/cancel`** | **必须作为通知发送（无 `id`）**。带 id 会返回 `Method not found` 而静默失败 |
| `session/new` 的 cwd | **必须绝对路径**；`mcpServers` 必须为 `[]` |
| 多会话 | 一条 ACP 连接可拥有多个会话，各自独立结算 |
| 会话日志 | 配 `packChunks:false` + `persistenceCompression:none` 后为明文 NDJSON，`seq` 连续 |
| 日志路径 | `<sessionsRoot>/--<规范化 cwd>--/<sessionId>/session.jsonl`。**规范化有损，用 sessionId 通配查找** |
| 上下文窗口 | `deepseek-v4-pro` 实测 `contextWindow: 1000000` |
| 历史面 | `<sessionsRoot>/session-query.db`，`persisted_sessions` + `persisted_docs`(FTS5)。**只读** |
| 缺陷 D1 | `${DSH_HOME}` 不被 Cordis 展开。修法 `!!js process.env.DSH_HOME + '/sessions'`（已验证） |
| 缺陷 D2 | `molv-tokens.css:7` 的 Google Fonts `@import` 在中国大陆不可达 |
| 缺陷 D3 | 不得依赖系统 Node，随包带 `node.exe` |

复现命令见 `.planning/research/V5-SELECTION.md` §5。

---

## 5. 仓库路径

```
/Users/dongli/Workspace/inkstatute-suite     # 本仓（工作目录）
/Users/dongli/Workspace/lawyer-desktop       # UI 移植源（只读）
/Users/dongli/Workspace/deepseek-harness     # DSH 源码（只读参照；构建走 npm，不需要它）
/Users/dongli/Workspace/ai-for-china-legal   # 语料仓，348 个 SKILL.md
```

> V4 文档里的 `/home/sorawatcher/...` 在本机不存在，遇到时按上表替换。

---

## 6. 常用命令

```bash
# 门禁（每个 phase 结束都要跑）
node scripts/gates/v5/run-gates.mjs

# 前端
cd packages/ui-core && bunx tsc --noEmit && bunx vitest run
cd packages/ui-core && bun run build      # 改过 ui-core/src 就必须重建（dist/ 已 gitignore，不会误提交）
cd apps/desktop     && bunx tsc --noEmit && bunx vitest run

# Rust
cd apps/desktop/src-tauri && cargo check && cargo test
cargo test -- --ignored          # 需要网络/真实引擎的集成测试

# 真机
cd apps/desktop && bunx tauri dev
```

包管理器：前端用 **bun**，Rust 用 **cargo**，引擎装配用 **Rust 自己的 lockfile 装配器**（运行时不用 npm）。

---

## 7. 提交约定

- 每完成一个 **task** 就提交一次（小步、可编译、测试绿）。
- commit message：`<type>(<phase>): <描述>`，例如 `feat(122): npm lockfile 装配器`
- 每完成一个 **plan**，更新 `.planning/STATE.md` 的 `completed_plans` 与 `progress.percent`。
- 每完成一个 **phase**，写 `<phase>-SUMMARY.md`（做了什么、门禁结果、遗留项），
  并在 `.planning/ROADMAP.md` 把该 phase 打勾。
- **不要提交**：API 密钥、`resources/node/`、`resources/engine/`、构建产物。

---

## 8. 卡住时怎么办

| 情况 | 做法 |
|---|---|
| 同一问题失败 3 次 | **停止**，把已试过的方案与错误写进 `<phase>-BLOCKERS.md`，继续做本 phase 中不依赖它的 task |
| 实测事实与文档矛盾 | **以实测为准**，把新事实追加进 `.planning/research/V5-SELECTION.md` 并注明日期 |
| 需要真实 API 密钥 | Phase 123-03（回灌闸门，已通过）与 Phase 128 端到端（需 ≥2 家厂商）。**停下来找业主**，不要用假 key 假装通过 |
| 某 plan 的设计明显有问题 | 在 `<phase>-BLOCKERS.md` 写清问题与建议，**先做完不受影响的部分**，再找业主 |
| DSH 上游行为与文档不符 | DSH 是 pre-release。记录实际行为，按实际行为实现，写进 BLOCKERS |

**永远不要为了让测试变绿而删测试、跳测试或放宽断言。**

---

## 9. 完成的定义

v5.0 完成 = 以下全部成立：

- [ ] 122–127 六个 phase 的所有 plan 的 `<verification>` 块全绿（128 为交付后增强，单独验收）
- [ ] `node scripts/gates/v5/run-gates.mjs` 输出 `6 passed, 0 failed`（Phase 128 后为 7）
- [ ] `123-DECISION.md` 结论为「回灌方案验证通过」
- [ ] 干净 Windows 机器上 PRD §2 的七个验收场景全部演示通过
- [ ] 仓库无明文密钥、无占位公钥、无 CDN 依赖
- [ ] `apps/flutter_app` 与 lawyer-desktop 未被修改
- [ ] `packages/ui-core/src/event-reducer.ts` 未被修改

律师人工闸门（HG-1 / HG-3）**不在此列**，保持 DEFERRED。
