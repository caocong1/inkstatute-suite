# Requirements: 墨律 InkStatute — v3.1 Legal AI Arena

**Defined:** 2026-08-08
**Core Value:** 律师可在桌面 app 内创建法律任务，选择多个 ACP 后端 agent 并行处理，每个 agent 自评迭代到满意后交叉评审，最终由独立 session 综合评审意见产出最终版——全程流式可见、法律护栏不绕过。

## v3.1 Requirements

Requirements for the Legal AI Arena milestone. Each maps to roadmap phases (105–110).

### Arena Contract

- [ ] **CONTRACT-01**: Arena lifecycle events added to event vocabulary (`arena.workflow_started/completed`, `arena.score_recorded`, `arena.review_completed`, `arena.synthesis_started/completed`, `arena.adversarial_challenge_completed`, `arena.early_stop_triggered`)
- [ ] **CONTRACT-02**: `ArenaWorkflowConfig` / `ArenaHandle` / `ArenaStatus` / `ArenaUserAction` Python dataclasses and TypeScript interfaces defined
- [ ] **CONTRACT-03**: `ArenaWorkflow` Protocol defined in `platform-runtime`
- [ ] **CONTRACT-04**: Arena events validated via JSON Schema, fixture replay, and composability tests

### ACP fs Handler

- [ ] **FS-01**: `acp-client` advertises `clientCapabilities.fs.readTextFile: true` at `initialize`
- [ ] **FS-02**: Inbound `fs/read_text_file` requests routed to registered handler
- [ ] **FS-03**: Path sandboxing (resolve + prefix-check + symlink rejection + extension allowlist + size cap)
- [ ] **FS-04**: Backward compatible with Gateway path (no `client_capabilities` passed)

### Arena Engine (4 modes)

- [ ] **ENGINE-01**: Mode 1 Standard — N agents process in parallel via `asyncio.TaskGroup`, user selects result
- [ ] **ENGINE-02**: Mode 2 Self-score iteration — agent self-scores with 10-point framework, self-optimizes, user manually stops
- [ ] **ENGINE-03**: Mode 3 Arena review — self-score iteration + multi-agent cross-review + independent session synthesis
- [ ] **ENGINE-04**: Mode 4 Adversarial — arena review + adversarial weakness-finding + multi-round synthesis + early stopping
- [ ] **ENGINE-05**: Orchestrator never produces content (gate test: no LLM provider imports in arena-engine)
- [ ] **ENGINE-06**: Fresh context per round for cross-review/synthesis (gate test: no `session/resume` calls)
- [ ] **ENGINE-07**: Artifact persistence — structured output per agent per round, reference-first logging
- [ ] **ENGINE-08**: Agent failure recovery — timeout, retry, partial results, asyncio exception isolation
- [ ] **ENGINE-09**: User stop/pause/cancel with graceful partial result handling

### Arena Service

- [ ] **SVC-01**: Local HTTP+SSE service bound to `127.0.0.1:8001` with local token auth
- [ ] **SVC-02**: Endpoints: create/stream/cancel/action/status arena workflow
- [ ] **SVC-03**: N agent streams multiplexed on single SSE connection with `metadata.agent_slot`
- [ ] **SVC-04**: Output boundary enforced (same ACP output filter as Gateway)
- [ ] **SVC-05**: Permission safety — dangerous kinds denied immediately, no batch approve
- [ ] **SVC-06**: Subprocess liveness check + per-run timeout + partial-result acceptance
- [ ] **SVC-07**: SSE reconnection support (buffer by run ID)
- [ ] **SVC-08**: Staggered startup semaphore to avoid concurrent `initialize` contention

### Arena UI

- [ ] **UI-01**: Arena workflow creator (mode/agent/task/directory selection)
- [ ] **UI-02**: Parallel stream panel — N demultiplexed live agent streams
- [ ] **UI-03**: Score card display (per agent, per round)
- [ ] **UI-04**: Review summary display (findings, confidence, confirmed/disproved)
- [ ] **UI-05**: Synthesis viewer (final version + Word-native track-changes export)
- [ ] **UI-06**: `ArenaEventReducer` demultiplexes — composes existing `reduce()` per slot
- [ ] **UI-07**: Refresh preserves state — run state persistence + SSE reconnection

### Legal Safety & Guardrails

- [ ] **SAFE-01**: Legal guardrails non-bypassable in all 4 modes (research-gate, citation audit, ask-user, de-AI polish)
- [ ] **SAFE-02**: Post-hoc citation audit for external ACP agents (v3.0 guardrails live in `turn_loop.py`)
- [ ] **SAFE-03**: Post-hoc de-AI polish for external ACP agents
- [ ] **SAFE-04**: High-risk legal conclusions retain `requires_human_review=true`
- [ ] **SAFE-05**: Prompt injection sanitization for reference files
- [ ] **SAFE-06**: Cross-family review enforcement (`backend_family(A) != backend_family(B)`)
- [ ] **SAFE-07**: Provenance logging per claim (agent → reviewer → source)

### Integration & Gates

- [ ] **GATE-01**: Gate-coverage meta-test updated (34 → 36+ gates)
- [ ] **GATE-02**: `solutions/demo_non_legal` arena variant composability test
- [ ] **GATE-03**: End-to-end integration tests across all 4 modes
- [ ] **GATE-04**: fs/* sandbox escape tests (path traversal, symlinks, absolute paths)
- [ ] **GATE-05**: Permission safety tests (no batch approve, dangerous kinds preserved)
- [ ] **GATE-06**: Orphaned subprocess test on cancel (zero PID assertion)

## Future Requirements (post-v3.1)

- **FUTURE-01**: Reliability-weighted score aggregation (confirmation-rate tracking, bias-correction factor)
- **FUTURE-02**: Prompt enrichment via skill-index lookup (expand terse instructions)
- **FUTURE-03**: Quality-cost trade-off display (tokens, time, rounds per arena session)
- **FUTURE-04**: Arena run state persistence format (atomic JSON vs SQLite)
- **FUTURE-05**: Cross-family taxonomy definition (backend_family classification schema)
- **FUTURE-06**: Arena composability with remote Gateway (skill index / practice config / persistence)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Orchestrator produces content | ultra-review proves separation is load-bearing; bypasses guardrails and output boundary |
| Fixed scoring dimensions | LLM4Review rubric rigidity; legal reasoning quality is task-dependent, not dimension-bound |
| Numeric confidence percentages | ultra-review: "nobody can calibrate 67% confident"; categorical (Certain/Likely/Possible) is more honest |
| Auto-approve high-risk legal conclusions | Binding v3.0 constraint SAFE-01: `requires_human_review` always true |
| Fixed agent type catalog | Roles emerge from mode, not from fixed roster; user selects ACP backends |
| Mid-flight agent coordination | Destroys independence; agents communicate via structured artifacts only |
| Speed optimization / turbo mode | Legal work is high-stakes; trading thoroughness for speed is wrong optimization |
| Auto-synthesize/modify legal conclusion skills | Binding v3.0 constraint; arena produces outputs, not skills |
| Bypass guardrails for efficiency | 4 guardrails non-bypassable by design; any bypass is liability |
| Commit secrets or raw legal payloads | Binding privacy constraint; reference-first logging, local artifacts only |
| Mobile native app | V4 scope (carried from v3.0) |
| SaaS scaling (agent pool / remote ACP) | V4 scope (carried from v3.0) |

## Traceability

To be populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| (pending roadmap) | | |

**Coverage:**
- v3.1 requirements: 38 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 38 ⚠️

---
*Requirements defined: 2026-08-08*
*Last updated: 2026-08-08 after initial definition*
