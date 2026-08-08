---
phase: 109
slug: arena-service
status: complete
created: 2026-08-09
---

# Phase 109 — Context

> **Discuss phase was skipped.** All implementation choices are at the agent's discretion — use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

## Phase Goal

本地 HTTP+SSE 服务将引擎、acp-client、契约组装为可被桌面 app 消费的单元——绑定 127.0.0.1:8001，多流复用，输出边界与权限安全双重生效，子进程受控

## Requirements

- **SVC-01**: Local binding + token auth — 127.0.0.1:8001, non-localhost rejected, no-token rejected
- **SVC-02**: Endpoints — create/stream/cancel/user-action/status arena + OpenAPI docs
- **SVC-03**: SSE multiplexing — N agents' events on single SSE, metadata.agent_slot tagging
- **SVC-04**: Output boundary enforcement — ACP output filter, no meta/gateway/system noise to client
- **SVC-05**: Permission security — dangerous kinds (terminal/execute_code) rejected, no batch approve
- **SVC-06**: Subprocess control — liveness check + per-run timeout + partial-result acceptance
- **SVC-07**: SSE reconnection — buffer by run ID, resume from breakpoint, no dup/loss
- **SVC-08**: Staggered startup semaphore — prevent N agents initializing simultaneously
- **GATE-05**: Permission security test in CI — all green
- **GATE-06**: Orphan process test in CI — zero PID residue after cancel

## Success Criteria

1. `services/arena-service` 绑定 `127.0.0.1:8001`，本地 token auth 生效；非 localhost 连接被拒，无 token 请求被拒
2. 端点齐全：create arena / stream arena / cancel arena / user action / status arena，且有 OpenAPI 文档
3. N 个 agent 的流式事件在单条 SSE 连接上复用，每个事件带 `metadata.agent_slot`；客户端可按 slot 解复用
4. 输出边界在服务层强制执行——与 Gateway 相同的 ACP 输出过滤器，后端 meta/gateway/system 噪声不可到达客户端
5. 权限安全：dangerous kinds（`terminal` / `execute_code`）被立即拒绝，不存在 batch approve 路径；`_DANGEROUS_PERMISSION_KINDS` 原样保留
6. 子进程受控：liveness check + per-run timeout + partial-result acceptance；agent 崩溃/超时后 run 不卡死，partial results 被接受并标记
7. SSE 重连：客户端带 run ID 重连后从断点续传，事件不重复不丢失（buffer by run ID）
8. 错峰启动 semaphore 防止 N 个 agent 同时 `initialize` 导致竞争
9. 权限安全测试（GATE-05）与孤儿进程测试（GATE-06）在 CI 中运行且全绿——cancel 后零 PID 残留

## Key Decisions

All decisions at agent's discretion. Follow AGENTS.md binding architecture decisions, especially:
- **Local-only binding** — 127.0.0.1:8001, reject non-localhost connections
- **Token auth** — local token required for all requests
- **Output boundary** — same ACP output filter as Gateway, no meta/gateway/system noise
- **Dangerous permissions** — terminal/execute_code immediately rejected, no batch approve
- **Subprocess control** — liveness + timeout + partial-result acceptance
- **SSE reconnection** — buffer by run ID, resume from breakpoint
- **Staggered startup** — semaphore to prevent N agents initializing simultaneously

## Dependencies

- **Phase 108** (Arena Engine — Modes 3+4) — completed (Mode 1-4, ArenaEngine, cross-family)
- **Phase 106** (ACP fs Handler) — completed (FSSandbox, ReferenceSanitizer, output filter)
