---
phase: 12-channel-interface-wecom-wrapper-web-sse-client-sdk
status: complete
researched: 2026-06-29
source: inline codex research
---

# Phase 12 Research: Channel Interface + WeCom Wrapper + Web/SSE + Client SDK

## Question

What existing code and constraints shape Phase 12?

## Source Anchors

- `.planning/REQUIREMENTS.md` maps Phase 12 to `REQ-channel-adapter-interface`, `REQ-multichannel-fixture`, and `REQ-client-embedding-surface`.
- `docs/architecture/agent-platform-north-star.md` defines `ChannelAdapter` as the channel seam and states channels must not call backend adapters directly.
- `.planning/drafts/agent-platformization-plan-v5.md` names `INKSTATUTE_CHANNEL_WRAPPER_WECOM_ENABLED` and `INKSTATUTE_WEB_SSE_CHANNEL_ENABLED` as default-off gates.
- `packages/platform-runtime/src/platform_runtime/protocols.py` already defines `ChannelAdapter`, `RawInbound`, `AckResponse`, `InboundNormalized`, `ChannelDelivery`, and `DeliveryResult`.
- `packages/platform-runtime/src/platform_runtime/runtime.py` owns backend submission through `RunRuntime`; channel adapters should call runtime hosts, not backends.
- `services/wecom-service/src/wecom_service/protocol.py`, `normalization.py`, and `sender.py` provide sanitized WeCom primitives that can be wrapped.
- Phase 10 fake runtime/channel tests provide dependency-injected fake patterns; Phase 11 concrete backend package provides the concrete-package layout pattern.

## Implementation Findings

### WeCom Wrapper

The existing WeCom service has useful ref-first primitives:

- `verify_callback_signature` and `ack_response`
- `parse_callback_envelope`
- `normalize_wecom_turn`
- `normalize_wecom_feedback_callback`
- `build_text_send_envelope`, `build_file_send_envelope`, and `build_template_card_envelope`

The wrapper should live under `packages/channels/wecom`, import these service primitives, implement the `ChannelAdapter` protocol, and remain default-off. Existing production service code should not be moved.

### Web/SSE Channel

The non-WeCom channel should be fixture-grade and dependency-free. A `web_sse` channel can normalize sanitized Web message dictionaries into `AgentTurn`/`FeedbackEvent` and serialize `RunEvent` objects as SSE frames. It should not host a server itself.

### Platform API And SDK

Phase 12 can provide a thin host package rather than a production server framework:

- `apps/platform_api` exposes pure route-handler functions and a deterministic OpenAPI document.
- tests exercise handlers with `DefaultRunRuntime` plus fakes.
- `packages/platform-sdk-ts` can be generated deterministically from the OpenAPI document by a Python script, avoiding new JS tooling.

### Web Chat Component

The embeddable component can be a small TypeScript module that consumes SDK-shaped run/SSE events and renders message text, status, artifact cards, and errors. Tests can be Python source/fixture checks unless a JS runner already exists, which it does not.

## Risks And Mitigations

- Channel adapters might import concrete backends. Mitigation: boundary tests scan `packages/channels` for backend imports.
- Web/SSE work could become an unplanned production web UI. Mitigation: fixture-only docs and default-off flags.
- OpenAPI/SDK drift could occur. Mitigation: deterministic generator and tests that fail when generated SDK differs.
- WeCom wrapper could regress production service behavior. Mitigation: keep wrapper separate and run existing WeCom service tests.
- Secret refs could bleed across channels. Mitigation: channel binding metadata uses `secret_ref`/`channel_binding_ref`, never raw keys.

## Validation Architecture

1. `python -m compileall packages/channels apps/platform_api packages/contract-test-suite/tests`
2. WeCom wrapper tests with service path on `PYTHONPATH`.
3. Web/SSE channel tests.
4. Platform API and SDK generation determinism tests.
5. Web chat component fixture tests.
6. Full contract runner with new package paths.
7. Boundary scans proving channels do not import backend packages and fixture data remains reference-first.

