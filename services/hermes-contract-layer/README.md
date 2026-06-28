# Hermes Contract Layer

This package is the InkStatute V2 shadow contract layer for the existing Hermes `lawfirm` profile.

It is a thin hook artifact and Python library that can record standard platform contract events from Hermes hook context. It is not a Hermes runtime replacement and does not own Hermes routing, sessions, skills, MCP configuration, model gateway behavior, WeCom gateway behavior, or feedback-channel normalization.

## Hook Artifact

The repo-owned hook artifact lives at:

```text
hooks/response_filter_contract_result_recorder/
```

The directory name is intentional. Hermes loads hook directories in lexicographic order, so this directory sorts after `response_filter` and can observe fields that the lawfirm response filter writes into the shared `agent:end` hook context. The manifest hook name remains `contract_result_recorder`.

Do not deploy or copy this artifact into `/home/sorawatcher/.hermes` as part of repo tests. Live Hermes profile deployment is out of scope for Phase 4 and belongs to a later validation or explicit deployment step.

## Runtime Boundary

The hook handler must return without changing outbound Hermes values such as `response`, `message_id`, `platform`, `user_id`, `chat_id`, `session_id`, or `message`. Contract logging failures must not propagate back into Hermes.

## Phase 5 Validation

WeCom shadow loop validation is documented in [docs/wecom_shadow_loop_validation.md](docs/wecom_shadow_loop_validation.md). It separates fixture-backed checks from opt-in live Hermes validation and requires `INKSTATUTE_CONTRACT_LOG_PATH` to point outside this repo for live runs.

repo tests never mutate `/home/sorawatcher/.hermes`; live hook deployment must be explicit and reversible.
