---
phase: 104
slug: legacy-convergence
status: planning
created: 2026-08-08
---

# Phase 104: Legacy Convergence — Research

## Goal

V3 承诺的存量收敛全部执行到位，仓库不再携带被取代的重复实现，且质量体系完整覆盖新结构。

## Requirements

- CONV-01: 退役 `packages/backends/hermes` (1,843 行) 与 `packages/backends/codex` (2,032 行)
- CONV-02: 退役 `packages/channels/web_sse` (259 行) 与 `apps/web_chat`
- CONV-03: 归并 `services/lawyer-web-chat` (1,331 行) 进 Gateway；缩减 `services/hermes-contract-layer` (1,205 行)
- CONV-04: 冻结 `packages/multi-agent-adapter` (标记 experimental，保留代码与测试)
- CONV-05: gate 体系更新（新增包有 gate，退役包 gate 移除，gate-coverage meta-test 断言全覆盖）
- SAFE-06: 可组合性保持 + WeCom/QQ 回归测试全绿

## Success Criteria

1. `packages/backends/hermes` 与 `packages/backends/codex` 已退役；兼容矩阵与 bootstrap_check 逻辑存在于 ACP adapter 中
2. `packages/channels/web_sse` 与 `apps/web_chat` 已退役
3. `services/lawyer-web-chat` 已归并进 Gateway 并移除；`services/hermes-contract-layer` 已缩减为 Hermes 专属配置
4. `packages/multi-agent-adapter` 标记 experimental 冻结
5. gate 体系更新：新增包有 gate，退役包 gate 移除，gate-coverage meta-test 全覆盖
6. 可组合性保持：`solutions/demo_non_legal` 跑通，无法律字段泄漏
7. 全量 gate 运行通过，WeCom/QQ 回归测试全绿

## Legacy Packages to Retire

| Package | Lines | Status | Action |
|---------|-------|--------|--------|
| `packages/backends/hermes` | ~35K chars | Replaced by `acp-client` | DELETE |
| `packages/backends/codex` | ~36K chars | Replaced by `acp-client` | DELETE |
| `packages/channels/web_sse` | ~13K chars | Replaced by `services/gateway` | DELETE |
| `services/lawyer-web-chat` | ~45K chars | Replaced by `services/gateway` | DELETE |
| `services/hermes-contract-layer` | ~42K chars | Replaced by `acp-client` | DELETE |
| `packages/multi-agent-adapter` | ~36K chars | Experimental | FREEZE (keep code, add README) |

Note: `apps/web_chat` does not exist (there is `apps/web` instead).

## External References to Legacy Packages

Files outside legacy packages that import from them:
- `services/gateway/tests/test_integration.py` — 8 matches (imports from backends.hermes etc.)
- `packages/contract-test-suite/src/contract_test_suite/boundary_checks.py` — 2 matches
- `packages/contract-test-suite/tests/test_phase55_wecom_service_loop.py` — 1 match
- `packages/contract-test-suite/tests/test_phase5_wecom_loop.py` — 1 match
- `packages/platform-runtime/src/platform_runtime/feature_flags.py` — 1 match
- `services/admin-console-api/tests/test_contract_freeze.py` — 1 match
- `scripts/audit_v2_requirements.py` — 2 matches

These references need to be updated or the tests need to be archived before deletion.

## Gate System

### Current gates: 38 (including meta-gates)
### Gates to remove (4):
1. `hermes-contract-layer` gate
2. `codex-backend` gate
3. `lawyer-web-chat` gate
4. `web-sse-channel` gate

### New packages that already have gates:
- ✅ `acp-client` — has gate
- ✅ `skill-index` — has gate
- ✅ `agent-core` — has gate
- ✅ `ui-core` — has gate
- ✅ `gateway` — has gate

### compileall gate update:
Remove retired package paths from the compileall gate's path list.

## ACP Adapter Compatibility

The `ACPBackendAdapter` in `packages/acp-client/` has:
- `HERMES_COMPATIBILITY_MATRIX` (0.17.0, 0.18.0, 0.19.0)
- `bootstrap_check()` with version + capability checking
- `_check_version_compatibility()` function
- `capability_negotiation.py` for capability matching

**No capabilities are lost** — the ACP adapter is a superset of the legacy backend adapters.

## Composability Tests

Location: `solutions/demo_non_legal/tests/test_demo_non_legal_solution.py`
- 9 tests verifying industry neutrality, no legal field leakage, manifest validation
- Status: ✅ comprehensive

## WeCom/QQ Regression Tests

- WeCom: `services/wecom-service/tests/test_cross_channel_consistency.py`
- QQ: `services/qqbot-service/tests/test_cross_channel_consistency.py`
- Both verify cross-channel consistency (same messages, cards, files, citations)
- Status: ✅ comprehensive

## Risk Assessment

- LOW RISK: All new packages have gates, ACP adapter has full parity
- CAUTION: Must update external references before deletion
- CAUTION: Multi-agent-adapter should be frozen, not deleted
- CAUTION: Must run full gate suite after removal

## Plan Structure

### Plan 104-01: Retire legacy backends (hermes + codex)
- Delete `packages/backends/hermes/` and `packages/backends/codex/`
- Remove `codex-backend` gate
- Update external references (gateway tests, contract-test-suite, feature_flags)
- Verify ACP adapter has all capabilities
- Tests: verify no broken imports, gates pass

### Plan 104-02: Retire legacy channels + services
- Delete `packages/channels/web_sse/`
- Delete `services/lawyer-web-chat/`
- Delete `services/hermes-contract-layer/` (or reduce to config-only)
- Remove `web-sse-channel`, `lawyer-web-chat`, `hermes-contract-layer` gates
- Update external references
- Tests: verify no broken imports, gates pass

### Plan 104-03: Freeze multi-agent-adapter + gate system update
- Add FROZEN.md to `packages/multi-agent-adapter/`
- Update `scripts/run_v2_gates.py`: remove retired gates, update compileall paths
- Verify gate-coverage meta-test passes
- Tests: full gate suite green

### Plan 104-04: Composability + regression + phase completion
- Run composability tests (`solutions/demo_non_legal`)
- Run WeCom/QQ regression tests
- Run full gate suite
- Success criteria mapping tests
- Phase completion
