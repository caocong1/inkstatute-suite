# InkStatute Provider Model Backend Adapter (Prototype)

Provider model backend adapter prototype proving BackendAdapter contract portability via
AsyncOpenAI lazy SDK import. Prototype only — `production_ready: false`,
`no_channel_io: true`, `invocation_mode: direct_llm`.

The adapter returns platform objects only; ordinary-user WeCom delivery is owned
by `inkstatute_wecom_service`.
