---
phase: 90-acp-event-bridge-output-boundary
plan: 03
subsystem: backend
tags: [privacy-scanning, secrets-detection, reference-first, raw-payload-ref, acp-credentials]
requires:
  - phase: 90-01
    provides: EventBridge
  - phase: 90-02
    provides: ACPOutputFilter
provides:
  - packages/acp-event-bridge/src/inkstatute_acp_event_bridge/privacy_scan.py — ScanResult, scan_event, scan_events, assert_reference_first, assert_all_reference_first, EVENT_TYPES_REQUIRING_RAW_PAYLOAD_REF
  - 12 secret pattern categories (6 from output_boundary.py + 4 ACP-specific + 2 from channel-core/output_policy.py)
  - Reference-first logging enforcement — asserts raw_payload_ref for sensitive event types
  - packages/acp-event-bridge/tests/test_privacy_scan.py — 20 tests for secret detection and reference-first enforcement
affects: [90-04]
key-files:
  - packages/acp-event-bridge/src/inkstatute_acp_event_bridge/privacy_scan.py
  - packages/acp-event-bridge/src/inkstatute_acp_event_bridge/__init__.py
  - packages/acp-event-bridge/tests/test_privacy_scan.py
key-decisions:
  - "Secret patterns reused from output_boundary.py (6 patterns) + ACP-specific patterns (4: hermes_home_path, hermes_dot_path, acp_env_secret, acp_debug) + channel-core patterns (2: profile_path, env_secret_combo) — total 12 pattern categories"
  - "Findings never include original secret text — only rule_id, matched_pattern name, field_path, and audit metadata (hash prefix + length + privacy marker)"
  - "EVENT_TYPES_REQUIRING_RAW_PAYLOAD_REF: 4 event types (message.completed, tool_call.completed, artifact.created, citation.recorded) — delta/elicitation/permission events exempt because content needed for real-time interaction"
  - "assert_reference_first returns True for exempt types, True if raw_payload_ref present, False if sensitive field exists without raw_payload_ref"
  - "Recursive dict/list scanning with dotted field paths (e.g. payload.metadata.inner.secret, payload.items[1])"
patterns-established:
  - "Privacy scan pattern: scan_event → ScanResult with clean flag + findings list, no original text in any finding"
  - "Reference-first enforcement: assert_reference_first + assert_all_reference_first — checks raw_payload_ref in metadata for sensitive event types"
  - "Audit metadata structure: {rule_id, field_path, input_hash_prefix (16 hex chars), input_length, privacy: 'no_original_text_stored'}"
  - "Sensitive field names frozenset: content, delta, raw_input, raw_output, text, data, body — these fields trigger reference-first requirement"
requirements-completed: [SAFE-02]
coverage: 67 tests total (30 from Plan 01 + 17 from Plan 02 + 20 from Plan 03), 30 gates green
duration: 1 session
completed: 2026-08-07
status: complete
---

# Plan 90-03 Summary — Privacy Scanning & Secrets Detection

## What Was Built

Implemented `privacy_scan.py` with ACP-specific secret pattern detection and reference-first logging enforcement for all bridge output events. This module scans unified `RunEvent` objects produced by the bridge for secret patterns and asserts that no bridge event stores sensitive full text — all events must use `raw_payload_ref` (hash + length) instead.

1. **ScanResult dataclass** (`privacy_scan.py`) — Frozen slotted dataclass with `clean: bool`, `findings: list[dict]`, `event_id: str`, `event_type: str`. Each finding contains `rule_id`, `matched_pattern` (pattern name, not secret text), `field_path`, and `audit` (hash prefix + length + privacy marker).

2. **12 secret pattern categories** (`_SECRET_PATTERNS`) — Compiled regex patterns:
   - From `output_boundary.py`: `secret_like`, `secret_assignment`, `internal_path`, `windows_path`, `provider_leak`, `api_error`
   - ACP-specific (RESEARCH.md §4): `hermes_home_path`, `hermes_dot_path`, `acp_env_secret`, `acp_debug`
   - From `channel-core/output_policy.py`: `profile_path`, `env_secret_combo`

3. **Sensitive field names** (`_SENSITIVE_FIELD_NAMES`) — 7 field names that trigger reference-first requirement: `content`, `delta`, `raw_input`, `raw_output`, `text`, `data`, `body`.

4. **Event types requiring raw_payload_ref** (`EVENT_TYPES_REQUIRING_RAW_PAYLOAD_REF`) — 4 event types: `message.completed`, `tool_call.completed`, `artifact.created`, `citation.recorded`. Delta/elicitation/permission events are exempt.

5. **Scanning functions**:
   - `_scan_string(value, field_path)` — scans a single string against all patterns
   - `_scan_dict(obj, field_path)` — recursively scans dict values with dotted paths
   - `scan_event(event)` — scans a RunEvent's payload and metadata
   - `scan_events(events)` — batch scanning

6. **Reference-first enforcement**:
   - `assert_reference_first(event)` — checks single event compliance
   - `assert_all_reference_first(events)` — returns list of violating event_ids

7. **Audit metadata** (`_audit_value`) — SHA-256 hash prefix (16 hex chars) + input length + privacy marker. No original text stored.

8. **__init__.py exports** — `ScanResult`, `scan_event`, `scan_events`, `assert_reference_first`, `assert_all_reference_first` exported alongside existing `ACPOutputFilter` and `FilterDecision`.

9. **Tests** — 20 test methods covering: clean events, API key/token detection, HERMES_HOME/ACP env/agent env detection, provider leak, ACP debug, nested dict scanning, list scanning, no-original-text verification, batch scanning, reference-first compliance/violation/exempt types, assert_all_reference_first, audit metadata structure, Chinese legal content no false positives.

## Acceptance Criteria Results

All acceptance criteria for all 4 tasks PASS:
- `from inkstatute_acp_event_bridge.privacy_scan import scan_event, scan_events, assert_reference_first, assert_all_reference_first, ScanResult, EVENT_TYPES_REQUIRING_RAW_PAYLOAD_REF` succeeds ✓
- `scan_event` with `api_key=abc123` returns `clean == False` with secret pattern finding ✓
- `scan_event` with `HERMES_HOME=/home/user/.hermes` returns `clean == False` with `hermes_home_path` or `acp_env_secret` ✓
- `scan_event` with Chinese legal text returns `clean == True` ✓
- `scan_event` with `/home/user/.hermes/config` returns `clean == False` ✓
- Findings do NOT contain original secret text — only rule_id, matched_pattern, field_path, audit ✓
- `assert_reference_first` with `raw_payload_ref` returns `True` ✓
- `assert_reference_first` without `raw_payload_ref` for `message.completed` returns `False` ✓
- `assert_reference_first` for `message.delta` (exempt) returns `True` ✓
- `assert_all_reference_first` with compliant events returns empty list ✓
- `assert_all_reference_first` with violation returns list with event_id ✓
- `EVENT_TYPES_REQUIRING_RAW_PAYLOAD_REF` contains 4 event types ✓
- `python -m pytest test_privacy_scan.py -x` passes (20 tests) ✓
- `from inkstatute_acp_event_bridge import scan_event, scan_events, assert_reference_first, ScanResult` succeeds ✓
- `__init__.py` contains all required names in `__all__` ✓
- Existing exports (`ACPOutputFilter`, `FilterDecision`) preserved ✓
- `python -m compileall packages/acp-event-bridge/src` exits 0 ✓
- `python -m unittest discover -s packages/acp-event-bridge/tests` passes (67 tests) ✓
- `python scripts/run_v2_gates.py` exits 0 (all 30 gates green) ✓

## Deviations

1. **Pre-existing privacy gate failure fixed** — The `phase7-privacy-boundary` gate was failing due to a long secret-like value in `90-02-SUMMARY.md` line 86 (above the 12-char scanner threshold). Shortened the reference to avoid including the secret-like value. This was a pre-existing issue from Plan 90-02's deviation note, not caused by this plan.

## Self-Check: PASSED

- All 4 tasks executed and committed atomically
- All acceptance criteria PASS
- 30 gates green (29 existing + 1 acp-event-bridge)
- 67 tests in acp-event-bridge package (30 from Plan 01 + 17 from Plan 02 + 20 from Plan 03)
- 12 secret pattern categories (6 from output_boundary.py + 4 ACP-specific + 2 from channel-core)
- Findings never contain original secret text — only pattern name + audit metadata
- Reference-first enforcement: 4 event types require raw_payload_ref, exempt types pass
- Chinese legal content produces no false positives
- SAFE-02 complete
