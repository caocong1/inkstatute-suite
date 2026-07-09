# Phase 64: QQBotSessionRuntime + QQBotIngressRuntime - Research

**Researched:** 2026-07-09
**Domain:** Channel session continuity — compose `platform_runtime` (RunRuntime, SessionResolutionPolicy, InterruptStore, MemoryOrchestrator) inside `packages/channels/qqbot` without `wecom_service`
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
Discuss phase was skipped per user setting (`workflow.skip_discuss`). All implementation choices are at Claude's discretion.

Key constraints:
- Compose `platform_runtime` primitives directly — NO `wecom_service` import
- Scene-aware conversation identity: `qqbot:{scene}:{scene_id}:{user_openid}`
- Interrupt resume across user replies via InterruptStore
- Memory: pre-turn recall + post-turn retention via MemoryOrchestrator; fail-open on memory errors
- `dependencies = []` for qqbot package; no frozen protocol/platform-contract/channel-core edits
- Reuse existing normalization (Phase 60) and sender (Phase 62/63) where needed

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting.

### Deferred Ideas (OUT OF SCOPE)
None — discuss phase skipped. Full adapter Protocol IO promotion is Phase 65.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SESS-01 | QQBotSessionRuntime orchestrates continuous conversation via `RunRuntime` + `SessionResolutionPolicy` + `InterruptStore` + `MemoryOrchestrator`, composing `platform_runtime` directly (no `wecom_service`) | New `session_runtime.py` mirroring WeCom orchestration shape; inject Protocol/store/orchestrator; call `create_run` / `resume_interrupt` |
| SESS-02 | Interrupt resume preserves skill clarification across replies; scene-aware `conversation_id` partitions C2C vs group (no cross-scene collision) | Reuse Phase 60 `qqbot:{scene}:{scene_id}:{user_openid}`; InterruptStore `_scope_key` includes `conversation_id`; tests with two scenes |
| SESS-03 | Pre-turn recall + post-turn retention via `MemoryOrchestrator` with fail-open degradation matching WeCom | Wrap orchestrator recall + optional Memory retain in fail-open try/except; `finalize_memory` after reply; evidence refs only |
</phase_requirements>

## Summary

Phase 64 adds the QQ channel’s session/ingress orchestration layer that WeCom already has in `services/wecom-service`. The building blocks already exist in `packages/platform-runtime`: `RunRuntime` (Protocol + `DefaultRunRuntime`), `SessionResolutionPolicy` / `resolve_session_turn`, `InMemoryInterruptStore`, and `MemoryOrchestrator`. Phase 60 already emits scene-aware `AgentTurn.conversation_id` values (`qqbot:c2c:…` / `qqbot:group:…`). This phase wires those pieces inside `packages/channels/qqbot` as **pure, host-injectable** modules — no network IO, no signature verification, no Protocol surface changes, and **zero** `wecom_service` imports (copy the *pattern*, not the package).

WeCom’s `WeComSessionRuntime.handle_turn()` is the behavioral analog: idempotent duplicate handling → pending interrupt expiry → `resolve_session_turn` → `resume_interrupt` **or** `create_run` (with memory context merge). `WeComRuntimeIngress.handle_callback()` is the ingress analog: sanitize/normalize → `SessionScope` + `RunRequest` → session runtime. QQ should call Phase 60 `parse_envelope` / `normalize_message_event` (message turns only in this phase; feedback/interaction stays for Phase 66).

**Primary recommendation:** Implement `session_runtime.py` (`QQBotSessionRuntime`) and `ingress_runtime.py` (`QQBotRuntimeIngress`) in `inkstatute_channels_qqbot`, composing `platform_runtime` only; local fail-open memory helpers (do not import `wecom_service.memory_integration`); extend `test_no_wecom_import.py` to cover the new modules.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Callback → AgentTurn (message events) | API / Backend (`ingress_runtime` + Phase 60 `normalization`) | — | Pure mapping; host supplies sanitized callback |
| SessionScope + RunRequest construction | API / Backend (`ingress_runtime`) | `platform_runtime` types | Channel-local metadata (`source=qqbot_ingress_runtime`) |
| Session continue / start / interrupt resume | API / Backend (`session_runtime`) | `RunRuntime` + `SessionResolutionPolicy` + `InMemoryInterruptStore` | Same decision graph as WeCom; no WeCom import |
| Scene partition (C2C vs group) | API / Backend (conversation_id from Phase 60) | InterruptStore scope key | `conversation_id` is part of `_scope_key` |
| Pre-turn memory recall | API / Backend (`session_runtime`) | `MemoryOrchestrator` | Merge context refs into `RunRequest.metadata` before `create_run` |
| Post-turn memory retention | API / Backend (`session_runtime.finalize_memory`) | optional `Memory` port | Host calls after reply finalized; fail-open |
| Signature / ACK / deliver | Deferred Phase 65 (`adapter.py`) | Phase 59/62/63 | Out of Phase 64 scope |
| Feedback / INTERACTION_CREATE loop | Deferred Phase 66 | — | Ingress may ignore non-message categories |

## Project Constraints (from AGENTS.md / ROADMAP)

- Never commit secrets, tokens, runtime DBs, logs, customer documents, or raw legal payloads. `[VERIFIED: AGENTS.md]`
- Contract logs prefer `raw_payload_ref`; no sensitive full text by default. `[VERIFIED: AGENTS.md]`
- Do not introduce a new service, database, queue, or runtime dependency unless required. `[VERIFIED: AGENTS.md]`
- Keep changes scoped to the active GSD phase. `[VERIFIED: AGENTS.md]`
- `dependencies = []` for qqbot; no `wecom_service` imports. `[VERIFIED: pyproject.toml, test_no_wecom_import.py]`
- Frozen ChannelAdapter / BackendAdapter / platform-contract / channel-core must not be modified (ADAPTER-04). `[VERIFIED: ROADMAP.md]`
- Compose `platform_runtime` directly — WeCom is analog only. `[VERIFIED: 64-CONTEXT.md, REQUIREMENTS SESS-01]`

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `platform_runtime.protocols.RunRuntime` | in-repo | `create_run` / `resume_interrupt` | Frozen Protocol already used by WeCom + adapter imports `[VERIFIED: protocols.py:255-265]` |
| `platform_runtime.DefaultRunRuntime` | in-repo | Optional concrete runtime for hosts/tests | Exported from `__init__.py` `[VERIFIED: runtime.py, __init__.py]` |
| `platform_runtime.SessionResolutionPolicy` + `resolve_session_turn` | in-repo | CONTINUE / START / RESUME / ACTIVE_TASK decisions | Same as WeCom `[VERIFIED: session_resolver.py]` |
| `platform_runtime.InMemoryInterruptStore` | in-repo | Pending clarification + duplicate/expiry | Scope key includes `conversation_id` `[VERIFIED: interrupts.py:432-441]` |
| `platform_runtime.MemoryOrchestrator` | in-repo | Pre-turn recall + ContextBundle refs | SESS-03 primary surface `[VERIFIED: memory_orchestrator.py]` |
| `platform_runtime.Memory` + `RetryableMemory` (optional) | in-repo | Post-turn `aretain` / pre-turn `arecall` | WeCom dual-path; fail-open via local policy `[VERIFIED: wecom memory_integration.py]` |
| Phase 60 `normalization.parse_envelope` / `normalize_message_event` | in-repo | Callback → AgentTurn | Already produces scene-aware ids `[VERIFIED: normalization.py:296]` |
| Python stdlib `dataclasses` / `enum.StrEnum` / `unittest` | 3.11+ (env 3.14.6) | Outcome types + tests | Matches qqbot + WeCom style |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `platform_runtime.FakeIdFactory` / `FakeRuntimeClock` | in-repo | Deterministic tests | Copy WeCom test fakes pattern |
| `platform_runtime.fakes` / RecordingRuntime in tests | test-local | Assert create vs resume | Same as `test_ingress_runtime.py` |
| `platform_contract.events.AgentTurn` | frozen | Turn payload | Already used by normalization |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Compose `platform_runtime` in qqbot package | Import / subclass `WeComSessionRuntime` | **Forbidden** — SESS-01 + `test_no_wecom_import` |
| Thin re-export of WeCom helpers via shared package | New `channel_core.session_runtime` | Out of scope; CONTEXT forbids channel-core edits; Phase 64 is qqbot-local |
| Skip MemoryOrchestrator; only raw Memory | Memory-only like early WeCom | SESS-03 explicitly requires MemoryOrchestrator |
| Full active-task notice routing (`route_active_task_turn` + WeCom sender envelopes) | Decision-only ACTIVE_TASK outcome | WeCom router is service-local; SESS success criteria omit notices — return action + evidence, no WeCom sender |
| Install httpx/botpy for ingress | N/A | Phase 64 is pure orchestration; no new deps |

**Installation:** None — no new packages. Workspace PYTHONPATH already supplies `platform_runtime` / `platform_contract` / `channel_core` (same as existing `adapter.py`).

**Version verification:** No PyPI packages added. In-repo imports verified via `PYTHONPATH=packages/platform-runtime/src:packages/platform-contract/src python3 -c "from platform_runtime import …"`. `[VERIFIED: shell 2026-07-09]`

## Package Legitimacy Audit

> No external packages are installed in this phase.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| — | — | — | — | — | — | N/A — no installs |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck not required — zero new registry dependencies.*

## Architecture Patterns

### System Architecture Diagram

```text
Host (sanitized QQ webhook body + headers already verified elsewhere)
        │
        ▼
QQBotRuntimeIngress.handle_callback(callback, received_at, …)
        │  parse_envelope / normalize_message_event (Phase 60)
        │  build SessionScope(channel_id="qqbot", conversation_id=turn.conversation_id, user_id=openid)
        │  build RunRequest(turn, solution, tenant/workspace/bot, metadata refs)
        ▼
QQBotSessionRuntime.handle_turn(turn, scope, run_request, recent_session, active_task?, …)
        │
        ├─ idempotency / duplicate interrupt answer ──► DUPLICATE_ANSWER_IGNORED
        ├─ pending interrupt expired ──► INTERRUPT_EXPIRED (store resolve)
        ├─ resolve_session_turn(policy, …)
        │     │
        │     ├─ RESUME_INTERRUPT ──► RunRuntime.resume_interrupt(…)
        │     ├─ ACTIVE_TASK_FOLLOW_UP ──► outcome only (no WeCom router import)
        │     └─ CONTINUE / START_NEW ──► [optional Memory fail-open recall]
        │                                   [MemoryOrchestrator.recall_and_assemble fail-open]
        │                                   RunRuntime.create_run(decision_request)
        ▼
QQBotSessionRuntimeOutcome (action, decision, run_id, evidence)
        │
        ▼ (host, after agent reply + output policy)
QQBotSessionRuntime.finalize_memory(…) ──► Memory.aretain fail-open (optional)
```

### Recommended Project Structure

```text
packages/channels/qqbot/src/inkstatute_channels_qqbot/
├── session_runtime.py      # QQBotSessionRuntime + Outcome/Action + fail-open memory helpers
├── ingress_runtime.py      # QQBotRuntimeIngress: callback → turn → session_runtime
├── normalization.py        # Phase 60 (reuse)
├── adapter.py              # Phase 65 wires these; do not promote Protocol IO here
└── …

packages/channels/qqbot/tests/
├── test_session_runtime.py           # Wave 0+ : interrupt / continue / scene isolation
├── test_ingress_runtime.py           # Wave 0+ : callback wiring
├── test_session_memory_runtime.py    # fail-open recall/retain + orchestrator metadata
└── test_no_wecom_import.py            # extend AST coverage to new modules
```

### Pattern 1: Channel Session Runtime (WeCom analog, qqbot-local)

**What:** Inject `RunRuntime`, optional `InMemoryInterruptStore`, `SessionResolutionPolicy`, optional `MemoryOrchestrator` / `Memory`; `handle_turn` returns a frozen outcome StrEnum.
**When to use:** Every normalized user message turn that should continue a conversation.
**Example (shape — adapt from WeCom, do not import):**

```python
# Analog source: services/wecom-service/src/wecom_service/session_runtime.py
# [VERIFIED: codebase read 2026-07-09]
class QQBotSessionRuntimeAction(StrEnum):
    RESUME_INTERRUPT = "resume_interrupt"
    DUPLICATE_ANSWER_IGNORED = "duplicate_answer_ignored"
    INTERRUPT_EXPIRED = "interrupt_expired"
    INTERRUPT_CANCELLED = "interrupt_cancelled"
    ACTIVE_TASK_FOLLOW_UP = "active_task_follow_up"
    CONTINUE_SESSION = "continue_session"
    START_NEW_SESSION = "start_new_session"

# Decision branch (conceptual):
# if decision.action == SessionResolutionAction.RESUME_INTERRUPT:
#     run = await self.runtime.resume_interrupt(...)
# else:
#     decision_request = _with_memory_context(...)  # fail-open
#     run = await self.runtime.create_run(decision_request)
```

### Pattern 2: Ingress Boundary

**What:** Host-callable class with no network/DB; builds scope/request and delegates.
**When to use:** Production hosts and tests that already have a sanitized callback mapping.
**Example:**

```python
# Analog source: services/wecom-service/src/wecom_service/ingress_runtime.py
# [VERIFIED: codebase read 2026-07-09]
outcome = await ingress.handle_callback(
    callback,
    received_at=received_at,
    recent_session=recent_session,
    metadata={"recent_turn_refs": (...), "privacy": "no_raw_payload_or_legal_text_stored"},
)
```

### Pattern 3: Scene-aware identity (already shipped)

**What:** `conversation_id = f"qqbot:{scene}:{scene_id}:{user_openid}"`.
**When to use:** Always for C2C / GROUP_AT / interaction normalization (Phase 60).
**Verified values:** `qqbot:c2c:{openid}:{openid}`, `qqbot:group:{group_openid}:{member_openid}`. `[VERIFIED: normalization.py:296, test_normalization.py]`

### Anti-Patterns to Avoid

- **Importing `wecom_service`:** Breaks SESS-01 and AST gate; copy patterns locally.
- **Putting raw answer/legal text in outcome evidence or RunRequest.metadata:** Use refs + sha16 only (WeCom `_safe_json` / privacy keys).
- **Calling MemoryOrchestrator on RESUME_INTERRUPT path:** WeCom skips orchestrator on resume/active/duplicate — match that. `[VERIFIED: test_session_memory_runtime.py:280-282]`
- **Editing frozen protocols / channel-core / platform-contract:** ADAPTER-04.
- **Declaring PyPI deps in qqbot `pyproject.toml`:** Keep `dependencies = []`; rely on workspace PYTHONPATH like `adapter.py`.
- **Wiring Phase 65 adapter flag / live IO here:** Deferred.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Session continue vs new vs interrupt | Custom if/else on message text only | `SessionResolutionPolicy` + `resolve_session_turn` | Idle window, terminal statuses, pending interrupt precedence already encoded `[VERIFIED: session_resolver.py]` |
| Pending clarification storage | Ad hoc dict keyed by openid | `InMemoryInterruptStore` | Expiry, duplicate answer, scope isolation `[VERIFIED: interrupts.py]` |
| Backend run submission | Direct Hermes/backend calls | `RunRuntime.create_run` / `resume_interrupt` | Backend-neutral Protocol |
| Memory context assembly | Manual ContextBundle construction | `MemoryOrchestrator.recall_and_assemble` | Isolation checks + MemoryUse evidence modes |
| Conversation id format | New scheme | Phase 60 `qqbot:{scene}:{scene_id}:{user_openid}` | Already fixture-tested; InterruptStore partitions on it |

**Key insight:** Phase 64 is composition and channel-local metadata — not new runtime primitives.

## Common Pitfalls

### Pitfall 1: Accidental wecom_service coupling
**What goes wrong:** Copy-paste imports `from wecom_service…` or docstring contains the forbidden string in AST-scanned files.
**Why it happens:** WeCom files are the closest analog.
**How to avoid:** Reimplement helpers in qqbot; extend `test_no_wecom_import.py` for `session_runtime.py` / `ingress_runtime.py`; avoid literal `wecom_service` in module docstrings (Phase 60 lesson).
**Warning signs:** AST test red; import error in isolated qqbot PYTHONPATH without wecom-service.

### Pitfall 2: Cross-scene interrupt collision
**What goes wrong:** Same user openid in C2C and group resumes the wrong interrupt.
**Why it happens:** Keying only on `user_id` / openid.
**How to avoid:** Always put Phase 60 `conversation_id` on `SessionScope`; InterruptStore `_scope_key` already includes it. `[VERIFIED: interrupts.py:432-441]`
**Warning signs:** Test with two scopes (c2c vs group) sharing user_id but different conversation_id fails isolation.

### Pitfall 3: MemoryOrchestrator fail-closed by default
**What goes wrong:** `MemoryUseEvidenceFailureMode.FAIL_CLOSED` or uncaught exceptions block `create_run`.
**Why it happens:** WeCom’s `_with_memory_context` does **not** catch orchestrator errors; fail-open is on the separate `Memory` + `MemoryIntegrationPolicy` path. SESS-03 still requires fail-open for QQ.
**How to avoid:** For QQ, wrap `recall_and_assemble` in try/except (fail-open default); use orchestrator policy `DEGRADED` for evidence; local `MemoryFailureMode.FAIL_OPEN` for optional Memory retain/recall. Document evidence metadata `memory_degraded=true` without raising.
**Warning signs:** FailingMemoryOrchestrator prevents `runtime.created` non-empty.

### Pitfall 4: Treating interaction/feedback as session turns
**What goes wrong:** INTERACTION_CREATE routed into `handle_turn` as AgentTurn.
**Why it happens:** Ingress receives full gateway envelopes.
**How to avoid:** Ingress only normalizes message categories (C2C / GROUP_AT); return a clear skip/empty outcome for validation/unknown/interaction (Phase 66 owns feedback).
**Warning signs:** FeedbackEvent fields appear on RunRequest.turn.

### Pitfall 5: Forgetting finalize_memory is post-reply
**What goes wrong:** Retaining before agent reply exists, or retaining raw legal text into contract logs.
**Why it happens:** `handle_turn` only has user text.
**How to avoid:** Mirror WeCom `finalize_memory` separate API; host calls after output policy; store refs/summaries per Memory policy, not in outcome evidence.
**Warning signs:** Tests call retain inside `handle_turn` only.

## Code Examples

### InterruptStore scope includes conversation_id

```python
# Source: packages/platform-runtime/src/platform_runtime/interrupts.py
def _scope_key(scope: SessionScope) -> tuple[str, ...]:
    return (
        scope.tenant_id,
        scope.workspace_id,
        scope.channel_id,
        scope.user_id,
        scope.bot_instance_id,
        scope.conversation_id,
        scope.thread_id or "",
    )
```

### Scene-aware conversation_id (Phase 60)

```python
# Source: packages/channels/qqbot/src/inkstatute_channels_qqbot/normalization.py
conversation_id = f"qqbot:{scene}:{scene_id}:{user_openid}"
```

### WeCom fail-open Memory recall (replicate locally, do not import)

```python
# Analog: services/wecom-service/src/wecom_service/memory_integration.py
# Default failure_mode = FAIL_OPEN; except Exception: return ()
async def recall_for_turn(...):
    try:
        result = await memory.arecall(...)
        return tuple(m.text for m in result.memories)
    except Exception:
        if policy.failure_mode == MemoryFailureMode.FAIL_CLOSED:
            raise
        return ()
```

### Recommended QQ orchestrator fail-open wrapper

```python
# [ASSUMED] recommended qqbot-local helper — WeCom does not wrap orchestrator today
def _with_memory_context_fail_open(run_request, *, memory_orchestrator, ...):
    try:
        return _with_memory_context(run_request, memory_orchestrator=memory_orchestrator, ...)
    except Exception:
        metadata = dict(run_request.metadata)
        metadata["memory_orchestrator_status"] = "degraded"
        metadata["privacy"] = "no_raw_payload_or_legal_text_stored"
        return replace(run_request, metadata=_safe_json(metadata))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixture-only QQBot adapter loop | Real normalization (60) + sender (62/63) + session/ingress (64) | v1.8 | Continuous conversation without WeCom coupling |
| WeCom-only session runtime | Channel-local runtimes composing shared `platform_runtime` | v1.2–v1.4 WeCom; v1.8 QQ | Pattern reuse without shared channel-core session module |

**Deprecated/outdated:**
- Importing WeCom for QQ session continuity — explicitly forbidden by SESS-01.
- Keying sessions only on openid — superseded by scene-aware conversation_id.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | QQ should wrap `MemoryOrchestrator.recall_and_assemble` in fail-open even though WeCom currently lets FAIL_CLOSED evidence errors raise | Pitfall 3 / Code Examples | Planner may under-specify SESS-03 vs WeCom parity; confirm fail-open applies to orchestrator path |
| A2 | ACTIVE_TASK_FOLLOW_UP can return outcome without porting `wecom_service.active_task_router` notice envelopes | Architecture | Hosts needing WeCom-parity notices may need a later phase |
| A3 | Ingress should skip non-message gateway categories (interaction/validation) rather than error | Pitfalls | Hosts may prefer explicit error; Phase 66 may redefine |
| A4 | Optional `Memory` port alongside MemoryOrchestrator matches SESS-03 “via MemoryOrchestrator” for retention | Standard Stack | If retention must go only through orchestrator, drop Memory port |

## Open Questions

1. **Orchestrator fail-open vs WeCom strict evidence** — **RESOLVED (planner D-01)**
   - What we know: WeCom `test_fail_closed_memory_evidence_error_blocks_backend_submission` expects raise; SESS-03 asks fail-open matching WeCom *session* memory behavior (MemoryIntegrationPolicy default FAIL_OPEN).
   - Resolution: Default fail-open for both Memory and MemoryOrchestrator paths in QQ; optional `failure_mode=FAIL_CLOSED` policy flag for tests only. Planned in `64-03-PLAN.md`.

2. **Export surface in `__init__.py`** — **RESOLVED (planner D-02)**
   - What we know: Today exports only adapter + config.
   - Resolution: Export `QQBotSessionRuntime`, `QQBotSessionRuntimeAction`, `QQBotSessionRuntimeOutcome`, and `QQBotRuntimeIngress` from `__init__.py` for host discoverability. Planned in `64-02-PLAN.md`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | qqbot package | ✓ | 3.14.6 | — |
| `platform_runtime` (workspace) | session/ingress | ✓ | in-repo | PYTHONPATH in tests/gates |
| `platform_contract` (workspace) | AgentTurn | ✓ | in-repo | — |
| `unittest` / `pytest` | tests | ✓ | stdlib / local pytest | Prefer unittest like existing qqbot tests |
| Live QQ network | — | N/A | — | Not required for Phase 64 |
| `wecom-service` | — | present but **must not be imported** | — | Analog read-only |

**Missing dependencies with no fallback:** none

**Missing dependencies with fallback:** none

Step 2.6: External tools beyond workspace packages — none required for implementation.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | unittest (stdlib) + `IsolatedAsyncioTestCase` |
| Config file | `packages/channels/qqbot/pyproject.toml` |
| Quick run command | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src" python3 -m unittest packages.channels.qqbot.tests.test_session_runtime packages.channels.qqbot.tests.test_ingress_runtime -v` |
| Full suite command | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src" python3 -m unittest discover -s packages/channels/qqbot/tests -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SESS-01 | handle_turn create_run / resume_interrupt via injected RunRuntime | unit | `… test_session_runtime` | ❌ Wave 0 |
| SESS-01 | ingress callback → session runtime | unit | `… test_ingress_runtime` | ❌ Wave 0 |
| SESS-02 | pending clarification → resume_interrupt; duplicate ignored | unit | `… test_session_runtime` | ❌ Wave 0 |
| SESS-02 | c2c vs group conversation_id isolation (no cross resume) | unit | `… test_session_runtime.SceneIsolation` | ❌ Wave 0 |
| SESS-03 | MemoryOrchestrator metadata merged on create_run | unit | `… test_session_memory_runtime` | ❌ Wave 0 |
| SESS-03 | failing memory/orchestrator still create_run (fail-open) | unit | `… test_session_memory_runtime` | ❌ Wave 0 |
| SESS-03 | finalize_memory retain fail-open | unit | `… test_session_memory_runtime` | ❌ Wave 0 |
| ADAPTER-04 | no wecom_service import; dependencies=[]; freeze | unit | `… test_no_wecom_import test_v1_8_safety_baseline test_contract_freeze_not_violated` | ✅ extend |

### Sampling Rate

- **Per task commit:** quick run (session + ingress)
- **Per wave merge:** full qqbot suite
- **Phase gate:** full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `packages/channels/qqbot/tests/test_session_runtime.py` — covers SESS-01/02
- [ ] `packages/channels/qqbot/tests/test_ingress_runtime.py` — covers SESS-01 ingress wiring
- [ ] `packages/channels/qqbot/tests/test_session_memory_runtime.py` — covers SESS-03
- [ ] Extend `test_no_wecom_import.py` for `session_runtime.py` + `ingress_runtime.py`
- [ ] Implementation modules `session_runtime.py` + `ingress_runtime.py` (RED → GREEN)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Signature/ACK remain Phase 59/65; ingress assumes sanitized input |
| V3 Session Management | yes | SessionScope + conversation_id partition; InterruptStore scoped keys |
| V4 Access Control | yes | Tenant/workspace/bot/user/conversation isolation on scope |
| V5 Input Validation | yes | Reuse Phase 60 normalizer; validate turn/scope/request match (WeCom `_validate_turn_scope`) |
| V6 Cryptography | no | No new crypto in Phase 64 |

### Known Threat Patterns for channel session runtime

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-tenant / cross-scene session bleed | Elevation / Info disclosure | Full SessionScope key including conversation_id |
| Raw legal text in runtime metadata | Info disclosure | Refs only; `_safe_json`; privacy markers |
| Memory backend outage blocks lawyer reply | Denial of service | Fail-open recall/retain (SESS-03) |
| Duplicate clarification answer double-submit | Tampering / replay | Idempotency key + InterruptStore duplicate resolve |
| Accidental WeCom coupling | — | AST `test_no_wecom_import` |

## Sources

### Primary (HIGH confidence)

- `services/wecom-service/src/wecom_service/session_runtime.py` — WeComSessionRuntime orchestration analog
- `services/wecom-service/src/wecom_service/ingress_runtime.py` — WeComRuntimeIngress analog
- `services/wecom-service/src/wecom_service/memory_integration.py` — fail-open Memory policy analog
- `packages/platform-runtime/src/platform_runtime/{protocols,session_resolver,interrupts,memory_orchestrator,runtime}.py`
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/normalization.py` — scene-aware conversation_id
- `.planning/REQUIREMENTS.md` SESS-01..03; `.planning/ROADMAP.md` Phase 64
- `.planning/phases/60-qq-event-normalization/60-01-SUMMARY.md`, `60-02-SUMMARY.md`
- `.planning/research/STACK.md` § Runtime Session Continuity

### Secondary (MEDIUM confidence)

- WeCom tests: `test_ingress_runtime.py`, `test_session_interrupt_runtime.py`, `test_session_memory_runtime.py`, `test_session_memory_integration.py`
- Phase 63 RESEARCH/VALIDATION patterns for qqbot unittest PYTHONPATH

### Tertiary (LOW confidence)

- Graphify disabled — no graph relationships injected
- A1–A4 assumptions on fail-open orchestrator / active-task / ingress skip

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all primitives verified in-repo; no new packages
- Architecture: HIGH — WeCom analog + Phase 60 ids + InterruptStore scope key verified
- Pitfalls: HIGH — import isolation, scene collision, memory fail modes evidenced by existing tests

**Research date:** 2026-07-09
**Valid until:** 2026-08-08 (30 days; stable in-repo APIs)

## Analog File Paths (for planner)

| Role | Path |
|------|------|
| WeCom session runtime (analog) | `services/wecom-service/src/wecom_service/session_runtime.py` |
| WeCom ingress runtime (analog) | `services/wecom-service/src/wecom_service/ingress_runtime.py` |
| WeCom memory fail-open (analog) | `services/wecom-service/src/wecom_service/memory_integration.py` |
| WeCom active-task router (analog, optional) | `services/wecom-service/src/wecom_service/active_task_router.py` |
| WeCom session/interrupt tests | `services/wecom-service/tests/test_session_interrupt_runtime.py` |
| WeCom ingress tests | `services/wecom-service/tests/test_ingress_runtime.py` |
| WeCom memory tests | `services/wecom-service/tests/test_session_memory_runtime.py`, `test_session_memory_integration.py` |
| RunRuntime Protocol | `packages/platform-runtime/src/platform_runtime/protocols.py` |
| DefaultRunRuntime | `packages/platform-runtime/src/platform_runtime/runtime.py` |
| SessionResolutionPolicy | `packages/platform-runtime/src/platform_runtime/session_resolver.py` |
| InMemoryInterruptStore | `packages/platform-runtime/src/platform_runtime/interrupts.py` |
| MemoryOrchestrator | `packages/platform-runtime/src/platform_runtime/memory_orchestrator.py` |
| QQ conversation_id | `packages/channels/qqbot/src/inkstatute_channels_qqbot/normalization.py` |
| No-wecom AST gate | `packages/channels/qqbot/tests/test_no_wecom_import.py` |
