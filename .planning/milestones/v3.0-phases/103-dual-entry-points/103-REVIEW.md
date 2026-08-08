---
phase: 103
slug: dual-entry-points
status: complete
created: 2026-08-08
review_depth: standard
---

# Phase 103 — Code Review

## Summary

Phase 103 implements dual entry points for the self-built agent core: an
in-process `InProcessAgentCoreAdapter` (BackendAdapter Protocol) and an ACP
server CLI (`inkstatute-agent acp`). Both share the same `run_turn()` async
generator, proving the core has no architectural privilege.

**Security posture is strong.** Permission safety is correctly implemented in
both entry points: `terminal` and `execute_code` are never auto-approved in the
in-process adapter, and the ACP server never sets `auto_approve` or
`default_decision` for any permission request. The ACP server declares only
`streaming`, `elicitation`, and `permissions` — no `fs/*` or `terminal/*`
capabilities leak. This satisfies AGENTS.md SAFE-04.

**One correctness bug found** in the cancellation sentinel logic
(`backend_adapter.py`): `asyncio.current_task().cancelled()` returns `False`
during the `finally` block, causing a premature `_STREAM_DONE` sentinel that
makes `stream_events` consumers miss the `run.state_changed` cancelled event.
The existing test passes only because it cancels before the background task
starts (a Python 3.11+ optimization where the coroutine body never executes).

**Several warnings** relate to incomplete functionality in the ACP server
(fire-and-forget elicitation, no session message history update, no
tool_executor) and architectural inequality between the two entry points
(different system prompts, missing artifact/citation event forwarding).

9 source files reviewed, 4 test files assessed for quality.

## Findings

### Critical

None. No security-critical issues found. Permission safety and capability
declaration are correct in both entry points.

### Warning

#### W-1: Cancellation sentinel race condition — cancelled event lost
**File:** `backend_adapter.py` lines 483–487
**Severity:** Warning (correctness bug, masked by test timing)

The `finally` block in `_run_turn_background` uses
`asyncio.current_task().cancelled()` to decide whether to push the
`_STREAM_DONE` sentinel. The intent is: if the task was cancelled,
`cancel_run` will push the sentinel (after the cancelled event), so the
background task should not push it.

**The check does not work.** Verified empirically: `Task.cancelled()`
returns `False` during the `finally` block because the task has not yet
transitioned to the `_CANCELLED` state (that transition happens in
`Task.__step`'s `except CancelledError` handler, which runs *after* the
coroutine fully exits).

**Impact:** When `cancel_run` is called after the background task has
started (the normal production case), the queue receives:

```
[...events..., _STREAM_DONE (from bg task), cancelled_event (from cancel_run), _STREAM_DONE (from cancel_run)]
```

`stream_events` breaks on the first `_STREAM_DONE` and never yields the
`cancelled_event`. The run status is still correctly set to `CANCELLED`
(via `replace(run, status=...)`), so `get_run` returns the right state,
but the event stream is missing the terminal `run.state_changed` event.

**Why the test passes:** `test_cancel_run_emits_state_changed` calls
`cancel_run` immediately after `submit_run` with no `await` in between.
In Python 3.11+, when a task is cancelled before its first `__step`, the
coroutine body never executes — the task is directly marked cancelled.
So the `finally` block never runs, no premature sentinel is pushed, and
the test sees the cancelled event. Verified empirically:

```
# Cancel after task started (race triggers):
BG TASK: pushing _STREAM_DONE (cancelled()=False)
CANCEL_RUN: pushing cancelled_event
CANCEL_RUN: pushing _STREAM_DONE
STREAM: got _STREAM_DONE, breaking        ← cancelled_event missed!

# Cancel before task started (test scenario, race avoided):
CANCEL_RUN: pushing cancelled_event
CANCEL_RUN: pushing _STREAM_DONE
STREAM: got cancelled_event               ← works correctly
STREAM: got _STREAM_DONE, breaking
```

**Fix:** Use an explicit cancellation flag instead of
`asyncio.current_task().cancelled()`:

```python
# In cancel_run, before task.cancel():
self._cancel_flags.add(run_id)

# In _run_turn_background finally:
finally:
    if run_id not in self._cancel_flags:
        await queue.put(_STREAM_DONE)
```

#### W-2: ACP server blocks the main loop during session/prompt — cancel is unreachable
**File:** `acp_server.py` lines 327–422, 448–483

`handle_session_prompt` runs `run_turn()` inline (not as a background
task). The main loop (`run`) awaits `handle_session_prompt`, so no
further stdin messages are read while the turn is in progress. This
means `session/cancel` and `session/close` messages sent during a
long-running turn are queued in stdin but never processed until the
turn completes.

The `session.cancelled` flag (checked at line 384) only works between
events — it cannot interrupt a long LLM call or tool execution.

Additionally, `SessionState.active_turn` is declared (line 239) and
checked in `handle_session_cancel` (line 431) and `handle_session_close`
(line 440), but is **never assigned** in `handle_session_prompt`. So
`session.active_turn.cancel()` is always a no-op (None check fails).

**Fix:** Run `run_turn()` as a background `asyncio.Task`, assign it to
`session.active_turn`, and process stdin messages concurrently so
`session/cancel` can be handled while the turn is running.

#### W-3: ACP server does not update session message history
**File:** `acp_server.py` lines 361–366

`handle_session_prompt` prepends `session.messages` to the new messages
(line 366: `messages = session.messages + messages`), but after the turn
completes, `session.messages` is **never updated** with the new user
message or the assistant's response. Subsequent prompts in the same
session will not see the conversation history, breaking session memory
support.

**Fix:** After the turn completes, append the user message and assistant
response to `session.messages`.

#### W-4: ACP server elicitation/permission requests are fire-and-forget
**File:** `acp_server.py` lines 388–398

When the turn loop emits `elicitation.requested` or
`permission.requested`, the ACP server sends the JSON-RPC request to the
client but **never waits for the response**. The `continue` statement
skips to the next event, and the turn loop proceeds without the user's
answer. The code comment acknowledges this ("In a full implementation,
we would wait for the client's response here").

This means elicitation questions are asked but answers are ignored, and
permission requests are sent but approvals are never received. The turn
loop's side-channel handling may paper over this in some cases, but the
client's response is lost.

**Fix:** After sending the request, await the client's response (read
from stdin) and feed it back into the turn loop via the emitter's
side-channel buffer.

#### W-5: In-process adapter _pending_approvals is never consumed
**File:** `backend_adapter.py` line 352

`submit_approval` stores approvals in `self._pending_approvals` (line
352), but this dict is **never read** by the turn loop or any other
method. The turn loop has no mechanism to receive approval responses
from the adapter. This means the in-process adapter can record approval
decisions but cannot actually resume an interrupted turn based on them.

**Fix:** Add a mechanism for the turn loop to poll or await pending
approvals (e.g., via the emitter's side-channel buffer or an asyncio
Event).

#### W-6: Event stream non-equivalence — artifact.created and citation.recorded dropped by ACP server
**File:** `acp_server.py` lines 84–174

`map_run_event_to_acp_update` returns `None` for `artifact.created` and
`citation.recorded` events. The comment (line 171–173) says these are
"handled separately or are internal-only," but they are **not handled
separately** — they are silently dropped.

This means the ACP entry point's event stream is missing two event types
that the in-process entry point emits:
- `artifact.created` — the ACP client will never produce artifact events,
  so the Gateway's artifact collection won't work for ACP-driven runs.
- `citation.recorded` — citation audit events are lost in the ACP path.

**Fix:** Add ACP update mappings for `artifact.created` (e.g., a custom
update type or an `artifact` update) and `citation.recorded` (e.g., a
`citation` update), or document that these are intentionally internal
and handle them via a separate sideband mechanism.

#### W-7: System prompt divergence between entry points
**File:** `backend_adapter.py` lines 404–426 vs `acp_server.py` lines 354–364

The in-process adapter's `_build_messages` uses a hardcoded 2-line
Chinese system prompt (lines 416–419) that does not use the Phase 102
`build_system_prompt` function. The ACP server uses
`build_system_prompt` with `AgentMode.CHAT` (lines 354–360).

This means the two entry points produce **different system prompts** for
the same input, violating the architectural equality principle. The
in-process adapter does not benefit from skill-aware prompt assembly,
research-gate content, or guardrail instructions.

**Fix:** Use `build_system_prompt` in `_build_messages` (or accept
pre-built messages via RunRequest metadata, as the docstring suggests).

#### W-8: ACP server does not pass tool_executor to run_turn
**File:** `acp_server.py` lines 375–383

The ACP server's `run_turn` call omits the `tool_executor` parameter,
while the in-process adapter passes it from config (line 229). This
means the ACP server cannot execute real tools — it falls back to the
fixture tool result behavior. The two entry points are not functionally
equivalent for tool-call turns.

**Fix:** Accept an optional `tool_executor_factory` in `ACPServer.__init__`
and pass the executor to `run_turn`.

### Info

#### I-1: Dead code — _DANGEROUS_PERMISSION_KINDS in acp_server.py
**File:** `acp_server.py` lines 74–76

The constant `_DANGEROUS_PERMISSION_KINDS` is defined but never
referenced anywhere in `acp_server.py`. The ACP server's safety approach
is to never set `auto_approve` for *any* permission (not just dangerous
ones), which is actually safer. The unused constant should be removed
or used for an explicit assertion/log.

#### I-2: shutdown() does not await cancelled tasks
**File:** `backend_adapter.py` lines 383–393

`shutdown` calls `task.cancel()` on all background tasks but does not
`await` them before clearing the dicts. This can produce "Task was
destroyed but it is pending" warnings and may leave resources
uncleaned. The ACP adapter has the same pattern but mitigates it by
closing client transports.

**Fix:** `await asyncio.gather(*tasks, return_exceptions=True)` before
clearing.

#### I-3: No queue overflow protection in in-process adapter
**File:** `backend_adapter.py` line 219

`asyncio.Queue()` has no `maxsize`, so if `stream_events` is never
called or is called slowly, events accumulate unboundedly. For very
long runs with many events, this could consume significant memory.
Consider `asyncio.Queue(maxsize=N)` with backpressure, or document
that consumers must drain promptly.

#### I-4: No explicit validation for backend_selection fields
**File:** `validate.py` (no backend_selection check)

`validate_document` does not explicitly validate `backend_selection`
fields (e.g., non-empty `default_backend_id`, non-empty override
keys/values). The generic `_walk_value` scan catches secret markers and
Hermes paths, but structural validation (e.g., rejecting
`default_backend_id=""`) is missing. Low risk since the resolver has a
hard default of `"inkstatute"`.

#### I-5: ACP server phase parameter hardcoded
**File:** `acp_server.py` line 382

The ACP server passes `phase="research"` to `run_turn`, while the
in-process adapter relies on the default (`"research"`). Both are
consistent, but the ACP server could make the phase configurable via
session metadata or prompt params.

#### I-6: _default_document function is unused
**File:** `backend_selection.py` lines 61–62

The function `_default_document()` is defined but never called.
`load_backend_selection` returns `None` when the store is missing, and
`resolve_backend_id` handles `None` by returning the hard default.
The unused function should be removed.

## File-by-File Analysis

### backend_adapter.py

**9-method BackendAdapter Protocol implementation over `run_turn()`.**

**Security:** Permission safety is correctly implemented. The
`_DANGEROUS_PERMISSION_KINDS` frozenset matches the ACP adapter exactly.
`submit_approval` rejects `terminal` and `execute_code` auto-approvals
by setting the run to `WAITING_FOR_USER` with an `approval_rejected`
metadata key (lines 334–349). The pattern is identical to
`ACPBackendAdapter.submit_approval`.

**Capabilities:** Declares `stream_event_support`, `cancel_support`,
`approval_support`, `session_memory_support` only — no `fs/*` or
`terminal/*`. Correct per AGENTS.md.

**Event buffering:** Uses `asyncio.Queue` per run — a good design for
real-time streaming. The `_STREAM_DONE` sentinel pattern is clean but
has the cancellation race condition (W-1). The `_collect_artifact`
method handles `Artifact` dataclass, dict, and generic object forms —
thorough.

**Architectural equality:** Follows the same BackendAdapter contract as
`ACPBackendAdapter` (same 9 methods, same permission safety, same
capability set shape). The `_SystemClock` is duplicated from the ACP
adapter — a minor DRY issue but acceptable for protocol compliance.
The hardcoded system prompt (W-7) is the main inequality.

**Naming/structure:** Clean, well-documented, consistent with the ACP
adapter's style. Method numbering (1–9) mirrors the Protocol definition.

### backend_config.py

**Frozen dataclass config for the in-process adapter.**

Clean and minimal. The `provider_factory` default (`_raise_no_provider`)
is a good fail-loud sentinel. The `tool_executor_factory` is optional
and correctly typed. The `backend_id` default of `"inkstatute"` matches
the operator-config hard default.

No issues found.

### acp_server.py

**ACP v1 server over stdio — the second entry point.**

**Security:** `AGENT_CAPABILITIES` declares only `streaming`,
`elicitation`, `permissions` — no `fs/*` or `terminal/*`. The
`map_run_event_to_acp_request` function for `permission.requested` does
not set `auto_approve` or `default_decision` for any permission kind.
Tests verify this for both `terminal` and `execute_code`.

**Reverse event mapping:** `map_run_event_to_acp_update` covers 9 event
types (message.delta, message.completed, thought.delta, tool_call
started/delta/completed, plan.updated, phase.changed, error). Missing:
`artifact.created` and `citation.recorded` (W-6). The `run.state_changed`
and `session.started` are correctly filtered as internal.

**Request mapping:** `map_run_event_to_acp_request` handles
`elicitation.requested` and `permission.requested` correctly, producing
full JSON-RPC request dicts with unique IDs.

**Server design:** The main loop uses `asyncio.to_thread` for blocking
stdin reads — good for keeping the event loop responsive. However,
`handle_session_prompt` blocks the loop (W-2), making cancel unreachable
during turns. `SessionState.active_turn` is never set (W-2).

**Provider factory:** `default_provider_factory` reads env vars for
OpenAI/Anthropic/Ollama — no secrets committed. API keys are read from
env, not stored. The `run_check` function is a clean bootstrap check
matching the `hermes acp --check` pattern.

**Dead code:** `_DANGEROUS_PERMISSION_KINDS` is defined but unused (I-1).

### __main__.py

**CLI entry point with argparse.**

Clean and minimal. The `--version` flag, `acp` subcommand, and `--check`
flag are well-structured. The `main` function returns exit codes
correctly. No issues found.

### pyproject.toml (modified)

**Console script entry point added.**

`inkstatute-agent = "inkstatute_agent_core.__main__:main"` — correct
setuptools console script declaration. `dependencies = []` is
intentional (dependencies are managed via PYTHONPATH in the monorepo).
No issues found.

### backend_selection.py

**Per-tenant backend routing resolver.**

Clean, well-documented. The resolution order (None → hard default,
tenant override → mapped value, else → default) is correct and
well-tested. The `_LoadableStore` Protocol is a good duck-typing
approach. The `load_backend_selection` function handles missing stores
and exceptions gracefully (returns `None`).

Minor: `_default_document()` is unused (I-6).

### schemas.py (modified)

**BackendSelectionDoc added to operator config schemas.**

Frozen, slots-based dataclass — consistent with all other schemas in the
file. `default_backend_id="inkstatute"` matches the hard default in
`resolve_backend_id`. `backend_overrides` defaults to empty dict. Added
to `OperatorConfigDocument` as `backend_selection` field with
`default_factory=BackendSelectionDoc`. Added to `__all__`.

No issues found.

### store.py (modified)

**Backend selection parsing and serialization added.**

`document_from_payload` parses `backend_selection` from JSON using
`_str_dict` for `backend_overrides` (correctly typed as `dict[str,str]`).
The `default_backend_id` defaults to `"inkstatute"` when absent. The
parsing is fail-closed (raises `OperatorConfigStoreError` on bad shapes).
`document_to_payload` uses `asdict` which correctly serializes the
nested dataclass.

No issues found.

### __init__.py (modified)

**Public API exports for backend selection.**

`BackendSelectionDoc`, `load_backend_selection`, `resolve_backend_id`
are exported. Added to `__all__`. Imports are placed after existing
imports — consistent with the file's style.

No issues found.

## Test Quality Assessment

### test_backend_adapter.py (22 tests)
Comprehensive coverage of all 9 BackendAdapter methods. Uses
`FixtureProvider` with deterministic scripts — no external LLM calls.
Covers: backend_id, capabilities (including fs/terminal exclusion),
bootstrap check (success + failure), submit_run, get_run (including
KeyError), stream_events (message.delta, message.completed,
thought.delta, tool_call events, terminal state), cancel_run (including
KeyError), submit_approval (terminal rejected, execute_code rejected,
safe permission accepted), collect_artifacts (empty + populated),
monotonic seq. Good test quality.

**Gap:** The cancel test (test 14) does not trigger the W-1 race because
it cancels before the background task starts. A test that `await
asyncio.sleep(0)` between `submit_run` and `cancel_run` would expose the
bug.

### test_acp_server.py (25+ tests)
Thorough coverage of ACP protocol: initialize (protocol version,
agentInfo, capabilities, no fs/terminal), session/new, session/prompt
(chunk notifications, final message, empty result response),
session/cancel, session/close, unknown method, --check flag (success +
failure), reverse event mapping (all 9 types), elicitation/permission
request mapping, dangerous permission safety (no auto_approve), full
round-trip, ACPClient integration (subprocess), CLI entry point.

**Gap:** No test for multi-turn sessions (would expose W-3). No test for
cancel during a running turn (would expose W-2).

### test_entry_point_equivalence.py (10+ tests)
Compares event type sequences and content between in-process and ACP
entry points. Covers: message.delta/completed, thought.delta, tool_call
events, citation filtering, error events, run.state_changed. Uses a
local ACP update type mapping when acp-client is not on PYTHONPATH —
good defensive design.

**Gap:** The comparable subset is limited to `message.delta` and
`message.completed` (line 387–390). Thought.delta and tool_call
equivalence is tested separately but not in the sequence comparison.
Artifact.created and citation.recorded non-equivalence is documented but
not asserted as a known gap.

### test_backend_selection.py (14 tests)
Covers: BackendSelectionDoc defaults and frozenness, resolve_backend_id
(None, default, custom, tenant override, None/empty tenant),
load_backend_selection (None store, missing file, present file, defaults
when absent, round-trip), document_from_payload parsing. Good test
quality.

## Verdict

**Findings found.** No critical or security issues. One correctness bug
(W-1: cancellation sentinel race) that is masked by test timing but
would manifest in production. Seven warnings related to incomplete ACP
server functionality (blocking main loop, no session history,
fire-and-forget elicitation, unconsumed approvals, missing event
mappings, prompt divergence, no tool executor) and six info-level
suggestions.

**Security: PASS.** Permission safety and capability declaration are
correct in both entry points. No `fs/*` or `terminal/*` capabilities.
No auto-approval of dangerous permissions.

**Architectural equality: PARTIAL.** Both entry points share `run_turn()`
and implement the same 9-method BackendAdapter contract, but the ACP
server has incomplete functionality (elicitation, session memory, tools)
and the in-process adapter uses a different system prompt.

**Recommendation:** Fix W-1 before Phase 104. Address W-2 through W-8 as
part of Phase 104 convergence or a follow-up patch. The security-critical
requirements (CORE-10, SAFE-04, no fs/terminal capabilities) are met.
