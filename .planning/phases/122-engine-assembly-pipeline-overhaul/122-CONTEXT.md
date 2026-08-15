# Phase 122: Engine Assembly Pipeline Overhaul - Context

**Gathered:** 2026-08-15
**Status:** Ready for execution
**Requirements:** ENG-01, ENG-02, ENG-03, ENG-04, GATE-11

<domain>
## Phase Boundary

把引擎装配从「克隆 DSH 源码 + pnpm 构建 + 170MB zip」换成「按 npm lockfile 铺平依赖树」，并修复 V4 遗留的 ACP 配置缺陷。

**本阶段不做**：不写 Rust 引擎主管（Phase 123）、不接前端（Phase 125）、不做更新器 UI（Phase 127）。
本阶段只交付「一条能从空目录装出可启动引擎的管线」。

**为什么排第一**：它是所有后续阶段的物理前提，且不依赖 UI、不依赖真实 API key，最容易独立验证。
</domain>

<decisions>
## Implementation Decisions

### 已由实测定案（不需要再调研，见 `.planning/research/V5-SELECTION.md`）

1. **npm 装配可行**：87 包 / 9 秒 / 85MB，用未经修改的 `engines/acp.cordis.yml` 直接启动，`initialize` → `session/new` 全通。
2. **lockfile 树全平**：v3 格式 104 条，**零嵌套 `node_modules`**，100% 带 `resolved` + sha512 `integrity`。
3. **必须钉精确版本**：`@deepseek-ai/dsh-*` 的 `latest` 指向 `0.0.1-rc.1`（旧），`next` 才是 `0.1.0-rc.6`。**禁止在任何地方使用 dist-tag。**
4. **`${DSH_HOME}` 不被 Cordis 展开**：会建出字面量目录。修法 `!!js process.env.DSH_HOME + '/sessions'` 已验证。
5. **体积**：85MB 中 58MB 是 `node-pty/prebuilds` 四平台预编译；只留 `win32-x64` 后约 42MB。

### Claude's Discretion（执行时可自行决定）

- Rust 装配器放在 `apps/desktop/src-tauri/src/engine/` 下的新模块。
- 并发下载度数自定（建议 8），但必须逐包校验 sha512 后才落盘。
- `engine-lock.json` 生成脚本用 Node 写（仓库已有 Node 工具链），放 `scripts/`。

### 硬约束（不得违反）

- **不得修改 `apps/flutter_app/`**（冻结，只读参照）。
- **不得在任何配置、脚本、日志中写入 API 密钥。**
- 装配器**运行时不得依赖 npm / pnpm / yarn**——只用 HTTP + sha512 + tar.gz 解包。
- registry 基址必须可配，默认 `https://registry.npmmirror.com`，回退 `https://registry.npmjs.org`。
</decisions>

<code_context>
## Existing Code

| 对象 | 路径 | 处置 |
|---|---|---|
| 旧 pin 文件 | `engines/dsh-pin.txt` | **改写**：git commit → npm 版本 + 包清单 |
| 旧构建脚本 | `scripts/build_dsh_release.sh` | **退役**：删除或改名 `.deprecated`，并在文件头注明被 `scripts/gen-engine-lock.mjs` 取代 |
| ACP 组合配置 | `engines/acp.cordis.yml` | **修改**：persistenceRoot / packChunks / persistenceCompression / 供应商块 |
| 旧引擎清单 | `engines/releases/engine-manifest.json` | **删除**（被 `engine-lock.json` 取代） |
| Tauri Rust 工程 | `apps/desktop/src-tauri/` | **新增模块**：`src/engine/` |
| Cargo 依赖 | `apps/desktop/src-tauri/Cargo.toml` | **增**：`reqwest`(stream,json) · `flate2` · `tar` · `sha2`(已有) · `futures`；**删**：`docx-rs` · `pdf-extract` |

## 组合包清单（15 个，全部钉 `0.1.0-rc.6`）

```
@deepseek-ai/dsh-acp-demo                 # 入口，bin 在 lib/bin.js
@deepseek-ai/dsh-llm-deepseek             # 将在 ENG-04 中被 dsh-llm-pi-ai 取代或并存
@deepseek-ai/dsh-sandbox-local
@deepseek-ai/dsh-sandbox-policy
@deepseek-ai/dsh-subprocess-local
@deepseek-ai/dsh-bash-sandbox
@deepseek-ai/dsh-user-approval
@deepseek-ai/dsh-token-meter
@deepseek-ai/dsh-compaction-basic
@deepseek-ai/dsh-session-projection
@deepseek-ai/dsh-fs-sandbox
@deepseek-ai/dsh-fs-observation-policy
@deepseek-ai/dsh-tool-fs
@deepseek-ai/dsh-tool-todo
@deepseek-ai/dsh-repeat-tool-reminder
```

多供应商额外包：`@deepseek-ai/dsh-llm-pi-ai@0.1.0-rc.6`

## 引擎启动形态（实测）

```bash
node <engineDir>/node_modules/@deepseek-ai/dsh-acp-demo/lib/bin.js \
     --config <engineDir>/acp.cordis.yml
# 工作目录 = engineDir
# 环境：DSH_HOME=<绝对路径>, <PROVIDER>_API_KEY=<密钥>
```

握手预期输出：

```json
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":1,"agentInfo":{"name":"deepseek-harness-acp","version":"0.0.1"},"agentCapabilities":{"promptCapabilities":{"image":false,"audio":false,"embeddedContext":false}},"authMethods":[]}}
```
</code_context>

<research>
## 复现命令（验证环境用）

```bash
mkdir -p /tmp/engine-probe && cd /tmp/engine-probe && npm init -y
V=0.1.0-rc.6
set --
for p in dsh-acp-demo dsh-llm-deepseek dsh-llm-pi-ai dsh-sandbox-local dsh-sandbox-policy \
         dsh-subprocess-local dsh-bash-sandbox dsh-user-approval dsh-token-meter \
         dsh-compaction-basic dsh-session-projection dsh-fs-sandbox \
         dsh-fs-observation-policy dsh-tool-fs dsh-tool-todo dsh-repeat-tool-reminder; do
  set -- "$@" "@deepseek-ai/$p@$V"
done
npm install "$@" --no-audit --no-fund
```

lockfile 结构断言：

```bash
python3 -c "import json;d=json.load(open('package-lock.json'));p=d['packages'];\
print('entries',len(p));\
print('nested',sum(1 for k in p if k.count('node_modules')>1));\
print('missing_resolved',sum(1 for k,v in p.items() if k and not v.get('resolved')))"
# 期望：nested=0, missing_resolved=0
```
</research>

<risks>
## Risks

| # | 风险 | 缓解 |
|---|---|---|
| 1 | npm 上的 rc 版本被 unpublish 或改动 | lockfile 里有 sha512，校验失败即拒绝装配；把生成的 `engine-lock.json` 提交进仓库 |
| 2 | `node-pty` 裁剪破坏运行时（bash 工具依赖 pty） | 裁剪后必须跑冒烟：`initialize` + `session/new` + 一次 bash 工具调用路径存在性检查 |
| 3 | 不同 registry 的 tarball URL 域名不同 | 装配器按包名 + 版本自行拼 URL，不直接信任 lockfile 里的域名；只信任 `integrity` |
| 4 | Windows 长路径 | 装配目标目录层级浅（树全平），无嵌套 `node_modules`，风险低 |
</risks>
