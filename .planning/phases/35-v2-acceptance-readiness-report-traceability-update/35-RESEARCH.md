# Phase 35: V2 Acceptance Readiness Report & Traceability Update - Research

**Researched:** 2026-07-03
**Status:** Complete

## Research Questions

### RQ-1: What input artifacts exist from Phase 33 and Phase 34?

**Method:** Inspected `acceptance/` directory and ran audit/gate scripts.

**Finding:** Three JSON sidecars are the primary inputs:

| Artifact | Source | Content |
|----------|--------|---------|
| `acceptance/v2-traceability.json` | Phase 33 | 10 requirements (9 satisfied, 0 gap, 1 human_gate), 15 PRD §10 criterion-to-test mappings |
| `acceptance/v2-composability-coverage.json` | Phase 34 | 7/7 §10.3 synthetic task types covered, 0 missing |
| `acceptance/v2-output-boundary-evidence.json` | Phase 34 | 4/4 §10.2 categories covered (gateway/rewrite, update/block, command/block, meta/block) |

All three are deterministic (sorted keys, no timestamps, `generated_at: "deterministic"`).

The 10 requirements in `v2-traceability.json`:

| Req ID | Status | PRD § | Human Gate | Description |
|--------|--------|-------|------------|-------------|
| WECOM-01 | satisfied | 10.2 | No | WeCom service receive/send/ACK/normalization/delivery/feedback/idempotency/output policy |
| ADAPTER-01 | satisfied | 10.2 | No | Agent backend adapter contract + runtime selector |
| HERMES-01 | satisfied | 10.4 | No | Hermes bootstrap path (sanitized bundle, version matrix, health checks) |
| OUTPUT-01 | satisfied | 10.2 | No | Assistant output boundary (gateway/update/command/meta blocked/rewritten) |
| LOOP-01 | satisfied | 10.2 | No | WeCom task→agent→reply→card→feedback loop validation |
| FEEDBACK-01 | satisfied | 10.2 | No | Feedback normalization (dedupe, classification, skill_candidate) |
| READVIEW-01 | satisfied | 10.2 | No | Read-only conversation/task/feedback APIs from contract logs |
| OBSERVE-01 | satisfied | 10.2 | No | Observability/replay/privacy/legal safety baselines |
| COMPOSE-01 | satisfied | 10.3 | No | Composability + industry-neutral contract behavior in CI |
| TRIAL-01 | human_gate | 10.4 | Yes | Five-workday lawyer trial acceptance criteria |

### RQ-2: What is the current V2 gate suite status?

**Method:** Ran `python scripts/run_v2_gates.py` from repository root.

**Finding:** All 9 gates pass green with 465 tests total:

| Gate | Tests | Status |
|------|-------|--------|
| platform-contract | 21 | OK |
| wecom-service | 71 | OK |
| hermes-contract-layer | 30 | OK |
| conversation-read-view | 18 | OK |
| feedback-service | 31 | OK |
| phase7-privacy-boundary | 13 | OK |
| contract-test-suite | 281 | OK |
| v2-acceptance-traceability | (gap check) | OK |
| compileall | (bytecode) | OK |

**Total: 465 tests, exit 0.**

### RQ-3: What PROJECT.md evolution protocol exists?

**Method:** Read `.planning/PROJECT.md` lines 159-164.

**Finding:** The evolution protocol states:

> **After each phase transition** (via `$gsd-transition`):
> 1. Requirements invalidated? Move to Out of Scope with reason.
> 2. Requirements validated? Move to Validated with phase reference.
> 3. New requirements emerged? Add to Active.
> 4. Decisions to log? Add to Key Decisions.
> 5. "What This Is" still accurate? Update if drifted.

Currently, PROJECT.md lines 43-52 contain 10 unchecked `[ ]` Active requirements. The first 5 (lines 38-42) are already checked `[x]` — these were validated in earlier phases. The 10 unchecked requirements map exactly to the 10 requirements in `v2-traceability.json`.

For Phase 35:
- 9 satisfied requirements → move from Active `[ ]` to Validated with phase references (Phase 33/34 audit + v1.1–v1.4 implementation phases)
- 1 human_gate requirement (TRIAL-01) → remains unchecked `[ ]` in Active until live evidence exists

### RQ-4: What milestone-audit convention exists?

**Method:** Read `.planning/milestones/v1.4-MILESTONE-AUDIT.md`.

**Finding:** The milestone audit format uses:
- YAML frontmatter (milestone, status, scores, gaps, tech_debt)
- Summary section with high-level pass/fail
- Requirements Coverage table (REQ-ID, Description, Phase, Verification, Final Status)
- Phase Verification Summary table
- Integration Check Results
- Tech Debt table
- Recommendations

The V2 acceptance readiness report should follow this convention but extend it with:
- Two-tier status model (autonomous closure READY vs V2 acceptance BLOCKED ON HUMAN GATES)
- PRD §10.1–10.4 section mirroring
- §13 residual risk classification
- Human-gate documentation (Phase 5 UAT, Phase 8 trial)

### RQ-5: What §13 residual risks exist and how should they be classified?

**Method:** Read V2-PRD.md §13 (lines 688-708) — 17 residual risks.

**Finding:** The PRD §13 lists 17 residual risks. Each must be classified as:
- **source-resolved**: Risk addressed by PRD design decisions (no additional code needed beyond following the PRD)
- **implementation-resolved**: Risk addressed by specific code implementations (tests, modules, fixtures, gates)
- **live-evidence-pending**: Risk requires human-gate evidence (Phase 5 UAT or Phase 8 trial) to fully close

Classification:

| # | Risk (short) | Classification | Rationale |
|---|-------------|----------------|-----------|
| 1 | hook event ordering | implementation-resolved | Phase 3 source-confirmed hook ordering; occurred_at + ingested_at + seq + replay tests prove it |
| 2 | inbound event missing | implementation-resolved | agent:end reverse inference approach implemented; fixtures prove AgentTurn reconstruction |
| 3 | message_id stability | implementation-resolved | response_filter generates message_id; feedback loop fixtures prove stable mapping |
| 4 | long-task state source | implementation-resolved | Async state machine implemented; fixtures cover queued/running/failed/succeeded |
| 5 | response_filter + template card | implementation-resolved | feedback_target 1:1 mapping implemented; fixtures prove single card per reply |
| 6 | feedback dedup | implementation-resolved | Idempotency module + dedupe fixtures (repeated clicks, network retry) |
| 7 | raw payload storage | source-resolved | PRD defines raw_payload_ref approach; implementation follows — no sensitive full text in logs |
| 8 | sensitive info redaction | implementation-resolved | privacy_scan.py + coverage report ≥95%; privacy gates pass green |
| 9 | route log gap | implementation-resolved | RouteDecision.mode=simple_qa implemented; fixtures cover skipped route |
| 10 | CI fixture representativeness | implementation-resolved | Composability coverage 7/7 task types (route error, long-task failure, feedback dedup, non-legal) |
| 11 | skill synthesis boundary | source-resolved | PRD defines skill_candidate only (no auto-modify); implementation records candidates without auto-synthesis |
| 12 | lawyer trial sample size | live-evidence-pending | 5 workdays / 15 tasks requires live human execution — Phase 8 human gate |
| 13 | multi-hook same-event ordering | implementation-resolved | Phase 3 source-confirmed 3-hook ordering (admin_notice, response_filter, contract_result_recorder) |
| 14 | Hermes gateway not user channel | implementation-resolved | Output boundary 4/4 categories blocked/rewritten; InkStatute WeCom service owns ingress/egress |
| 15 | Hermes version drift | implementation-resolved | Capability probe + version matrix in bootstrap.py; adapter_manifest schema |
| 16 | profile bundle reproducibility | implementation-resolved | Sanitized bundle + bootstrap check + external secrets/env; fixtures prove |
| 17 | WeCom service protocol risk | live-evidence-pending | Fixture-satisfied (callback verification, ACK, 5s timeout, token refresh); live UAT evidence needed — Phase 5 human gate |

**Summary:** 2 source-resolved, 13 implementation-resolved, 2 live-evidence-pending.

### RQ-6: What trial acceptance thresholds exist in code?

**Method:** Read `packages/contract-test-suite/src/contract_test_suite/trial_acceptance.py`.

**Finding:** The `evaluate_trial_acceptance()` function encodes all §10.4 thresholds:

| Threshold | Value | Source |
|-----------|-------|--------|
| Minimum workdays | 5 | §10.4 "连续 5 个工作日" |
| Minimum tasks | 15 | §10.4 "至少 15 个真实任务" |
| Minimum business output | 12 | §10.4 "至少 12 个有明确业务产出" |
| Minimum task categories | 3 | §10.4 "覆盖至少 3 类任务" |
| Long-task success rate | ≥ 80% | §10.4 "长任务成功率 ≥ 80%" |
| Ordinary task success rate | ≥ 85% | §10.4 "普通任务成功率 ≥ 85%" |
| Feedback capture rate | ≥ 60% | §10.4 "反馈采集率 ≥ 60%" |
| Positive feedback share | ≥ 60% | §10.4 "正向反馈占比 ≥ 60%" |
| Negative feedback response | 48h | §10.4 "负面反馈 48 小时内有响应" |
| Route mismatch max | 3 | §10.4 "route_mismatch 不超过 3 条" |
| Long task threshold | > 60s | `LONG_TASK_SECONDS = 60.0` |

The `TrialTaskEvidence` dataclass (22 fields) defines the metric-collection row schema. An existing template exists at `.planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json`.

### RQ-7: What report generator pattern exists?

**Method:** Read `scripts/generate_gap_evidence_reports.py` (Phase 34 deliverable).

**Finding:** The existing pattern is:
- Stdlib-only (`argparse`, `json`, `sys`, `pathlib`)
- `main(argv)` function with argparse
- `--check` flag for CI gate integration (exit non-zero on failures)
- Deterministic output (sorted keys, no timestamps)
- Repo root resolution: `Path(__file__).resolve().parents[1]`
- Writes to `acceptance/` directory

The V2 readiness report generator should follow this pattern but:
- Output is Markdown (not JSON) → `.planning/milestones/v1.5-V2-ACCEPTANCE-READINESS.md`
- Uses triple-quoted f-strings for report sections (no Jinja2)
- Reads 3 JSON sidecars as input
- `--check` flag verifies the report was generated and key sections exist

### RQ-8: What Phase 5 live WeCom UAT context exists?

**Method:** Searched PROJECT.md, ROADMAP.md, and PRD §10.4/§12 for Phase 5 references.

**Finding:** Phase 5 is "WeCom 可用闭环加固" (WeCom Usable Loop Hardening) per PRD §12.1 step 5. It is a human gate because:
- The WeCom service code is complete and fixture-satisfied (WECOM-01 satisfied)
- But live WeCom UAT requires: deploying InkStatute WeCom service, configuring WeCom callback URL/token/encoding AES key, sending real messages through WeCom, confirming ACK/text/file/card delivery, and verifying feedback callbacks
- PRD §10.4 states: "V2 live acceptance 使用 InkStatute WeCom service 完成接收、ACK、发送文本/文件/卡片和反馈回调，不使用 Hermes gateway 作为普通用户通道"

The Phase 5 UAT documentation needs:
- Operator checklist (deployment steps, WeCom config, test messages)
- Fixture evidence summary (what fixtures prove the code is ready)
- Pass/fail criteria (what constitutes UAT success)

## Conclusion

All research is complete. The phase is primarily documentation generation:
1. A stdlib-only report generator script reads 3 JSON sidecars and produces a Markdown readiness report
2. PROJECT.md is updated to move 9 satisfied requirements to Validated (TRIAL-01 stays unchecked)
3. The readiness report includes Phase 5 UAT and Phase 8 trial documentation sections
4. §13 residual risks are classified into 3 tiers
5. Two-tier status model distinguishes autonomous closure from V2 acceptance

No new services, no new dependencies, no new runtime components — only a script, a generated report, and a PROJECT.md edit.
