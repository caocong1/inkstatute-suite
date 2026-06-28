# Phase 7: CI, Composability, and Privacy Gates - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-28T07:58:00Z
**Phase:** 7-CI, Composability, and Privacy Gates
**Areas discussed:** CI entrypoint, Coverage thresholds, Privacy scanning, Thin-layer enforcement, Reports and artifacts
**Mode:** `--auto`; recommended defaults selected without user prompts.

---

## CI Entry Point

| Option | Description | Selected |
|--------|-------------|----------|
| Local runner plus GitHub Actions wrapper | Build one repo-root command and have CI call it. | ✓ |
| GitHub Actions only | Put all commands directly in workflow YAML. | |
| Add tox/nox/pytest stack | Introduce new tooling to orchestrate tests. | |

**User's choice:** Auto-selected local runner plus GitHub Actions wrapper.
**Notes:** This keeps failures reproducible locally and preserves the repo's dependency-light pattern.

---

## Coverage Thresholds

| Option | Description | Selected |
|--------|-------------|----------|
| Fixture-proven reporter with optional runtime input | CI proves calculations on sanitized fixtures and reports missing live input honestly. | ✓ |
| Treat fixtures as real-task coverage | Count synthetic fixtures as live real-task evidence. | |
| Defer all coverage reporting to Phase 8 | Avoid Phase 7 coverage tooling. | |

**User's choice:** Auto-selected fixture-proven reporter with optional runtime input.
**Notes:** Phase 7 can implement the reporter and gate semantics without committing real logs or claiming trial acceptance.

---

## Privacy Scanning

| Option | Description | Selected |
|--------|-------------|----------|
| Strict data scan plus source allowlist | Fail fixture/docs/data leaks while allowing guard strings in validators/tests. | ✓ |
| Global raw string ban | Fail any occurrence of sensitive words, including test guard code. | |
| Manual review only | Rely on humans to inspect privacy issues. | |

**User's choice:** Auto-selected strict data scan plus source allowlist.
**Notes:** Existing validators and tests intentionally mention `raw_payload`; the gate must distinguish guard code from leaked data.

---

## Thin-Layer Enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| Import/schema/fixture boundary checks | Fail platform-core imports of services/Hermes and legal-only schema coupling. | ✓ |
| Documentation-only boundary | Record the rule without automated checks. | |
| Runtime integration checks | Build new runtime probes in Phase 7. | |

**User's choice:** Auto-selected import/schema/fixture boundary checks.
**Notes:** This directly supports `REQ-v2-thin-contract-layer` without rebuilding Hermes or adding runtime services.

---

## Reports and Artifacts

| Option | Description | Selected |
|--------|-------------|----------|
| Sanitized summaries only | Emit concise stdout/JSON/text summaries; upload no raw runtime artifacts. | ✓ |
| Commit generated reports | Store generated coverage/privacy output in the repo. | |
| Upload full logs for debugging | Keep CI artifacts with command logs and data samples. | |

**User's choice:** Auto-selected sanitized summaries only.
**Notes:** Generated artifacts must not contain runtime logs, callback bodies, customer documents, media, databases, or raw legal payloads.

---

## the agent's Discretion

- Exact script/workflow names are left to the planner.
- Exact plan split is left to the planner; a natural split is local gates/reporting, privacy/composability helpers, and CI/docs.
- The planner may choose whether privacy/coverage helpers live in `packages/contract-test-suite` or root `scripts/`, as long as the local runner remains dependency-free.

## Deferred Ideas

- Real lawyer-trial metrics and live evidence collection stay in Phase 8.
- Complete security platform features remain beyond V2.

