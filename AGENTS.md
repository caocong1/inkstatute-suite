# InkStatute Agent Instructions

## Project Source Of Truth

- Current product specification: `docs/requirements/V2-PRD.md`.
- V1 is retired and must not be reintroduced as an active requirement source.
- This repo implements V2 as a backend-neutral platform contract, InkStatute-owned WeCom service, and agent-adapter layer. Hermes `lawfirm` is the first supported agent backend, not the channel boundary. Do not rebuild Hermes core, session storage, router, skill registry, MCP registry, or model gateway unless an active GSD phase explicitly changes scope.
- User-facing WeCom ingress/egress must be owned by InkStatute. Hermes must only provide agent logic in Hermes mode; Hermes gateway/meta/system/update/command/help notices must not leak to ordinary lawyer users.

## GSD Continuation Protocol

- When the user says "continue", "继续开发", "resume", or asks what is next, first run or follow `$gsd-resume-work` if `.planning/` exists.
- For hands-free progression, use `$gsd-progress --next --auto`.
- Treat `.planning/STATE.md`, `.planning/ROADMAP.md`, and phase artifacts as the persistent project memory.
- If `.planning/` is missing, bootstrap from `docs/requirements/V2-ingest-manifest.yaml` with `$gsd-ingest-docs --manifest docs/requirements/V2-ingest-manifest.yaml --mode new`.
- Do not skip GSD safety gates: unresolved checkpoints, failed verification, or missing summaries must be handled before advancing.

## Implementation Priorities

1. `packages/platform-contract/`: five V2 contract schemas, async task state machine, error codes, JSON Schema and Python bindings first.
2. `packages/contract-test-suite/`: schema validation, fixture replay, relationship checks, composability tests, CI gate.
3. `services/wecom-service/`: InkStatute-owned WeCom receive/send service for callbacks, ACK, message normalization, text/file/card delivery, feedback callbacks, idempotency, and output policy.
4. Agent adapter contract and runtime selector: support Hermes agent logic first, while keeping room for later `codex` and direct `provider_model` modes through the same platform contract.
5. Hermes agent adapter/bootstrap: version-aware, low-coupling integration with the existing `lawfirm` profile or a sanitized reproducible profile bundle; runtime secrets stay outside the repo.
6. Assistant output boundary: filter/rewrite/drop backend-originated meta/system/gateway/update/command notices inside InkStatute WeCom delivery, without rewriting legal business conclusions.
7. `services/hermes-contract-layer/`: hook-based shadow recorder, mapper, contract event writer, and Hermes agent adapter support.
8. `services/feedback-service/`: normalize feedback into `FeedbackEvent`, dedupe callbacks, classify feedback, produce pending queues.
9. `services/conversation-read-view/`: read-only view from contract logs. Sessions DB can be a Hermes-specific fallback, not the authority.

## Safety And Privacy

- Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads.
- Contract logs should prefer references such as `raw_payload_ref` and must not store sensitive full text by default.
- Legal-specific fields belong in `industry_context`; platform-level schemas must remain industry-neutral.
- Backend/gateway/system notices are not user-facing legal assistant output and must be suppressed or converted to InkStatute-owned service notices before ordinary WeCom delivery.
- WeCom keys, callback tokens, encoding AES keys, runtime message payloads, and media files must not be committed.
- High-risk legal feedback must remain human-reviewed. V2 records `skill_candidate`; it does not auto-synthesize or auto-modify legal conclusion skills.

## Coding Rules

- Keep changes scoped to the active GSD phase and its plan.
- Add tests before or with behavior changes, especially for schemas, mappers, event ordering, dedupe, and fixture replay.
- Prefer structured parsers and schema validators over ad hoc string parsing.
- Do not introduce a new service, database, queue, or runtime dependency unless the V2 PRD or the active GSD plan requires it.
- Update docs and GSD artifacts when implementation decisions change.
