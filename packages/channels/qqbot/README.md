# QQBot Channel Adapter

QQBot ChannelAdapter implementation proving ChannelAdapter portability beyond WeCom. Implements all 6 ChannelAdapter Protocol methods (channel_id, capabilities, verify_and_ack, normalize_inbound, deliver, health). Handles receive (single mode / webhook), send (text/markdown/card/rich media), and callback verification. Imports from channel-core (NOT from wecom_service).

## Feature flag → config mapping (host responsibility)

`RuntimeFeatureFlags.qqbot_channel_enabled` and `QQBotChannelConfig.enabled` both default to `False`. Hosts map the platform flag into adapter config when constructing the adapter:

```python
flags = RuntimeFeatureFlags()  # or load from host config
adapter = QQBotChannelAdapter(
    QQBotChannelConfig(
        enabled=flags.qqbot_channel_enabled,
        # ... secret refs ...
    ),
    token_manager=...,  # required for live IO
    transport=...,      # FakeMessageTransport in CI; UrllibMessageTransport in production
)
```

The adapter gates solely on `QQBotChannelConfig.enabled` (plus injected `token_manager` and `transport` via `_live_io_ready()`). It does **not** import `RuntimeFeatureFlags`. When the gate is off, ACK/delivery are refused and metadata stays `fixture_only=True` / `network_io=False` so the Phase 43 fixture loop remains CI-green.

## Real IO (flag-gated)

When `enabled=True` and both `token_manager` and `transport` are injected, capabilities advertise `fixture_only=False` / `network_io=True` with `ack_strategy=op12_plus_interaction_put`. `health()` reports presence-only (`token_manager_present`, `transport_present`, `live_io_ready`) and never calls `get_token()` by default. Live OpenAPI calls use injectable Fake transports in tests and `Urllib*` transports in production — package `dependencies=[]` (stdlib only).

QQBot feedback maps to existing `FeedbackEvent.source` enum value `CARD_BUTTON` ("card_button") — no new enum values added.
