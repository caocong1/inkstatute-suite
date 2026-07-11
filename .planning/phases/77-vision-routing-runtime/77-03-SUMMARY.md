---
phase: 77-vision-routing-runtime
plan: 03
type: execute
wave: 2
depends_on:
  - 77-01
status: complete
commits:
  - ab14491
files_created:
  - packages/platform-runtime/src/platform_runtime/vision_router.py
  - packages/platform-runtime/tests/test_vision_router.py
files_modified:
  - packages/platform-runtime/src/platform_runtime/__init__.py
requirements:
  - VIS-02
  - VIS-03
  - VIS-04
---

# Plan 77-03 Summary — Platform-runtime vision router

## What was built

A pure decision function `VisionRouter.decide()` in
`packages/platform-runtime/src/platform_runtime/vision_router.py` that routes
image-bearing turns according to operator vision policy, plus public
re-exports and a comprehensive test suite.

### Public API

- `VisionRoute` — `StrEnum` with `multimodal_main`, `vision_then_main`,
  `fail_closed`, `text_only`.
- `VisionRoutingDecision` — frozen slotted dataclass: `route`, `notice`,
  `reason`, `metadata`.
- `VisionRouter.decide(turn, vision_policy, *, main_supports_vision, vision_pair_configured)`
  — pure decision function (no I/O, no model invocation, no secret resolution,
  no image fetching).
- `has_image_attachments(turn)` — detects images via `kind == "image"` or
  `mime_type` starting with `image/` (case-insensitive); never reads URIs or
  raw bytes.
- `FAIL_CLOSED_NOTICE` — InkStatute-owned service notice constant that passes
  through `DefaultAssistantOutputBoundary` unmodified.

### Routing matrix

| Condition | Route | Reason |
|---|---|---|
| No image attachments (any mode) | `text_only` | `no_image_attachments` |
| Image + `auto`/None + main supports vision | `multimodal_main` | `main_supports_vision` |
| Image + `auto`/None + no main vision + vision pair | `vision_then_main` | `vision_then_main_mix` |
| Image + `auto`/None + no path | `fail_closed` | `no_vision_capable_path` |
| Image + `always_preprocess` + vision pair | `vision_then_main` | `always_preprocess_vision_mix` |
| Image + `always_preprocess` + no pair | `fail_closed` | `no_vision_pair_configured` |
| Image + `main_only` + main supports vision | `multimodal_main` | `main_only_supports_vision` |
| Image + `main_only` + no main vision | `fail_closed` | `main_only_no_vision_support` |
| Image + unsupported routing_mode | `fail_closed` | `unsupported_routing_mode` |

## Design decisions

- **No direct operator-config runtime dependency**: the router accepts a
  duck-typed `_VisionPolicyLike` Protocol (`routing_mode`, `vision_provider_id`,
  `vision_model_id`) rather than importing `inkstatute_operator_config`. A
  `TYPE_CHECKING` import of `VisionPolicyDoc` is kept for typing only. This
  keeps platform-runtime free of a direct operator-config runtime dependency.
- **`main_supports_vision` and `vision_pair_configured` are caller-resolved
  bools**: the caller resolves `supports_vision` from the catalog and the
  vision-pair completeness, keeping the router a pure decision function.
- **Reference-first metadata**: decision `metadata` carries only `image_count`
  (integer) and `reason` codes — never raw image bytes, base64 data, URIs, or
  provider endpoint details (VIS-03).
- **Output-boundary-safe fail-closed**: `FAIL_CLOSED_NOTICE` contains no
  provider names, model names, stack traces, tokens, or quota language, so it
  passes through `DefaultAssistantOutputBoundary.apply()` with `ALLOW` (VIS-04).
- **Source-text hygiene**: the router source contains none of the forbidden
  leak words (`Hermes`, `WeCom`, `lawfirm`, `gateway`, `.hermes`) checked by the
  existing `test_runtime_source_does_not_embed_concrete_leak_examples` test.

## Test results

```
cd packages/platform-runtime && PYTHONPATH=src:../../packages/platform-contract/src \
  python -m pytest tests/test_vision_router.py -q
24 passed, 7 subtests passed
```

Full platform-runtime suite: `399 passed, 3 skipped, 182 subtests passed`.

### Test coverage

- Image detection: kind-based, mime-type-based, case-insensitive, empty list,
  non-image mime types, None mime type.
- Fail-closed notice: no provider/trace/token language; passes through output
  boundary with `ALLOW`.
- Decision shape: `VisionRoute` has exactly four values; `VisionRoutingDecision`
  is frozen.
- Routing logic: all three modes (`auto`, `always_preprocess`, `main_only`),
  text-only turns, `routing_mode=None` default-to-auto, unsupported
  `routing_mode` fail-closed without crashing or leaking the invalid value.
- Reference-first safety: metadata contains `image_count` (integer) and never
  raw bytes, base64, URIs, or endpoint details.

## Files

- **Created**: `packages/platform-runtime/src/platform_runtime/vision_router.py`
- **Created**: `packages/platform-runtime/tests/test_vision_router.py`
- **Modified**: `packages/platform-runtime/src/platform_runtime/__init__.py`
  (re-exports `VisionRoute`, `VisionRouter`, `VisionRoutingDecision`)

## Commit

- `ab14491` — `feat(77-03): platform-runtime vision router with image detection and fail-closed notice`

## Deviations from plan

None. The plan was executed as specified. The `_policy` test helper used
`types.SimpleNamespace` instead of a nested class to avoid Python closure
scoping issues in class bodies — this is a test-fixture implementation detail
that does not affect the plan's behavior or acceptance criteria.
