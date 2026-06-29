---
phase: 12-channel-interface-wecom-wrapper-web-sse-client-sdk
status: complete
created: 2026-06-29
---

# Phase 12 Pattern Map

## Target Files To Create

| Target | Role | Analog |
|---|---|---|
| `packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py` | WeCom `ChannelAdapter` wrapper | `services/wecom-service/src/wecom_service/*`, `FakeChannelAdapter` |
| `packages/channels/web_sse/src/inkstatute_channels_web_sse/adapter.py` | Fixture Web/SSE channel | `FakeChannelAdapter`, `RunEvent` streaming tests |
| `apps/platform_api/src/platform_api/app.py` | Pure platform API route handlers | `DefaultRunRuntime` tests |
| `apps/platform_api/openapi/platform-api.json` | Deterministic OpenAPI contract | JSON Schema package fixtures |
| `packages/platform-sdk-ts/src/index.ts` | Generated TypeScript SDK | Generated-from-contract pattern |
| `apps/web_chat/src/render.ts` | Embeddable chat event renderer | Fixture-driven frontend logic |

## Reusable Patterns

- Use `src/` Python package layout and stdlib-only runtime dependencies.
- Keep concrete packages under `packages/channels/*`; do not edit neutral runtime protocols unless a protocol gap blocks implementation.
- Treat all new lanes as default-off through config objects and exact env gates.
- Use refs/hashes in fixtures; never commit raw callback bodies, runtime payloads, media, logs, or secrets.
- Channel adapters normalize/deliver channel objects; runtime hosts submit through `RunRuntime`.

## Anti-Patterns

- Do not move or rewrite the production WeCom service.
- Do not let channel packages import concrete backend packages.
- Do not build a production web UI, account/session system, queue, database, or live HTTP server unless a plan explicitly requires it.
- Do not generate SDK files nondeterministically.
- Do not claim Web/SSE fixture evidence as live acceptance.

