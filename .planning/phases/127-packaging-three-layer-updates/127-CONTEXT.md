# Phase 127: Packaging & Three-Layer Updates - Context

**Gathered:** 2026-08-15
**Status:** Ready for execution
**Requirements:** ENG-05, PKG-11..15, GATE-13
**Depends on:** Phase 126 四门全绿

<domain>
## Phase Boundary

收口：把「开发机上能跑的东西」变成「律师电脑上双击就能用的东西」。
便携 Node、字体本地化、单 exe 安装包、首启向导、三层更新器、回滚门禁。

**本阶段是 v5.0 的交付闸。** 完成后应达到 PRD §2 的七个验收场景全部可演示。
</domain>

<decisions>
## 三层更新的分工（已定案）

| 层 | 节奏 | 机制 | 归属 |
|---|---|---|---|
| App | 静默检查 + 提示 | `tauri-plugin-updater` | PKG-15 |
| **引擎** | 检查 → 提示 → **用户确认** → 自动替换 | lockfile 装配 + 版本目录 + **冒烟闸** + 指针切换 | ENG-05 |
| 内容包 | 全自动，用户无感 | Phase 126-01 已实现 | 已完成 |

## 引擎更新七步（不变式：冒烟通过前 `current` 指针一次都不动）

```
1. 取版本  ── 拉 engine-lock.json（业主托管，约 40KB），比对 engine\current
2. 兼容闸  ── app 版本 ∈ lock.compatible_app_range，否则只提示升 app
3. 下载    ── 逐包下载 tarball，逐包校验 sha512（Phase 122-02 的 assemble）
4. 铺树    ── 展开到 engine\<新版本>\，写入 acp.cordis.yml
5. 冒烟    ── 启动新引擎跑 initialize → session/new → 退出（Phase 122-03 的 smoke_test）
              任一步失败即删除新目录，current 不动，用户无感
6. 切换    ── 冒烟通过后原子写 current，下次启动生效
7. 回滚    ── current 写回旧版本号；旧目录保留一代
```

**Phase 122 已经把第 3/4/5 步的能力做好了**，本阶段只是编排 + UI + 指针管理。

## Phase 122 遗留给打包阶段的两项瘦身（执行 127-03 时处理）

1. **构建主机的 node-pty prebuild 要剔除。**
   `engine-lock.json` 的 `prune` 目前只删 `darwin-x64` 与 `win32-arm64`，
   **保留了 `darwin-arm64`**——那是为了让 macOS 开发机能跑冒烟测试。
   Windows 安装包**不应**带 darwin 预编译，打包脚本必须额外剔除构建主机的那份，
   只留 `win32-x64`。做完断言 `node_modules/node-pty/prebuilds/` 下只有一个目录。

2. **评估剔除 AWS SDK。**
   `@aws-sdk/*`(22) + `@smithy/*`(9) = 31 包，占依赖树 15%，
   由 `dsh-llm-pi-ai` 的 Bedrock 支持带入，**本产品永不使用 Bedrock**。
   剔除前必须验证：pi-ai 在缺 AWS SDK 时是否只在**实际选用 bedrock 路由**时才报错，
   而非加载期就崩。验证方法：装配一份剔除后的引擎，跑冒烟 + 一次真实 deepseek 路由问答。
   **若加载期即报错则放弃剔除**，把这 15% 当作既定成本。

## 已知待修缺陷

| # | 缺陷 | 位置 | 本阶段修法 |
|---|---|---|---|
| D2 | Google Fonts CDN 中国大陆不可达，字体静默回退 | `packages/ui-core/src/themes/molv-tokens.css:7` | 移除 `@import`，字体本地化（PKG-12） |
| D3 | 依赖系统 Node | Flutter 版写死 `executable: 'node'` | 随包带 `node.exe`，绝对路径 spawn（PKG-11） |
| — | 占位签名公钥 | lawyer-desktop `tauri.conf.json` 的 `dW5zZXQtcmVwbGFjZS13aXRoLXNpZ25lci1wdWJrZXk=` | 换真实公钥（PKG-15） |

## 字体决策（PKG-12）

`molv-tokens.css` 声明的字体族：

```css
--serif: "Noto Serif SC", "Newsreader", Georgia, serif;
--sans:  "Noto Sans SC", -apple-system, "Segoe UI", system-ui, sans-serif;
--mono:  "Spline Sans Mono", "SF Mono", ui-monospace, monospace;
```

**完整 CJK 字体子集很大**（Noto Serif SC 完整版 > 10MB/字重）。方案：

1. **首选**：只内嵌拉丁部分（Newsreader / Spline Sans Mono，各约 100-200KB WOFF2），
   CJK 回退到 Windows 自带的**思源宋体/等线/微软雅黑**，把回退栈写得更精确：
   ```css
   --serif: "Newsreader", "Source Han Serif SC", "Noto Serif CJK SC", "SimSun", serif;
   --sans:  "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", system-ui, sans-serif;
   ```
2. **不做**：内嵌完整 CJK 字体（体积不可接受）。
3. **不做**：运行时按需下载字体（违反"断网可用"）。

**变更后必须真机核对**：Windows 上渲染效果与 lawyer-desktop 在联网时的效果差异可接受。
若差异不可接受，退而求其次做 CJK 子集（按 `ai-for-china-legal` 语料的字频取前 6000 字）。
</decisions>

<risks>
| # | 风险 | 缓解 |
|---|---|---|
| 1 | 字体回退后中文观感下降 | 真机核对；不可接受则做字频子集 |
| 2 | 引擎更新中途断网留半成品 | Phase 122-02 的 assemble 已用 `.partial` 临时目录 + 全成功才 rename |
| 3 | 冒烟通过但真实使用崩 | 冒烟只保基本可用；引擎版本保留一代，设置里提供"回退到上一版本" |
| 4 | 安装包体积过大 | node.exe ~37MB(zip) + 引擎 ~42MB + 内容包 + app ≈ 120-150MB。可接受 |
| 5 | Windows Defender 误报未签名 exe | 代码签名证书由业主准备；无证书时在 README 写明首次运行需点"仍要运行" |
| 6 | 首启向导后引擎起不来 | 向导末尾即跑一次冒烟，失败当场给中文原因与重试 |
</risks>
