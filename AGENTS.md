# InkStatute Agent Instructions

## Project Source Of Truth

- **Current product specification: `docs/requirements/V3-PRD.md`.**
- Selection evidence and research: `.planning/research/V3-SELECTION.md`.
- V1 and V2 are retired as active requirement sources. `docs/requirements/V2-PRD.md` is kept as a historical document only; do not treat its scope statements as current constraints.
- This repo implements V3: **one legal capability core, one event vocabulary, two transports.** To clients it speaks HTTP+SSE; to agent backends it speaks ACP (Zed Agent Client Protocol) over stdio. The platform does fan-out, tenancy, persistence, output boundary, and channel degradation — it does not execute legal tasks and does not write per-backend glue.
- The three layers:
  - **Channel layer** — Web (desktop + mobile browser), Desktop App (Tauri), WeCom bot, QQ bot. All share one UI core; chat UI must have exactly one implementation.
  - **Backend layer** — any ACP-speaking agent (Hermes, Codex, Claude Code, Gemini CLI) plus InkStatute's own Python agent core. Swapping `backend_id` must not require changes to any channel or UI code.
  - **Capability layer** — 396 real Chinese legal skills from `ai-for-china-legal` (345) and `legal-skills` (51), referenced by read-only vendoring. The platform provides an index and per-backend materialization; it does not copy the corpus and does not build a skill execution runtime.

## GSD Continuation Protocol

- When the user says "continue", "继续开发", "resume", or asks what is next, first run or follow `$gsd-resume-work`.
- For hands-free progression, use `$gsd-autonomous` (current milestone is v3.0, Phases 88–104).
- Treat `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, and phase artifacts as the persistent project memory.
- Do not skip GSD safety gates: unresolved checkpoints, failed verification, or missing summaries must be handled before advancing.
- Human gates must never be auto-closed. See "Human Gates" below.

## Current Milestone: v3.0 Unified Legal Core (Phases 88–104)

| Stage | Phases | State after completion |
|---|---|---|
| A 协议底座 | 88-90 | Hermes drivable via ACP |
| B 通道统一 | 91-95 | Lawyers can use the same capability from web / desktop / WeCom / QQ |
| C 能力层 | 96-99 | 396 real legal skills enter the platform for the first time |
| D 自研核心 | 100-104 | Heart swapped to the self-built Python core, zero channel-layer changes |

**Critical path:** 88 → 89 → 90 → 91 → 92 → 93 (a usable web product exists at the end of it).

## Binding Architecture Decisions

Do not relitigate these without an explicit user decision. Full rationale in `.planning/PROJECT.md` Key Decisions.

1. **Backend seam is ACP v1.** Verified locally: `hermes acp --check` → `Hermes ACP check OK` (Hermes Agent v0.19.0). Lock protocol v1 and negotiate at `initialize`; ACP v2 is draft with known breaking changes — keep v2 features flagged off.
2. **Channel seam is not aligned to any external protocol** (not AG-UI, not Vercel AI SDK, not A2A) because all clients are first-party. But the event vocabulary is **isomorphic to ACP `session/update`** so the platform stays a thin relay.
3. **The self-built agent core is Python.** Decided on capability, not cost: Word-native track-changes docx already exists as 41,185 bytes of Python (`lawfirm-profile/scripts/contract_review_trackchanges.py`) vs 74 lines of basic Rust docx generation; the skill corpus contains 140 Python scripts; the platform is 118K lines of Python with 28 gates. Rust's offline-embedding advantage is void because the desktop app is online-first / offline-read-only.
4. **Protocol first, heart second.** Stages A+B+C ship a usable product on `hermes acp`. Do not put the ~4,000-line Rust→Python port on the critical path.
5. **The self-built core is the default backend but has no architectural privilege.** One implementation, two entry points: in-process `BackendAdapter` and `inkstatute-agent acp`.
6. **Skill corpus is read-only vendored.** Never copy it into this repo. Never write back to the skill repos. Build an index + per-backend materializers.
7. **Tool rounds must stream.** `lawyer-desktop`'s current non-streaming tool round is a defect to fix, not an asset to port.
8. **Mobile native apps are V4.** This milestone ships mobile browser support only.
9. **Single-firm scale first.** ACP per-session subprocess is fine at ≤50 lawyers. Expose `backend_process_mode` (`per_session` / `pooled` / `remote`) in the contract; implement only `per_session`.

## Related Repositories (siblings of this repo, not vendored yet)

| Repo | Role |
|---|---|
| `ai-for-china-legal` | 345 SKILL.md, 13 plugins, Claude-Code-plugin format, pure prompt. Contains `shared/inkstatute-integration/` — the ask_user protocol and agent UX requirements written *for this platform*. Honor them. |
| `legal-skills` | 51 SKILL.md, 37 with `scripts/` (140 .py). MIT + CC-BY-NC dual license — respect it. |
| `lawyer-desktop` | This project's predecessor (Tauri 2.11 + SolidJS). Migration source for the UI (23 components + 墨律 three themes) and the agent core logic (router 627 / classifier 691 / tool_leak 392 / citations). |
| `lawfirm-profile` | The production Hermes profile, 312 skills. `scripts/router.py` (498-line strong-signal router) and `scripts/contract_review_trackchanges.py` (Word-native track changes) are capabilities that must not regress. |
| `lawyer-ai` | OpenCode prototype, shelved. Do not migrate. |

## Implementation Priorities

Follow the roadmap phase order. Within a phase:

1. `packages/platform-contract`: the unified event vocabulary comes before anything that emits or consumes events.
2. `packages/contract-test-suite`: schema validation, fixture replay, relationship checks, composability tests, CI gates — add gates as you add packages.
3. `packages/acp-client`: one ACP client replaces the per-backend adapters. Bridge and output boundary before any channel work.
4. `services/gateway`: one client-facing entry point. Do not add a second HTTP/SSE surface.
5. `packages/ui-core`: extract before building `apps/web` or `apps/desktop`. Never write chat UI twice.
6. `packages/skill-index` then materializers: index before routing; routing before practice profiles.
7. `packages/agent-core`: skeleton → tools → guardrail port → dual entry points. Guardrails are the highest-risk work.
8. `Phase 104` convergence last: retire legacy only after replacements are proven.

## Safety And Privacy

- Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads.
- Contract logs prefer references such as `raw_payload_ref` and must not store sensitive full text by default.
- Legal-specific fields belong in `industry_context`; platform-level schemas must remain industry-neutral (verified by `solutions/demo_non_legal` composability tests).
- **Output boundary is enforced twice**: at the ACP event bridge and at the Gateway. Backend/gateway/system/update/command notices must never reach ordinary lawyer users.
- **Permission requests must never be auto-approved server-side.** ACP `session/request_permission` for `terminal` / `execute_code` must be explicitly denied or escalated to a user approval card. (Reference failure: Buzz's ACP bridge auto-answers `allow_once`, letting agents run shell commands unprompted.)
- **Legal guardrails are non-bypassable**: research-gate (search before concluding), ask-user-enforcement (block drafting when key facts are missing), citation audit (verified / retrieved / unverified), de-AI polish.
- High-risk legal conclusions stay human-reviewed. Record `skill_candidate` with `requires_human_review=true`; never auto-synthesize or auto-modify legal conclusion skills.
- WeCom keys, callback tokens, encoding AES keys, ACP subprocess credentials, runtime message payloads, and media files must not be committed.

## Human Gates (never auto-close, never claim as passed)

| Gate | Content | Phase |
|---|---|---|
| HG-1 法律质量 | Ported prompt assembly and legal guardrails must be sampled and confirmed by a lawyer as no worse than current lawyer-desktop / Hermes | 102 |
| HG-4 修订稿质量 | Word-native track-changes docx must be confirmed by a lawyer as usable for external negotiation | 101 |
| HG-2 真机通道 | Live WeCom send/receive acceptance | carried from V2 |
| HG-3 律师试运行 | Five-workday / 15-real-task lawyer trial | carried from V2 |
| — | Operator `--live` QQ OpenAPI acceptance | carried from v1.9 |

## Coding Rules

- Keep changes scoped to the active GSD phase and its plan.
- Add tests before or with behavior changes, especially for schemas, event mapping, ordering, dedupe, degradation, and fixture replay.
- Prefer structured parsers and schema validators over ad hoc string parsing.
- Do not introduce a new service, database, queue, or runtime dependency unless the V3 PRD or the active GSD plan requires it.
- Every new `packages/*/src` and `services/*/src` directory must be covered by a gate — the `gate-coverage` meta-test enforces this.
- Run `python scripts/run_v2_gates.py` before claiming a phase complete. The existing 28 gates must stay green throughout V3.
- When porting logic from `lawyer-desktop` (Rust), use the Rust-side test cases as the Python-side golden fixture set. Do not port by reading and re-writing from memory.
- Update docs and GSD artifacts when implementation decisions change.
