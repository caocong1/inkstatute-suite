# 墨律 InkStatute

InkStatute is a full-stack Agent platform project. The first industry package is a legal assistant for mainland China law practice, exposed through an InkStatute-owned WeCom service and backed by Hermes `lawfirm` through a low-coupling agent adapter. The platform should also support other industry agents and backend modes in the future.

This repository starts as a V2 product, architecture, and implementation workspace. V2 deliberately does not rebuild Hermes: Hermes `lawfirm` is the first production agent backend, while this repository owns WeCom receive/send, platform contracts, adapter contracts, assistant output boundary, contract tests, read views, and feedback normalization needed to make the system observable, testable, portable, and user-facing as a pure lawyer assistant.

## Positioning

- Chinese product name: 墨律
- English product name: InkStatute
- Repository name: `inkstatute-suite`
- Product shape: full-stack monorepo
- First vertical: law firm assistant
- Long-term direction: reusable industry Agent platform

## V2 Source Of Truth

- [V2 Requirements Specification](docs/requirements/V2-PRD.md)

V1 has been retired. V2 is the current specification and replaces the earlier platform rebuild plan.

## V2 Monorepo Shape

The V2 implementation should use this logical layout:

```text
services/
  wecom-service/         # InkStatute-owned WeCom callbacks, ACK, send, cards, feedback
  hermes-contract-layer/ # Hermes agent adapter hooks, mappers, contract event writer
  conversation-read-view/# Read-only conversation/task view built from contract logs
  feedback-service/     # InkStatute feedback callbacks plus feedback.jsonl compatibility
packages/
  platform-contract/    # JSON Schema, Python types, async state machine, error codes, adapter contract
  contract-test-suite/  # schema validation, fixture replay, composability CI
docs/
  requirements/         # Product requirements
  architecture/         # Architecture decisions and diagrams
  api/                  # API contracts
  operations/           # Deployment and maintenance notes
```

## Hermes Source Context

The V2 requirements are derived from the local Hermes `lawfirm` profile, especially:

- `SOUL.md`: legal assistant identity, compliance boundaries, and operating rules
- `skills/`: legal skills, workflow skills, methodology skills, and platform skills
- `skills/lawfirm-router/`, `scripts/router.py`, `data/skill_index.json`: routing layer
- `mcp_servers` in `config.yaml`: legal database and court judgment connectors
- `feedback/`, `skillopt-runner`, and WeCom template-card hooks: feedback and iteration loop
- Existing WeCom gateway/channel state: runtime evidence and migration input, not the target user-facing channel boundary
- Hermes gateway/update/restart/command send paths: source-confirmed reason to keep Hermes out of ordinary WeCom ingress/egress

Sensitive runtime data, logs, account tokens, local databases, and user files must stay outside this repository.

## AI Development Workflow

This repository uses GSD planning state for autonomous AI development:

- `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, and `.planning/STATE.md` are the continuation source once generated.
- Start a new session with `$gsd-resume-work` or continue automatically with `$gsd-progress --next --auto`.
- Keep V2 contract tests and fixtures ahead of WeCom service, Hermes agent adapter, hook, and output-policy changes.
