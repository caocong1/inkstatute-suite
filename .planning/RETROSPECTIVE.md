# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v3.0 — Unified Legal Core

**Shipped:** 2026-08-08
**Phases:** 17 | **Plans:** 69 | **Tasks:** 192

### What Was Built

- 13-category unified event vocabulary isomorphic to ACP v1 session/update (15 JSON Schemas, 18 Python dataclasses, 18 TypeScript interfaces).
- Python ACP client driving Hermes via stdio subprocess with bidirectional event bridge and output boundary enforced twice.
- Unified multi-tenant HTTP+SSE Gateway replacing platform_api + lawyer-web-chat overlap.
- @inkstatute/ui-core extracted from lawyer-desktop (23 components, 3 themes) with single chat UI implementation.
- Responsive web client (desktop + mobile browser), Tauri desktop shell, WeCom/QQ refactored as Gateway consumers with non-streaming degradation.
- 396 real Chinese legal skills indexed from ai-for-china-legal (345) + legal-skills (51), read-only vendored, per-backend materialized.
- Self-built Python async streaming agent core with context budget, model layer, tool layer, Word-native track-changes docx.
- 4 legal guardrails ported from Rust: research-gate, ask-user, citation audit, de-AI polish.
- Dual entry points: in-process BackendAdapter + `inkstatute-agent acp` CLI.
- Legacy convergence: ~10,483 lines retired (hermes/codex backends, web_sse channel, lawyer-web-chat, hermes-contract-layer), multi-agent-adapter frozen, gate system updated (38→34 gates).

### What Worked

- Protocol-first staging (A→B→C→D) shipped a usable product on Hermes ACP before the self-built core was ready, de-risking the critical path.
- Rust→Python port used Rust-side test cases as golden fixtures, preventing regression in legal guardrails.
- Dual entry points sharing one `run_turn()` implementation eliminated backend duplication.
- Gate-coverage meta-test caught missing gates automatically during legacy retirement.
- Composability tests (demo_non_legal) caught legal field leakage in platform-neutral schemas.
- Code review subagents found real bugs: C-1 SAFE-01 bypass, W-1 sentinel race, W-7 prompt parity.

### What Was Inefficient

- 10 phases (91-99, 101) completed in prior sessions lack VERIFICATION.md metadata, requiring override closeout. Verification discipline should be enforced per-phase, not retroactively.
- ROADMAP.md progress table was stale for several phases (showed "In Progress" when work was done). Manual updates are error-prone — should be automated by phase.complete.
- MILESTONES.md accomplishment extraction from SUMMARY.md produced garbled output (date strings, phase names instead of one-liners). The summary-extract query needs better field parsing.
- Some SUMMARY.md files used non-standard formats that confused the extraction tool.

### Patterns Established

- **Protocol-isomorphic event vocabulary**: Platform events mirror ACP `session/update` so the platform stays a thin relay. This pattern should continue for any new event types.
- **Output boundary enforced twice**: At the ACP event bridge AND at the Gateway. Never rely on a single enforcement point.
- **Read-only skill vendoring**: Never copy the corpus into the repo. Index + materialize, don't duplicate.
- **Dual entry points for agent core**: One implementation, two entry points (in-process + ACP CLI). No architectural privilege for the self-built core.
- **Gate-coverage meta-test**: Every `packages/*/src` and `services/*/src` directory must have a gate. Automated enforcement prevents drift.
- **Rust golden fixtures**: When porting logic from Rust, use Rust-side test cases as the Python-side golden fixture set.

### Key Lessons

1. Protocol-first staging de-risks the critical path — ship on the existing backend before building the replacement.
2. Verification metadata must be created per-phase, not deferred to milestone close. Override closeouts are a smell.
3. Code review subagents are worth the cost — they found 3 real bugs across 3 phases that tests missed.
4. Legacy retirement is safe when gated by gate-coverage meta-tests and composability regression tests.
5. ~10,483 lines can be retired in one phase when replacements are proven and references are updated before deletion.
6. Human gates (HG-1, HG-4) must be explicitly tracked and never auto-closed, even when all automated tests pass.

### Cost Observations

- Model mix: ~70% sonnet, ~25% haiku, ~5% opus (estimated)
- Sessions: multiple across 43 days (2026-06-27 → 2026-08-08)
- Notable: The most complex work (Phase 102 guardrail port, Phase 104 legacy retirement) was executed via subagents with detailed prompts, keeping the main context clean.

---

## Milestone: v1.9 — QQBot Host Composition

**Shipped:** 2026-07-10
**Phases:** 5 | **Plans:** 14 | **Tasks:** 29

### What Was Built

- Empty-deps `services/qqbot-service/` host skeleton with V2 gate coverage and secret-ref process-edge resolution.
- Dual-knob runtime wiring injecting `QQBotChannelAdapter` into `DefaultRunRuntime.channels` with disabled-path refuse.
- ACK-first stdlib webhook composing package Protocol methods end-to-end with Fake transports.
- Smoke `--dry-run` Protocol-path hardening via host helpers; sanitized non-acceptance evidence.
- Controlled `--live` honesty gates + operator runbook; live OpenAPI acceptance remains HUMAN GATE.

### What Worked

- Closing only v1.8 accepted host gaps kept scope tight and avoided re-phasing package crypto/normalize/send.
- Composition-only host + Protocol freeze preserved ADAPTER-04 and empty-deps invariants.
- Same-day 14-plan execution with audit-passed close kept planning files compact after archive.

### What Was Inefficient

- Info-tier review leftovers (CALLBACK_PATH duplication, AST dynamic-import miss) remain as non-blocking debt.
- `--live` stayed on leaf OpenAPI path rather than host Protocol rewrite — documented tradeoff, but splits proof surfaces.

### Patterns Established

- Host services compose package Protocol methods; they do not reimplement channel crypto/normalize/send.
- Dual default-OFF knobs + explicit channel injection beat auto-discovery for live-IO safety.
- CI dry-run must exercise the same host helpers as production composition, or fail closed.

### Key Lessons

1. Accepted audit gaps make excellent next-milestone scope when they are composition/wiring, not feature rewrites.
2. Preserve carried human-gate phase dirs (Phase 08) during phase archival — never delete them with milestone phases.
3. Force `not_live_acceptance=true` in evidence schemas so CI cannot silently claim live success.

### Cost Observations

- Model mix: not tracked in repo-local artifacts.
- Sessions: single-day autonomous GSD execution for Phases 68–72.
- Notable: Milestone closed same calendar day as execution start after audit passed.

---

## Milestone: v1.2 — Conversational Context and Memory Foundation

**Shipped:** 2026-07-02
**Phases:** 6 | **Plans:** 16 | **Sessions:** multiple autonomous/resumed GSD sessions

### What Was Built

- Backend-neutral context, memory, and interrupt contracts with Python bindings and sanitized fixtures.
- Scoped session resolution, interrupt lifecycle, and WeCom session runtime behavior for continuation, new-task splitting, active-task precedence, and clarification resume.
- Deterministic short-term context assembly with protected refs, rolling summaries, memory refs, feedback corrections, artifacts, and budget trimming.
- Platform-native memory and feedback learning policies with human-reviewed candidates and no automatic legal skill modification.
- External memory adapter contracts and recommendation, keeping platform-native memory as the live legal default while allowing future sanitized spikes.
- Phase 19 E2E closure so ordinary WeCom continue/start callbacks reach runtime run creation through a pure ingress boundary.

### What Worked

- Reference-first privacy rules stayed consistent across contracts, runtime metadata, fixtures, and tests.
- Keeping WeCom ingress as a dependency-injected library boundary avoided adding a server, queue, database, live WeCom dependency, or Hermes core coupling during the closure phase.
- The milestone audit caught a real E2E wiring gap that unit-level phase completion had missed, and a small closure phase resolved it cleanly.

### What Was Inefficient

- Nyquist validation artifacts were not produced uniformly during the earlier v1.2 phases, so milestone close had to accept validation-documentation debt.
- The milestone completion tool overcounted historical phases because the live roadmap still contained older phase details; future milestones should keep `ROADMAP.md` compact after archive.
- Phase 18 expanded after a broader memory component study arrived, which was useful but added late-stage fixture and recommendation updates.

### Patterns Established

- Treat context/memory data as derived support state; contract logs and references remain the audit source.
- Resume clarification through runtime interrupts, not user-visible session commands.
- Represent external memory providers through capability manifests and local evaluations before any SDK or live provider integration.
- Add a closure phase when milestone audit finds critical wiring gaps instead of burying the fix inside closeout.

### Key Lessons

1. Milestone audits must exercise cross-layer flows, not just per-phase summaries and tests.
2. Live legal acceptance and operator UAT should stay explicit human gates even when fixture and library evidence pass.
3. Closeout tools need a compact current roadmap; otherwise archive summaries can accidentally mix historical and active phase scopes.
4. Privacy-safe metadata helpers should reject raw/full-text keys at ingress boundaries, not only at storage boundaries.

### Cost Observations

- Model mix: not tracked in repo-local artifacts.
- Sessions: multiple resumed autonomous sessions.
- Notable: The most valuable late work was audit-driven integration closure, not additional feature expansion.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.1 | multiple | 5 | Established default-off reusable platform seams. |
| v1.2 | multiple | 6 | Added memory/context runtime behavior and enforced audit-driven closure before archive. |
| v1.9 | same-day | 5 | Closed prior-milestone accepted gaps via composition-only host + Protocol-path CI honesty. |
| v3.0 | multiple | 17 | Protocol-first staging, self-built Python core, legacy retirement with gate-coverage enforcement. |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|------|----------|-------------------|
| v1.1 | 287 V2 gate tests | Contract, runtime, channel, backend, and solution-loader gates | Runtime, adapter, channel, SDK, and solution-loader foundations default-off |
| v1.2 | 51 WeCom-service tests plus contract/runtime suites cited in phase verification | Context, memory, interrupt, feedback, adapter, and WeCom session-runtime flows | Memory/context contracts, resolver, interrupt store, memory policy, adapter manifest, ingress helper |
| v1.9 | Host + smoke Protocol-path suites; 27 V2 gates with qqbot-service entry | Host composition, dual-knob wiring, ACK-first webhook, Protocol-path dry-run | `services/qqbot-service/` empty-deps composition host |
| v3.0 | 937 tests, 34 V2 gates | Unified event contract, ACP client, event bridge, Gateway, UI core, skill index, agent core, guardrails, legacy retirement | `packages/acp-client`, `packages/agent-core`, `packages/skill-index`, `packages/ui-core`, `services/gateway` |

### Top Lessons

1. Keep active planning files small after archive; full history belongs in milestone snapshots.
2. Separate autonomous-completable code/fixture work from live legal and operator gates.
3. Use post-phase milestone audits to catch missing cross-layer behavior before declaring a milestone shipped.
4. Composition hosts should call the same Protocol helpers CI dry-run proves — leaf-only paths must fail closed.
5. Protocol-first staging de-risks the critical path — ship on the existing backend before building the replacement.
6. Verification metadata must be created per-phase, not deferred to milestone close.
7. Legacy retirement is safe when gated by gate-coverage meta-tests and composability regression tests.
