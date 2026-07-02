# Phase 15: Session Resolver and Interrupt Runtime - Research

**Researched:** 2026-07-01  
**Domain:** Backend-neutral Python runtime session resolution, active-task routing, and run interrupt/resume  
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
All implementation choices are at the agent's discretion - discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, Phase 14 context/memory contracts, `.planning/REQUIREMENTS.md`, and existing codebase conventions to guide decisions.

Session decisions and interrupt records must be privacy-safe, reference-first, and backend-neutral. Do not store raw legal/customer text, callback bodies, runtime logs, media, secrets, or full legal payloads in contract logs or memory records.

Hermes remains an agent backend in Hermes mode, not the channel boundary. Ordinary WeCom users must see InkStatute-owned service wording, and Hermes gateway/meta/system/update/command/help/debug notices must not leak.

### the agent's Discretion
All implementation choices are at the agent's discretion - discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, Phase 14 context/memory contracts, `.planning/REQUIREMENTS.md`, and existing codebase conventions to guide decisions.

Session decisions and interrupt records must be privacy-safe, reference-first, and backend-neutral. Do not store raw legal/customer text, callback bodies, runtime logs, media, secrets, or full legal payloads in contract logs or memory records.

Hermes remains an agent backend in Hermes mode, not the channel boundary. Ordinary WeCom users must see InkStatute-owned service wording, and Hermes gateway/meta/system/update/command/help/debug notices must not leak.

### Deferred Ideas (OUT OF SCOPE)
Short-term context assembly belongs to Phase 16. Long-term memory and feedback learning belongs to Phase 17. External memory adapter evaluation belongs to Phase 18. Do not introduce a new service, database, queue, router, skill registry, MCP registry, or model gateway unless the active plan explicitly justifies it inside the V2 scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CTX-01 | Ordinary users can continue a conversation without typing `/new`, `/resume`, or any agent/session command. | Implement resolver policy inside `packages/platform-runtime`, then call it from WeCom/platform ingress before run creation. [VERIFIED: .planning/REQUIREMENTS.md; packages/platform-runtime/src/platform_runtime/protocols.py; packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py] |
| CTX-02 | The platform can resolve a stable `conversation_id` and active `session_id/thread_id` from channel, user, bot, active task, pending interrupt, and idle-window signals. | Existing inbound adapters expose channel conversation/user fields; Phase 14 added `Session`, `BotInstance.default_session_policy`, `Run`, `ContextBundle`, and `RunInterrupt` contract shapes. [VERIFIED: services/wecom-service/src/wecom_service/normalization.py; packages/platform-contract/src/platform_contract/schemas/session.schema.json; packages/platform-contract/src/platform_contract/schemas/bot_instance.schema.json; packages/platform-contract/src/platform_contract/schemas/run_interrupt.schema.json] |
| CTX-03 | The platform can automatically start a new session when the message is clearly a new task, the prior session is stale, or the active session has terminated. | Existing WeCom active-task router already classifies new parallel task intent during running tasks; Phase 15 should generalize session-level policy without storing raw text. [VERIFIED: services/wecom-service/src/wecom_service/active_task_router.py; services/wecom-service/tests/test_active_task_router.py] |
| CTX-04 | Session decisions are recorded as minimized metadata with raw payload references, not raw legal text. | `InMemoryContractLogStore` rejects `raw_payload` and full-text-like keys recursively; task-flow and active-task records already store hashes, lengths, refs, IDs, and privacy markers. [VERIFIED: packages/platform-runtime/src/platform_runtime/store.py; services/wecom-service/src/wecom_service/task_flow.py; services/wecom-service/src/wecom_service/active_task_router.py] |
| INT-01 | A backend/skill can return a platform interrupt that maps to `waiting_for_user` / `needs_clarification` and persists the required resume state. | `RunInterrupt` schema requires `interrupt_id`, `run_id`, `session_id`, `status`, `reason`, `prompt_ref`, and `resume_state_ref`; `Run.status` includes `waiting_for_user`; `AgentResult.status` includes `needs_clarification`. [VERIFIED: packages/platform-contract/src/platform_contract/schemas/run_interrupt.schema.json; packages/platform-contract/src/platform_contract/schemas/run.schema.json; packages/platform-contract/src/platform_contract/schemas/agent_result.schema.json] |
| INT-02 | WeCom delivery sends the clarification question as ordinary lawyer-assistant output, and the user's next answer resumes the paused run instead of starting an unrelated task. | `WeComChannelAdapter.deliver` owns text/card/file egress and uses WeCom service send envelopes; output boundary already filters backend-originated meta notices in runtime streams. [VERIFIED: packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py; packages/platform-runtime/src/platform_runtime/runtime.py; packages/platform-runtime/tests/test_output_boundary.py] |
| INT-03 | Interrupts preserve multiple-choice or freeform question metadata when available, but do not require ordinary users to know any agent terminology. | `RunInterrupt.expected_response_schema_ref` can point to response metadata, while user-facing delivery should use ordinary service wording and prompt refs, not backend command terms. [VERIFIED: packages/platform-contract/src/platform_contract/schemas/run_interrupt.schema.json; AGENTS.md] |
| INT-04 | Timeout, cancellation, and duplicate-answer behavior are deterministic and privacy-safe. | Existing task-flow models timeout/cancel states; idempotency exists for WeCom callbacks; contract log privacy enforcement exists for stored decision evidence. [VERIFIED: services/wecom-service/src/wecom_service/task_flow.py; services/wecom-service/src/wecom_service/idempotency.py; packages/platform-runtime/src/platform_runtime/store.py] |
</phase_requirements>

## Project Constraints (from AGENTS.md)

- V2 PRD is the active product source of truth; V1 must not be reintroduced. [VERIFIED: AGENTS.md]
- InkStatute owns WeCom ingress/egress; Hermes is only an agent backend in Hermes mode. [VERIFIED: AGENTS.md]
- Do not rebuild Hermes core, session storage, router, skill registry, MCP registry, or model gateway unless an active GSD phase changes scope. [VERIFIED: AGENTS.md]
- Ordinary WeCom users must not see Hermes gateway/meta/system/update/command/help notices. [VERIFIED: AGENTS.md]
- Never commit secrets, runtime DBs, logs, customer documents, media files, callback tokens, WeCom keys, encoding AES keys, or raw legal payloads. [VERIFIED: AGENTS.md]
- Contract logs prefer references such as `raw_payload_ref` and must not store sensitive full text by default. [VERIFIED: AGENTS.md]
- Legal-specific fields belong in `industry_context`; platform-level schemas remain industry-neutral. [VERIFIED: AGENTS.md]
- Add tests before or with behavior changes, especially for schemas, mappers, event ordering, dedupe, and fixture replay. [VERIFIED: AGENTS.md]
- Prefer structured parsers and schema validators over ad hoc string parsing. [VERIFIED: AGENTS.md]
- Do not introduce a new service, database, queue, or runtime dependency unless the V2 PRD or active GSD plan requires it. [VERIFIED: AGENTS.md]

## Summary

Phase 15 should add a backend-neutral session resolver and interrupt store/resume runtime to `packages/platform-runtime`, then integrate it with WeCom/platform channel ingress as a library call before run creation. [VERIFIED: packages/platform-runtime/src/platform_runtime/protocols.py; packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py; .planning/ROADMAP.md] The codebase already has the contract vocabulary needed for this phase: `Session`, `Run`, `RunInterrupt`, `ContextBundle`, `AsyncTaskState.WAITING_FOR_USER`, and `AgentResultStatus.NEEDS_CLARIFICATION`. [VERIFIED: packages/platform-contract/src/platform_contract/events.py; packages/platform-contract/src/platform_contract/enums.py; packages/platform-contract/src/platform_contract/schemas/*.schema.json]

Use a deterministic precedence order: pending unresolved interrupt first, active running task second, viable recent session third, and new session fallback last. [VERIFIED: .planning/REQUIREMENTS.md; services/wecom-service/src/wecom_service/active_task_router.py; packages/platform-contract/src/platform_contract/schemas/run_interrupt.schema.json] Store decision evidence as IDs, timestamps, reasons, status, raw payload refs, hashes, lengths, and capability metadata only; never persist raw user text, callback bodies, backend notices, or full legal/customer payloads. [VERIFIED: AGENTS.md; packages/platform-runtime/src/platform_runtime/store.py; services/wecom-service/tests/test_active_task_router.py]

**Primary recommendation:** Build three plan slices: resolver contracts and in-memory stores in `platform-runtime`, interrupt/resume support in `DefaultRunRuntime` and fakes, then WeCom integration plus contract-test-suite fixtures proving pending interrupt resume, stale/new session split, active-task precedence, idempotent duplicate answers, timeout/cancel, and privacy gates. [VERIFIED: packages/platform-runtime/tests/test_run_runtime_lifecycle.py; services/wecom-service/tests/test_task_flow.py; packages/contract-test-suite/src/contract_test_suite/schema_validation.py]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Channel/user/bot signal extraction | Channel Adapter / WeCom Service | Platform Runtime | WeCom and Web/SSE adapters already normalize inbound payloads into `AgentTurn`/`FeedbackEvent` with refs and metadata. [VERIFIED: packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py; packages/channels/web_sse/src/inkstatute_channels_web_sse/adapter.py] |
| Session resolution policy | Platform Runtime | Channel Adapter | The policy must be backend-neutral and reusable across WeCom and platform channels, while adapters supply channel-local IDs. [VERIFIED: packages/platform-runtime/src/platform_runtime/protocols.py; .planning/ROADMAP.md] |
| Active-task follow-up classification | WeCom Service today; Platform Runtime resolver consumes snapshot | Backend Adapter capabilities | Existing logic is WeCom-specific and privacy-safe; the resolver should call or mirror its output rather than duplicate raw-text storage. [VERIFIED: services/wecom-service/src/wecom_service/active_task_router.py] |
| Interrupt persistence | Platform Runtime | Contract Log Store | `RunInterrupt` is a platform contract, and runtime store privacy checks already exist. [VERIFIED: packages/platform-contract/src/platform_contract/schemas/run_interrupt.schema.json; packages/platform-runtime/src/platform_runtime/store.py] |
| Resume paused run | Platform Runtime | Backend Adapter | `RunRuntime` owns run lifecycle operations; backend adapters expose submit/get/cancel/approval today but lack a dedicated resume method. [VERIFIED: packages/platform-runtime/src/platform_runtime/protocols.py; packages/backends/hermes/src/inkstatute_backends_hermes/adapter.py] |
| Clarification delivery | Channel Adapter / WeCom Service | Output Boundary | WeCom adapter owns outbound envelopes and runtime stream boundary filters backend/operator notices. [VERIFIED: packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py; packages/platform-runtime/src/platform_runtime/output_boundary.py] |
| Contract/fixture validation | Contract Test Suite | Platform Contract | Fixture validation already accepts optional `run_interrupt` and context/memory keys. [VERIFIED: packages/contract-test-suite/src/contract_test_suite/schema_validation.py; packages/contract-test-suite/fixtures/phase14_context_memory_foundation.json] |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python standard library | Python 3.14.6 available; packages require Python >=3.11 | Dataclasses, protocols, datetime, hashing, regex, JSON, unittest. | Existing packages are dependency-free and use stdlib-only implementations. [VERIFIED: local `python --version`; packages/platform-runtime/pyproject.toml; services/wecom-service/pyproject.toml] |
| `inkstatute-platform-contract` | 0.1.0 | JSON Schema and Python dataclass bindings for `Session`, `Run`, `RunInterrupt`, `AgentResult`, and state enums. | It is the existing pure definition package for platform contracts. [VERIFIED: packages/platform-contract/pyproject.toml; packages/platform-contract/README.md] |
| `inkstatute-platform-runtime` | 0.1.0 | Runtime protocols, `DefaultRunRuntime`, fakes, feature flags, output boundary, and in-memory contract log store. | It already owns backend-neutral run lifecycle surfaces and privacy-checked contract log storage. [VERIFIED: packages/platform-runtime/pyproject.toml; packages/platform-runtime/src/platform_runtime/runtime.py; packages/platform-runtime/src/platform_runtime/store.py] |
| `inkstatute-wecom-service` | 0.1.0 | WeCom callback parsing, normalization, idempotency, task-flow, active-task routing, output policy, and send envelopes. | It is the InkStatute-owned WeCom service primitive package. [VERIFIED: services/wecom-service/pyproject.toml; services/wecom-service/src/wecom_service/*.py] |
| `inkstatute-contract-test-suite` | 0.1.0 | Schema validation, fixture replay, and relationship/privacy checks. | Existing fixtures and tests validate additive platform objects including `run_interrupt`. [VERIFIED: packages/contract-test-suite/pyproject.toml; packages/contract-test-suite/src/contract_test_suite/schema_validation.py] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | 9.1.1 available | Optional local test runner for existing unittest suites. | Use only as a runner convenience; tests are written with stdlib `unittest`. [VERIFIED: local `pytest --version`; packages/platform-runtime/tests/*.py] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| New database/queue | SQLite/Postgres/Redis | Out of scope for Phase 15 because AGENTS.md forbids new service/database/queue dependencies unless required by the active plan; use injected in-memory/test stores and host-provided persistence ports first. [VERIFIED: AGENTS.md; packages/platform-runtime/src/platform_runtime/ports.py] |
| Hermes session storage as authority | Hermes `sessions.db` fallback | Existing project rules say read views may use Hermes sessions only as fallback and not as authority. [VERIFIED: services/conversation-read-view/README.md; AGENTS.md] |
| External memory framework | Mem0/Zep-style adapter | Deferred to Phase 18 and not required for session/interrupt runtime. [VERIFIED: .planning/REQUIREMENTS.md; docs/architecture/memory/context-memory-contracts.md] |

**Installation:** No new packages should be installed for Phase 15. [VERIFIED: packages/*/pyproject.toml; services/wecom-service/pyproject.toml]

## Package Legitimacy Audit

Not applicable: Phase 15 should not install external packages. [VERIFIED: AGENTS.md; packages/platform-runtime/pyproject.toml; services/wecom-service/pyproject.toml]

## Architecture Patterns

### System Architecture Diagram

```text
WeCom/Web inbound callback
  -> ChannelAdapter.verify_and_ack()
  -> ChannelAdapter.normalize_inbound()
  -> SessionResolver.resolve(turn, bot/session policy, stores, active task snapshot)
       -> pending unresolved RunInterrupt? -> RESUME_INTERRUPT
       -> active non-terminal task? -> ACTIVE_TASK_CONTROL_PLANE
       -> recent non-terminal/non-stale session? -> CONTINUE_SESSION
       -> clearly new/stale/terminal? -> START_NEW_SESSION
  -> Runtime
       -> resume paused run OR create new run OR route active-task notice
  -> BackendAdapter
       -> run result / waiting_for_user / needs_clarification
  -> InterruptStore / ContractLogStore
       -> append minimized RunInterrupt, run_event, session_decision evidence
  -> WeComChannelAdapter.deliver()
       -> ordinary InkStatute-owned clarification/status/business output
```

### Recommended Project Structure

```text
packages/platform-runtime/src/platform_runtime/
├── session_resolution.py      # Session resolver types, policy, decision reasons
├── interrupt_runtime.py       # Interrupt store helpers and resume-state transitions
├── protocols.py               # Add optional ports/data shapes only if needed
├── runtime.py                 # Minimal DefaultRunRuntime integration points
├── fakes.py                   # Deterministic fake backend/store support
└── store.py                   # Reuse privacy checks; optionally add lookup helpers

services/wecom-service/src/wecom_service/
├── active_task_router.py      # Keep/extend existing fast control-plane routing
└── task_flow.py               # Reuse non-terminal/terminal task snapshots

packages/contract-test-suite/fixtures/
└── phase15_session_interrupt_runtime.json
```

### Pattern 1: Resolver Decision Is Data, Not Side Effect

**What:** Return a frozen decision object with `action`, `conversation_id`, `session_id`, optional `run_id`, optional `interrupt_id`, `reason`, `raw_payload_ref`, `text_sha256_16`, `text_length`, and sanitized metadata. [VERIFIED: services/wecom-service/src/wecom_service/active_task_router.py; packages/platform-runtime/src/platform_runtime/store.py]  
**When to use:** Every inbound user message before run creation or interrupt resume. [VERIFIED: .planning/REQUIREMENTS.md]  
**Example:**

```python
# Source: local pattern in services/wecom-service/src/wecom_service/active_task_router.py
event = {
    "event": "session_resolution",
    "action": "resume_interrupt",
    "conversation_id": turn.conversation_id,
    "session_id": decision.session_id,
    "interrupt_id": decision.interrupt_id,
    "reason": "pending_interrupt_precedence",
    "raw_payload_ref": turn.metadata.get("raw_payload_ref"),
    "text_sha256_16": sha256_16(turn.content or ""),
    "text_length": len(turn.content or ""),
    "privacy": "no_raw_payload_or_legal_text_stored",
}
```

### Pattern 2: Pending Interrupt Precedes Active Task

**What:** If an unresolved, unexpired `RunInterrupt` exists for the channel/user/bot session, the next user message should resolve that interrupt before starting or updating another task. [VERIFIED: .planning/REQUIREMENTS.md; packages/platform-contract/src/platform_contract/schemas/run_interrupt.schema.json]  
**When to use:** WeCom clarification answers and backend skill questions. [VERIFIED: .planning/REQUIREMENTS.md]  
**Example:**

```python
# Source: local contract in packages/platform-contract/src/platform_contract/schemas/run_interrupt.schema.json
if pending_interrupt and not pending_interrupt.is_expired(now):
    return SessionResolutionDecision(
        action="resume_interrupt",
        session_id=pending_interrupt.session_id,
        run_id=pending_interrupt.run_id,
        interrupt_id=pending_interrupt.interrupt_id,
        reason="pending_interrupt_precedence",
    )
```

### Pattern 3: Backend Capability Truthfulness

**What:** Route cancel/update/parallel-task behavior through declared adapter capabilities; do not claim a message was applied unless the adapter supports and confirms it. [VERIFIED: services/wecom-service/src/wecom_service/active_task_router.py; packages/platform-contract/src/platform_contract/agent_adapter.py; .planning/STATE.md]  
**When to use:** Active task follow-ups and interrupt cancellation. [VERIFIED: services/wecom-service/tests/test_active_task_router.py]  
**Example:**

```python
# Source: local pattern in services/wecom-service/src/wecom_service/active_task_router.py
capabilities = AdapterTaskCapabilities(
    supports_cancel=backend_caps.cancel_support,
    supports_live_task_update=backend_caps.live_update_support,
    supports_parallel_tasks=backend_caps.parallel_task_support,
)
decision = route_active_task_turn(
    text=turn.content,
    active_task=active_task_snapshot,
    capabilities=capabilities,
    raw_payload_ref=turn.metadata.get("raw_payload_ref"),
)
```

### Anti-Patterns to Avoid

- **Storing raw clarification answers in interrupt/session decisions:** Store `raw_payload_ref`, hashes, lengths, and refs; raw text belongs outside contract logs. [VERIFIED: AGENTS.md; packages/platform-runtime/src/platform_runtime/store.py]
- **Making Hermes session DB authoritative:** The platform contract keeps `conversation_id` stable and backend-neutral; Hermes session data can only be an explicit fallback. [VERIFIED: docs/requirements/V2-PRD.md; services/conversation-read-view/README.md]
- **Adding a new runtime database in Phase 15:** Use injected ports and in-memory fakes first; new DB/queue/service is not required by the phase context. [VERIFIED: AGENTS.md; .planning/phases/15-session-resolver-and-interrupt-runtime/15-CONTEXT.md]
- **Delivering backend prompt/system wording directly to WeCom users:** WeCom egress must use InkStatute-owned wording and output boundary policy. [VERIFIED: AGENTS.md; packages/platform-runtime/tests/test_output_boundary.py]

## Recommended Plan Slices

| Slice | Scope | Primary Files | Tests |
|-------|-------|---------------|-------|
| 15-01 Resolver policy and stores | Add `SessionResolutionDecision`, resolver precedence, in-memory session/interrupt lookup stores, idle-window/stale/terminal handling, and privacy-safe decision events. [VERIFIED: .planning/REQUIREMENTS.md] | `packages/platform-runtime/src/platform_runtime/session_resolution.py`, `packages/platform-runtime/src/platform_runtime/store.py`, `packages/platform-runtime/src/platform_runtime/__init__.py` | `packages/platform-runtime/tests/test_session_resolution.py`; privacy mutation tests against raw text keys. [VERIFIED: packages/platform-runtime/tests/test_contract_log_store.py] |
| 15-02 Interrupt lifecycle and runtime resume | Add `RunInterrupt` creation/resolution helpers, map `AgentResult.needs_clarification` and `Run.status.waiting_for_user`, add fake backend script for waiting/resume, and log minimized run/interrupt events. [VERIFIED: packages/platform-contract/src/platform_contract/schemas/run_interrupt.schema.json] | `packages/platform-runtime/src/platform_runtime/interrupt_runtime.py`, `runtime.py`, `fakes.py`, `protocols.py` if a resume port is required | `packages/platform-runtime/tests/test_interrupt_runtime.py`, `test_run_runtime_lifecycle.py` additions. |
| 15-03 WeCom integration and fixture evidence | Apply resolver after WeCom normalization and before run routing; pending interrupt answer resumes paused run; active task follow-ups continue using fast control plane; add contract-test-suite fixture. [VERIFIED: packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py; services/wecom-service/src/wecom_service/active_task_router.py] | `packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py` or host orchestration seam, `services/wecom-service/src/wecom_service/*`, `packages/contract-test-suite/fixtures/phase15_session_interrupt_runtime.json` | WeCom unit tests, contract-test-suite schema and fixture replay tests. |

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Raw callback parsing | Custom string parsing | Existing `parse_callback_envelope` and channel adapters | It already rejects raw payload keys and normalizes scalar WeCom fields. [VERIFIED: services/wecom-service/src/wecom_service/protocol.py] |
| Privacy filtering | New ad hoc redaction | `InMemoryContractLogStore` privacy checks plus existing output boundary | Store rejects raw payload/full-text-like keys; output boundary filters ordinary-user visible backend notices. [VERIFIED: packages/platform-runtime/src/platform_runtime/store.py; packages/platform-runtime/src/platform_runtime/output_boundary.py] |
| Active-task intent classifier | Duplicate raw-text classifier in runtime | Existing `route_active_task_turn` or a shared extraction with the same metadata pattern | Existing classifier stores only hash/length/ref evidence and capability decisions. [VERIFIED: services/wecom-service/src/wecom_service/active_task_router.py] |
| Async state vocabulary | New status enum | `AsyncTaskState` and `InterruptStatus` | Contract enum already includes `waiting_for_user`; interrupt enum includes waiting/resolved/expired/cancelled. [VERIFIED: packages/platform-contract/src/platform_contract/enums.py] |
| Fixture validation | New JSON validator | Existing contract-test-suite `validate_event_bundle` | It already validates optional `run_interrupt` and related objects. [VERIFIED: packages/contract-test-suite/src/contract_test_suite/schema_validation.py] |

**Key insight:** Phase 15 is orchestration and state-resolution glue over existing contracts, not a new persistence or agent framework phase. [VERIFIED: .planning/phases/15-session-resolver-and-interrupt-runtime/15-CONTEXT.md; docs/architecture/memory/context-memory-contracts.md]

## Common Pitfalls

### Pitfall 1: Resuming a Stale or Terminal Session

**What goes wrong:** A user sends a clearly new task but the system attaches it to an old terminal session. [VERIFIED: .planning/REQUIREMENTS.md]  
**Why it happens:** Resolver lacks idle-window and terminal-state checks. [VERIFIED: .planning/ROADMAP.md]  
**How to avoid:** Make stale/terminal/new-task reasons explicit in `SessionResolutionDecision` and test each branch. [VERIFIED: services/wecom-service/tests/test_active_task_router.py]  
**Warning signs:** Decision metadata lacks `reason`, `session_updated_at`, or `prior_run_status`. [ASSUMED]

### Pitfall 2: Interrupt Answer Routed as a New Task

**What goes wrong:** The clarification answer starts a new run instead of resolving `RunInterrupt`. [VERIFIED: .planning/REQUIREMENTS.md]  
**Why it happens:** Active-task or new-task classifier runs before pending interrupt lookup. [ASSUMED]  
**How to avoid:** Pending unresolved/unexpired interrupt gets first precedence. [VERIFIED: packages/platform-contract/src/platform_contract/schemas/run_interrupt.schema.json; .planning/REQUIREMENTS.md]  
**Warning signs:** A fixture contains `run_interrupt.status=waiting_for_user` and the next turn creates a new `session_id` without `resolved_turn_id`. [VERIFIED: packages/platform-contract/fixtures/context_memory_foundation.json]

### Pitfall 3: Raw Legal Text Leaks Into Decision Records

**What goes wrong:** Session decision or interrupt metadata stores the user's legal facts or answer text. [VERIFIED: AGENTS.md]  
**Why it happens:** Developer copies `turn.content` into metadata for debugging. [ASSUMED]  
**How to avoid:** Use `text_sha256_16`, `text_length`, `raw_payload_ref`, `prompt_ref`, `resume_state_ref`, and source refs only. [VERIFIED: services/wecom-service/src/wecom_service/active_task_router.py; packages/platform-contract/src/platform_contract/schemas/run_interrupt.schema.json]  
**Warning signs:** Tests find keys like `raw_payload`, `full_text`, `document_text`, `payload_text`, or `case_facts`. [VERIFIED: packages/platform-runtime/src/platform_runtime/store.py; packages/contract-test-suite/tests/test_phase10_runruntime_contracts.py]

### Pitfall 4: Capability Overclaiming

**What goes wrong:** The service says a cancel/update/parallel task was applied when Hermes one-shot cannot do it. [VERIFIED: .planning/STATE.md; packages/backends/hermes/src/inkstatute_backends_hermes/manifest.py]  
**Why it happens:** Control-plane wording is not tied to adapter capabilities. [VERIFIED: services/wecom-service/src/wecom_service/active_task_router.py]  
**How to avoid:** Map backend capabilities into `AdapterTaskCapabilities` and use accepted/unsupported notice kinds. [VERIFIED: services/wecom-service/tests/test_active_task_router.py]  
**Warning signs:** `accepted_by_backend=True` with Hermes one-shot `live_update_support=False` or `cancel_support=False`. [VERIFIED: packages/backends/hermes/src/inkstatute_backends_hermes/manifest.py]

## Code Examples

### Append Privacy-Safe Session Decision

```python
# Source: local store pattern in packages/platform-runtime/src/platform_runtime/store.py
store.append(
    "session_resolution",
    {
        "decision_id": "session-decision-001",
        "conversation_id": turn.conversation_id,
        "session_id": session_id,
        "action": "continue_session",
        "reason": "recent_active_session",
        "raw_payload_ref": turn.metadata.get("raw_payload_ref"),
        "text_sha256_16": sha256_16(turn.content or ""),
        "text_length": len(turn.content or ""),
        "metadata": {"privacy": "no_raw_payload_or_legal_text_stored"},
    },
)
```

### Persist Pending Clarification Interrupt

```python
# Source: local schema in packages/platform-contract/src/platform_contract/schemas/run_interrupt.schema.json
interrupt = {
    "interrupt_id": "interrupt-001",
    "run_id": run.run_id,
    "session_id": session_id,
    "status": "waiting_for_user",
    "reason": "needs_clarification",
    "created_at": clock.now(),
    "prompt_ref": "ref://prompts/interrupt-001",
    "resume_state_ref": "ref://resume/interrupt-001",
    "expected_response_schema_ref": "ref://schemas/clarification-answer",
    "metadata": {"privacy": "prompt_and_resume_state_by_ref"},
}
```

### Resolve Duplicate Answer Deterministically

```python
# Source: local idempotency pattern in services/wecom-service/src/wecom_service/idempotency.py
answer_key = turn.metadata.get("idempotency_key")
if interrupt.resolved_turn_id == turn.turn_id or interrupt.metadata.get("resolved_idempotency_key") == answer_key:
    return ResumeDecision(action="duplicate_answer_ignored", interrupt_id=interrupt.interrupt_id)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| User/session commands such as `/new` or `/resume` | Invisible resolver from channel/user/bot, active task, pending interrupt, and idle-window signals | v1.2 requirements initialized 2026-06-30 | Phase 15 should not expose agent session commands to ordinary users. [VERIFIED: .planning/REQUIREMENTS.md] |
| One-shot path loses skill questions | Platform `RunInterrupt` with `waiting_for_user` and `resume_state_ref` | Phase 14 completed 2026-06-30 | Phase 15 can persist and resume clarification without raw payload storage. [VERIFIED: .planning/phases/14-memory-research-and-contract-spec/14-01-SUMMARY.md] |
| Hermes/channel session as boundary | InkStatute platform contract and WeCom-owned channel boundary | V2/v1.1 architecture decisions | Resolver must remain backend-neutral and cannot make Hermes gateway the user channel. [VERIFIED: AGENTS.md; .planning/PROJECT.md] |

**Deprecated/outdated:**
- Asking ordinary WeCom users to type session commands is explicitly out of scope. [VERIFIED: .planning/REQUIREMENTS.md]
- Treating memory/context systems as the session resolver authority is deferred; Phase 16-18 own context assembly and long-term memory. [VERIFIED: .planning/phases/15-session-resolver-and-interrupt-runtime/15-CONTEXT.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Session stale/new-task warning metadata should include `session_updated_at` and `prior_run_status`. | Common Pitfalls | Planner may choose different metadata names, but tests still need equivalent evidence. |
| A2 | Interrupt-answer misrouting commonly happens when active-task/new-task logic runs before pending interrupt lookup. | Common Pitfalls | If the implementation has a different orchestration order, planner should still preserve pending interrupt precedence. |
| A3 | Developers may accidentally copy `turn.content` into debug metadata. | Common Pitfalls | Privacy tests should catch this regardless of developer intent. |

## Open Questions

1. **Default idle window**
   - What we know: Phase requirements require idle-window signals, and `BotInstance.default_session_policy` exists as a metadata container. [VERIFIED: .planning/REQUIREMENTS.md; packages/platform-contract/src/platform_contract/schemas/bot_instance.schema.json]
   - What's unclear: No concrete default idle duration is locked in local docs. [VERIFIED: .planning/research/SUMMARY.md]
   - Recommendation: Put a conservative default in runtime policy metadata and make it injectable/tested; avoid hardcoding product policy in WeCom-only code. [ASSUMED]

2. **Backend resume surface**
   - What we know: `RunRuntime` has create/poll/stream/cancel/approve, and `BackendAdapter` has submit/get/stream/cancel/submit_approval but no dedicated `resume_run`. [VERIFIED: packages/platform-runtime/src/platform_runtime/protocols.py]
   - What's unclear: Whether resume should be modeled as a new backend protocol method, `submit_approval`, or a new run with `resume_state_ref`. [VERIFIED: packages/platform-runtime/src/platform_runtime/protocols.py; packages/platform-contract/src/platform_contract/schemas/run_interrupt.schema.json]
   - Recommendation: Plan should make this an explicit Wave 0 design task and keep Hermes one-shot capability-truthful. [ASSUMED]

3. **Where host orchestration currently lives**
   - What we know: Channel adapters normalize/deliver, runtime runs backends, and WeCom service has primitives; no single production orchestrator file was found in targeted search. [VERIFIED: packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py; packages/platform-runtime/src/platform_runtime/runtime.py; services/wecom-service/src/wecom_service/*.py]
   - What's unclear: Which app/host should wire resolver to WeCom ingress in this phase. [ASSUMED]
   - Recommendation: Planner should add a narrow host integration task only after selecting the existing orchestration seam by code search. [ASSUMED]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | All Phase 15 Python packages/tests | ✓ | 3.14.6 | Python >=3.11 per pyproject files. [VERIFIED: local command; pyproject.toml files] |
| pytest | Optional test runner | ✓ | 9.1.1 | `python -m unittest discover ...` works because tests use stdlib unittest. [VERIFIED: local command; packages/platform-runtime/tests/*.py] |
| Node/npm | GSD graph/tooling only, not implementation | ✓ | Node v24.16.0, npm 11.13.0 | Not needed for Phase 15 runtime code. [VERIFIED: local command] |
| ctx7 | External docs lookup | ✗ | — | Not needed; user requested local sources and no internet unless necessary. [VERIFIED: local command] |
| slopcheck | Package legitimacy gate | ✗ | — | Not needed because no package installs are recommended. [VERIFIED: local command] |

**Missing dependencies with no fallback:** None for the recommended no-new-dependency implementation. [VERIFIED: local command; pyproject.toml files]

**Missing dependencies with fallback:** `ctx7` and `slopcheck` are unavailable but not required because this phase is local-code-only and installs no packages. [VERIFIED: local command]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | stdlib `unittest`; pytest 9.1.1 available as runner. [VERIFIED: packages/*/tests/*.py; local `pytest --version`] |
| Config file | none found for pytest/unittest at repo root. [VERIFIED: local `find` for pytest.ini/tox.ini] |
| Quick run command | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests` |
| WeCom quick command | `PYTHONPATH=packages/platform-contract/src:services/wecom-service/src python -m unittest discover -s services/wecom-service/tests` |
| Contract suite command | `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| CTX-01 | No `/new`/`/resume` command needed for continuation | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_session_resolution.py -k continue` | ❌ Wave 0 |
| CTX-02 | Resolver uses channel/user/bot, active task, pending interrupt, idle window | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_session_resolution.py` | ❌ Wave 0 |
| CTX-03 | New/stale/terminal sessions open a new session | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_session_resolution.py -k new_session` | ❌ Wave 0 |
| CTX-04 | Session decisions store refs/hash/length only | unit/privacy | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_session_resolution.py -k privacy` | ❌ Wave 0 |
| INT-01 | Backend clarification becomes `waiting_for_user` and `RunInterrupt` | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_interrupt_runtime.py` | ❌ Wave 0 |
| INT-02 | Next WeCom answer resumes paused run | integration/unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:services/wecom-service/src:packages/channels/wecom/src python -m unittest discover -s services/wecom-service/tests -p 'test_session_interrupt*.py'` | ❌ Wave 0 |
| INT-03 | Freeform/multiple-choice metadata preserved by ref | schema/unit | `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py'` | ✅ existing schema support; add fixture |
| INT-04 | Timeout/cancel/duplicate answer deterministic and privacy-safe | unit | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_interrupt_runtime.py -k duplicate` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** Run the narrow package tests touched by the task. [VERIFIED: existing package test layout]
- **Per wave merge:** Run platform-runtime, WeCom service, and contract-test-suite commands above. [VERIFIED: existing package test layout]
- **Phase gate:** Full affected Python suites green before `$gsd-verify-work`; include contract fixture replay. [VERIFIED: AGENTS.md; packages/contract-test-suite/tests/test_fixture_replay.py]

### Wave 0 Gaps

- [ ] `packages/platform-runtime/tests/test_session_resolution.py` — covers CTX-01 through CTX-04.
- [ ] `packages/platform-runtime/tests/test_interrupt_runtime.py` — covers INT-01, INT-03, INT-04.
- [ ] `services/wecom-service/tests/test_session_interrupt_runtime.py` or channel-host equivalent — covers INT-02.
- [ ] `packages/contract-test-suite/fixtures/phase15_session_interrupt_runtime.json` — covers schema/relationship fixture evidence.
- [ ] Optional helper tests for no raw text in phase fixture, mirroring Phase 10 privacy assertions.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no direct new auth | Phase uses existing channel identity fields; do not add auth secrets. [VERIFIED: packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py; AGENTS.md] |
| V3 Session Management | yes | Backend-neutral resolver with deterministic stale/terminal/new-session policy and privacy-safe session IDs. [VERIFIED: .planning/REQUIREMENTS.md] |
| V4 Access Control | yes | Scope lookup by tenant/workspace/channel/user/bot; no cross-user pending interrupt/session reuse. [VERIFIED: packages/platform-contract/src/platform_contract/schemas/session.schema.json; packages/platform-contract/src/platform_contract/schemas/bot_instance.schema.json] |
| V5 Input Validation | yes | Existing structured callback parsers and schema validators; no ad hoc raw XML/body storage. [VERIFIED: services/wecom-service/src/wecom_service/protocol.py; packages/contract-test-suite/src/contract_test_suite/schema_validation.py] |
| V6 Cryptography | yes, limited | Use hashing for evidence; do not hand-roll secrets/encryption or store WeCom keys. [VERIFIED: services/wecom-service/src/wecom_service/active_task_router.py; AGENTS.md] |

### Known Threat Patterns for Phase 15

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Session fixation/cross-user resume | Elevation of Privilege | Match pending interrupts and sessions by tenant/workspace/channel/user/bot, not only `conversation_id`. [VERIFIED: packages/platform-contract/src/platform_contract/schemas/session.schema.json] |
| Duplicate WeCom callback answer | Tampering/Replay | Use existing idempotency key patterns and store resolved idempotency metadata. [VERIFIED: services/wecom-service/src/wecom_service/idempotency.py] |
| Raw legal payload leakage in logs | Information Disclosure | Contract log privacy rejection plus fixture privacy assertions. [VERIFIED: packages/platform-runtime/src/platform_runtime/store.py; packages/platform-runtime/tests/test_contract_log_store.py] |
| Backend/system notice leak during clarification | Information Disclosure | Use runtime output boundary and WeCom-owned service wording. [VERIFIED: packages/platform-runtime/src/platform_runtime/output_boundary.py; AGENTS.md] |
| Unauthorized legal skill modification through feedback/interrupt | Tampering | Preserve human-review boundary; Phase 15 should not auto-modify legal skills. [VERIFIED: AGENTS.md; docs/architecture/memory/context-memory-contracts.md] |

## Sources

### Primary (HIGH confidence)

- `AGENTS.md` - project source of truth, privacy, WeCom/Hermes boundary, dependency and testing constraints.
- `docs/requirements/V2-PRD.md` - V2 contract/session state context and `waiting_for_user` async state.
- `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md` - milestone scope, phase requirements, and current decisions.
- `.planning/phases/15-session-resolver-and-interrupt-runtime/15-CONTEXT.md` - Phase 15 boundary and deferrals.
- `.planning/phases/14-memory-research-and-contract-spec/14-CONTEXT.md` and `14-*-SUMMARY.md` - Phase 14 contracts and completed fixture support.
- `packages/platform-contract/src/platform_contract/schemas/*.schema.json`, `events.py`, `enums.py` - contract source for `Session`, `Run`, `RunInterrupt`, states, and dataclasses.
- `packages/platform-runtime/src/platform_runtime/*.py` and tests - runtime protocols, feature flags, fakes, output boundary, and contract log store.
- `services/wecom-service/src/wecom_service/*.py` and tests - WeCom normalization, idempotency, task flow, active-task routing, and privacy patterns.
- `packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py` - WeCom channel adapter ingress/egress boundary.
- `packages/contract-test-suite/src/contract_test_suite/schema_validation.py` and fixtures - schema validation and additive optional object support.

### Secondary (MEDIUM confidence)

- None used; internet and external docs were intentionally avoided per user instruction.

### Tertiary (LOW confidence)

- Assumptions A1-A3 in the Assumptions Log.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - verified from local pyproject files and package tests.
- Architecture: HIGH - verified from local contracts, runtime protocols, WeCom service code, and phase requirements.
- Pitfalls: MEDIUM - core risks are verified by requirements and code; warning signs include a few implementation assumptions.

**Research date:** 2026-07-01  
**Valid until:** 2026-07-31 for local codebase planning, or until Phase 15 implementation changes the runtime/channel surfaces.
