# InkStatute WeCom Service

This package contains dependency-light primitives for the InkStatute-owned V2 WeCom service boundary.

It owns ordinary lawyer-user callback receipt, ACK behavior, sanitized callback normalization, outbound send envelope construction, feedback callback receipt, and assistant output policy. It does not call live WeCom, Hermes, databases, queues, or runtime secret stores in repo tests.

Hermes lawfirm is an agent backend behind the adapter boundary. Hermes gateway, operator UI, update, command, help, debug, and lifecycle notices must not be sent directly to ordinary WeCom users.

All ordinary-user outbound envelopes are built by this service and pass through the assistant output boundary first. The boundary may allow legal business replies unchanged, rewrite backend lifecycle notices into InkStatute-owned service wording, or block internal/debug/secret-bearing text. It must not semantically rewrite legal conclusions, citations, factual assumptions, risk judgments, jurisdiction conclusions, liability conclusions, or user-provided case facts.

## Channel config apply (operator store)

WeCom channel enablement is a dual default-OFF AND of:

1. Platform flag `RuntimeFeatureFlags.wecom_channel_enabled` (deploy-owned; read-only from the admin console)
2. Host/doc `channels.wecom.enabled` from `OperatorConfigStore` (or env bootstrap when the store file is absent)

Helpers live in `wecom_service.channel_wiring` (`build_wecom_channel_config`, `load_wecom_channel_config`). Store wins when the configured store path exists; env `from_env` is fallback only. **Restart the WeCom host process to apply store changes** — PUT persists refs/host knobs but does not hot-reload in-memory adapters.
