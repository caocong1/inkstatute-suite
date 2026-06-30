# @inkstatute/web-chat

Embeddable, remote/thin web chat renderer for InkStatute `RunEvent`
streaming. The renderer is a pure TypeScript function over sanitized
SDK/API event records; it never embeds a local runtime, queue, database,
backend, or framework, and it is **not** live acceptance evidence.

## Status

- Default **off** — the renderer is opt-in and ships behind the
  `INKSTATUTE_PLATFORM_API_ENABLED` and `INKSTATUTE_WEB_SSE_CHANNEL_ENABLED`
  env gates (set on the platform API host and the Web/SSE channel
  respectively).
- The committed fixtures are **not** live acceptance and must not be cited
  as production readiness.
- No production web UI is provided. The renderer is a building block, not a
  full chat product.

## Boundary

```
Tauri / Electron / Flutter webview / browser
        |
        v
+-----------------------+
| @inkstatute/web-chat  |  <-- default-off, remote/thin, no local runtime
| (renderRunEvents)     |
+-----------------------+
        |
        v
+-----------------------+
| @inkstatute/          |
| platform-sdk-ts       |  <-- remote/thin SDK, no embedded runtime
| (PlatformApiClient)   |
+-----------------------+
        |
        v
+-----------------------+
| apps/platform_api     |  <-- default-off, INKSTATUTE_PLATFORM_API_ENABLED
| (PlatformApiApp)      |
+-----------------------+
        |
        v
+-----------------------+
| Injected RunRuntime   |  <-- platform-runtime (DefaultRunRuntime or other)
+-----------------------+
```

The renderer:

- Accepts `SseFrame`-shaped records (`{ event, id, data }`) and unwrapped
  `RunEvent` records.
- Returns DOM-free `RenderRecord` objects that a host view layer
  (React/Preact/lit-html/raw DOM/server template) can map into the
  desired presentation. The renderer **never** uses `innerHTML`,
  `outerHTML`, `document.write`, `eval`, or `new Function`.
- Escapes every visible text field (`<`, `>`, `&`, `"`, `'`).
- Rejects metadata that contains `raw_payload` / `raw_body` /
  `callback_body` style keys and rejects `message_delta` text that
  contains secret markers.

## Public surface

- `renderRunEvents(events)` — returns `{ records, summary }`.
- `escapeText(value)` — exposed for downstream hosts that want to apply
  additional formatting consistently.
- `ChatEventInput`, `ChatRenderResult`, `RenderRecord`, `RenderRole` —
  TypeScript types for hosts that consume the renderer.

The host view layer is responsible for turning `RenderRecord` into pixels
or strings; the renderer never builds HTML.

## Embedding guidance

| Host | How to embed |
|---|---|
| Tauri (webview) | Load `src/render.ts` via the bundle; pass SSE frames from `PlatformApiClient.streamRun` into `renderRunEvents`. |
| Electron (renderer process) | Same as Tauri; the renderer process keeps no runtime state, just React/Preact/lit-html views driven by `RenderRecord`. |
| Flutter webview | Use a small JS shim in the webview; forward SSE frames into `renderRunEvents` and serialize `RenderRecord` back to the Dart side. |
| Plain browser | Bundle with esbuild/rollup; call `renderRunEvents` from a worker or main thread. |

In every case the host **must**:

- Keep secrets in the platform API host, not the renderer. The renderer
  only sees sanitized event records.
- Avoid building HTML by string concatenation; map `RenderRecord` to
  framework primitives instead.
- Respect the default-off contract: do not enable the platform API or the
  Web/SSE channel in production without an operator gate.

## Configuration (operator side)

| Env var | Effect |
|---|---|
| `INKSTATUTE_PLATFORM_API_ENABLED` | Enables the platform API host that the SDK talks to. |
| `INKSTATUTE_WEB_SSE_CHANNEL_ENABLED` | Enables the Web/SSE channel that produces sanitized SSE frames. |
| `INKSTATUTE_CHANNEL_WRAPPER_WECOM_ENABLED` | Enables the WeCom channel wrapper. (Not used by the web chat renderer directly, but the WeCom lane is the parallel default-off channel.) |

The renderer itself has **no** runtime configuration. It is a pure
function over records.

## Not a production web UI

The renderer does not provide:

- A user account, session, or auth system.
- A production HTTP server, ASGI/WSGI host, or web server.
- A database, queue, or background job runner.
- A backend adapter, run runtime, or any other production logic.

The platform API host and the Web/SSE channel are themselves default-off
and fixture-grade. Treat this package as a small, embeddable building
block for clients that need to render sanitized `RunEvent` streams.

## Not live acceptance

The committed fixtures (`fixtures/run_events.json`) are **not** live
acceptance evidence. They are sanitized, default-off, reference-only
inputs that the Python contract test harness uses to prove the
renderer's boundary and shape.

## Tests

```bash
PYTHONPATH=apps/web_chat python -m unittest apps.web_chat.tests.test_web_chat_render
```

```bash
PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src:packages/channels/wecom/src:packages/channels/web_sse/src:apps/platform_api/src \
  python packages/contract-test-suite/scripts/run_contract_tests.py
```

The Python tests read the committed renderer source and the committed
fixture and assert the contract guarantees (no framework imports, no
local runtime imports, no `innerHTML` patterns, a real escape function,
sanitized fixture policy, full lifecycle coverage, boundary
rejection of `raw_payload` metadata and HTML in `message_delta`).
