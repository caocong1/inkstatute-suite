# InkStatute QQBot Service

InkStatute-owned QQBot webhook host package. This host will own the HTTP edge,
secret resolution at process edge, and wiring of channel/session/feedback
composition in later phases (69–70).

Ownership boundary:

- `inkstatute_channels_qqbot` owns Protocol IO (verify/normalize/deliver).
- This host package owns deployable composition and process-edge concerns.
- ADAPTER-04: no `wecom_service` imports on the QQBot host path.
- Live-IO feature flags default OFF.
- Secrets are stored as references only; raw values are never committed.

Phase 68 delivers the empty-deps skeleton and safety baseline only — no webhook
composition yet.

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

1. **Flag → config:** `RuntimeFeatureFlags.qqbot_channel_enabled` maps onto
   `QQBotChannelConfig.enabled`. `QQBotHostConfig.enabled` alone cannot enable
   the channel.
2. **Live injection:** `token_manager` and `transport` are injected into
   `QQBotChannelAdapter` only when the platform flag is ON **and** both deps are
   available. When the flag is OFF, caller-supplied transports are stripped so
   `_live_io_ready()` stays False.
3. **Explicit DI:** `DefaultRunRuntime` is constructed with
   `channels=(adapter,)` — no auto-discovery inside `platform-runtime`.

### Disabled composed path (HOST-03)

When `qqbot_channel_enabled` is OFF, the composed adapter refuses live IO:
`verify_and_ack` returns HTTP 503 / `accepted=False`, `deliver` is refused, and
OpenAPI transports are never invoked (even if Fake transports were mistakenly
passed into the factory — they are stripped). Capabilities report
`network_io=False` / `fixture_only=True`.

Webhook HTTP composition remains Phase 70.
