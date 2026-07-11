---
phase: 77-vision-routing-runtime
status: auto-gathered
generated: 2026-07-11
source: autonomous context gathering (skip_discuss=true)
---

# Phase 77 Context: Vision Routing Runtime

## Goal
On image-bearing turns, runtime routes multimodal main vs vision→main mix (or fail-closed InkStatute notice) according to operator policy, without vision on text-only turns or meta leaks to lawyers.

## Requirements
- VIS-01: Operator can configure vision routing mode (`auto` | `always_preprocess` | `main_only`) plus optional dedicated vision provider/model
- VIS-02: On image-bearing turns, runtime routes: multimodal main if `supports_vision`; else vision→main mix when vision model configured; else fail-closed with InkStatute-owned notice (never silent image drop)
- VIS-03: Text-only turns never invoke the vision model; contract/audit evidence stays reference-first (no raw image bytes in contract logs)
- VIS-04: Vision/provider error paths pass through the assistant output boundary (no provider stack traces or gateway meta to ordinary users)

## Existing Infrastructure

### VisionPolicyDoc (Phase 76 stub)
- `packages/operator-config/src/inkstatute_operator_config/schemas.py:92-105`
- Fields: `routing_mode`, `main_model_id`, `vision_model_id`, `vision_provider_id` (all `str | None`)
- Phase 76 created as stub; routing_mode validation deferred to Phase 77

### Built-in Catalog with supports_vision
- `packages/operator-config/src/inkstatute_operator_config/catalog.py:48-88`
- `BUILTIN_MODEL_CATALOG`: gpt-5 (openai, supports_vision=True), claude-opus-4-8 (anthropic, supports_vision=True)
- Helpers: `builtin_catalog_entry(vendor_id, model_id)`, `builtin_vendor_profile(vendor_id)`

### Vision Validation (Phase 76 draft-tolerant)
- `packages/operator-config/src/inkstatute_operator_config/validate.py:234-245`
- `_check_vision_selection` uses `_resolve_selection_pair` with `allow_partial=True`
- Phase 77 must add routing_mode enum validation and enforce completeness when images present

### Probe Infrastructure (Phase 76)
- `services/admin-console-api/src/admin_console_api/probe.py`
- `probe_provider()` with SSRF checks, no-redirect, no-body-logging, generic codes
- Phase 76 already supports `target=vision` in the API handler (stored-target probe)
- UI probe form needs vision probe button when vision is configured

### Assistant Output Boundary
- `packages/platform-runtime/src/platform_runtime/output_boundary.py`
- `DefaultAssistantOutputBoundary.apply()` — blocks secrets/traces/provider leaks, rewrites lifecycle notices
- Phase 77 vision error paths must pass through this boundary

### Channel Output Policy
- `packages/channel-core/src/channel_core/output_policy.py`
- `apply_output_policy()` — block/rewrite/allow decisions for WeCom delivery

### Contract Events (reference-first)
- `packages/platform-contract/src/platform_contract/events.py`
- `AttachmentRef`: attachment_id, kind, uri, name, mime_type, metadata
- `raw_payload_ref` pattern used across AgentTurn, ChannelMessage, FeedbackEvent, ExecutionTrace
- Phase 77 must store image references only, never raw image bytes

### Hermes Adapter
- `packages/backends/hermes/src/inkstatute_backends_hermes/adapter.py`
- `RunRequest.turn` includes `attachments: list[AttachmentRef]`
- No current image/vision routing logic — Phase 77 adds this

### Admin Web UI (Phase 76 patterns)
- `services/admin-web-ui/src/admin_web_ui/csrf.py` — signed CSRF tokens
- `services/admin-web-ui/src/admin_web_ui/providers.py` — provider registry SSR
- `services/admin-web-ui/src/admin_web_ui/catalog.py` — model catalog SSR with vision badges
- Phase 77 extends with vision config form + vision probe

## Key Decisions

1. **Routing modes**: `auto` (default — multimodal main if supports_vision, else vision→main mix), `always_preprocess` (always vision→main mix), `main_only` (never invoke vision, fail-closed on images if main doesn't support vision)
2. **Image detection**: Check `turn.attachments` for `kind="image"` or `mime_type` starting with `image/`
3. **Fail-closed**: When images present but no vision-capable path available, return InkStatute-owned notice (never silent drop)
4. **Reference-first**: Contract logs store `AttachmentRef.uri` (reference), never raw image bytes
5. **Output boundary**: Vision/provider errors pass through `DefaultAssistantOutputBoundary` before user visibility
6. **Text-only turns**: Never invoke vision model (cost + correctness) — routing decision checks attachment kinds first

## Files to Modify
1. `packages/operator-config/src/inkstatute_operator_config/schemas.py` — routing_mode enum validation
2. `packages/operator-config/src/inkstatute_operator_config/validate.py` — routing_mode validation, vision completeness when images present
3. `services/admin-console-api/src/admin_console_api/config_api.py` — vision config PUT endpoint
4. `services/admin-console-api/src/admin_console_api/probe.py` — vision probe (extend existing)
5. `services/admin-web-ui/src/admin_web_ui/server.py` — vision route dispatch
6. `services/admin-web-ui/src/admin_web_ui/dashboard.py` — nav link for vision config

## Files to Create
1. `packages/platform-runtime/src/platform_runtime/vision_router.py` — routing decision logic
2. `services/admin-web-ui/src/admin_web_ui/vision.py` — vision config SSR form
3. Test files for each new module

## Dependencies
- Phase 76 (catalog supports_vision, VisionPolicyDoc, probe infrastructure)
- Phase 75 (channel image ingress paths, optional)
