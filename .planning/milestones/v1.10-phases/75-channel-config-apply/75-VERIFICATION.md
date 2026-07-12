---
phase: 75-channel-config-apply
verified: 2026-07-10T08:36:46Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
re_verification: false
deferred:
  - truth: "Complete CSRF-protected SSR surface verification for channel (and other) config forms"
    addressed_in: "Phase 78"
    evidence: "Phase 78 success criteria: 'Admin Web UI exposes config pages for channels, providers/catalog, and vision as SSR forms with CSRF protection'; Phase 75 README/UI-SPEC honesty documents incremental csrf_token field only"
---

# Phase 75: Channel Config Apply Verification Report

**Phase Goal:** Operators can configure QQ and WeCom channel enablement and credential refs with dual-knob effective state visible, without collapsing safety knobs or echoing resolved secrets

**Verified:** 2026-07-10T08:36:46Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Operator can configure QQBot channel settings (enable knobs, credential refs, callback-related refs) via admin config API and SSR form | ✓ VERIFIED | PUT `/config/channels` persists `channels.qqbot` host `enabled` + `*_ref` fields via `handle_config_put` → `OperatorConfigStore`; SSR `parse_channels_form` + POST `/config/channels` → `proxy_put` → `handle_admin_put`; `test_config_api` / `test_channels_form` green |
| 2 | Operator can configure WeCom channel settings (enable knobs, credential refs) via admin config API and SSR form | ✓ VERIFIED | Same channels section carries `channels.wecom`; WeCom panel + ref fields in `channels.py`; `WeComChannelConfig.from_operator_doc` + store load helpers present; form/API tests cover wecom section |
| 3 | Dual-knob effective enablement visible (platform AND host) for QQ and WeCom — no single bypass toggle | ✓ VERIFIED | `_channels_effective` returns `platform_flag`/`host_enabled`/`effective_enabled` from `qqbot_channel_enabled`/`wecom_channel_enabled` AND `data.*.enabled` without collapsing host enabled; SSR renders three rows + legend; matrix tests in `test_config_channels_effective` + `test_channels_form` |
| 4 | Credential fields accept secret refs only (`env:…` / `secret://…`); GET never echoes resolved secrets | ✓ VERIFIED | `normalize_config_secret_ref` + `validate_document` reject raw/planted values; GET/PUT return refs-only via `document_to_payload`; planted-secret tests assert 400 and absence from `data`/`effective`/`metadata` JSON |
| 5 | `RuntimeFeatureFlags.wecom_channel_enabled` defaults False; admin contract freeze exact-set includes it | ✓ VERIFIED | `feature_flags.py` field default False; `test_feature_flags` + `test_contract_freeze` OK; WeCom platform label uses `wecom_channel_enabled` (not `channel_delivery_enabled`) |
| 6 | Channels responses include `metadata.apply_semantics=restart_required`; PUT never accepts/writes platform flags | ✓ VERIFIED | `_config_metadata(section="channels")` sets `apply_semantics`; platform flags read only from `RuntimeFeatureFlags` in `_channels_effective`; channel docs have no platform-flag fields; non-channels omit effective/apply_semantics |
| 7 | QQ store-wins-if-exists host load; dual-knob AND unchanged; materialize does not resolve secrets | ✓ VERIFIED | `load_qqbot_host_config` uses `store.path.exists()` → `from_operator_doc` else `from_env`; `build_qqbot_wired_runtime` calls load when `host_config` omitted then `build_qqbot_channel_config` AND; `test_store_apply` proves no `resolve_secret_ref` during materialize |
| 8 | WeCom `from_operator_doc` + `channel_wiring` dual-knob AND with store-wins load | ✓ VERIFIED | Channel package materializer flag-free; `build_wecom_channel_config` / `load_wecom_channel_config` AND `wecom_channel_enabled` with host doc; exported from `wecom_service`; dual-knob + store/env tests green |

**Score:** 8/8 truths verified

### Deferred Items

Items not yet met but explicitly addressed in later milestone phases.

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | Complete CSRF-protected SSR surface verification | Phase 78 | Phase 78 SC#1 CSRF-protected SSR; Phase 75 ships hidden `csrf_token` + README honesty only |

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `packages/platform-runtime/.../feature_flags.py` | `wecom_channel_enabled` default OFF | ✓ VERIFIED | Exists; field next to `qqbot_channel_enabled` |
| `services/admin-console-api/tests/test_contract_freeze.py` | Freeze includes `wecom_channel_enabled` | ✓ VERIFIED | Exact-set allowlist updated; tests OK |
| `scripts/run_v2_gates.py` | `operator_config_src` on qqbot/wecom gates | ✓ VERIFIED | Present on qqbot-service + wecom-service PYTHONPATH tuples |
| `services/admin-console-api/.../config_api.py` | effective + apply_semantics | ✓ VERIFIED | `_channels_effective` + restart_required metadata |
| `services/admin-console-api/tests/test_config_channels_effective.py` | CHAN-03 matrix + no-echo | ✓ VERIFIED | 251 lines; 5 tests OK |
| `services/qqbot-service/.../config.py` | `load_qqbot_host_config` store-wins | ✓ VERIFIED | Substantive; wired into compose |
| `services/qqbot-service/.../wiring.py` | `config_store` → dual-knob | ✓ VERIFIED | Calls load + `build_qqbot_channel_config` |
| `services/qqbot-service/tests/test_store_apply.py` | Store/env/dual-knob proofs | ✓ VERIFIED | 209 lines; 7 tests OK |
| `packages/channels/wecom/.../config.py` | `from_operator_doc` | ✓ VERIFIED | Flag-free materializer |
| `services/wecom-service/.../channel_wiring.py` | dual-knob build/load | ✓ VERIFIED | 77 lines; exported from package |
| `services/wecom-service/tests/test_channel_wiring_dual_knob.py` | AND matrix + store load | ✓ VERIFIED | 153 lines; 5 tests OK |
| `services/admin-web-ui/.../channels.py` | SSR dual-knob form | ✓ VERIFIED | 439 lines; render + parse |
| `services/admin-web-ui/.../server.py` | GET+POST `/config/channels` | ✓ VERIFIED | Route + POST proxy |
| `services/admin-web-ui/.../api_client.py` | `proxy_put` | ✓ VERIFIED | Injects Authorization like GET |
| `services/admin-web-ui/tests/test_channels_form.py` | SSR + POST proofs | ✓ VERIFIED | 473 lines; 12 tests OK |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `feature_flags.py` | `test_contract_freeze.py` | exact-set field names | ✓ WIRED | `wecom_channel_enabled` in both |
| `run_v2_gates.py` | `packages/operator-config/src` | qqbot/wecom gate PYTHONPATH | ✓ WIRED | `operator_config_src` on both service gates |
| `config_api.py` | `feature_flags.py` | effective platform flags | ✓ WIRED | Reads `qqbot_channel_enabled` / `wecom_channel_enabled` |
| `handle_config_get/put` | `document_to_payload` | refs-only data + separate effective | ✓ WIRED | Manual (gsd-tools `from` is not a path); payload for `data`, `_channels_effective` additive |
| `load_qqbot_host_config` | `store.path.exists` | store wins else from_env | ✓ WIRED | Manual; `config.py` lines 107–114 |
| `build_qqbot_wired_runtime` | `build_qqbot_channel_config` | host load then AND | ✓ WIRED | Manual; wiring compose path |
| `channel_wiring.py` | `feature_flags.py` | `wecom_channel_enabled` AND doc.enabled | ✓ WIRED | Pattern in source |
| `load_wecom_channel_config` | `store.path.exists` | store wins else from_env | ✓ WIRED | Manual; `channel_wiring.py` 58–72 |
| `server.py` | `handle_admin_put` | `proxy_put` on POST channels | ✓ WIRED | Pattern in server + api_client |
| `channels.py` render | effective API block | platform/host/effective display | ✓ WIRED | Manual; reads `platform_flag` / `host_enabled` / `effective_enabled` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `config_api` channels GET/PUT | `body["data"]` / `body["effective"]` | `OperatorConfigStore.load` + `RuntimeFeatureFlags` | Yes — store document + live flags | ✓ FLOWING |
| `channels.py` SSR panels | platform/host/effective + refs | GET `/config/channels` JSON (`effective` + `data`) | Yes — proxied admin GET; tests use real handlers | ✓ FLOWING |
| `load_qqbot_host_config` | `QQBotHostConfig` refs/enabled | store doc or env | Yes — store fixture tests prove store-wins | ✓ FLOWING |
| `load_wecom_channel_config` | `WeComChannelConfig` | store doc or env + flags | Yes — dual-knob tests; helper exported (thin apply; not yet called from WeCom HTTP entry — in-scope per plan) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Feature flags incl. WeCom knob | `python -m unittest ...test_feature_flags -q` | 17 tests OK | ✓ PASS |
| Contract freeze allowlist | `...test_contract_freeze -q` | 7 tests OK | ✓ PASS |
| Channels effective + secrets | `...test_config_channels_effective -q` | 5 tests OK | ✓ PASS |
| QQ store apply | `...test_store_apply -q` | 7 tests OK | ✓ PASS |
| WeCom from_operator_doc | `...test_from_operator_doc -q` | 3 tests OK | ✓ PASS |
| WeCom dual-knob wiring | `...test_channel_wiring_dual_knob -q` | 5 tests OK | ✓ PASS |
| SSR channels form | `...test_channels_form -q` | 12 tests OK | ✓ PASS |

### Probe Execution

| Probe | Command | Result | Status |
| ----- | ------- | ------ | ------ |
| — | — | No phase-declared or conventional probes for this phase | SKIP |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| CHAN-01 | 75-02, 75-03, 75-05 | Configure QQBot via API/UI | ✓ SATISFIED | API PUT + SSR form + store→host load |
| CHAN-02 | 75-02, 75-04, 75-05 | Configure WeCom via API/UI | ✓ SATISFIED | API PUT + SSR form + from_operator_doc/wiring |
| CHAN-03 | 75-01, 75-02, 75-03, 75-04, 75-05 | Dual-knob effective visibility | ✓ SATISFIED | `wecom_channel_enabled` + effective block + SSR three-row UI + host AND helpers |
| CHAN-04 | 75-02, 75-05 | Refs-only; no secret echo | ✓ SATISFIED | validator + planted-secret tests + ref-only inputs |

No orphaned requirements: REQUIREMENTS.md maps CHAN-01..04 only to Phase 75; all appear in plan frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `services/wecom-service/.../channel_wiring.py` | — | Helper exported/tested but not invoked from WeCom HTTP/main entry | ℹ️ Info | Plan scoped thin apply helper only; restart-to-apply documented; not a goal blocker |
| `services/admin-web-ui/.../channels.py` / `server.py` | csrf_token | Hidden field without server-side CSRF validation | ℹ️ Info | Explicitly deferred to Phase 78 with README honesty |

No `TBD`/`FIXME`/`XXX` debt markers in phase-modified sources.

### Human Verification Required

None. Plans contain no deferred `<human-check>` blocks; dual-knob HTML contract and POST proxy are covered by automated form tests. CSRF completeness is deferred to Phase 78 (see Deferred Items), not a Phase 75 human gate.

### Gaps Summary

No blocking gaps. Phase goal achieved: operators can configure QQ/WeCom channel host knobs and secret refs through `/config/channels` API and SSR, see non-collapsed dual-knob effective state, and never receive resolved secrets on GET. Host apply helpers preserve fail-closed AND semantics with store-wins-if-exists load.

**Disconfirmation notes (non-blocking):**
1. WeCom `load_wecom_channel_config` is not yet called from the WeCom service HTTP entrypoint — intentional thin-apply scope (Plan 04).
2. SSR includes `csrf_token` but does not enforce CSRF — deferred to Phase 78.
3. `resolve_secret_ref` still exists on QQ live TokenManager injection when channel is ON — outside materialize path; materialize tests prove no resolve during store→host copy.

---

_Verified: 2026-07-10T08:36:46Z_
_Verifier: Claude (gsd-verifier)_
