# Phase 122 总结：引擎装配管线换血

## 目标

把 V4 的引擎构建管线（克隆 DSH 源码 + pnpm 构建 + 170MB zip）换成按 npm lockfile 在空目录中铺平依赖树的 Rust 装配器，并修复 V4 遗留的 ACP 持久化根路径缺陷。

## 成果

### Plan 122-01（已完成并提交）

- `engines/dsh-pin.txt` 改为 npm 精确版本（16 个 DSH 包均 `0.1.0-rc.6`）。
- `scripts/gen-engine-lock.mjs` 生成 `engines/engine-lock.json`（196 个包，3 个嵌套依赖）。
- `engines/acp.cordis.yml` 修复：
  - `persistenceRoot` 使用 `!!js process.env.DSH_HOME + '/sessions'`。
  - `persistenceCompression: none`、`packChunks: false`。
  - 多供应商 `dsh-llm-pi-ai` 配置，新增智谱（`zhipu`）通义（`qwen-token-plan-cn`）显式声明。
- `scripts/build_dsh_release.sh` 退役为 `.deprecated`。
- `engines/releases/engine-manifest.json` 删除，目录保留 `.gitkeep`。

### Plan 122-02

- 新增 Rust 模块：
  - `apps/desktop/src-tauri/src/engine/mod.rs`（`EngineError`）。
  - `apps/desktop/src-tauri/src/engine/lock.rs`（lock 解析与 SHA-512 校验）。
  - `apps/desktop/src-tauri/src/engine/assemble.rs`（并发下载、完整性校验、安全解压、partial 装配）。
  - `apps/desktop/src-tauri/src/engine/paths.rs`（应用数据路径、引擎版本指针）。
  - `apps/desktop/src-tauri/src/engine/smoke.rs`（`smoke_test` API）。
- `Cargo.toml`：移除 `docx-rs`、`pdf-extract`；新增 `reqwest`、`futures`、`flate2`、`tar`、`base64`、`thiserror`。
- `src/lib.rs` 注册 `pub mod engine`。
- `src/workspace/parser.rs` 移除 `docx-rs`/`pdf-extract` 依赖，改为返回标记文本。
- 集成测试：
  - `tests/engine_assemble_test.rs`（`#[ignore]` 真实装配）。
  - `tests/engine_smoke_test.rs`（`#[ignore]` 真实 engine 冒烟）。

### Plan 122-03

- `scripts/gates/v5/engine-assembly.mjs`：
  - 校验 `dsh-pin.txt` 无 dist-tag。
  - 校验 `acp.cordis.yml` 无 `${DSH_HOME}`、含 `process.env.DSH_HOME`、`packChunks: false`、`persistenceCompression: none`、无裸露 `sk-...` 密钥。
  - 校验 `engine-lock.json` schema/包结构/完整性/cordis sha256。
  - 运行 `cargo check`、`cargo test`、`cargo test -- --ignored`。
  - 扫描仓库无 plaintext API keys（排除规划文档与测试文件）。
- `scripts/gates/v5/run-gates.mjs`：
  - 默认执行全部已注册 gate，支持 `node run-gates.mjs engine-assembly` 单独运行。
  - 输出 `[PASS|FAIL] <gate-name> (<ms>ms)` 与最终 `N passed, M failed`。

## 验证

```bash
node scripts/gates/v5/run-gates.mjs
# [PASS] engine-assembly (≈45s)
# 1 passed, 0 failed
```

- `cargo check` 通过。
- `cargo test -- --test-threads=1` 通过。
- `cargo test -- --ignored --test-threads=1` 通过（真实装配 + 真实 engine `initialize` → `session/new`）。
- `cargo tree` 无 `docx-rs`、`pdf-extract`。
- `grep -rnE '"(npm|pnpm|yarn)"' apps/desktop/src-tauri/src/engine/` 无运行时包管理器调用。

## 已知取舍

- `node-pty` prebuilds 保留 `win32-x64`（目标平台）与构建主机平台（如 `darwin-arm64`），以便 macOS 开发机跑通冒烟测试。Windows 安装包将在 Phase 127 仅保留 `win32-x64`。
- 智谱（`zhipu`）在 `pi-ai` 没有预装 catalog，故按 OpenAI-compatible 网关显式声明 `api`、`baseURL` 与 `models`。
- 冒烟测试在 `session/new` 成功后主动 `kill` 子进程；DSH 在 stdin 关闭后不会自动退出，但 kill 可保证无孤儿。

## 输出物

- `engines/engine-lock.json`
- `engines/acp.cordis.yml`
- `apps/desktop/src-tauri/src/engine/*`
- `apps/desktop/src-tauri/tests/engine_*_test.rs`
- `scripts/gates/v5/*`

## 状态

- Phase 122 已完成，所有 GATE-11 条件满足，准备进入 Phase 123（Engine Supervisor + Real Path）。
