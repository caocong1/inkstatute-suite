---
phase: 115-skill-content-auto-update
milestone: v4.0
created: 2026-08-14
mode: auto
prior_phase: 114-skill-pipeline-dsh-target
requirements: SKL-04
---

# Phase 115: Context — Skill Content Auto-Update

## Phase goal

app 侧内容包更新器上线：启动与手动检查两条路径，manifest 比对 → 原子下载解压 → sha256 校验 → current 指针切换，失败自动回滚 last-good，离线降级；全程零用户操作、零重启（DSH skill watcher 生效）。

## Locked decisions (from prior phases, PRD, AGENTS.md)

1. **内容包 = 唯一自动更新层**（manifest + sha256 + 原子切换 + 回滚）；app 与引擎层禁自动。
2. **manifest schema** 已在 Phase 114 定义：`apps/flutter_app/lib/content/manifest_schema.dart` — `ContentManifest.fromJson()` / `isCompatibleWith()` / `totalSkillCount` / `domainNames`。
3. **min_engine_version = `47f943859b`** — 更新器必须拒绝不匹配的引擎版本。
4. **Zip 结构**：`legal-skills-content-<version>.zip` 包含 `content-manifest.json` + `<domain>/<skill-name>/SKILL.md` 树。
5. **`CONTENT_RELEASE_URL`** 环境变量是可配置的内容源 — Phase 114 发布脚本支持。
6. **`customSkillDirs`** 指向 `~/.agent-presets/<domain>/skills` — 更新器解包到此路径。
7. **DSH skill watcher** 在会话中刷新目录（`depth: 1` chokidar watcher）— 零重启验证依赖此行为。
8. **DSH 钉版本 + 禁自动升级引擎** — 内容包更新不触碰引擎层。
9. **V3.x 平台冻结** — 更新器只在 Flutter app 中实现。
10. **安全**：sha256 链式校验（manifest 中每个 skill 的 sha256 + zip 本身的 sha256 sidecar）；降级攻击（更低 release_version）被拒。

## Gray areas (auto-resolved)

### [auto] GA-1: 内容源 URL 配置方式

**Question:** `CONTENT_RELEASE_URL` 如何在 app 中配置？

**Selected:** 环境变量 + 设置页可覆盖

**Rationale:** 开发时用环境变量，生产时通过设置页配置。默认值指向 GitHub Release。app 启动时读环境变量，设置页可覆盖并持久化到本地配置文件。

### [auto] GA-2: 本地内容包存储路径

**Question:** 内容包解压到哪？

**Selected:** `%LOCALAPPDATA%\InkStatute\content\skills\<release>\` + `current` 指针文件

**Rationale:** Windows 标准 app 数据目录。`current` 文件指向当前激活的 release 目录。`last-good` 文件指向上一个成功的 release（回滚用）。DSH `customSkillDirs` 指向 `current` 指针指向的目录。

### [auto] GA-3: 下载实现方式

**Question:** 用什么 HTTP 客户端下载 zip？

**Selected:** Dart `http` 包 + `dart:io` 文件操作

**Rationale:** Flutter 生态标准。`http` 包已在 PRD 中列为允许的依赖。下载到临时文件，校验 sha256，解压到目标目录。

### [auto] GA-4: 原子性保证方式

**Question:** 如何保证原子切换？

**Selected:** 解压到临时目录 → 全量 sha256 校验 → 原子 rename → 更新 current 指针 → 清理旧版本

**Rationale:** 文件系统 rename 是原子操作（同一卷上）。先解压到 `<release>-staging/`，校验通过后 rename 为 `<release>/`，然后更新 `current` 文件。如果任何步骤失败，staging 目录被清理，current 指针不变。

### [auto] GA-5: 离线降级行为

**Question:** 离线时如何降级？

**Selected:** 用 `last-good` 指针指向的版本启动，设置页显示"技能更新不可用"

**Rationale:** 不阻塞会话功能。如果 `current` 指针存在且目录完整，用 current。如果 current 损坏，回退到 last-good。如果两者都不存在，用 app 内置的 fallback skills（Phase 113 synthetic fixtures）。

### [auto] GA-6: 更新触发时机

**Question:** 何时触发更新检查？

**Selected:** 启动时自动检查 + 设置页手动检查按钮

**Rationale:** PRD SKL-04 明确。启动时后台异步检查（不阻塞 UI）。设置页提供手动检查按钮。两条路径都走同一个 `ContentUpdater.checkAndUpdate()` 方法。

### [auto] GA-7: 版本比对逻辑

**Question:** 如何判断有更新？

**Selected:** 比对 `release_version` 字段（semver 比较）

**Rationale:** 远程 manifest 的 `release_version` > 本地 current 的 `release_version` → 有更新。拒绝更低版本（降级攻击防护）。`min_engine_version` 必须匹配当前引擎版本。

## Deferred ideas

- 增量更新（只下载变化的 skill 文件）→ 后续 milestone
- P2P 分发 → 不考虑
- 自动回滚到 last-good 的健康检查 → Phase 120 收敛时评估

## Downstream guidance

### For researcher (115-RESEARCH.md)

1. 检查 DSH skill watcher 的刷新行为 — 确认 `customSkillDirs` 变更后 watcher 自动发现新技能
2. 检查 Flutter `http` 包是否已在 `pubspec.yaml` 中，或需要添加
3. 检查 Windows `%LOCALAPPDATA%` 路径在 Dart 中的获取方式
4. 检查 `dart:io` 的 rename 原子性保证
5. 评估 GitHub Release 作为内容源在中国大陆网络环境的可用性
6. 检查 Phase 114 `manifest_schema.dart` 的完整 API

### For planner

1. Plans 应覆盖：ContentUpdater 核心 → 下载+解压+校验 → 原子切换+回滚 → 离线降级 → 设置页 UI → 测试
2. 所有改动在 `apps/flutter_app/` 中
3. 测试用 mock HTTP server + 本地文件系统
4. 零重启验证：测试 DSH skill watcher 在目录变更后自动刷新
5. 安全测试：伪造 manifest、截断 zip、降级版本、不匹配引擎版本

## Success criteria (from ROADMAP.md)

1. 启动时 + 设置页手动检查拉 manifest，版本比对
2. 原子性：解压到临时目录 → sha256 校验 → current 指针切换 → 清理旧版本（保留 last-good）；失败回滚
3. 离线/拉取失败：用 last-good 启动，设置页显示"技能更新不可用"
4. 更新后零重启验证：技能目录 watcher 刷新
5. RESEARCH 结论落 `115-RESEARCH.md`：GitHub Release 在中国大陆可用性 + 备选方案
6. 安全：sha256 链式校验，伪造/截断/降级包被拒
