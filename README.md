# 墨律 InkStatute

InkStatute is a full-stack Agent platform project. The first industry package is a legal assistant for mainland China law practice, based on the existing Hermes `lawfirm` profile. The platform should also support other industry agents in the future.

This repository starts as a product and architecture workspace. V1 is a requirements-first milestone: define the backend platform, agent adapters, skill and MCP orchestration, feedback loop, and frontend access surfaces before implementation.

## Positioning

- Chinese product name: 墨律
- English product name: InkStatute
- Repository name: `inkstatute-suite`
- Product shape: full-stack monorepo
- First vertical: law firm assistant
- Long-term direction: reusable industry Agent platform

## V1 Documentation

- [V1 Requirements Specification](docs/requirements/V1-PRD.md)

## Planned Monorepo Shape

The first code milestone should use this logical layout:

```text
apps/
  web/                  # Web client
  desktop/              # Tauri desktop client
  bots/                 # WeCom, QQ Bot, and future channel adapters
services/
  backend/              # Unified API, task orchestration, auth, audit, storage
packages/
  agent-core/           # Agent runtime abstractions and provider interfaces
  skills/               # Skill registry, industry packs, and skill packaging
  connectors/           # MCP, legal databases, document tooling, external systems
docs/
  requirements/         # Product requirements
  architecture/         # Architecture decisions and diagrams
  api/                  # API contracts
  operations/           # Deployment and maintenance notes
```

## Current Source Of Truth

The first requirements document is derived from the local Hermes `lawfirm` profile, especially:

- `SOUL.md`: legal assistant identity, compliance boundaries, and operating rules
- `skills/`: legal skills, workflow skills, methodology skills, and platform skills
- `skills/lawfirm-router/`, `scripts/router.py`, `data/skill_index.json`: routing layer
- `mcp_servers` in `config.yaml`: legal database and court judgment connectors
- `feedback/`, `skillopt-runner`, and WeCom template-card hooks: feedback and iteration loop
- WeCom and QQBot gateway/channel state: existing bot access channels

Sensitive runtime data, logs, account tokens, local databases, and user files must stay outside this repository.

