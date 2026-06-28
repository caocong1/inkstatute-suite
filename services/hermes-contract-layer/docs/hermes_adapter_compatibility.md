# Hermes Adapter Compatibility

This matrix defines the minimum Hermes evidence required for InkStatute V2 Hermes mode. It is compatibility documentation for the adapter/bootstrap layer, not approval to use Hermes gateway as the ordinary WeCom channel.

## Verified Hermes Evidence

| Evidence | Status | V2 Use |
|----------|--------|--------|
| Hook directories load in lexicographic order | source_confirmed | `response_filter_contract_result_recorder` can observe response-filter context after `response_filter`. |
| `agent:end` hook event exists | source_confirmed | Shadow recorder can map result-side events. |
| `gateway:startup` hook event exists | source_confirmed | Existing card/shim setup remains migration evidence only. |
| `response_filter` writes `message_id` into hook context | source_confirmed | Feedback target can use `message_id` when present. |
| `agent:start` evidence remains partial for full input content and attachments | partial | Full AgentTurn input requires InkStatute WeCom service or runtime-owned references. |

## Required Capabilities

Hermes mode can be considered V2-compatible only when all of these are true:

| Capability | Required Value | Reason |
|------------|----------------|--------|
| hook/event support | `agent:end`; after-filter recorder directory loaded after `response_filter` | Contract result recording must see post-filter `message_id` and response preview. |
| invocation mode | `sync` or supported async adapter invocation through InkStatute service | WeCom service dispatches `AgentTurn`; Hermes must not own channel send. |
| feedback target support | stable `message_id` or explicit generated target | `AgentResult.feedback_target` must join to `FeedbackEvent`. |
| session read support | available or explicitly unsupported with reference fallback | Read views may use Hermes session only as fallback, not authority. |
| artifact return support | true or explicitly unavailable with status | Files/artifacts must return through InkStatute service envelopes. |
| trace support | true or explicit limited trace status | ExecutionTrace must remain auditable. |
| no_channel_io | true | Hermes adapter must not send directly to ordinary WeCom users. |

## Known Gateway Direct-Send Paths To Avoid

Hermes gateway/operator paths that must not reach ordinary WeCom users include lifecycle notices, restart/update prompts, slash command/help/status/credits/insights notices, memory/tool progress, delivery debug, and any internal path, command, token, env/profile/runtime detail.

The assistant output boundary in `services/wecom-service` is the ordinary-user send boundary. `response_filter` is useful for final agent text, but it is not the channel boundary.

## Supported Mode Decision

| Hermes Evidence State | Supported Mode |
|-----------------------|----------------|
| Required capabilities present and `no_channel_io=true` | `hermes` may be selected for V2 fixture/live acceptance. |
| Agent invocation works but `no_channel_io` is false or unknown | Unsupported for V2 live WeCom acceptance. |
| Hook order cannot place recorder after `response_filter` | Unsupported unless recording is moved inside/adjacent to `response_filter` with explicit coupling approval. |
| Feedback target cannot be stabilized | Fixture-only or blocked until target mapping is proven. |
| Only Hermes gateway can complete ordinary WeCom flow | Unsupported; do not route ordinary users through Hermes gateway. |

## Fallback Behavior

Version drift must report one of these states rather than silently falling back to Hermes gateway:

- `supported`: all required capabilities are present and `no_channel_io=true`.
- `fixture_only`: enough behavior exists for sanitized fixture replay but not live WeCom acceptance.
- `fallback_required`: a documented adapter fallback is required before use.
- `unsupported`: Hermes version cannot satisfy V2 channel ownership or adapter contract rules.

If a Hermes version lacks agent invocation or `no_channel_io`, it cannot pass V2 live WeCom acceptance. The fallback must be adapter-side or fixture-only; ordinary users must not be routed through Hermes gateway.

## Sanitized Bundle Rules

The sanitized lawfirm bundle manifest is a manifest of structure and references only. It may list profile layout templates, hook artifact names, skills/MCP/script references, SOUL/profile references, adapter config, and external environment reference names.

It must not include WeCom credential values, model credential values, AES material, runtime databases, runtime logs, feedback callback payloads, customer documents, media files, raw legal payloads, complete callback bodies, or generated confidential documents.

Current manifest:

```text
services/hermes-contract-layer/bundles/lawfirm-profile-bundle.manifest.json
```

## Health Check Command

Run the non-mutating bootstrap tests:

```bash
PYTHONPATH=services/hermes-contract-layer/src:packages/platform-contract/src \
  python -m unittest discover -s services/hermes-contract-layer/tests -p 'test_adapter_bootstrap.py' -v
```

For a deployment-specific check, call `probe_hermes_capabilities(root_path, profile_path, contract_log_path)` with sanitized paths and confirm the report has `passed=true`, `no_channel_io=true`, `response_filter_present=true`, `after_filter_recorder_present=true`, and `contract_log_outside_repo=true`.
