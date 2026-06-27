# 墨律 InkStatute

InkStatute is a full-stack Agent platform project. The first industry package is a legal assistant for mainland China law practice, based on the existing Hermes `lawfirm` profile. The platform should also support other industry agents in the future.

This repository starts as a V2 product, architecture, and implementation workspace. V2 deliberately does not rebuild Hermes: Hermes `lawfirm` remains the runtime backend, and this repository adds the platform contract layer, contract tests, read views, and feedback normalization needed to make the system observable, testable, and portable.

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
  hermes-contract-layer/ # Hermes hook adapters, mappers, contract event writer
  conversation-read-view/# Read-only conversation/task view built from contract logs
  feedback-service/     # feedback.jsonl normalization, dedupe, queue export
packages/
  platform-contract/    # JSON Schema, Python types, async state machine, error codes
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
- WeCom and QQBot gateway/channel state: existing bot access channels

Sensitive runtime data, logs, account tokens, local databases, and user files must stay outside this repository.

## AI Development Workflow

This repository uses GSD planning state for autonomous AI development:

- `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, and `.planning/STATE.md` are the continuation source once generated.
- Start a new session with `$gsd-resume-work` or continue automatically with `$gsd-progress --next --auto`.
- Keep V2 contract tests and fixtures ahead of Hermes hook changes.
