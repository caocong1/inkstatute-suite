# Deferred Items — Phase 13

Pre-existing issues discovered during plan execution that are out of scope for
the current plan (per executor deviation rules: "Only auto-fix issues DIRECTLY
caused by the current task's changes").

## Pre-existing gate failures (not caused by 13-02)

### phase7-privacy-boundary: test_default_privacy_data_paths_are_clean

- **File:** `.planning/phases/12-channel-interface-wecom-wrapper-web-sse-client-sdk/12-04-SUMMARY.md`
- **Issue:** The untracked 12-04-SUMMARY.md contains raw callback-body
  markers (`callback-body` and `callback_xml_body`) that trip the privacy scan's raw-callback-body
  marker rule (9 issues).
- **Owner:** Phase 12-04 SUMMARY sanitization (the SUMMARY is untracked; the
  orchestrator's final docs commit for 12-04 should sanitize those markers, or
  the privacy scan rule needs to whitelist `.planning/` SUMMARY paths).
- **Not caused by 13-02:** The 12-04-SUMMARY.md is untracked from prior Phase 12
  work; 13-02 does not touch `.planning/phases/12-*`.

### contract-test-suite: test_phase55_wecom_service_loop module import

- **File:** `packages/contract-test-suite/tests/test_phase55_wecom_service_loop.py`
- **Issue:** `ModuleNotFoundError: No module named 'wecom_service'` when run via
  plain `discover` without the full gate PYTHONPATH. The gate script includes
  `wecom_src` in PYTHONPATH for the contract-test-suite gate; running discover
  with the gate's full PYTHONPATH set resolves this.
- **Not caused by 13-02:** Pre-existing Phase 5.5 test wiring.

### contract-test-suite: test_phase13_solution_evidence (Plan 13-04 test file)

- **File:** `packages/contract-test-suite/tests/test_phase13_solution_evidence.py`
- **Issue:** Imports `scan_bundle_dir` from `inkstatute_solution_loader` (a
  Plan 13-04 re-export per 13-01 SUMMARY) and `solutions_meta` (untracked,
  Plan 13-04 glue). This test file is on disk from prior pre-plan work but
  belongs to Plan 13-04; it cannot pass until 13-04 ships the
  `scan_bundle_dir`/`BINARY_REFUSE_EXTENSIONS`/`TEXT_EXTENSIONS` re-exports in
  `packages/solution-loader/src/inkstatute_solution_loader/__init__.py` and
  commits `solutions_meta.py`.
- **Not caused by 13-02:** 13-02 does not own the `scan_bundle_dir` re-export.
  Plan 13-04 will close this loop.

## Status

These items are acknowledged and carried forward. They do not block 13-02's
acceptance criteria (which require only that 13-02 not *regress* existing
gates; the failures above pre-date 13-02).