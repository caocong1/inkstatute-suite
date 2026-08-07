---
phase: 90
slug: acp-event-bridge-output-boundary
status: draft
created: 2026-08-07
skip_discuss: true
---

# Phase 90 — ACP Event Bridge & Output Boundary

## Phase Goal

ACP 事件与统一事件之间双向无损映射，且输出边界与权限安全默认在这个桥上强制执行——后端噪声与危险权限请求不可能穿过

## Requirements

- **ACP-04**: ACP `session/update` ⟷ 统一事件双向映射（含 `tool_call_update` / `plan` / `elicitation` / `request_permission`），往返语义无损
- **ACP-05**: 输出边界在事件桥上强制执行——后端 meta / gateway / system / update / command / help / `available_commands_update` / `terminal` 类内容不得到达普通用户
- **ACP-07**: 权限请求安全默认——`terminal` / `execute_code` 类权限请求必须显式拒绝或上抛用户审批，服务端不得默认 allow
- **SAFE-02**: 契约日志 reference-first（`raw_payload_ref`），不存敏感全文；secrets 不入仓 / 不入日志 / 不入契约事件；ACP 子进程凭据经环境注入
- **SAFE-03**: 输出边界贯穿事件桥与 Gateway 两处，后端 meta / gateway / system 噪声不得到达普通律师用户

## Success Criteria

1. ACP `session/update` 的每个变体与统一事件双向映射，往返测试语义无损
2. ACP `elicitation/create` 与 `session/request_permission` 正确映射为 `elicitation.requested` / `permission.requested`，用户答复能正确回注到 ACP 侧
3. 输出边界在桥上强制执行：给定一组后端 meta / gateway / system / update / command / help / `available_commands_update` / `terminal` 类内容的 fixture，全部被阻断或改写为 InkStatute 业务化提示，无一到达普通用户事件流
4. 权限安全默认：`terminal` / `execute_code` 类权限请求被显式拒绝或上抛为用户审批，服务端不得默认 allow；有测试断言不存在自动 `allow_once` 路径
5. secrets 不出现在任何契约事件、日志或落库记录中；ACP 子进程凭据仅经环境注入；有隐私扫描测试
6. 契约日志保持 reference-first（`raw_payload_ref`），不存敏感全文

## Existing Infrastructure (from Phase 89 + V2)

### Forward Mapping (ACP → Unified) — COMPLETE
- `packages/acp-client/src/inkstatute_acp_client/event_mapping.py` (339 lines)
- Maps 15+ ACP notification variants to unified RunEventType values
- Already strips `auto_approve` and `default_decision` from permission requests
- Already handles `elicitation/create` and `session/request_permission` as separate methods

### Output Boundary — EXISTS in two places
- `packages/platform-runtime/src/platform_runtime/output_boundary.py` (218 lines) — runtime-level boundary with ALLOW/REWRITE/BLOCK actions, secret patterns, operator command blocking, artifact metadata filtering
- `packages/channel-core/src/channel_core/output_policy.py` (107 lines) — channel-level policy (second enforcement point)

### Permission Safety — EXISTS in adapter
- `packages/acp-client/src/inkstatute_acp_client/adapter.py` lines 111-114, 386-427
- `_DANGEROUS_PERMISSION_KINDS = frozenset({"terminal", "execute_code"})`
- `submit_approval` rejects approved decisions for dangerous kinds → `WAITING_FOR_USER`

### Reference-First Logging — EXISTS
- `raw_payload_ref` pattern in 5 contract types (AgentTurn, ChannelMessage, MemoryRecord, MemoryCandidate, ContextBundle)
- `_audit()` function in output_boundary.py stores hash prefix + length, not original text

## Key Decisions (Auto-Selected)

### 1. Package Location: New `packages/acp-event-bridge/`

[auto] Q: "Where should the ACP event bridge code live?" → Selected: "New package `packages/acp-event-bridge/`" (recommended default)

**Rationale:** The bridge is a separate concern from the ACP client (which handles transport and session lifecycle). The bridge handles event transformation and output boundary enforcement. Following the existing package-per-concern pattern (`platform-contract`, `platform-runtime`, `acp-client`, `channel-core`), a new package keeps the bridge testable and gates-covered independently.

### 2. Reverse Mapping: `map_unified_to_acp()` functions

[auto] Q: "How should reverse mapping (unified → ACP) be implemented?" → Selected: "Dedicated reverse mapping functions for user responses" (recommended default)

**Rationale:** The forward mapping (ACP → unified) is complete in `event_mapping.py`. The reverse mapping is needed for:
- Elicitation answers: unified `elicitation.response` → ACP `elicitation/answer` method
- Permission decisions: unified `permission.decision` → ACP `session/request_permission` response
- Run cancellation: unified `run.cancel` → ACP `session/cancel` method

The reverse mapping functions will be in the new `acp-event-bridge` package, not in `acp-client`, because they are bridge-level concerns (the client just sends/receives JSON-RPC; the bridge decides what to send).

### 3. Output Boundary: Extend existing + ACP-specific rules

[auto] Q: "Should the output boundary be a new implementation or extend existing?" → Selected: "Extend existing `output_boundary.py` with ACP-specific rules" (recommended default)

**Rationale:** `output_boundary.py` already has the ALLOW/REWRITE/BLOCK framework, secret patterns, operator command blocking, and artifact metadata filtering. Phase 90 adds ACP-specific blocked content categories:
- `meta` / `gateway` / `system` / `update` / `command` / `help` / `available_commands_update` / `terminal` type ACP notifications
- These are ACP backend noise that must never reach ordinary users

The bridge will call the existing `DefaultAssistantOutputBoundary.apply()` method and add ACP-specific pre-filtering for notification types that are pure backend noise.

### 4. V3 Events Only

[auto] Q: "Should the bridge handle V2 legacy event types?" → Selected: "V3 unified events only" (recommended default)

**Rationale:** The bridge sits between ACP (which speaks V3-isomorphic events) and the platform (which consumes V3 events). V2 legacy events are handled by the existing runtime and are not part of the ACP bridge. The bridge maps ACP ↔ V3 only.

### 5. Secrets Scanning: Reuse existing patterns

[auto] Q: "How should secrets scanning work in the bridge?" → Selected: "Reuse existing sanitization + add ACP-specific patterns" (recommended default)

**Rationale:** The existing `_audit()` function and sanitization patterns in `output_boundary.py` already handle:
- Secret-like patterns (access_token, api_key, secret, token=)
- Internal paths (/home/..., C:\...)
- Provider leaks (model:, provider:, api key invalid)

Phase 90 adds:
- ACP subprocess credential patterns (HERMES_HOME paths, env vars with secrets)
- Reference-first enforcement: all bridge events use `raw_payload_ref` instead of full text
- Privacy scan test: scan all bridge output events for secret patterns

### 6. Permission Safety: Bridge-level enforcement + existing adapter-level

[auto] Q: "Where should permission safety be enforced?" → Selected: "Both adapter (existing) and bridge (new)" (recommended default)

**Rationale:** AGENTS.md requires "Permission requests must never be auto-approved server-side." The existing adapter-level enforcement (in `submit_approval`) rejects dangerous permissions. The bridge adds a second layer:
- Filter `permission.requested` events to ensure they are forwarded to the user (not auto-answered)
- Assert no `allow_once` or `auto_approve` field exists in any permission event
- Test that the bridge never generates an auto-approval response

## Key Files

### New Package to Create
- `packages/acp-event-bridge/` — New Python package
  - `src/inkstatute_acp_event_bridge/` — Main source
    - `bridge.py` — EventBridge class: forward + reverse mapping, output boundary integration
    - `reverse_mapping.py` — `map_unified_to_acp()` functions for user responses
    - `output_filter.py` — ACP-specific output boundary rules (blocked notification types)
    - `privacy_scan.py` — Secrets scanning for bridge output events
  - `tests/` — Test suite
    - `test_bridge.py` — Bidirectional mapping tests
    - `test_output_filter.py` — Output boundary enforcement tests
    - `test_privacy_scan.py` — Secrets scanning tests
    - `fixtures/` — Backend noise fixtures (meta, gateway, system, etc.)
  - `pyproject.toml` — Package configuration

### Existing Files to Reference
- `packages/acp-client/src/inkstatute_acp_client/event_mapping.py` — Forward mapping (ACP → unified)
- `packages/platform-runtime/src/platform_runtime/output_boundary.py` — Existing output boundary
- `packages/channel-core/src/channel_core/output_policy.py` — Channel-level output policy
- `packages/acp-client/src/inkstatute_acp_client/adapter.py` — Permission safety in submit_approval
- `packages/platform-contract/src/platform_contract/enums.py` — RunEventType enum (23 members)
- `packages/platform-contract/src/platform_contract/unified_events.py` — Unified event dataclasses
- `scripts/run_v2_gates.py` — Gate registration pattern (need to add acp-event-bridge gate)

## Patterns Established

- **Bridge pattern:** The event bridge sits between the ACP client and the platform runtime, transforming events in both directions
- **Double enforcement:** Output boundary is enforced at the bridge (first pass) and at the channel (second pass) — matching AGENTS.md's "enforced twice" requirement
- **Reference-first logging:** All bridge events store `raw_payload_ref` (hash + length), never full text
- **Permission safety double-layer:** Adapter rejects dangerous approvals + bridge ensures permission events are forwarded (not auto-answered)
