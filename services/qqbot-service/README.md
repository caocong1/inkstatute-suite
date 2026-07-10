# InkStatute QQBot Service

InkStatute-owned QQBot webhook host package. Owns the HTTP edge, secret
resolution at process edge, dual-knob runtime wiring, and ACK-first webhook
composition over package Protocol methods.

Ownership boundary:

- `inkstatute_channels_qqbot` owns Protocol IO (verify/normalize/deliver).
- This host package owns deployable composition and process-edge concerns.
- ADAPTER-04: no `wecom_service` imports on the QQBot host path.
- Live-IO feature flags default OFF.
- Secrets are stored as references only; raw values are never committed.

## Secret references (SAFE-02)

`QQBotHostConfig` stores only `*_ref` fields. Raw secret values must never be
assigned onto the config object. Resolve values at process edge with
`resolve_secret_ref(ref, env)` using an injected env mapping (callers may pass
`os.environ` in later phases; the resolver itself never reads `os.environ`).

### Ref schemes

| Ref form | Resolution |
|----------|------------|
| `None` / empty | `None` (fail closed) |
| `env:VAR_NAME` | `env["VAR_NAME"]` |
| bare env key name (e.g. `MY_VAR`) | `env["MY_VAR"]` if present |
| `secret://qqbot/…` | mapped value env key (table below) |
| unknown scheme/path | `None` (fail closed) |

### `secret://` → value env map

| Ref | Value env var |
|-----|---------------|
| `secret://qqbot/app-id` | `INKSTATUTE_QQBOT_APP_ID` |
| `secret://qqbot/app-secret` | `INKSTATUTE_QQBOT_CLIENT_SECRET` |
| `secret://qqbot/token` | `INKSTATUTE_QQBOT_TOKEN` |
| `secret://qqbot/bot-secret` | `INKSTATUTE_QQBOT_BOT_SECRET` |

Config `from_env` reads only `INKSTATUTE_QQBOT_CHANNEL_ENABLED` and
`INKSTATUTE_QQBOT_*_REF` keys. Planted raw value keys are ignored.

## Runtime wiring (Phase 69)

Host factory (`qqbot_service.wiring`) owns dual-knob mapping and live injection:

1. **Dual-knob AND → config:** `QQBotChannelConfig.enabled` is
   `flags.qqbot_channel_enabled and host_config.enabled` (both default OFF).
   Either knob alone cannot enable the channel.
2. **Live injection:** `token_manager` and `transport` are injected into
   `QQBotChannelAdapter` only when the composed channel is ON **and** both deps
   are available. When either knob is OFF, caller-supplied transports are
   stripped so `_live_io_ready()` stays False. Env auto-build of
   `TokenManager` also requires an explicit `token_transport` (fail closed —
   never silent `UrllibTokenTransport`).
3. **Explicit DI:** `DefaultRunRuntime` is constructed with
   `channels=(adapter,)` — no auto-discovery inside `platform-runtime`.

### Disabled composed path (HOST-03)

When `qqbot_channel_enabled` is OFF, the composed adapter refuses live IO:
`verify_and_ack` returns HTTP 503 / `accepted=False`, `deliver` is refused, and
OpenAPI transports are never invoked (even if Fake transports were mistakenly
passed into the factory — they are stripped). Capabilities report
`network_io=False` / `fixture_only=True`.

## Webhook composition path (Phase 70)

Thin host composition over package Protocol methods:

1. **ACK-first:** `verify_and_ack` → HTTP op=13 challenge or `{"op":12}` body ACK
   returns before heavy agent/ingress work (HOST-02).
2. **Post-ACK:** scheduled thunk runs normalize →
   `QQBotRuntimeIngress.handle_callback` (messages) or
   `handle_feedback_callback` (INTERACTION) →
   `runtime.output_boundary` → `adapter.deliver` (HOST-01).
3. **HTTP edge:** `QQBotWebhookServer` (stdlib `BaseHTTPRequestHandler`) reads
   `Content-Length` body bytes **once** from `rfile` and delegates to
   `handle_qqbot_webhook_request` — never re-serialize JSON for signature verify.

### Endpoint

`POST /qqbot/callback`

### Public exports

- `handle_qqbot_webhook_request` — pure handler (unit-testable, no port bind)
- `QQBotWebhookServer` — stdlib HTTP wrapper
- `build_qqbot_wired_runtime` — dual-knob DI factory (Phase 69)

### Fake unit tests (no live QQ)

```bash
PYTHONPATH="services/qqbot-service/src:packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:services/feedback-service/src" \
  python3 -m unittest discover -s services/qqbot-service/tests -v
```

Suites: `test_webhook_ack_first`, `test_webhook_composition`,
`test_webhook_http_raw_body` (plus Phase 68–69 host tests).

### Out of scope here

- Phase 71: smoke `--dry-run` Protocol-path hardening (`scripts/smoke_test.py`)
- Phase 72: live QQ `--live` HUMAN GATE — never auto-claimed from CI
