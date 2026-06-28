# Phase 8: Lawyer Trial Acceptance - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-06-28T09:19:46Z
**Phase:** 8-Lawyer Trial Acceptance
**Mode:** `--auto`
**Areas discussed:** Trial start gate and evidence source, Metrics counting and thresholds, Feedback and legal safety, Reporting and automation boundary, Privacy and artifact handling

---

## Trial Start Gate And Evidence Source

| Option | Description | Selected |
|--------|-------------|----------|
| Live InkStatute WeCom gate | Start counting only after InkStatute owns receive/send, Hermes is agent logic only, and output boundary evidence is available. | yes |
| Fixture readiness gate | Allow synthetic fixtures to stand in for live acceptance. | |
| Hermes gateway migration gate | Count usage through Hermes gateway if the lawyer can complete tasks. | |

**Auto choice:** Live InkStatute WeCom gate.
**Notes:** Fixture evidence and Hermes gateway migration evidence remain readiness inputs only. They cannot satisfy Phase 8 live lawyer-trial acceptance.

---

## Metrics Counting And Thresholds

| Option | Description | Selected |
|--------|-------------|----------|
| Minimized task rows | Track one sanitized row per real task with stable refs, category, timing, success, feedback, route mismatch, and response-action fields. | yes |
| Full transcript rows | Store prompts, replies, and callback bodies in the report for audit convenience. | |
| Manual narrative only | Rely on prose notes without machine-checkable rows. | |

**Auto choice:** Minimized task rows.
**Notes:** This keeps the report auditable while respecting raw-payload and customer-document privacy rules.

---

## Feedback And Legal Safety

| Option | Description | Selected |
|--------|-------------|----------|
| Human-reviewed feedback queue | Negative feedback and route mismatch require explicit human review and response-action tracking. | yes |
| Auto-repair legal skills | Trigger skill changes from negative feedback during acceptance. | |
| Ignore negative feedback until after trial | Measure only task success and feedback share. | |

**Auto choice:** Human-reviewed feedback queue.
**Notes:** High-risk legal feedback must not auto-modify legal conclusions or skills. Route mismatch must link structured candidate evidence.

---

## Reporting And Automation Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Fail-closed checker | Produce `pending`, `blocked`, `failed`, or `passed` with concrete threshold evidence and require runtime input for live pass. | yes |
| Best-effort checklist | Produce a human checklist without strict status calculation. | |
| CI-only pass | Treat green local/CI gates as sufficient for acceptance. | |

**Auto choice:** Fail-closed checker.
**Notes:** `python scripts/run_v2_gates.py --json-summary` remains a readiness baseline. It is not live acceptance.

---

## Privacy And Artifact Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Reference-first artifacts | Commit templates, runbooks, and sanitized summaries only; keep raw runtime evidence external. | yes |
| Commit sanitized transcripts | Include redacted prompt/reply excerpts for convenience. | |
| Commit runtime logs temporarily | Use repo history as acceptance storage, then clean later. | |

**Auto choice:** Reference-first artifacts.
**Notes:** No WeCom secrets, callback bodies, raw legal payloads, media files, customer documents, runtime databases, or logs should enter the repo.

---

## the agent's Discretion

- Choose exact file/module names for Phase 8 trial runbooks, templates, metric helpers, and acceptance reports.
- Choose whether threshold logic lives in `packages/contract-test-suite`, `scripts/`, or planning artifacts, as long as it remains dependency-free and locally testable.
- Split planning into readiness, metric tooling, live evidence collection, and final audit if that best matches the human trial gate.

## Deferred Ideas

- Ongoing post-V2 legal quality evaluation.
- Production dashboard/UI for trial metrics.
- Durable trial database or operational analytics.
- Automatic legal skill synthesis.
