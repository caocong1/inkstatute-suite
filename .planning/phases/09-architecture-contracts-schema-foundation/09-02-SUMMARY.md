---
phase: 09-architecture-contracts-schema-foundation
plan: 09-02
subsystem: platform-contract
tags: [json-schema, python, dataclasses, adapter-capabilities, contract-self-check]

requires:
  - phase: 09-01
    provides: North Star architecture authority and signature-only runtime Protocol context
provides:
  - Additive neutral platform resource schemas for channel, run, artifact, identity, solution, bot, and channel binding contracts
  - Frozen slotted Python bindings for the new platform contract objects
  - Backward-compatible AdapterCapabilitySet extension and manifest schema support
  - Extended platform-contract self-check coverage for new schema/binding parity
affects: [phase-09, phase-10, phase-11, phase-12, phase-13, platform-contract, platform-runtime, contract-test-suite]

tech-stack:
  added: []
  patterns:
    - "Stdlib-only JSON Schema plus frozen slotted Python dataclass bindings"
    - "Additive adapter capability fields with legacy manifest compatibility"
    - "Run.status reuses AsyncTaskState values exactly"

key-files:
  created:
    - packages/platform-contract/src/platform_contract/schemas/channel_message.schema.json
    - packages/platform-contract/src/platform_contract/schemas/channel_delivery.schema.json
    - packages/platform-contract/src/platform_contract/schemas/run.schema.json
    - packages/platform-contract/src/platform_contract/schemas/run_event.schema.json
    - packages/platform-contract/src/platform_contract/schemas/run_step.schema.json
    - packages/platform-contract/src/platform_contract/schemas/tool_call.schema.json
    - packages/platform-contract/src/platform_contract/schemas/approval.schema.json
    - packages/platform-contract/src/platform_contract/schemas/artifact_record.schema.json
    - packages/platform-contract/src/platform_contract/schemas/session.schema.json
    - packages/platform-contract/src/platform_contract/schemas/tenant.schema.json
    - packages/platform-contract/src/platform_contract/schemas/workspace.schema.json
    - packages/platform-contract/src/platform_contract/schemas/solution_package_manifest.schema.json
    - packages/platform-contract/src/platform_contract/schemas/bot_instance.schema.json
    - packages/platform-contract/src/platform_contract/schemas/channel_binding.schema.json
  modified:
    - packages/platform-contract/src/platform_contract/enums.py
    - packages/platform-contract/src/platform_contract/events.py
    - packages/platform-contract/src/platform_contract/agent_adapter.py
    - packages/platform-contract/src/platform_contract/__init__.py
    - packages/platform-contract/src/platform_contract/schemas/common.schema.json
    - packages/platform-contract/src/platform_contract/schemas/agent_adapter_manifest.schema.json
    - packages/platform-contract/scripts/self_check.py
    - packages/platform-contract/tests/test_agent_adapter.py
    - packages/platform-contract/tests/test_self_check.py

key-decisions:
  - "Extend AdapterCapabilitySet additively so existing manifests and constructors remain valid while new run/runtime capabilities are expressible."
  - "Represent Run.status with the existing AsyncTaskState values instead of introducing a separate run-state enum."
  - "Keep ArtifactRecord as a top-level reference object while preserving nested AgentResult.artifacts unchanged."
  - "Use neutral skill and MCP descriptors in SolutionPackageManifest instead of Hermes SKILL.md runtime structure."

patterns-established:
  - "New standalone schemas include draft-2020-12 metadata, required stable identifiers/timestamps, and optional metadata/industry_context extension containers."
  - "Self-check schema/binding parity now covers both original five V2 events and new standalone platform contracts."

requirements-completed:
  - REQ-platform-contract-extension
  - REQ-platform-north-star

duration: 8 min
completed: 2026-06-29
---

# Phase 09 Plan 02: Platform Contract Schema And Binding Extension Summary

**Additive neutral platform schemas and stdlib Python bindings for channel, run, artifact, identity, solution, bot, and channel-binding contracts.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-06-28T18:40:46Z
- **Completed:** 2026-06-28T18:48:49Z
- **Tasks:** 4
- **Files modified:** 23

## Accomplishments

- Extended adapter capabilities with optional run invocation, stream, cancel, approval, live update, parallel task, and session memory support while preserving legacy constructor and manifest validation behavior.
- Added 14 standalone neutral JSON Schemas plus shared definitions for secret references, solution bindings, neutral skill descriptors, and MCP descriptors.
- Added frozen, slotted Python dataclasses and package exports for all new contract objects, including `Run`, `ChannelMessage`, `ChannelDelivery`, `ArtifactRecord`, `SolutionPackageManifest`, `NeutralSkillDescriptor`, and `McpServerDescriptor`.
- Extended `self_check.py` so new schema/binding parity is validated without requiring existing five-event fixtures to include new resource objects.

## Task Commits

Each task was committed atomically:

1. **Task 09-02-01: Add neutral enum values and additive adapter capability fields** - `d585944` (feat)
2. **Task 09-02-02: Add JSON Schemas for channel, run, artifact, identity, and solution contracts** - `8e574e9` (feat)
3. **Task 09-02-03: Add Python dataclass bindings and exports for new contract objects** - `779a9bd` (feat)
4. **Task 09-02-04: Update platform-contract self-checks for additive schema/binding parity** - `4eedd5d` (test)

## Files Created/Modified

- `packages/platform-contract/src/platform_contract/enums.py` - Added neutral approval, delivery, run event, and run step enum domains.
- `packages/platform-contract/src/platform_contract/agent_adapter.py` - Added defaulted `AdapterCapabilitySet` capability fields.
- `packages/platform-contract/src/platform_contract/events.py` - Added frozen, slotted dataclass bindings for new platform contract objects.
- `packages/platform-contract/src/platform_contract/__init__.py` - Exported new dataclasses and enum domains.
- `packages/platform-contract/src/platform_contract/schemas/common.schema.json` - Added shared reusable definitions for new neutral platform contracts.
- `packages/platform-contract/src/platform_contract/schemas/agent_adapter_manifest.schema.json` - Permitted optional extended capability fields without changing required legacy fields.
- `packages/platform-contract/src/platform_contract/schemas/*.schema.json` - Added standalone schemas for channel, run, tool, approval, artifact, identity, solution, bot, and channel binding objects.
- `packages/platform-contract/scripts/self_check.py` - Added new schema/binding parity checks while keeping original fixture requirements.
- `packages/platform-contract/tests/test_agent_adapter.py` - Added legacy and extended adapter capability compatibility tests.
- `packages/platform-contract/tests/test_self_check.py` - Added new schema parity, forbidden required field, and fixture compatibility tests.

## Decisions Made

- `Run.status` directly enumerates `queued`, `running`, `waiting_for_user`, `succeeded`, `failed`, and `cancelled`, matching `AsyncTaskState`.
- `ArtifactRecord` is a separate top-level contract object; `agent_result.schema.json` and `AgentResult.artifacts` remain unchanged.
- Channel binding and MCP descriptors use `secret_ref` / `secret_refs` references only, not plaintext secret values.
- New fixtures are not required in this plan; existing five-event fixtures remain valid and Plan 09-03 owns relationship fixture expansion.

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope change.

## Issues Encountered

None.

## Verification Results

- `python -m compileall packages/platform-contract/src packages/platform-contract/tests`
  - Result: PASS
  - Output included:
    - `Listing 'packages/platform-contract/src'...`
    - `Listing 'packages/platform-contract/src/platform_contract'...`
    - `Listing 'packages/platform-contract/src/platform_contract/schemas'...`
    - `Listing 'packages/platform-contract/tests'...`
- `PYTHONPATH=packages/platform-contract/src python -m unittest packages/platform-contract/tests/test_agent_adapter.py`
  - Result: PASS
  - Output: `Ran 9 tests in 0.000s` and `OK`
- `PYTHONPATH=packages/platform-contract/src python -m unittest packages/platform-contract/tests/test_self_check.py`
  - Result: PASS
  - Output: `Ran 12 tests in 0.041s`, `OK`, and `platform-contract self-check passed`
- `PYTHONPATH=packages/platform-contract/src python packages/platform-contract/scripts/self_check.py`
  - Result: PASS
  - Output: `platform-contract self-check passed`

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 09-03. The new schemas and Python bindings are available for platform-foundation relationship fixtures and replay coverage.

## Self-Check: PASSED

- Found created schema files for `ChannelMessage`, `ChannelDelivery`, `Run`, `RunEvent`, `RunStep`, `ToolCall`, `Approval`, `ArtifactRecord`, `Session`, `Tenant`, `Workspace`, `SolutionPackageManifest`, `BotInstance`, and `ChannelBinding`.
- Found summary file: `.planning/phases/09-architecture-contracts-schema-foundation/09-02-SUMMARY.md`
- Found task commit: `d585944`
- Found task commit: `8e574e9`
- Found task commit: `779a9bd`
- Found task commit: `4eedd5d`

---
*Phase: 09-architecture-contracts-schema-foundation*
*Completed: 2026-06-29*
