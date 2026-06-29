# inkstatute-channels-web-sse

Fixture-grade Web API / SSE `ChannelAdapter` implementation for the InkStatute agent platform.

This package exists to prove channel neutrality — that any non-WeCom channel can be plugged into the same platform contract runtime — without committing a production web stack, a real HTTP server, or live customer data.

## Status

- Default **off** behind `INKSTATUTE_WEB_SSE_CHANNEL_ENABLED` (truthy values: `1`, `true`, `yes`).
- The adapter is **fixture-only**: it does not bind ports, send network requests, or store raw inbound payloads.
- The fixture evidence is **not** live acceptance and **must not** be cited as production readiness.

## Public Surface

- `WebSseChannelConfig` — channel-local configuration with only refs to external session secrets.
- `WebSseChannelAdapter` — `ChannelAdapter` implementation that normalizes Web/Form messages into platform `AgentTurn` / `FeedbackEvent` and records sanitized `ChannelDelivery` results.
- `encode_sse_event` — deterministic `RunEvent` -> Server-Sent Events frame encoder.

## Boundaries

- No backend imports. The channel adapter is a runtime-side object that submits through `RunRuntime`; it must not import `BackendAdapter`, `backends`, or `inkstatute_backends_hermes`.
- No raw payload fields. Inbound payloads must carry refs/hashes; keys that look like `raw_payload`, `raw_body`, or `callback_body` are rejected at the boundary.
- No framework dependency. The package uses only the Python standard library plus the platform runtime protocols.

## Layout

```
packages/channels/web_sse/
+- pyproject.toml
+- README.md
+- src/inkstatute_channels_web_sse/
|  +- __init__.py
|  +- adapter.py
|  +- config.py
|  +- sse.py
+- fixtures/
|  +- multichannel_web_sse.json
+- tests/
   +- test_web_sse_channel.py
```
