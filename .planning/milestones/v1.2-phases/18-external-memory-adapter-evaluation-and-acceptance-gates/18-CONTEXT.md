---
phase: 18-external-memory-adapter-evaluation-and-acceptance-gates
created: 2026-07-01
mode: autonomous-smart-discuss
user_direction: "User delegated implementation choices and asked for prepared tests and test environment before validation."
status: ready-for-planning
---

# Phase 18 Context

## User Intent

The user does not want to decide implementation details upfront. They asked the agent to decide autonomously unless a prepared test environment and test content make validation concrete.

For Phase 18 this means:

- Do not ask the user to choose Mem0, Zep, or platform-native memory before evidence exists.
- Prepare local, synthetic verification content.
- Keep external memory systems behind adapter contracts and acceptance gates.
- Finish with a production recommendation that can be reviewed without live legal data or API keys.

## Source of Truth

- `docs/requirements/V2-PRD.md` remains the product source of truth.
- `.planning/ROADMAP.md` defines Phase 18 success criteria.
- `.planning/REQUIREMENTS.md` tracks EXT-02, EXT-03, and EXT-04.
- `docs/architecture/memory/context-memory-contracts.md` defines Phase 14 memory vocabulary, privacy policy, and external adapter criteria.
- `.planning/phases/17-long-term-memory-and-feedback-learning/17-VERIFICATION.md` proves Phase 17 local memory and feedback learning behavior.

## Phase 18 Goal

The team knows whether to use platform-native memory, Mem0, Zep, or another adapter later, based on contract evidence and privacy gates.

## Requirements

- `EXT-02`: External memory stores can be represented behind a `MemoryStore` adapter contract and capability manifest without becoming the default legal path.
- `EXT-03`: Any external adapter spike uses synthetic or sanitized fixtures only.
- `EXT-04`: The final recommendation documents whether Mem0, Zep, another store, or platform-native storage should be used for later production work.

## Constraints

- Do not add Mem0/Zep SDK dependencies, network calls, API keys, Docker services, or new databases in this milestone phase.
- Do not make any external memory provider the legal production default.
- Do not store raw legal/customer payloads, secrets, callback bodies, documents, or high-risk legal conclusions as reusable memory.
- Do not modify RunRuntime or channel contracts to know about specific memory providers.
- High-risk legal feedback and skill/routing changes remain pending human review.

## Working Assumptions

- Phase 18 can implement an adapter capability contract in `packages/platform-runtime` as a dependency-free library surface.
- Provider-specific spikes should be represented by manifests and sanitized fixtures, not live API calls.
- The final recommendation should prefer platform-native memory for current legal production until external providers pass privacy, deletion/export, tenant isolation, data residency, security, and operational review.

## Prepared Validation Shape

- Unit tests for manifest validation and readiness decisions.
- Contract-suite fixture tests for sanitized Mem0/Zep-style adapter evidence.
- Documentation checks for final recommendation and acceptance gate language.
- Full local commands documented in `18-VALIDATION.md`.
