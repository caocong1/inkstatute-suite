---
phase: 106
slug: acp-fs-handler
status: complete
created: 2026-08-08
---

# Phase 106 — Context

> **Discuss phase was skipped.** All implementation choices are at the agent's discretion — use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

## Phase Goal

ACP agent 可自主读取用户选定目录内的参考文件，且路径沙箱从第一天起就不可逃逸——遍历、符号链接、绝对路径、非法扩展名、超大文件全部被拒；Gateway 路径不受影响

## Requirements

- **FS-01**: `acp-client` advertises `clientCapabilities.fs.readTextFile: true` at `initialize`
- **FS-02**: Inbound `fs/read_text_file` requests routed to registered handler
- **FS-03**: Path sandboxing (resolve + prefix-check + symlink rejection + extension allowlist + size cap)
- **FS-04**: Backward compatible with Gateway path (no `client_capabilities` passed)
- **SAFE-05**: Prompt injection sanitization for reference files
- **GATE-04**: fs/* sandbox escape tests (path traversal, symlinks, absolute paths)

## Success Criteria

1. `packages/acp-client` 在 `initialize` 时声明 `clientCapabilities.fs.readTextFile: true`，且入站 `fs/read_text_file` 请求被路由到已注册的 handler（未注册时返回明确错误而非崩溃）
2. 路径沙箱五重防护全部生效：resolve 规范化 + prefix-check 根目录约束 + symlink rejection + 扩展名 allowlist + size cap；有测试覆盖 path traversal（`../`）、symlink escape、绝对路径越界、非 allowlist 扩展名、超大文件五种攻击向量
3. Gateway 路径向后兼容：不传 `client_capabilities` 时 `acp-client` 不声明 fs 能力，Gateway 行为零变化，现有 34 gate 全绿
4. 参考文件在交付给 agent 前经过 prompt injection 消毒（分隔符包裹 + 模式检测 + 检测日志），消毒后的内容可安全注入 agent 上下文
5. fs/* 沙箱逃逸测试套件（GATE-04）在 CI 中运行且全绿

## Key Decisions

All decisions at agent's discretion. Follow AGENTS.md binding architecture decisions, especially:
- **Output boundary is enforced twice**: at the ACP event bridge and at the Gateway
- **Permission requests must never be auto-approved server-side**
- **Contract logs prefer references such as `raw_payload_ref`**
- **Legal-specific fields belong in `industry_context`**

## Dependencies

- **Phase 105** (Arena Contract Extension) — completed
