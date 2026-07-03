# Phase 34: V2 Code Gap Closure - Research

**Researched:** 2026-07-03
**Status:** Complete

## Research Questions

### RQ-1: Does the Phase 33 audit correctly classify all 9 code requirements as satisfied?

**Method:** Ran `python scripts/audit_v2_requirements.py` for each requirement and verified every evidence path (implementation files, test modules, fixtures) exists on disk via a programmatic check against `acceptance/v2-traceability.json`.

**Finding:** All evidence paths exist. Zero missing files across all 10 requirements.

| Req ID | Status | Impl Files | Test Modules | Fixtures | Gates | Missing |
|--------|--------|------------|--------------|----------|-------|---------|
| WECOM-01 | satisfied | 15 | 10 | 5 | 1 | 0 |
| ADAPTER-01 | satisfied | 22 | 1 | 1 | 2 | 0 |
| HERMES-01 | satisfied | 7 | 1 | 0 | 1 | 0 |
| OUTPUT-01 | satisfied | 15 | 1 | 1 | 2 | 0 |
| LOOP-01 | satisfied | 15 | 1 | 3 | 2 | 0 |
| FEEDBACK-01 | satisfied | 4 | 3 | 3 | 2 | 0 |
| READVIEW-01 | satisfied | 4 | 2 | 1 | 2 | 0 |
| OBSERVE-01 | satisfied | 15 | 3 | 3 | 3 | 0 |
| COMPOSE-01 | satisfied | 8 | 3 | 6 | 1 | 0 |
| TRIAL-01 | human_gate | 8 | 1 | 0 | 1 | 0 |

**Conclusion:** The audit results are correct. GAP-01 through GAP-06 have no genuine code gaps to close — all 9 code requirements are satisfied by shipped v1.1–v1.4 code with verified evidence paths.

### RQ-2: Do all 7 V2 gate suites pass green at baseline?

**Method:** Ran `python scripts/run_v2_gates.py` from repository root.

**Finding:** All 9 gates pass green (7 original + v2-acceptance-traceability + compileall):

```
==> platform-contract          OK
==> wecom-service              OK
==> hermes-contract-layer      OK
==> conversation-read-view     OK
==> feedback-service           OK
==> phase7-privacy-boundary    OK
==> contract-test-suite        OK
==> v2-acceptance-traceability OK
==> compileall                 OK
EXIT: 0
```

**Conclusion:** GAP-07 baseline is green. Post-change regression check must maintain this.

### RQ-3: Which §10.3 synthetic task types are covered by fixtures?

**Method:** Cross-referenced V2-PRD §10.3 (7 synthetic task types) against all fixture files in `packages/contract-test-suite/fixtures/` and `packages/platform-contract/fixtures/`.

**Finding:** All 7 §10.3 synthetic task types have fixture coverage:

| §10.3 Task Type | Fixtures | Evidence |
|-----------------|----------|----------|
| simple_legal_qa (简单法律问答/短任务) | `phase4_simple_qa_event_stream.jsonl`, `phase3_non_legal_wild_task_contract_fixture.json` | `route_decision.mode=simple_qa` |
| contract_review (合同审查/长任务+skill+gate+Artifact) | `phase4_success_event_stream.jsonl`, `legal_wecom_contract_review.json` | `primary_skill=lawfirm.contract_review`, `artifacts_written` |
| legal_retrieval (法律检索/MCP tool trace) | `phase5_wecom_contract_stream.jsonl` | `primary_skill=lawfirm.legal_retrieval`, `tool_calls=[law-database]` |
| route_error (路由错误模拟/route_mismatch) | `phase3_route_error_contract_fixture.json`, `phase5_wecom_feedback_sample.jsonl`, `phase6_read_feedback_bundle.json` | `route_mismatch=true`, `action=route_wrong` |
| wecom_feedback (WeCom反馈/模板卡片→FeedbackEvent) | `phase5_wecom_feedback_loop_fixture.json`, `phase5_wecom_feedback_sample.jsonl`, `phase3_repeated_feedback_clicks_contract_fixture.json` | `feedback_event`, `feedback_target` linking |
| long_task_failure (长任务失败/AsyncTask.status=failed) | `phase3_long_task_failure_contract_fixture.json`, `phase4_failed_long_task_event_stream.jsonl` | `state=failed`, `errors=[runtime_error]` |
| non_legal_synthetic (非法律合成任务/财税+工程+教育) | `non_legal_finance_tax_task.json`, `non_legal_education_task.json`, `non_legal_engineering_task.json`, `platform_foundation_non_legal_run.json` | `industry_context.domain` in {finance_tax, engineering, education} |

**Conclusion:** All 7/7 §10.3 task types are covered. GAP-08 requires a report documenting this mapping — no new fixtures needed for coverage, but the report itself is a new deliverable.

### RQ-4: Does the output boundary fixture cover all 4 §10.2 categories (gateway/update/command/meta)?

**Method:** Analyzed `packages/contract-test-suite/fixtures/phase55_output_policy_cases.json` (3 cases) against §10.2 requirement: "后端 gateway/update/command/meta 样例必须被阻断或改写为 InkStatute 服务提示".

**Finding:** The fixture has 3 cases but does NOT explicitly cover all 4 categories:

| Category | Covered? | Fixture Case | Action |
|----------|----------|--------------|--------|
| gateway | YES | `rewrite-gateway-lifecycle` | rewrite |
| update | **NO** | — | — |
| command | YES | `block-command-debug-stack` | block |
| meta | **PARTIAL** | `block-command-debug-stack` (ADMIN_NOTICE mixed with command/debug) | block |

**This is a genuine gap found during spot-check.** The `phase55_output_policy_cases.json` fixture needs explicit "update" and "meta" cases to fully satisfy §10.2's requirement that all 4 categories have fixture evidence.

**Note:** The production code (`output_policy.py`) already handles all 4 categories correctly — `_BLOCK_PATTERNS` covers update (`/update`, `self-update`) and meta (`admin_notice`, `tool progress`, `memory sync`, `insights`). The gap is in fixture evidence, not production behavior. The `test_output_policy.py` test `test_blocks_or_rewrites_backend_meta_notices` does test these patterns inline, but the committed fixture does not have dedicated cases.

**Conclusion:** GAP-09 requires (a) closing this fixture gap by adding "update" and "meta" cases, and (b) building an evidence summary report proving all 4 categories are blocked or rewritten.

### RQ-5: What evidence producer modules exist for building the GAP-08 and GAP-09 reports?

**Method:** Examined `packages/contract-test-suite/src/contract_test_suite/` modules.

**Finding:**

| Module | Purpose | Reuse for GAP-? |
|--------|---------|-----------------|
| `coverage_report.py` | AgentTurn/AgentResult coverage + relationship breakage summaries | GAP-08 (add task-type coverage function) |
| `boundary_checks.py` | Thin-layer boundaries, import boundaries, industry-neutral schemas, output boundary checks | GAP-09 (add evidence summary function) |
| `privacy_scan.py` | Secret/PII/raw_payload scanning | GAP-09 (privacy baseline reference) |
| `fixture_replay.py` | Golden fixture replay + relationship integrity | GAP-08 (fixture loading) |
| `schema_validation.py` | JSON Schema subset validation | Both (fixture validation) |

**Conclusion:** GAP-08 report function fits naturally in `coverage_report.py` (fixture coverage). GAP-09 report function fits naturally in `boundary_checks.py` (output boundary). Both are in-place additions to existing modules — no new services.

### RQ-6: What script pattern should the report generator follow?

**Method:** Examined `scripts/audit_v2_requirements.py` (Phase 33 deliverable, 1266 lines).

**Finding:** The audit script pattern is:
- Stdlib-only (`argparse`, `json`, `pathlib`, `re`, `ast`, `dataclasses`)
- Deterministic output (`sort_keys=True`, sorted lists, no timestamps)
- Writes JSON sidecar to `acceptance/` directory
- Has `--check-gaps` mode for CI gate integration
- Tests in `packages/contract-test-suite/tests/test_audit_v2_requirements.py`

**Conclusion:** The GAP-08/GAP-09 report generator should follow the same pattern: a script in `scripts/` that calls evidence producer functions and writes deterministic JSON sidecars to `acceptance/`. The script should be added to the `compileall` gate path list.

## Research Summary

| Question | Answer | Impact on Plan |
|----------|--------|----------------|
| RQ-1: Audit correct? | Yes — 9 satisfied, 0 gap, all evidence paths exist | GAP-01–06: verify only, no code gaps to close |
| RQ-2: Gates green? | Yes — all 9 gates pass at baseline | GAP-07: regression check post-change |
| RQ-3: §10.3 coverage? | 7/7 task types covered by fixtures | GAP-08: build report, no new fixtures needed |
| RQ-4: §10.2 output boundary? | **Gap found**: fixture missing update + meta cases | GAP-09: close fixture gap + build evidence summary |
| RQ-5: Evidence producers? | coverage_report.py + boundary_checks.py are reuse targets | In-place additions, no new services |
| RQ-6: Script pattern? | Follow audit_v2_requirements.py pattern | scripts/generate_gap_evidence_reports.py |

## Key Decisions

1. **GAP-01 through GAP-06**: No code changes needed — audit confirmed no gaps. Spot-check verification is the deliverable.
2. **GAP-07**: Baseline established (9 gates green). Post-change regression check required.
3. **GAP-08**: Add `build_composability_coverage_report()` to `coverage_report.py` + report generator script + tests. All 7 task types already covered.
4. **GAP-09**: Close fixture gap (add update + meta cases to `phase55_output_policy_cases.json`) + add `build_output_boundary_evidence_summary()` to `boundary_checks.py` + report generator script + tests.
5. **Report generator**: Single script `scripts/generate_gap_evidence_reports.py` producing two JSON sidecars in `acceptance/`.
