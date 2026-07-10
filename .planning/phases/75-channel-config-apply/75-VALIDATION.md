---
phase: 75
slug: channel-config-apply
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-10
---

# Phase 75 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `unittest` (stdlib; V2 gates) |
| **Config file** | none — discover via `python -m unittest discover` / `scripts/run_v2_gates.py` |
| **Quick run command** | `PYTHONPATH=services/admin-console-api/src:packages/operator-config/src:packages/platform-runtime/src:packages/rbac/src:packages/platform-contract/src:services/conversation-read-view/src:services/feedback-service/src python -m unittest services.admin-console-api.tests.test_config_channels_effective services.admin-console-api.tests.test_config_api -q` |
| **Full suite command** | Quick + `… test_contract_freeze -q` + qqbot `test_store_apply test_wiring_flag_config` + wecom `test_from_operator_doc` + wecom-service `test_channel_wiring_dual_knob` + admin-web-ui `test_channels_form` + platform-runtime `test_feature_flags` (each with package-appropriate PYTHONPATH including `operator_config_src` where needed) |
| **Estimated runtime** | ~15–30s quick; ~60–90s full targeted |

---

## Sampling Rate

- **After every task commit:** Run the task `<automated>` command from the active PLAN.md
- **After every plan wave:** Wave 1 → freeze + feature_flags; Wave 2 → effective API + QQ store apply + WeCom dual-knob; Wave 3 → channels SSR form
- **Before `/gsd-verify-work`:** Full targeted suite green (admin-console-api + qqbot-service + wecom channel/service + admin-web-ui + platform-runtime proofs above)
- **Max feedback latency:** 60 seconds for quick command

**Critical:** Phase verification must **not** require live WeCom/QQ credentials or network. Carried human gates (Phase 5 / Phase 8 / QQ `--live`) must not be auto-closed. Tests must inject temp-path `OperatorConfigStore` — never commit or rely on `.inkstatute/operator-config.json`.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 75-01-01 | 01 | 1 | CHAN-03 | T-75-01 / T-75-02 | `wecom_channel_enabled` default OFF; freeze exact-set; host gates get operator_config_src | unit+meta | `test_feature_flags` + `test_contract_freeze` + operator_config_src count | ⚠️ evolve | ⬜ pending |
| 75-01-02 | 01 | 1 | CHAN-03 | — | Wave 0 scaffolds for effective/apply/SSR | scaffold | `test -f` five test modules | ❌ W0 | ⬜ pending |
| 75-02-01 | 02 | 2 | CHAN-01..04 | T-75-03 / T-75-05 | effective + apply_semantics on channels GET/PUT; no platform PUT | unit | import/source assert effective + apply_semantics | ⚠️ evolve config_api | ⬜ pending |
| 75-02-02 | 02 | 2 | CHAN-03 / CHAN-04 | T-75-04 | Dual-knob matrix + planted no-echo including effective | unit | `test_config_channels_effective` + `test_config_api` | ❌→✅ W0 | ⬜ pending |
| 75-03-01 | 03 | 2 | CHAN-01 | T-75-06 | load_qqbot_host_config store-wins-if-exists | unit | import load_qqbot_host_config | ❌ W0 | ⬜ pending |
| 75-03-02 | 03 | 2 | CHAN-01 / CHAN-03 | T-75-07 | Store apply + dual-knob AND preserved | unit | `test_store_apply` + `test_wiring_flag_config` | ❌→✅ W0 | ⬜ pending |
| 75-04-01 | 04 | 2 | CHAN-02 | T-75-09 | from_operator_doc; channel package flag-free | unit | `test_from_operator_doc` | ❌→✅ W0 | ⬜ pending |
| 75-04-02 | 04 | 2 | CHAN-02 / CHAN-03 | T-75-08 | WeCom AND matrix + store/env load | unit | `test_channel_wiring_dual_knob` | ❌→✅ W0 | ⬜ pending |
| 75-05-01 | 05 | 3 | CHAN-01..04 | T-75-10 / T-75-11 | channels render/parse + proxy_put; WeCom label wecom_channel_enabled | smoke | import channels + proxy_put | ❌ W0 | ⬜ pending |
| 75-05-02 | 05 | 3 | CHAN-01..04 | T-75-10..12 | SSR GET/POST dual-knob + restart honesty | unit | `test_channels_form` | ❌→✅ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky / exists-needs-evolve*

### Requirement → verify crosswalk

| Req | Covered by task verifies | Primary test files |
|-----|--------------------------|--------------------|
| CHAN-01 | 75-02-*, 75-03-*, 75-05-* | `test_config_api`, `test_store_apply`, `test_channels_form` |
| CHAN-02 | 75-02-*, 75-04-*, 75-05-* | `test_config_channels_effective`, `test_channel_wiring_dual_knob`, `test_channels_form` |
| CHAN-03 | 75-01-01, 75-02-*, 75-03-02, 75-04-02, 75-05-* | freeze + effective + dual-knob wiring + SSR labels |
| CHAN-04 | 75-02-02, 75-05-* | planted no-echo + refs-only form inputs |

---

## Wave 0 Requirements

- [ ] `services/admin-console-api/tests/test_config_channels_effective.py` — CHAN-03 effective + apply_semantics
- [ ] `services/qqbot-service/tests/test_store_apply.py` — store→HostConfig→dual-knob + env fallback
- [ ] `packages/channels/wecom/tests/test_from_operator_doc.py` — doc materialize; no flag import
- [ ] `services/wecom-service/tests/test_channel_wiring_dual_knob.py` — WeCom AND matrix
- [ ] `services/admin-web-ui/tests/test_channels_form.py` — SSR render + POST proxy
- [ ] Update `test_contract_freeze.py` expected flag set for `wecom_channel_enabled`
- [ ] Extend planted-secret no-echo asserts to cover `effective` payload

*Created by plan 75-01; turned green by plans 75-02..05.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| — | — | All phase behaviors have automated verification | — |

Carried Phase 5 / Phase 8 / QQ `--live` human gates remain **outside** this phase and must not be auto-closed.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
