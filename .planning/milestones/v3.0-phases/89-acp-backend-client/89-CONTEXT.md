---
phase: 89
slug: acp-backend-client
status: draft
created: 2026-08-07
skip_discuss: true
---

# Phase 89 — ACP Backend Client

## Phase Goal

平台能以 Python ACP client 驱动任意 ACP agent 作为后端，`hermes acp` 生产可用，并有第二个 ACP 后端跑通同一契约以证明可替换性；子进程生命周期受控

## Requirements

- **ACP-01**: Python ACP client (stdio, lock protocol v1, `initialize` version/capability negotiation), implement BackendAdapter 9-method Protocol
- **ACP-02**: `hermes acp` backend usable, with capability detection and Hermes version compatibility matrix; replaces `packages/backends/hermes` custom HTTP runs API
- **ACP-03**: At least one additional ACP backend (`codex-acp` or `claude-agent-acp`) passes the same contract, proving backend replaceability
- **ACP-06**: ACP session and subprocess lifecycle management (new/resume/cancel/close, timeout recovery, crash restart), contract reserves `backend_process_mode` (per_session/pooled/remote)

## Success Criteria

1. `packages/acp-client` implements BackendAdapter's 9-method Protocol, based on PyPI `agent-client-protocol`, locks protocol v1 and negotiates version+capability at `initialize`; agents lacking required capabilities are explicitly rejected, not silently degraded
2. `backend_id="hermes"` works via `hermes acp`: can create session, send prompt, receive streaming `session/update`, cancel, close; includes Hermes version compatibility matrix and `bootstrap_check`
3. A second ACP backend (`codex-acp` or `claude-agent-acp`) passes the same test path, proving swapping `backend_id` requires no caller code changes
4. Subprocess lifecycle controlled: session-end recovery, timeout recovery, crash restart, no process leaks; tests assert no orphan processes
5. Contract exposes `backend_process_mode` (per_session/pooled/remote), currently implements `per_session`, other enum values exist but unimplemented and explicitly marked
6. In no-network/no-external-agent CI environment, use fixture ACP agent (in-repo echo agent) to run all tests

## Key Files

### New Package to Create
- `packages/acp-client/` — New Python package for ACP client implementation
  - `src/inkstatute_acp_client/` — Main source directory
  - `tests/` — Test suite
  - `pyproject.toml` — Package configuration with `agent-client-protocol` dependency

### Existing Files to Reference
- `packages/platform-runtime/src/platform_runtime/protocols.py` (lines 222-240) — BackendAdapter Protocol definition (9 methods)
- `packages/backends/hermes/src/inkstatute_backends_hermes/adapter.py` (423 lines) — Current Hermes backend implementation pattern
- `packages/backends/codex/src/inkstatute_backends_codex/adapter.py` (413 lines) — Codex backend implementation pattern
- `packages/backends/codex/src/inkstatute_backends_codex/exec_runner.py` (455 lines) — Subprocess-based runner pattern
- `packages/platform-contract/src/platform_contract/unified_events.py` (289 lines) — Phase 88 unified event vocabulary
- `packages/platform-contract/src/platform_contract/agent_adapter.py` (139 lines) — AdapterCapabilitySet structure
- `scripts/run_v2_gates.py` (278 lines) — Gate registration pattern (need to add acp-client gate)

## BackendAdapter Protocol (9 methods)

```python
class BackendAdapter(Protocol):
    def backend_id(self) -> str: ...
    def capabilities(self) -> AdapterCapabilitySet: ...
    async def bootstrap_check(self) -> BootstrapStatus: ...
    async def submit_run(self, req: RunRequest) -> RunHandle: ...
    async def get_run(self, run_id: str) -> Run: ...
    async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]: ...
    async def cancel_run(self, run_id: str) -> Run: ...
    async def submit_approval(self, run_id: str, approval: Approval) -> Run: ...
    async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]: ...
```

## Technical Approach

1. **Package Structure:** Create `packages/acp-client` with PyPI `agent-client-protocol` dependency
2. **Protocol Implementation:** Implement BackendAdapter's 9 methods using ACP stdio transport
3. **Version Negotiation:** Use ACP `initialize` to lock protocol v1 and negotiate capabilities
4. **Subprocess Lifecycle:** Implement per-session subprocess spawning with HERMES_HOME environment variable
5. **Capability Detection:** Map ACP capabilities to AdapterCapabilitySet
6. **Hermes Integration:** Support `hermes acp` command with version compatibility matrix
7. **Second Backend:** Support `codex-acp` or `claude-agent-acp` to prove replaceability
8. **Fixture Agent:** Create in-repo echo agent for CI testing without external dependencies

## User Decisions (Derived from ROADMAP/PRD/AGENTS.md)

- **ACP v1 Lock:** Lock protocol v1 at `initialize`, v2 features flagged off. Rationale: v2 is draft with breaking changes.
- **Backend Process Mode:** Implement `per_session` only; expose enum values `pooled`/`remote` but mark as unimplemented. Rationale: Single-firm scale (≤50 lawyers).
- **Second Backend:** Use `codex-acp` or `claude-agent-acp` (both verified available). Rationale: Prove backend replaceability.
- **Fixture Agent:** Create in-repo echo agent for CI. Rationale: Success criterion #6 requires CI compatibility.
- **Hermes Version Compatibility:** Build version compatibility matrix. Rationale: Success criterion #2.

## Risks and Pitfalls

1. **ACP SDK Version:** PyPI has 0.12.0 — verify compatibility before Phase 90
2. **Hermes Profile Loading:** `active_profile` sticky file not respected by ACP subprocess — must explicitly set `HERMES_HOME`
3. **Elicitation Stability:** ACP elicitation is UNSTABLE — requires `use_unstable_protocol=True` with `_meta` fallback
4. **Subprocess Leaks:** Must implement proper cleanup (session-end, timeout, crash recovery) with orphan process detection tests
5. **Permission Safety:** Must explicitly reject `terminal`/`execute_code` permissions (Buzz auto-allow failure reference)
6. **Gate Registration:** Manual gate registration required — add to `scripts/run_v2_gates.py` _gates() function

## Binding Constraints from AGENTS.md

1. Backend seam is ACP v1 — lock protocol v1, negotiate at `initialize`
2. The self-built core is the default backend but has no architectural privilege
3. `backend_process_mode` (`per_session`/`pooled`/`remote`) — implement only `per_session`
4. Permission requests must never be auto-approved server-side
5. Contract logs prefer references such as `raw_payload_ref`
6. Every `packages/*/src` directory must be covered by a gate
7. Run `python scripts/run_v2_gates.py` before claiming phase complete
