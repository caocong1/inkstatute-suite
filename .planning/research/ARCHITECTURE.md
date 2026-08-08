# Architecture Patterns

> Research for v3.1 Legal AI Arena — multi-agent workflow orchestration integrated
> onto the existing v3.0 Unified Legal Core platform.

## Recommended Architecture (diagram + description)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Desktop App (Tauri 2 + SolidJS + ui-core)                          │
│                                                                     │
│  ┌──────────────┐  ┌─────────────────────────────────────────────┐  │
│  │ Existing Chat │  │ Arena UI (NEW)                              │  │
│  │ WorkspacePage │  │  • Workflow creation (mode 1-4, agent pick) │  │
│  │ → Gateway     │  │  • Live parallel streams (multiplexed SSE)  │  │
│  │               │  │  • Self-score cards / cross-review display  │  │
│  │               │  │  • Intermediate + final result viewer       │  │
│  └──────┬────────┘  └──────────────┬──────────────────────────────┘  │
│         │ HTTP+SSE                  │ HTTP+SSE (isomorphic vocab)    │
│         │                           │                                 │
│         ▼                           ▼                                 │
│  ┌──────────────┐          ┌──────────────────────┐                  │
│  │  Gateway     │          │  Arena Service (NEW) │                  │
│  │  (existing)  │          │  services/arena-svc  │                  │
│  │  :8000       │          │  Python HTTP+SSE     │                  │
│  └──────────────┘          │  :8001 (localhost)   │                  │
│                            │                      │                  │
│                            │  ┌────────────────┐  │                  │
│                            │  │ arena-engine   │  │                  │
│                            │  │ (NEW package)  │  │                  │
│                            │  │  4-mode sched. │  │                  │
│                            │  │  parallel disp │  │                  │
│                            │  │  self-score    │  │                  │
│                            │  │  cross-review  │  │                  │
│                            │  │  final synth.  │  │                  │
│                            │  └───────┬────────┘  │                  │
│                            │          │           │                  │
│                            │  ┌───────▼────────┐  │                  │
│                            │  │ acp-client     │  │                  │
│                            │  │ (REUSED +     │  │                  │
│                            │  │  EXTENDED)     │  │                  │
│                            │  │  fs/* handler  │  │                  │
│                            │  └───────┬────────┘  │                  │
│                            │          │           │                  │
│                            │  ┌───────▼────────┐  │                  │
│                            │  │ agent-core     │  │                  │
│                            │  │ guardrails     │  │                  │
│                            │  │ skill-index    │  │  (REUSED)        │
│                            │  └────────────────┘  │                  │
│                            └──────────┬───────────┘                  │
└───────────────────────────────────────┼─────────────────────────────┘
                                        │ ACP over stdio
                                        │ (one subprocess per agent)
                          ┌─────────────┼─────────────┐
                          ▼             ▼             ▼
                   ┌──────────┐  ┌──────────┐  ┌──────────┐
                   │ Agent A  │  │ Agent B  │  │ Agent C  │
                   │ (hermes  │  │ (inkstat │  │ (codex   │
                   │  acp)    │  │ -agent   │  │  acp)    │
                   │          │  │  acp)    │  │          │
                   └──────────┘  └──────────┘  └──────────┘
```

### Description

The arena extends the v3.0 platform with **two new local components** and
**one new UI surface**, reusing the existing event vocabulary, ACP client,
agent core guardrails, and skill index without modification to their
contracts.

**Arena Service** (`services/arena-service`) is a local Python HTTP+SSE
service that exposes the arena workflow to the desktop app. It speaks the
**same 13-category event vocabulary** as the Gateway (`platform-contract`),
so the desktop app can reuse `PlatformApiClient`, `EventStreamStore`, and
the `event-reducer` from `ui-core` with minimal adaptation. The service is
the ACP **client** — it spawns agent subprocesses, negotiates `initialize`,
creates sessions, sends prompts, and streams `session/update` notifications.
Because agents are local stdio subprocesses, the service **must** run
locally (same machine as the desktop app).

**Arena Engine** (`packages/arena-engine`) is a pure-Python workflow
orchestration library imported by the arena service. It implements the four
workflow modes (standard, self-score iteration, competitive review,
adversarial). It **only schedules and aggregates** — it dispatches prompts
to agents via `acp-client`, collects their streamed events, scores results,
and synthesizes final versions by dispatching to a final agent session. It
**never produces content itself**.

**Arena UI** is a new surface in the desktop app (`apps/desktop`), built
with `ui-core` components and a new `ArenaEventStreamStore` that demultiplexes
the parallel agent streams. It reuses the existing `PlatformApiClient` pattern
(pointed at `localhost:8001` instead of `localhost:8000`).

The Gateway remains unchanged — it continues to serve the existing single-agent
chat workflow. The arena service is a **separate local service**, not a Gateway
endpoint, because (a) it must run locally to spawn stdio subprocesses, (b) it
needs ACP `fs/*` handling that the Gateway does not provide, and (c) it keeps
the arena's multi-agent lifecycle isolated from the Gateway's single-run model.

## Component Boundaries

| Component | Responsibility | Communicates With | Status |
|---|---|---|---|
| `packages/arena-engine` | 4-mode workflow orchestration: parallel dispatch, self-score iteration loop, cross-review pairing, final synthesis dispatch, early-stop evaluation. Pure scheduling + aggregation — never produces content. | `acp-client` (dispatch prompts, stream events), `agent-core` guardrails (enforce non-bypassable), `platform-contract` (event types) | **NEW** |
| `services/arena-service` | Local HTTP+SSE service exposing arena workflow to desktop app. ACP client role: spawns agent subprocesses, handles `fs/read_text_file` requests from agents, multiplexes parallel streams onto single SSE, enforces output boundary, denies/escalates dangerous permissions. | Desktop app (HTTP+SSE), `arena-engine` (orchestration), `acp-client` (ACP transport), `platform-contract` (event vocab), `platform-runtime.output_boundary` (output filter) | **NEW** |
| `packages/acp-client` | ACP v1 stdio client: `initialize` negotiation, `session/new`, `session/prompt`, `stream_updates`, `session/cancel`, `session/close`. **Extended** to advertise `clientCapabilities.fs.readTextFile` and handle inbound `fs/read_text_file` requests from agents. | Agent subprocesses (stdio), `arena-service` (caller) | **MODIFIED** (fs/* handler + client capability advertisement) |
| `packages/acp-event-bridge` | Bidirectional ACP↔unified event mapping, ACP output filter (pre-filter before default boundary). | `acp-client` (events), `arena-service` (output boundary) | **REUSED** (no changes) |
| `packages/agent-core` | Python async streaming turn loop, 4 legal guardrails, dual entry points. Guardrails enforced in all arena modes. | `arena-engine` (guardrail enforcement on dispatched prompts), agent subprocess via `inkstatute-agent acp` | **REUSED** (no changes to contract; guardrail enforcement hooks called by arena-engine) |
| `packages/skill-index` | 396 legal skills indexed, per-backend materialization. | `arena-engine` (skill context for prompt enrichment) | **REUSED** (no changes) |
| `packages/platform-contract` | 13-category event vocabulary, JSON Schemas, Python dataclasses, TypeScript interfaces. **Extended** with arena-specific event metadata (agent slot ID, score, review phase). | All components | **MODIFIED** (add arena event metadata fields, new schemas for score/review) |
| `packages/platform-sdk-ts` | TypeScript HTTP client + event type definitions. **Extended** with arena client methods and arena event types. | Desktop app, arena service | **MODIFIED** (add arena endpoints + event types) |
| `packages/ui-core` | SolidJS components, event-reducer, EventStreamStore. **Extended** with arena-specific components (parallel stream panels, score cards, review display). | Desktop app | **MODIFIED** (add arena components + multi-stream reducer) |
| `services/gateway` | Multi-tenant HTTP+SSE for single-agent chat. Unchanged. | Web/desktop chat clients | **REUSED** (no changes) |
| `apps/desktop` | Tauri 2 shell. **Extended** with Arena UI surface (new page/route), arena client config, arena event stream hook. | Gateway (existing chat), Arena Service (arena workflow) | **MODIFIED** (add arena UI + config) |
| `packages/platform-runtime` | Protocols (BackendAdapter, RunRuntime), output boundary. **Extended** with arena workflow Protocol. | `arena-engine`, `arena-service` | **MODIFIED** (add ArenaWorkflow Protocol) |

## Data Flow (for each of 4 workflow modes)

### Mode 1: Standard (N agents parallel, no iteration, no cross-review)

```
User creates workflow → selects N agents → submits task prompt
         │
         ▼
Arena Service receives POST /v1/arena/workflows
         │
         ▼
Arena Engine creates N agent slots (slot-0..slot-N-1)
         │
         ├──► acp-client.spawn(agent-A) → initialize → session/new → session/prompt
         ├──► acp-client.spawn(agent-B) → initialize → session/new → session/prompt
         └──► acp-client.spawn(agent-C) → initialize → session/new → session/prompt
                    │
                    │  Each agent streams session/update → map_acp_update_to_run_event
                    │  Events tagged with metadata.agent_slot = "slot-0"|"slot-1"|...
                    │
                    ▼
Arena Service multiplexes N event streams → single SSE to desktop
         │
         ▼
Desktop Arena UI shows N parallel stream panels (demultiplexed by agent_slot)
         │
         ▼
All N agents reach message.completed → Arena Engine emits workflow.completed
         │
         ▼
User selects preferred result (or views all N)
```

**Events on the wire:** Standard 13-category events (`message.delta`,
`message.completed`, `thought.delta`, `tool_call.started`, etc.) with
`metadata.agent_slot` added. The event vocabulary is unchanged — the slot
ID is carried in the existing `metadata` JsonObject field. A new
`arena.workflow_started` and `arena.workflow_completed` event (using the
`_meta`/`_` prefix convention for arena-specific extensions) brackets the
workflow.

### Mode 2: Self-Score Iteration (each agent self-scores + self-optimizes)

```
User creates workflow → selects N agents → submits task prompt
         │
         ▼
Arena Engine: Phase 1 — Parallel initial generation (same as Mode 1)
         │
         ▼
All N agents reach message.completed → Arena Engine collects final content
         │
         ▼
Arena Engine: Phase 2 — Self-score iteration loop (per agent, parallel)
         │
         ├──► For each agent slot:
         │      │
         │      ▼
         │    Dispatch score prompt to SAME agent session:
         │    "Rate your own answer on a 10-point framework. Output JSON: {score, reasoning}"
         │      │
         │      ▼
         │    Agent produces score → Arena Engine parses score
         │      │
         │      ▼
         │    If score < agent's self-declared threshold OR user hasn't stopped:
         │      Dispatch optimize prompt: "Improve your answer based on your self-critique"
         │      Agent streams improved answer → re-score → repeat
         │      │
         │      ▼
         │    User manually stops iteration (or max iterations reached)
         │
         ▼
Arena Engine emits arena.iteration_completed per slot
         │
         ▼
User views all N final self-optimized results + score history
```

**Events on the wire:** Standard events during generation + a new
`arena.score_recorded` event (carrying `agent_slot`, `score`, `iteration`,
`reasoning_ref`). The score prompt and optimize prompt are dispatched as
regular `session/prompt` calls — the agent treats them as normal turns.
Guardrails (citation audit, de-AI polish) run on every iteration's final
output.

### Mode 3: Competitive Review (self-score iteration + cross-review + final synthesis)

```
Phase 1: Parallel initial generation (same as Mode 1)
         │
Phase 2: Self-score iteration (same as Mode 2)
         │
         ▼
Phase 3: Cross-review (N agents review each other's best results)
         │
         ├──► Agent A reviews Agent B's result + Agent C's result
         ├──► Agent B reviews Agent A's result + Agent C's result
         └──► Agent C reviews Agent A's result + Agent B's result
              │
              │  Review prompt: "Review this legal analysis. Score 1-10.
              │  Identify strengths, weaknesses, missing citations, legal errors."
              │  Each review is a new session/prompt on the reviewing agent
              │
              ▼
         Arena Engine collects all cross-review scores + comments
         │
         ▼
Phase 4: Final synthesis (independent agent session)
         │
         ▼
         Arena Engine selects highest-scored result across all reviews
         │
         ▼
         Dispatch to independent synthesis session (could be any of the N agents
         or a separate agent):
         "Here is the highest-scored legal analysis [content] and all cross-review
         comments [reviews]. Produce the final version incorporating all feedback."
         │
         ▼
         Synthesis agent streams final answer → guardrails run → workflow completed
         │
         ▼
         User views: all N original results + cross-review scores + final synthesized version
```

**Events on the wire:** Standard events during all phases + `arena.score_recorded`
+ `arena.review_completed` (carrying `reviewer_slot`, `reviewed_slot`, `score`,
`comment_ref`) + `arena.synthesis_started` / `arena.synthesis_completed`. The
synthesis phase is a single-agent stream (no multiplexing needed — it's one
session producing the final answer).

### Mode 4: Adversarial (competitive review + adversarial challenge + multi-round synthesis + early stop)

```
Phase 1: Parallel initial generation (same as Mode 1)
Phase 2: Self-score iteration (same as Mode 2)
Phase 3: Cross-review (same as Mode 3)
         │
         ▼
Phase 4: Adversarial challenge
         │
         ├──► For each agent's result, assign an adversary agent:
         │      "Find the weakest point in this legal analysis. Challenge
         │       every citation, every legal conclusion, every assumption."
         │      Adversary streams critique → Arena Engine collects
         │
         ▼
Phase 5: Multi-round synthesis with early stop
         │
         ▼
         Round 1: Synthesis agent produces final version incorporating
                  all reviews + adversarial critiques
         │
         ▼
         Round 2: Adversary challenges the synthesis → synthesis agent revises
         │
         ▼
         Early stop evaluation: Arena Engine checks if synthesis score
         (from remaining reviewers) converges (delta < threshold) OR
         max rounds reached OR user stops
         │
         ▼
         Final synthesis emitted → guardrails run → workflow completed
         │
         ▼
         User views: all N originals + cross-reviews + adversarial critiques
                     + synthesis round history + final version
```

**Events on the wire:** All Mode 3 events + `arena.adversarial_challenge_completed`
+ `arena.synthesis_round_completed` (carrying `round`, `score`, `delta`) +
`arena.early_stop_triggered` (carrying `reason`: `converged` | `max_rounds` |
`user_stopped`).

## Integration with Existing v3.0 Packages

### platform-contract (MODIFIED — additive only)

The 13-category event vocabulary is **reused as-is**. Arena-specific metadata
travels in the existing `metadata` JsonObject field on `RunEvent` — no new
event types are needed for the core streaming events. However, arena workflow
lifecycle events (workflow started/completed, score recorded, review completed,
synthesis phases) are **new event types** added to the vocabulary:

- `arena.workflow_started` — carries `mode` (1-4), `agent_slots` list, `task_prompt_ref`
- `arena.workflow_completed` — carries `mode`, `final_result_ref`, `duration_ms`
- `arena.score_recorded` — carries `agent_slot`, `score`, `iteration`, `reasoning_ref`
- `arena.review_completed` — carries `reviewer_slot`, `reviewed_slot`, `score`, `comment_ref`
- `arena.synthesis_started` / `arena.synthesis_completed` — carries `synthesizer_slot`, `round`
- `arena.adversarial_challenge_completed` — carries `challenger_slot`, `target_slot`, `critique_ref`
- `arena.early_stop_triggered` — carries `reason`, `round`

These follow the existing `_meta` / `_` prefix convention for arena-specific
extensions (per V3-SELECTION §2.4: "`_meta` + `_` prefix custom methods for
legal-specific extensions"). JSON Schemas, Python dataclasses, and TypeScript
interfaces are added in parallel (isomorphic pattern preserved).

**No existing event types are modified.** This is purely additive.

### acp-client (MODIFIED — fs/* handler + client capability advertisement)

Two changes:

1. **`clientCapabilities` advertisement in `initialize`**: The current
   `ACPClient.initialize()` sends `protocolVersion: 1` and `clientInfo` but
   does **not** send `clientCapabilities`. Per ACP v1 spec, the client SHOULD
   advertise `clientCapabilities.fs.readTextFile: true` when it supports
   `fs/read_text_file`. The arena-service needs this capability so agents can
   read reference files from user-selected directories.

   The `ACPClient` is extended to accept an optional `client_capabilities`
   parameter and include it in the `initialize` request. The existing Gateway
   path (which does not need fs) passes no capabilities — backward compatible.

2. **Inbound request handling in `StdioACPTransport`**: The current transport
   only handles responses (messages with `id`, no `method`) and notifications
   (messages with `method`, no `id`). ACP `fs/read_text_file` is a **request
   from the agent to the client** — it has both `id` and `method`. The
   transport's `receive()` method currently skips notifications and buffers
   them; it must be extended to also detect inbound requests (has both `id`
   and `method`) and route them to a registered request handler.

   The `ACPClient` is extended with a `register_request_handler(method, handler)`
   API. When the transport encounters an inbound request, it calls the handler,
   sends the response back on stdin, and continues reading. The arena-service
   registers an `fs/read_text_file` handler that reads from user-selected
   directories.

   **`fs/write_text_file` is NOT advertised** — agents in the arena are
   read-only consumers of reference files. This follows the safety principle:
   agents should not write to the user's filesystem during a review workflow.

### acp-event-bridge (REUSED — no changes)

The `EventBridge` (forward + reverse mapping) and `output_filter` are reused
as-is. The arena-service uses the same ACP output filter as the Gateway path:
agent meta/gateway/system/update/command noise is blocked before reaching the
SSE stream. The output boundary is enforced at the arena-service (first point)
and can be enforced again in the SSE encoder (second point, same pattern as
Gateway's `GatewaySseStream.encode_event`).

### agent-core (REUSED — guardrail enforcement hooks)

The 4 legal guardrails (`research-gate`, `ask-user-enforcement`, `citation audit`,
`de-AI polish`) are **non-bypassable in all 4 arena modes**. The enforcement
mechanism:

- **When the agent is `inkstatute-agent acp`**: Guardrails are enforced inside
  the agent's own turn loop (`guardrails.py`). The arena-engine does not need
  to intervene — the guardrails are code-level enforced in the agent itself.

- **When the agent is a third-party ACP agent (hermes, codex, etc.)**: The
  arena-engine wraps the dispatched prompt with guardrail-enforcing prompt
  enrichment (using `prompt_assembler.build_system_prompt` to prepend the
  research-gate and ask-user mandate sections). For citation audit and de-AI
  polish, the arena-engine runs `guardrails.enforce_citation_audit()` and
  `guardrails.de_ai_polish()` on the agent's final output before accepting it
  as a completed result.

  This is a **post-hoc enforcement** pattern: the arena-engine cannot force a
  third-party agent to follow guardrails during generation, but it can (a)
  enrich the prompt with guardrail instructions and (b) audit the output
  afterward. If the citation audit finds unverified citations, the result is
  flagged with `[待律师复核]` labels (same as the existing agent-core behavior).

- **`skill_candidate.requires_human_review` invariant**: Preserved — the
  arena-engine uses `guardrails.create_skill_candidate()` (the only constructor)
  if it ever records skill candidates, ensuring `requires_human_review=True`.

### skill-index (REUSED — no changes)

The arena-engine can query `skill_index` to enrich prompts with relevant legal
skill context. This is the same mechanism the existing agent-core uses — no
changes to the skill-index package.

### platform-runtime (MODIFIED — add ArenaWorkflow Protocol)

A new `ArenaWorkflow` Protocol is added to `platform-runtime/protocols.py`,
defining the interface that `arena-engine` implements:

```python
class ArenaWorkflow(Protocol):
    async def create_workflow(self, config: ArenaWorkflowConfig) -> ArenaWorkflowHandle: ...
    async def stream_events(self, workflow_id: str) -> AsyncIterator[RunEvent]: ...
    async def cancel_workflow(self, workflow_id: str) -> ArenaWorkflowStatus: ...
    async def submit_user_action(self, workflow_id: str, action: ArenaUserAction) -> ArenaWorkflowStatus: ...
    async def get_workflow_status(self, workflow_id: str) -> ArenaWorkflowStatus: ...
```

This mirrors the existing `RunRuntime` Protocol pattern (create/stream/cancel/
approve/poll). The arena-service delegates to this Protocol.

### platform-sdk-ts (MODIFIED — add arena client methods)

New methods added to `PlatformApiClient` (or a new `ArenaApiClient` class):
- `createArenaWorkflow(body)` → POST `/v1/arena/workflows`
- `streamArenaWorkflow(workflow_id)` → GET `/v1/arena/workflows/{id}/stream` (SSE)
- `cancelArenaWorkflow(workflow_id)` → DELETE `/v1/arena/workflows/{id}`
- `submitArenaAction(workflow_id, body)` → POST `/v1/arena/workflows/{id}/actions`
- `getArenaWorkflowStatus(workflow_id)` → GET `/v1/arena/workflows/{id}`

New TypeScript interfaces for arena event payloads (mirroring the Python
dataclasses added to `platform-contract`).

### ui-core (MODIFIED — add arena components + multi-stream reducer)

New components:
- `ArenaWorkflowCreator` — mode selection (1-4), agent selection, task input
- `ParallelStreamPanel` — shows N agent streams side by side, demultiplexed by `agent_slot`
- `ScoreCard` — displays self-score / cross-review score with reasoning
- `ReviewSummary` — shows cross-review comments per agent
- `SynthesisViewer` — shows final synthesized result + synthesis round history
- `ArenaEventReducer` — extends `event-reducer.ts` to handle arena-specific events
  and demultiplex parallel streams into per-slot `RenderState` objects

The existing `event-reducer.ts` and `EventStreamStore` are **not modified** —
the arena reducer is a new module that composes with the existing one (each
agent slot's events are reduced by the existing `reduce()` function, and the
arena reducer manages the slot-level multiplexing).

### services/gateway (REUSED — no changes)

The Gateway continues to serve the existing single-agent chat workflow. The
arena is a separate service. This avoids coupling the arena's multi-agent
lifecycle to the Gateway's single-run model and avoids any risk to the
existing 34 green gates.

### apps/desktop (MODIFIED — add arena UI surface)

New files:
- `apps/desktop/src/config/arena.ts` — `ArenaApiClient` instance pointed at `localhost:8001`
- `apps/desktop/src/pages/ArenaPage.tsx` — arena workflow creation + live view
- `apps/desktop/src/hooks/useArenaEventStream.ts` — multi-stream SSE hook
- `apps/desktop/src/contexts/ArenaContext.tsx` — arena workflow state management

The existing `WorkspacePage`, `SessionContext`, and `useEventStream` are
unchanged — the arena is a separate page/route in the Tauri shell.

## ACP fs/* Handling

### The ACP fs/* mechanism

In ACP v1, `fs/read_text_file` is a **client-side capability**. The flow is:

1. **Client advertises capability at `initialize`**: The ACP client (the
   process that spawned the agent) sends `clientCapabilities.fs.readTextFile: true`
   in the `initialize` request. This tells the agent that the client can
   handle `fs/read_text_file` requests.

2. **Agent sends `fs/read_text_file` request**: During a session, the agent
   may send a JSON-RPC request with both `id` and `method: "fs/read_text_file"`:
   ```json
   {
     "jsonrpc": "2.0",
     "id": 3,
     "method": "fs/read_text_file",
     "params": {
       "sessionId": "sess_abc123",
       "path": "/home/user/docs/contract.pdf",
       "line": 1,
       "limit": 100
     }
   }
   ```

3. **Client responds**: The client reads the file from its filesystem and
   responds:
   ```json
   {
     "jsonrpc": "2.0",
     "id": 3,
     "result": { "content": "file contents here..." }
   }
   ```

### Arena-service as ACP fs/* handler

In the arena architecture, the **arena-service is the ACP client**. It spawns
agent subprocesses, so it is responsible for handling `fs/read_text_file`
requests from agents. The flow:

```
User selects reference directories in Arena UI
         │
         ▼
Desktop app passes directory paths to arena-service
(via POST /v1/arena/workflows params: reference_dirs: ["/path/1", "/path/2"])
         │
         ▼
Arena Service creates FsAccessPolicy:
  allowed_roots: ["/path/1", "/path/2"]
  denied_patterns: ["**/.git/**", "**/node_modules/**", "**/.env*"]
  max_file_size: 10_000_000  # 10 MB
  encoding: "utf-8"  # text files only
         │
         ▼
Arena Service registers fs/read_text_file handler on each ACPClient:
  acp_client.register_request_handler("fs/read_text_file", fs_handler)
         │
         ▼
Agent sends fs/read_text_file request during session/prompt
         │
         ▼
ACPClient.transport detects inbound request (has id + method)
         │
         ▼
ACPClient routes to registered fs_handler
         │
         ▼
fs_handler:
  1. Resolve path against allowed_roots (path traversal check)
  2. Deny if path outside allowed_roots → error response
  3. Deny if path matches denied_patterns → error response
  4. Check file size ≤ max_file_size
  5. Read file as UTF-8 text (line/limit support)
  6. Return { "content": file_contents }
         │
         ▼
ACPClient sends response back to agent on stdin
         │
         ▼
Agent continues with file contents in context
```

### Safety constraints

- **`fs/write_text_file` is NOT advertised.** Agents in the arena are
  read-only consumers. The arena-service does not register a write handler.
- **Path sandboxing**: All `fs/read_text_file` requests are validated against
  `allowed_roots` using `pathlib.Path.resolve()` + prefix check. Symlinks that
  escape the allowed roots are denied.
- **No binary files**: The handler reads as UTF-8 text; binary files return
  an error response (agents should use tools for binary content).
- **Size limit**: Files exceeding `max_file_size` return an error (prevents
  context budget exhaustion).
- **`terminal/*` not advertised**: The arena-service does NOT advertise
  `terminal` capability. Agents cannot execute shell commands.
- **`session/request_permission` for dangerous kinds**: If an agent sends a
  `session/request_permission` request with `kind: "terminal"` or
  `kind: "execute_code"`, the arena-service **denies it immediately** (same
  behavior as the existing `ACPBackendAdapter.submit_approval` which rejects
  dangerous permissions). The denial is logged but never auto-approved.

### Implementation in acp-client

The `StdioACPTransport.receive()` method currently classifies messages as:
- Has `id`, no `method` → response (return to caller)
- Has `method`, no `id` → notification (buffer for `receive_notification()`)

A third category is added:
- Has `id` AND `method` → inbound request from agent → route to registered handler

The `ACPClient` gains:
```python
class ACPClient:
    def register_request_handler(
        self, method: str, handler: Callable[[dict], Awaitable[dict]]
    ) -> None: ...

    async def _handle_inbound_request(self, request: dict) -> None:
        """Route an inbound agent request to the registered handler and send the response."""
        method = request.get("method", "")
        handler = self._request_handlers.get(method)
        if handler is None:
            # No handler — respond with method-not-found error
            response = {"jsonrpc": "2.0", "id": request["id"],
                        "error": {"code": -32601, "message": f"Method not found: {method}"}}
            await self._transport.send(response)
            return
        result = await handler(request.get("params", {}))
        response = {"jsonrpc": "2.0", "id": request["id"], "result": result}
        await self._transport.send(response)
```

The `initialize()` method is extended:
```python
async def initialize(self, client_capabilities: dict | None = None) -> CapabilityNegotiationResult:
    params = {
        "protocolVersion": 1,
        "clientInfo": {"name": "inkstatute-acp-client", "version": "0.1.0"},
    }
    if client_capabilities:
        params["clientCapabilities"] = client_capabilities
    # ... rest unchanged
```

The arena-service calls:
```python
await client.initialize(client_capabilities={
    "fs": {"readTextFile": True},  # NOT writeTextFile
})
client.register_request_handler("fs/read_text_file", fs_handler)
```

The existing Gateway path calls `await client.initialize()` with no
`client_capabilities` — backward compatible.

## Event Flow and Multiplexing

### The multiplexing problem

In Modes 1-4, N agents run in parallel, each producing a stream of `RunEvent`
objects. The desktop app needs to see all N streams simultaneously. The
arena-service must multiplex these onto a single SSE connection.

### Multiplexing strategy

Each `RunEvent` already has a `metadata` JsonObject field. The arena-service
tags every event from agent slot `i` with:

```json
{
  "metadata": {
    "arena_workflow_id": "wf-001",
    "agent_slot": "slot-0",
    "agent_backend_id": "hermes",
    "arena_phase": "initial_generation"
  }
}
```

The SSE stream from `GET /v1/arena/workflows/{id}/stream` carries these
events in arrival order (interleaved across slots). The desktop app's
`ArenaEventReducer` demultiplexes by `metadata.agent_slot`:

```
SSE stream (interleaved):
  event: message.delta    data: {..., metadata: {agent_slot: "slot-0", ...}}
  event: message.delta    data: {..., metadata: {agent_slot: "slot-1", ...}}
  event: thought.delta    data: {..., metadata: {agent_slot: "slot-0", ...}}
  event: message.delta    data: {..., metadata: {agent_slot: "slot-2", ...}}
  event: arena.score_recorded  data: {agent_slot: "slot-0", score: 7, ...}
  event: message.completed data: {..., metadata: {agent_slot: "slot-1", ...}}
  ...

Desktop ArenaEventReducer:
  slot-0 RenderState: {messages: [...], streaming: true, ...}
  slot-1 RenderState: {messages: [...], streaming: false, ...}
  slot-2 RenderState: {messages: [...], streaming: true, ...}
  workflowState: {phase: "self_score_iteration", scores: {slot-0: 7}}
```

### Arena lifecycle events

Arena-specific events (`arena.workflow_started`, `arena.score_recorded`,
`arena.review_completed`, etc.) are **not slot-specific** — they describe
workflow-level state transitions. They carry `agent_slot` when relevant but
are consumed by the workflow-level reducer, not the per-slot reducers.

### SSE encoding

The arena-service reuses the same SSE encoding pattern as the Gateway
(`encode_sse_event` from `services/gateway/sse.py`), including the output
boundary enforcement. The arena-service has its own SSE encoder that:

1. Calls the ACP output filter (`acp-event-bridge.output_filter`) on each
   event — blocks agent meta/gateway/system/update/command noise.
2. Calls `DefaultAssistantOutputBoundary.apply()` — blocks secrets, internal
   paths, provider leaks.
3. Encodes as SSE frame: `id: {event_id}\nevent: {event_type}\ndata: {json}\n\n`.

This is the same "output boundary enforced twice" pattern as the Gateway
(first at ACP event bridge, second at SSE encoder).

### Reconnection support

The arena-service maintains an event buffer (same pattern as Gateway's
`RunEventBuffer`) keyed by `workflow_id`. On SSE reconnection with
`Last-Event-ID`, buffered events with `seq > last_event_id` are replayed
first, then live streaming continues. The per-slot reducers are idempotent
(replayed events produce the same state).

### Permission and elicitation flow

When an agent sends `session/request_permission` or `elicitation/create`:

1. The arena-service maps it to `permission.requested` / `elicitation.requested`
   events (same as existing `event_mapping.py`).
2. These events are sent on the SSE stream with `metadata.agent_slot`.
3. The desktop app shows a permission/elicitation card **per agent slot**.
4. The user's response is sent back via `POST /v1/arena/workflows/{id}/actions`
   with `agent_slot` and `action_type: "approval" | "elicitation"`.
5. The arena-service routes the response to the correct `ACPClient` session
   via the `EventBridge` (same correlation mechanism as Gateway).

**Dangerous permissions** (`terminal`, `execute_code`) are denied immediately
by the arena-service — they never reach the desktop app as an approval card.
This matches the existing `ACPBackendAdapter` behavior.

## Suggested Build Order

The build order respects dependencies: contract first, then engine, then
service, then UI. Each phase produces a testable, gate-covered unit.

### Phase 1: Arena Contract Extension (platform-contract + platform-sdk-ts)

**Dependencies:** None (platform-contract is the foundation).

**Deliverables:**
- Add arena event types to `platform-contract`: `arena.workflow_started`,
  `arena.workflow_completed`, `arena.score_recorded`, `arena.review_completed`,
  `arena.synthesis_started/completed`, `arena.adversarial_challenge_completed`,
  `arena.early_stop_triggered`.
- Add JSON Schemas, Python dataclasses, TypeScript interfaces (isomorphic).
- Add `ArenaWorkflowConfig`, `ArenaWorkflowHandle`, `ArenaWorkflowStatus`,
  `ArenaUserAction` dataclasses.
- Add `ArenaWorkflow` Protocol to `platform-runtime/protocols.py`.
- Add arena client methods + event types to `platform-sdk-ts`.
- Add gate coverage for new schemas/dataclasses.

**Why first:** Everything else depends on the event vocabulary. The isomorphic
pattern (JSON Schema → Python dataclass → TypeScript interface) must be
established before any component can emit or consume arena events.

### Phase 2: ACP fs/* Handler (acp-client extension)

**Dependencies:** Phase 1 (for any new error types if needed).

**Deliverables:**
- Extend `StdioACPTransport` to detect inbound requests (has `id` + `method`).
- Add `ACPClient.register_request_handler(method, handler)` API.
- Extend `ACPClient.initialize()` to accept `client_capabilities` parameter.
- Implement `FsAccessPolicy` + `fs_read_text_file_handler` in a new
  `acp-client` submodule (or a new `packages/acp-fs-handler` package).
- Path sandboxing, size limits, denied patterns, UTF-8 text-only.
- Tests: path traversal denial, symlink escape denial, size limit, allowed
  read success, binary file rejection, no-handler-registered error response.
- Backward compatibility: existing Gateway path calls `initialize()` with no
  `client_capabilities` — all existing tests stay green.

**Why second:** The arena-service needs fs/* handling to spawn agents that
can read reference files. This is a prerequisite for the service. It extends
the existing acp-client without breaking the Gateway path.

### Phase 3: Arena Engine (packages/arena-engine)

**Dependencies:** Phase 1 (event types), Phase 2 (acp-client with fs/*).

**Deliverables:**
- `ArenaEngine` class implementing the `ArenaWorkflow` Protocol.
- Mode 1 (standard parallel): dispatch N agents, collect events, emit
  workflow_completed.
- Mode 2 (self-score iteration): per-agent score prompt dispatch, score
  parsing, optimize prompt dispatch, iteration loop with user-stop.
- Mode 3 (competitive review): cross-review pairing matrix, review prompt
  dispatch, score aggregation, highest-scored selection, final synthesis
  dispatch.
- Mode 4 (adversarial): adversarial challenge dispatch, multi-round synthesis
  with early-stop evaluation (convergence delta, max rounds, user stop).
- Guardrail enforcement: prompt enrichment for third-party agents, post-hoc
  citation audit + de-AI polish on all results.
- Event tagging: all events carry `metadata.agent_slot`, `metadata.arena_phase`.
- Pure library — no HTTP, no SSE, no subprocess management (delegates to
  `acp-client`). Testable with mock ACP clients.
- Gate coverage: new gate for `arena-engine`.

**Why third:** The engine is pure orchestration logic that depends on the
contract (Phase 1) and the extended acp-client (Phase 2). It can be fully
tested with mock agents before the service exists.

### Phase 4: Arena Service (services/arena-service)

**Dependencies:** Phase 1 (contract), Phase 2 (fs/* handler), Phase 3 (engine).

**Deliverables:**
- HTTP+SSE service (framework-free, stdlib pattern — same as Gateway).
- Endpoints: `POST /v1/arena/workflows`, `GET /v1/arena/workflows/{id}/stream`
  (SSE), `DELETE /v1/arena/workflows/{id}`,
  `POST /v1/arena/workflows/{id}/actions`, `GET /v1/arena/workflows/{id}`.
- Delegates to `ArenaEngine` for workflow orchestration.
- Registers `fs/read_text_file` handler on each `ACPClient` with the
  user-provided `reference_dirs` as allowed roots.
- SSE encoder with output boundary enforcement (ACP output filter + default
  boundary).
- Event buffer for SSE reconnection (same pattern as Gateway).
- Permission safety: dangerous permissions denied immediately.
- Multiplexing: tags events with `metadata.agent_slot`, interleaves onto
  single SSE stream.
- Local-only: binds to `127.0.0.1:8001`, no auth (local desktop app only).
- Gate coverage: new gate for `arena-service`.

**Why fourth:** The service wires together the engine, acp-client, and
contract into an HTTP-exposed unit. It depends on all three prior phases.

### Phase 5: Arena UI (ui-core + apps/desktop)

**Dependencies:** Phase 1 (TypeScript event types), Phase 4 (service to connect to).

**Deliverables:**
- `ArenaEventReducer` in `ui-core` — demultiplexes by `agent_slot`, manages
  per-slot `RenderState` + workflow-level state.
- New `ui-core` components: `ArenaWorkflowCreator`, `ParallelStreamPanel`,
  `ScoreCard`, `ReviewSummary`, `SynthesisViewer`.
- `ArenaApiClient` in `platform-sdk-ts` (or methods on `PlatformApiClient`).
- `apps/desktop` additions: `ArenaPage.tsx`, `useArenaEventStream.ts`,
  `ArenaContext.tsx`, `config/arena.ts`.
- Tauri shell integration: new route/menu item for Arena.
- Reuses existing `ui-core` components (ChatPanel, ClarificationCard,
  CitationPanel, DocPreview) within each agent slot panel.

**Why last:** The UI depends on everything below it. Building it last means
it can be developed against a running arena-service with real agents.

### Phase 6: Integration Testing + Gate Updates

**Dependencies:** All prior phases.

**Deliverables:**
- End-to-end test: create workflow (Mode 1) → 2 mock agents → verify SSE
  multiplexing → verify workflow_completed.
- End-to-end test: Mode 3 with mock agents → verify cross-review pairing →
  verify synthesis dispatch → verify final result.
- fs/* integration test: agent requests file read → verify sandboxed access.
- Permission safety test: agent requests terminal → verify immediate denial.
- Output boundary test: agent emits meta noise → verify blocked from SSE.
- Gate coverage meta-test update: new `packages/arena-engine/src` and
  `services/arena-service/src` directories covered by gates.
- Composability test: `solutions/demo_non_legal` arena variant (verify
  arena schema is industry-neutral, legal-specific fields in
  `industry_context`).

## Sources

- `/home/sorawatcher/workspace/inkstatute-suite/.planning/PROJECT.md` — v3.1 milestone context, 4 workflow modes, architecture diagram, key design decisions
- `/home/sorawatcher/workspace/inkstatute-suite/.planning/research/V3-SELECTION.md` — ACP v1 capability analysis, fs/* as client-side optional capability
- `packages/platform-contract/src/platform_contract/unified_events.py` — 13-category event vocabulary dataclasses
- `packages/platform-contract/src/platform_contract/enums.py` — `RunEventType` enum (V3 unified types)
- `packages/acp-client/src/inkstatute_acp_client/client.py` — `ACPClient` class, `initialize()`, `new_session()`, `prompt()`, `stream_updates()`
- `packages/acp-client/src/inkstatute_acp_client/adapter.py` — `ACPBackendAdapter` (9-method Protocol), `_DANGEROUS_PERMISSION_KINDS`, per-session subprocess spawning
- `packages/acp-client/src/inkstatute_acp_client/event_mapping.py` — ACP `session/update` → unified `RunEvent` mapping, `session/request_permission` handling
- `packages/acp-client/src/inkstatute_acp_client/capability_negotiation.py` — `RequiredCapabilities`, `CapabilityNegotiationResult`, `negotiate()`
- `packages/acp-event-bridge/src/inkstatute_acp_event_bridge/bridge.py` — bidirectional ACP↔unified mapping, request ID correlation
- `packages/acp-event-bridge/src/inkstatute_acp_event_bridge/output_filter.py` — ACP output boundary pre-filter (blocked categories, default-deny)
- `packages/agent-core/src/inkstatute_agent_core/guardrails.py` — 4 legal guardrails (research-gate, ask-user, citation audit, de-AI polish), `skill_candidate` invariant
- `packages/agent-core/src/inkstatute_agent_core/turn_loop.py` — async streaming turn loop, tool call events, heartbeat
- `packages/agent-core/src/inkstatute_agent_core/acp_server.py` — `inkstatute-agent acp` ACP server, reverse event mapping, no fs/*/terminal capabilities declared
- `packages/agent-core/src/inkstatute_agent_core/backend_adapter.py` — `InProcessAgentCoreAdapter` (in-process BackendAdapter)
- `packages/platform-runtime/src/platform_runtime/protocols.py` — `BackendAdapter` (9 methods), `RunRuntime`, `RunEvent`, `Run`, `Approval` dataclasses
- `packages/platform-runtime/src/platform_runtime/output_boundary.py` — `DefaultAssistantOutputBoundary`, `BoundaryAction` (ALLOW/REWRITE/BLOCK)
- `services/gateway/src/gateway/app.py` — `GatewayApp` dispatch, auth-before-routing, SSE stream with event buffer replay
- `services/gateway/src/gateway/sse.py` — `encode_sse_event`, forbidden payload key assertion, output boundary at SSE layer
- `services/gateway/src/gateway/runs.py` — run management handlers, tenant isolation
- `packages/ui-core/src/event-reducer.ts` — pure rendering state machine, 13 event types → `RenderState`
- `packages/ui-core/src/stores/eventStream.ts` — `EventStreamStore` with Last-Event-ID reconnection
- `packages/ui-core/src/index.ts` — ui-core public API (components, reducer, store, adapters)
- `packages/platform-sdk-ts/src/index.ts` — `PlatformApiClient` HTTP client, SSE frame parsing
- `packages/platform-sdk-ts/src/events.ts` — TypeScript event payload interfaces (isomorphic to Python dataclasses)
- `apps/desktop/src/config/gateway.ts` — desktop Gateway client config (`PlatformApiClient` at `localhost:8000`)
- `apps/desktop/src/hooks/useEventStream.ts` — SolidJS hook wrapping `EventStreamStore`
- `apps/desktop/src/contexts/SessionContext.tsx` — per-workspace run lifecycle management
- `packages/multi-agent-adapter/FROZEN.md` — experimental multi-agent adapter frozen (Phase 104), not a production consumer
- ACP v1 File System spec: `https://agentclientprotocol.com/protocol/v1/file-system` — `fs/read_text_file` client-side capability, `clientCapabilities.fs.readTextFile` advertisement
- ACP v1 Initialization spec: `https://agentclientprotocol.com/protocol/v1/initialization` — `clientCapabilities` structure
