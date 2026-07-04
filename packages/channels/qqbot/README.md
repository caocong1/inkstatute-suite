# QQBot Channel Adapter

QQBot ChannelAdapter implementation proving ChannelAdapter portability beyond WeCom. Implements all 6 ChannelAdapter Protocol methods (channel_id, capabilities, verify_and_ack, normalize_inbound, deliver, health). Handles receive (single mode / webhook), send (text), and callback verification. Imports from channel-core (NOT from wecom_service). Fixture-only — no network IO.

The `qqbot_channel_enabled` feature flag defaults to `False`. When disabled, ACK and delivery are refused.

QQBot feedback maps to existing `FeedbackEvent.source` enum value `CARD_BUTTON` ("card_button") — no new enum values added.
