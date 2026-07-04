# InkStatute Codex Backend Adapter (Prototype)

Codex backend adapter prototype proving BackendAdapter contract portability via
`codex exec --json` subprocess. Prototype only — `production_ready: false`,
`no_channel_io: true`.

The adapter returns platform objects only; ordinary-user WeCom delivery is owned
by `inkstatute_wecom_service`.
