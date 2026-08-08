# Feature Landscape: v3.1 Legal AI Arena

**Domain:** Multi-agent legal AI arena — parallel generation, self-score iteration, cross-review, adversarial refinement, independent final synthesis
**Milestone:** v3.1 Legal AI Arena
**Researched:** 2026-08-08
**Confidence:** HIGH (studied Crossfire, ultra-review, cross-agent-reviews, LLM4Review + related literature; v3.0 shipped ACP client, agent-core guardrails, skill-index, ui-core, event vocabulary)

## Scope Note

**Already shipped in v3.0 — do not re-scope as new work:**
- ACP client (`packages/acp-client`) — session lifecycle, `session/update` streaming, `elicitation`, `request_permission`, `fs/*` handlers
- Agent core (`packages/agent-core`) — 4 legal guardrails (research-gate, citation audit, ask-user, de-AI polish), context budget, tool layer, Word-native track-changes docx
- Skill index (`packages/skill-index`) — 396 legal skills indexed + per-backend materialization
- UI core (`packages/ui-core`) — 23 components, 3 themes, streaming chat, clarification cards
- Event vocabulary — 13-category isomorphic to ACP `session/update`, HTTP+SSE to clients
- Gateway (`services/gateway`) — multi-tenant HTTP+SSE, output boundary, channel degradation
- Dual entry points — in-process `BackendAdapter` + `inkstatute-agent acp` CLI

The arena builds **on top of** these capabilities. The arena-engine is new orchestration logic; it reuses acp-client for every agent session, agent-core for guardrails, skill-index for legal capability, and ui-core / event vocabulary for user-facing streaming.

---

## Table Stakes

Features expected in any multi-agent arena/cross-review workflow. Omitting these would make the product feel broken or amateurish.

| Feature | Why Expected | Complexity | Notes |
|---|---|---|---|
| Parallel agent execution | Core premise of "arena" — N agents process simultaneously. Every reference project runs generation/review in parallel. | Low-Medium | arena-engine dispatches N ACP sessions concurrently via acp-client. asyncio gather or task group. Complexity is in backpressure + cancellation, not parallelism itself. |
| Real-time streaming of intermediate results | User must see each agent's output as it streams. v3.0 already streams ACP `session/update` over HTTP+SSE. Lawyers won't trust a black box. | Low | Reuse existing event vocabulary + SSE. arena-engine forwards each agent's `session/update` events to the client with agent identity tags. No new transport. |
| Heterogeneous agent backends | Crossfire, ultra-review, and cross-agent-reviews all emphasize mixing LLMs for diversity. Our agents are Kimi-M3, Devin CLI, Codex — different families by design. | Low | ACP abstracts backend differences. Each agent is a stdio subprocess speaking ACP v1. arena-engine is backend-agnostic. |
| User can stop / pause / cancel | Self-score iteration (Mode 2) is user-manually-stopped. All modes need cancellation. | Medium | ACP session cancellation + subprocess termination. Must handle partial results gracefully (stream what was produced, persist incomplete state). Cancellation propagation through asyncio task tree. |
| Artifact persistence (all intermediate results) | Crossfire archives "every candidate, every review, every synthesis decision." ultra-review writes per-round markdown. LLM4Review yields "auditable artifacts at every step." Lawyers need audit trails. | Medium | arena-engine writes structured artifacts per round per agent. Reference-first logging (reuse v3.0 `raw_payload_ref` pattern). Store as JSON + markdown under arena session directory. |
| Orchestrator never produces content | ultra-review: "This separation is load-bearing — it keeps the orchestrator's judgment clean." PROJECT.md: "arena-engine 只调度和汇总，自己不产出内容." | Low | Architectural constraint, not a feature to build. Enforced by design: arena-engine only schedules, aggregates scores, and dispatches. Final version comes from an agent session, never the orchestrator. |
| Agent isolation / fresh contexts per round | Crossfire: "Fresh contexts prevent the same model from believing its own improvements are great." cross-agent-reviews: "fresh-session preflight before audit rounds." | Low-Medium | Each ACP session is a fresh subprocess. arena-engine creates new sessions per round, never reuses context. Mode 2 self-score iteration reuses the same session (agent iterates on its own work); Modes 3-4 use fresh sessions for cross-review. |
| User selects result (Mode 1) | Standard mode is "user picks result." Trivial but must exist. | Low | UI presents N streamed results side-by-side. User clicks one. arena-engine records selection. No scoring or synthesis. |
| Agent roster configuration | User must be able to select which agents participate and how many. ultra-review infers roster from diff; we let user pick. | Low | UI checkbox list of available ACP backends. arena-engine reads selection, spawns subprocesses. |
| Task instruction input | User must be able to describe the legal task. | Low | Reuse existing chat input from ui-core. arena-engine wraps instruction + selected reference directory path into ACP session prompt. |
| Reference directory selection | User selects a directory; agents use ACP `fs/read_text_file` to autonomously read reference files. | Low-Medium | UI directory picker (Tauri native dialog). arena-engine passes directory path to ACP `fs/*` handler. v3.0 already has ACP fs handlers; arena reuses them with a user-selected root instead of a fixed one. |
| Error handling / agent failure recovery | ultra-review: "agent crashes or times out mid-round → retry, reassign, or proceed without coverage and note the gap." | Medium | Per-agent timeout, retry policy, partial-result handling. arena-engine must not block all agents if one crashes. asyncio exception isolation. |

---

## Differentiators

Features that distinguish our arena from generic multi-agent tools. These are where legal-specific value and research-project patterns combine.

| Feature | Value Proposition | Complexity | Notes |
|---|---|---|---|
| Free-form scoring (10-point framework only) | Lawyers think in legal reasoning quality, not fixed dimensions like "clarity" or "novelty." A 10-point framework gives structure without forcing irrelevant criteria. Avoids the LLM4Review rubric-rigidity problem. | Low-Medium | arena-engine sends the 10-point framework as scoring guidance; agent returns free-form score + justification. No fixed dimensions to parse or validate. The framework is a prompt, not a schema. |
| Non-bypassable legal guardrails | research-gate, citation audit, ask-user, de-AI polish run inside every agent session regardless of mode. No agent can skip "search before concluding" or citation verification. This is impossible in Crossfire/ultra-review (they have no domain guardrails). | Medium | Reuse agent-core guardrails. The key work is ensuring guardrails fire inside ACP subprocess sessions, not just in-process. agent-core's dual entry point (`inkstatute-agent acp`) already enforces this. arena-engine must not bypass by using a raw ACP backend. |
| Independent session for final synthesis | Mode 3-4: a separate agent session takes the highest-scored result + all review opinions and produces the final version. The orchestrator doesn't synthesize — an agent does. This is our analogue to Crossfire's synthesizer and LLM4Review's Meta-Reviewer, but the synthesizer is a full agent session with guardrails, not a single LLM call. | Medium | arena-engine selects highest-scored result, collects all cross-review opinions, spawns a fresh ACP session with a synthesis prompt. The synthesis agent has guardrails + skill-index access. Output is the final version. |
| Adversarial weakness-finding (Mode 4) | Agents don't just review — they actively try to find weaknesses in the highest-scored result. From Crossfire ("attack them for weaknesses") and ultra-review ("try to DISPROVE findings"). For legal work, this means probing for citation gaps, logical flaws, missing counterarguments, jurisdiction errors. | Medium-High | arena-engine dispatches adversarial review sessions. Each gets the target result + a "find weaknesses" prompt. Results are structured weakness reports. Complexity is in prompt design + structuring output for the synthesis session to consume. |
| Early stopping (Mode 4) | Crossfire: "stops early if reviewers find no material weaknesses." cross-agent-reviews: "clean 3a → pipeline terminates." Saves tokens and time when convergence is reached. | Medium | arena-engine evaluates stopping condition after each round: if adversarial reviewers find no material weaknesses (or score delta below threshold), stop. Requires a structured "weaknesses found" signal from review sessions. |
| Self-score with self-model bias awareness | LLM4Review: "predictable biases (order, verbosity, self-model) mitigated by independence, aggregation, and optional cross-review." Our Mode 2 self-score is explicitly designed with this in mind — the 10-point framework is free-form to avoid anchoring, and Mode 3 cross-review exists precisely to counter self-score bias. | Low | Prompt design: self-score instruction includes awareness of self-model bias ("score as if reviewing a colleague's work, not your own"). No code complexity; this is a prompt engineering differentiator. |
| Reliability-weighted score aggregation | LLM4Review: "aggregate reviewer scores with reliability-aware weighting." Instead of simple averaging, weight each reviewer's score by their demonstrated reliability (e.g., did their weaknesses get confirmed by other reviewers?). | Medium-High | arena-engine tracks per-reviewer confirmation rate across rounds. Reviewers whose findings are independently confirmed get higher weight. Requires structured review output + cross-reference tracking. Could be deferred to post-MVP. |
| Cross-examination / disprove pattern | ultra-review Round 2: "Reviewers try to DISPROVE findings, not validate them. Survivors must be defensible." Applied to legal: cross-reviewers don't just score — they try to disprove the primary agent's legal reasoning, citation accuracy, and factual claims. | Medium | arena-engine structures cross-review as "attempt to disprove" not "rate quality." Prompt instructs reviewer to find specific disproofs. Output is structured: confirmed / disproven / cannot-verify per claim. |
| Review profiles by task risk | cross-agent-reviews: `patch` / `feature` / `greenfield` profiles set minimum review breadth. Our analogue: simple legal tasks (Mode 1-2) vs high-stakes (Mode 3-4). User picks mode = picks risk profile. | Low | Mode selection IS the profile. No separate config needed. Mode 4 (adversarial) is the "greenfield" equivalent — maximum scrutiny. |
| Prompt enrichment | Crossfire: "prompt enrichment step is especially useful for one-line instructions." For legal tasks, enrichment could expand a terse instruction into a structured legal task description with relevant skill references. | Medium | arena-engine (or a pre-processing agent session) expands the user's instruction using skill-index lookup. E.g., "review this contract" → enriched with relevant contract review skills + reference file context. Must not produce content — only enrich the prompt. |
| Categorical confidence labels | ultra-review: "Confidence is categorical, not numeric: Certain / Likely / Possible. Numeric confidence is theatre." For legal findings, categorical confidence is more honest and actionable than percentages. | Low | Review output schema includes confidence field with 3 levels. Lawyers understand "verified citation" vs "plausible but unverified" better than "67% confident." |
| Fresh-context multi-round synthesis (Mode 4) | Crossfire: "Each round starts clean, which avoids local optima." Multi-round synthesis with fresh contexts prevents the synthesis agent from anchoring on its own previous output. | Medium | Each synthesis round is a new ACP session. Input: previous round's output + new adversarial findings. arena-engine manages the round loop + stopping condition. |
| Independent confirmation as signal | ultra-review: "Two independent Likelys ≈ Certain. Overlap is a feature." When multiple cross-reviewers independently flag the same weakness, it's the strongest signal. | Low-Medium | arena-engine deduplicates findings and counts independent confirmations. Findings confirmed by 2+ reviewers get elevated priority in the synthesis input. |
| Word-native track-changes output | Legal-specific: the final synthesized version must be deliverable as a Word document with native track-changes for lawyer review and negotiation. No reference project does this. | Low | Reuse agent-core's `contract_review_trackchanges.py` (41,185 bytes, shipped in v3.0). The synthesis agent's output is post-processed into track-changes docx. |
| Provenance logging for legal documents | LLM4Review: "sanitization and provenance logging substantially reduce decision drift." For legal work, every claim must trace to a source (citation, statute, reference file). | Medium | arena-engine logs which agent produced which claim, which reviewer confirmed/disproved it, and which source it cites. Reuse v3.0 reference-first logging pattern. |
| Document-borne prompt injection sanitization | LLM4Review: "document-borne prompt injections can shift recommendations." Legal reference files (contracts, evidence) could contain adversarial text. | Medium | Sanitize reference file content before passing to agent sessions. Strip or flag embedded instructions. This is a legal-specific security concern — opposing counsel's documents could contain hidden instructions. |

---

## Anti-Features

Things we explicitly will NOT do, even though some multi-agent tools do them.

| Anti-Feature | Why Avoid | What to Do Instead |
|---|---|---|
| Orchestrator produces content | ultra-review proves the separation is load-bearing. If the orchestrator writes legal content, its judgment is contaminated by generation bias. It also creates a liability path — who is responsible for orchestrator-generated legal text? | arena-engine only schedules, aggregates scores, and dispatches. Final version always comes from an agent session with guardrails. |
| Fixed scoring dimensions | LLM4Review uses rubric-based critiques, but fixed dimensions (novelty, clarity, etc.) are irrelevant to legal work and create anchoring bias. Lawyers score on legal reasoning quality, which is task-dependent. | Free-form 10-point framework. The framework is a prompt, not a schema. Agent decides what dimensions matter for this specific task. |
| Numeric confidence percentages | ultra-review: "nobody can calibrate 67% confident meaningfully." Numeric confidence in legal findings is misleading and creates false precision. | Categorical confidence: Certain / Likely / Possible, with explicit "what would close the gap" statements. |
| Auto-approve high-risk legal conclusions | v3.0 SAFE-01: `requires_human_review` is always true for legal conclusion skills. Automating this would violate a binding safety constraint. | All high-risk legal conclusions flow through human review gates. arena-engine records `skill_candidate` with `requires_human_review=true`. |
| Fixed agent type catalog | ultra-review: "No fixed catalog of agent types. Every review is custom-designed from the diff." Fixed roles (Author, Reviewer, etc. from LLM4Review) are too rigid for diverse legal tasks. | User selects which ACP backends participate. Roles emerge from mode (generator, self-scorer, cross-reviewer, adversary, synthesizer) — same agent can play different roles in different modes. |
| Mid-flight agent coordination | ultra-review: "No mid-flight coordination. No splitting work between agents." Coordination introduces coupling and destroys independence, which is the whole point. | Agents work in isolated sessions. Communication happens through structured artifacts (files), not real-time messaging. |
| Speed optimization | ultra-review: "It will not run quickly. A medium review can take an hour. That is the point." Legal work is high-stakes; trading thoroughness for speed is the wrong optimization. | Modes 1-2 are fast (parallel, no iteration or user-stopped). Modes 3-4 are deliberately thorough. No "turbo mode" that skips guardrails or reduces review depth. |
| Auto-synthesize or auto-modify legal conclusion skills | Binding v3.0 constraint (SAFE-01, SAFE-04). The arena must not create new legal skills or modify existing ones. | Arena produces task outputs (documents, analyses), not skills. Skill candidates go through human review. |
| Bypass guardrails for "efficiency" | The 4 legal guardrails are non-bypassable by design. Any mode that skips them is a liability. | All 4 modes enforce guardrails inside every agent session. arena-engine must use agent-core's ACP entry point, not raw ACP backends. |
| Commit secrets or raw legal payloads | Binding privacy constraint. Arena artifacts could contain sensitive legal content. | Reference-first logging. Artifacts stored locally under arena session directory, never committed. Reuse v3.0 privacy patterns. |

---

## Feature Dependencies

```
v3.0 Shipped Capabilities (foundation — no new work)
├── packages/acp-client ──────────────────► Arena agent session management
│                                              (spawn, stream, cancel ACP subprocesses)
├── packages/agent-core ──────────────────► Legal guardrails in every session
│   ├── research-gate                         (non-bypassable, enforced in ACP entry)
│   ├── citation audit                        (verified/retrieved/unverified)
│   ├── ask-user enforcement                  (block drafting when facts missing)
│   └── de-AI polish                          (remove AI-speak)
├── packages/skill-index ─────────────────► Legal capability for all agents
│                                              (396 skills, per-backend materialization)
├── packages/ui-core ─────────────────────► Arena UI (streaming, cards, selection)
├── services/gateway (event vocabulary) ──► HTTP+SSE streaming to desktop app
└── ACP fs/* handlers ────────────────────► Reference file reading

v3.1 New Work
├── packages/arena-engine (NEW)
│   ├── Mode 1: Standard parallel ─────────► depends on: acp-client, event vocabulary
│   ├── Mode 2: Self-score iteration ──────► depends on: Mode 1 + 10-point framework prompt
│   ├── Mode 3: Arena review ──────────────► depends on: Mode 2 + cross-review dispatch
│   │   └── Independent synthesis session ──► depends on: acp-client, agent-core, skill-index
│   └── Mode 4: Adversarial arena ─────────► depends on: Mode 3 + adversarial prompts
│       ├── Early stopping ────────────────► depends on: structured weakness output
│       └── Multi-round synthesis ─────────► depends on: fresh-context round loop
│
├── services/arena-service (NEW)
│   ├── HTTP+SSE endpoint ─────────────────► depends on: event vocabulary (reuse Gateway patterns)
│   └── ACP fs/* handler (user-selected dir)► depends on: acp-client fs handlers
│
├── Arena UI (desktop app, NEW screens)
│   ├── Agent roster selection ────────────► depends on: ui-core
│   ├── Reference directory picker ────────► depends on: Tauri native dialog
│   ├── Mode selector ─────────────────────► depends on: ui-core
│   ├── Multi-agent streaming view ────────► depends on: ui-core, event vocabulary
│   ├── Score display ─────────────────────► depends on: ui-core
│   └── Result selection ──────────────────► depends on: ui-core
│
└── Cross-cutting
    ├── Artifact persistence ──────────────► depends on: arena-engine + reference-first logging
    ├── Provenance logging ────────────────► depends on: arena-engine + v3.0 contract log patterns
    └── Prompt injection sanitization ─────► depends on: arena-engine + reference file handler
```

**Critical path:** Mode 1 (Standard) → Mode 2 (Self-score) → Mode 3 (Arena review) → Mode 4 (Adversarial). Each mode builds on the previous. Mode 1 alone is a usable product (parallel comparison). Mode 3 is the differentiator (cross-review + independent synthesis). Mode 4 is the high-stakes variant.

---

## Pattern Mapping

Which patterns from the four reference projects map to our 4 workflow modes.

### Crossfire (ianreppel.org/crossfire)

| Pattern | Our Mode | How We Adopt |
|---|---|---|
| Generation → review → synthesis loop | Mode 3, 4 | Mode 3: agents generate → cross-review → independent synthesis. Mode 4: same loop + adversarial + multi-round. |
| Fresh contexts per round | Mode 3, 4 | Each cross-review and synthesis round is a fresh ACP session. Prevents anchoring. Mode 2 self-score reuses session (agent iterates on own work — intentional). |
| Prompt enrichment | All modes | Pre-processing step expands terse legal instructions using skill-index lookup. Optional; skipable for expert users. |
| Early stopping when no material weaknesses | Mode 4 | Adversarial reviewers find no material weaknesses → stop. Saves tokens on converged results. |
| Synthesizer picks best parts, discards weak | Mode 3, 4 | Independent synthesis session takes highest-scored result + all review opinions. Synthesizer is a full agent (with guardrails), not a single LLM call. |
| All artifacts archived locally | All modes | arena-engine writes structured artifacts per round per agent. Audit trail for legal work. |
| Parallel generation and review within rounds | All modes | N agents generate in parallel (Mode 1). N cross-reviewers review in parallel (Mode 3-4). asyncio concurrency. |

### ultra-review (alexrolls/ultra-review)

| Pattern | Our Mode | How We Adopt |
|---|---|---|
| Orchestrator never writes findings | All modes | arena-engine only schedules and aggregates. Final version from agent session. Binding architectural constraint. |
| 4-round adversarial deep review | Mode 4 | Our Mode 4 is adversarial. We don't fix 4 rounds — we use early stopping + user-configurable max rounds. But the discovery → cross-examine → finalize → digest shape maps directly. |
| Cross-examination: try to DISPROVE | Mode 3, 4 | Cross-reviewers attempt to disprove the primary agent's legal reasoning, not just rate it. Structured output: confirmed / disproven / cannot-verify. |
| Categorical confidence (Certain/Likely/Possible) | Mode 3, 4 | Review output includes categorical confidence with "what would close the gap" statements. No numeric percentages. |
| Multiple agents on hot areas (overlap is a feature) | Mode 3, 4 | Multiple cross-reviewers examine the same result from different angles. Independent confirmation = strongest signal. |
| No fixed agent type catalog | All modes | User selects ACP backends. Roles emerge from mode, not from a fixed roster. |
| Agents communicate via files, not return values | All modes | arena-engine passes structured artifacts between rounds via files / in-memory structured objects. Agents don't message each other directly. |
| High-impact override | Mode 4 | Legal high-risk areas (citation accuracy, jurisdiction, statutory interpretation) keep Likely/Possible findings regardless of confidence policy. |
| 80/20 effort split | Mode 3, 4 | Cross-reviewers focus on highest-risk aspects of the legal output (citation accuracy, logic, missing counterarguments) rather than evenly distributing attention. |

### cross-agent-reviews (j7an/cross-agent-reviews)

| Pattern | Our Mode | How We Adopt |
|---|---|---|
| 3-round audit → settle pipeline | Mode 3, 4 | Mode 3: self-score (audit) → cross-review (audit) → synthesis (settle). Mode 4 adds adversarial + multi-round. We don't fix 3 rounds — mode determines depth. |
| Review profiles by risk (patch/feature/greenfield) | All modes | Mode selection IS the profile. Mode 1 = patch (quick). Mode 4 = greenfield (maximum scrutiny). No separate config. |
| Fresh session per audit round | Mode 3, 4 | Cross-review rounds use fresh ACP sessions. Self-score (Mode 2) may reuse session (agent iterates on own work). Synthesis uses fresh session. |
| Clean final audit → terminate early | Mode 4 | If final adversarial round finds no material weaknesses, terminate. Maps to cross-agent-reviews "clean 3a → READY_FOR_IMPLEMENTATION." |
| State-driven pipeline | All modes | arena-engine maintains arena session state (current mode, round, agent results, scores). Enables pause/resume. |
| Terminal status (READY / CORRECTED) | Mode 3, 4 | arena-engine produces terminal status: user-selected (Mode 1), user-stopped (Mode 2), synthesized (Mode 3), adversarially-confirmed (Mode 4). |

### LLM4Review (OpenReview 7dJ7BFv9AT)

| Pattern | Our Mode | How We Adopt |
|---|---|---|
| Author / Reviewer / Reviser / Meta-Reviewer roles | Mode 3, 4 | Generator (Author) → Cross-reviewer (Reviewer) → Synthesis session (Reviser + Meta-Reviewer combined). We collapse Reviser + Meta-Reviewer into one independent synthesis session because the synthesizer is a full agent with guardrails, not a threshold-based gate. |
| Rubric-based critiques | Mode 2, 3 | Our 10-point framework is a lightweight rubric. But it's free-form (no fixed dimensions) — the agent decides what matters. This is a deliberate departure from LLM4Review's fixed rubric. |
| Reliability-aware weighting | Mode 3, 4 (post-MVP) | Weight cross-reviewer scores by confirmation rate. Reviewers whose findings are independently confirmed get higher weight. Deferred to post-MVP — simple averaging first. |
| Self-model bias mitigation | Mode 2, 3 | Mode 2 self-score prompt includes bias awareness. Mode 3 cross-review exists specifically to counter self-score bias. The progression from self-score to cross-review is our bias mitigation strategy. |
| Round-based protocol with quality tracking | Mode 2, 3, 4 | Track score across rounds. Mode 2: self-score should improve across iterations. Mode 4: synthesis quality should converge. |
| Document-borne prompt injection → sanitization + provenance | All modes | Legal reference files (contracts, evidence) could contain adversarial text. Sanitize before passing to agents. Log provenance of every claim. |
| Auditable artifacts at every step | All modes | Every agent output, score, review, synthesis decision is persisted. Legal audit trail. |
| Accept/continue/reject decision under thresholds | Mode 4 | Early stopping condition = "reject further rounds" when no material weaknesses found. "Continue" = another adversarial round. "Accept" = synthesize final version. |
| Quality-cost trade-off measurement | All modes (optional) | Track tokens, time, rounds per arena session. Display to user. Not a core feature but useful for mode selection guidance. |

---

## MVP Recommendation

**Ship Mode 1 (Standard) + Mode 2 (Self-score iteration) first. Mode 3 (Arena review) is the differentiator milestone. Mode 4 (Adversarial) is the high-stakes variant.**

### Phase 1: MVP — Mode 1 + Mode 2 (usable product)

| Feature | Priority | Complexity | Depends On |
|---|---|---|---|
| arena-engine core (session orchestration, parallel dispatch) | P0 | Medium | acp-client |
| Mode 1: N agents parallel, user picks result | P0 | Low | arena-engine, ui-core |
| Mode 2: self-score iteration with 10-point framework | P0 | Low-Medium | Mode 1 + scoring prompt |
| Real-time multi-agent streaming view | P0 | Low | event vocabulary, ui-core |
| Reference directory selection + ACP fs handler | P0 | Low-Medium | acp-client fs handlers |
| Artifact persistence (per agent, per round) | P0 | Medium | arena-engine |
| User stop/pause/cancel | P0 | Medium | arena-engine, ACP cancellation |
| arena-service HTTP+SSE endpoint | P0 | Medium | event vocabulary (reuse Gateway patterns) |
| Agent roster selection UI | P0 | Low | ui-core |
| Mode selector UI | P0 | Low | ui-core |

**Rationale:** Mode 1+2 is immediately useful (lawyers compare agent outputs, iterate on quality). It proves the arena-engine, streaming, and artifact persistence without the complexity of cross-review or synthesis. It's a complete product on its own.

### Phase 2: Differentiator — Mode 3 (Arena review)

| Feature | Priority | Complexity | Depends On |
|---|---|---|---|
| Cross-review dispatch (N reviewers examine each result) | P0 | Medium | Mode 2 |
| Structured review output (findings, confidence, confirmed/disproved) | P0 | Medium | arena-engine |
| Independent synthesis session (highest-scored + all opinions → final) | P0 | Medium | acp-client, agent-core, skill-index |
| Cross-examination / disprove prompt design | P0 | Medium | arena-engine |
| Categorical confidence labels in review output | P1 | Low | structured review output |
| Independent confirmation tracking | P1 | Low-Medium | structured review output |
| Score display UI (per agent, per round) | P0 | Low | ui-core |
| Word-native track-changes output for final version | P1 | Low | agent-core (shipped) |

**Rationale:** Mode 3 is the core differentiator. Cross-review + independent synthesis is what makes this an "arena" not just "parallel comparison." This is where the research-project patterns (Crossfire synthesis, ultra-review cross-examination, LLM4Review roles) converge.

### Phase 3: High-stakes — Mode 4 (Adversarial arena)

| Feature | Priority | Complexity | Depends On |
|---|---|---|---|
| Adversarial weakness-finding prompts | P0 | Medium-High | Mode 3 |
| Multi-round synthesis with fresh contexts | P0 | Medium | Mode 3 |
| Early stopping (no material weaknesses → terminate) | P0 | Medium | structured weakness output |
| Reliability-weighted score aggregation | P2 | Medium-High | cross-review tracking |
| Prompt enrichment (skill-index lookup) | P2 | Medium | skill-index |
| Prompt injection sanitization for reference files | P1 | Medium | arena-engine |
| Provenance logging (claim → source → reviewer) | P1 | Medium | arena-engine |
| Quality-cost trade-off display | P2 | Low | arena-engine |

**Rationale:** Mode 4 is for high-stakes legal tasks where thoroughness matters more than speed. It builds directly on Mode 3. Early stopping and multi-round synthesis are the key additions. Reliability-weighted aggregation and prompt enrichment are post-MVP polish.

### What NOT to build in v3.1

- Reliability-weighted aggregation (defer to post-MVP — simple averaging first)
- Fixed scoring dimensions (anti-feature — never build)
- Numeric confidence percentages (anti-feature)
- Auto-approve legal conclusions (binding constraint — never build)
- Fixed agent type catalog (anti-feature)
- Mid-flight agent coordination (anti-feature)
- Speed optimization / turbo mode (anti-feature)

---

## Sources

| Source | URL | Key Patterns Extracted |
|---|---|---|
| Crossfire | https://ianreppel.org/crossfire | generation→review→synthesis loop, fresh contexts per round, prompt enrichment, early stopping, synthesizer picks best parts, parallel within rounds, all artifacts archived |
| ultra-review | https://github.com/alexrolls/ultra-review | 4-round adversarial review, orchestrator never writes findings, cross-examination (disprove not validate), categorical confidence, overlap is a feature, no fixed agent catalog, agents communicate via files, high-impact override, 80/20 effort split |
| cross-agent-reviews | https://github.com/j7an/cross-agent-reviews | 3-round audit→settle pipeline, review profiles by risk (patch/feature/greenfield), fresh session per audit round, clean final audit terminates early, state-driven pipeline, terminal status |
| LLM4Review | https://openreview.net/forum?id=7dJ7BFv9AT | Author/Reviewer/Reviser/Meta-Reviewer roles, rubric-based critiques, reliability-aware weighting, self-model bias mitigation, round-based protocol, document-borne prompt injection → sanitization + provenance, auditable artifacts, accept/continue/reject thresholds, quality-cost trade-offs |
| LLM-REVal | https://arxiv.org/html/2510.12367 | LLM reviewers systematically inflate scores for LLM-authored work; linguistic feature bias; revisions guided by LLM reviews yield quality gains — validates our self-score → cross-review progression |
| PRE (Peer Review Evaluator) | https://arxiv.org/html/2401.15641 | Single-LLM evaluation has biasness; peer review mechanism outperforms baselines — validates multi-agent cross-review over single-agent scoring |
| RubricReviewer | https://arxiv.org/html/2608.00005 | Explicit rubric generation as intermediate step; rubric-conditioned review; robustness against prompt injection — supports our 10-point framework + injection sanitization |
| PROJECT.md | /home/sorawatcher/workspace/inkstatute-suite/.planning/PROJECT.md | v3.0 shipped capabilities, 4-mode workflow definition, architecture, binding decisions, legal guardrails, human gates |
