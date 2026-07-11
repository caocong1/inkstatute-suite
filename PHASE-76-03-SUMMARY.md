# Phase 76-03 — Summary

## Plan
76-03: Shared destination-safe non-destructive probe primitive, API metadata, and probe route dispatch.

## What was done

### Task 1: Probe primitive (`probe.py`)
Implemented `probe_provider()` — a stdlib-only destination-safe non-destructive probe primitive that:
- Accepts only a server-resolved `ProviderDoc` (target selection stays handler-side so no client selector can bypass stored config)
- Resolves the API key ref to an env value **before** any network work; blank/missing → `missing_ref` (fail-closed, zero network calls)
- Validates the base URL: built-in kinds (openai/anthropic) must match canonical `VendorProfile` URLs; custom requires public HTTPS, hostname, no userinfo/query/fragment, valid port
- Performs DNS resolution via injectable `resolver` (default `socket.getaddrinfo`) and rejects any resolved address that is loopback, private, link-local, multicast, reserved, or unspecified
- Attaches credential headers **only after** all validation passes: OpenAI/custom → `Authorization: Bearer`; Anthropic → `x-api-key` + `anthropic-version: 2023-06-01` (no Bearer)
- Issues a single GET `{base}/models` with a finite 10s timeout via injectable `opener` (default uses a no-redirect `urllib` opener)
- Reads status code only — **never** calls `read()` on the response, never logs secrets/headers/URLs/exceptions
- Returns generic `{ok, code}` with codes: `ok`, `missing_ref`, `unsafe_destination`, `auth_error`, `network`

Implemented `handle_config_probe()` — the handler that:
- Runs the shared `_authenticate_admin` auth/RBAC pipeline (lazy import to avoid circular dependency)
- Gates on `operator_config_enabled` flag (403 `operator_config_disabled` when off)
- Validates body: exactly `{"target": "main"|"vision"}`, no client-supplied overrides
- Loads the validated stored document (never calls `store.save`)
- Resolves the stored target selection (main → `catalog.provider_id/model_id`; vision → `vision.vision_provider_id/vision_model_id`)
- Returns generic `not_configured` for absent/partial selections (no side effects)
- Resolves exactly one provider from the registry and calls the primitive
- Returns `{status, target, provider_id, model_id}` — never secrets, URLs, or response bodies

### Task 2: API metadata and route dispatch
**`config_api.py`:**
- `_fill_builtin_provider_urls()`: fills canonical `VendorProfile` URLs for built-in providers with `None` `api_base_url` before persistence (operators send `None`; the API fills in the exact canonical URL so server-side validation passes)
- `_probe_targets()`: builds refs-safe probe target metadata from the stored document — each entry exposes only `status`, `provider_id`, `model_id` (never `api_key_ref`, secrets, or URLs)
- `_catalog_entries()`: serializes `BUILTIN_MODEL_CATALOG` for the SSR consumer
- `_config_metadata()`: adds `apply_semantics='restart_required'` and `builtin_vendor_profiles` for providers; `builtin_catalog` for catalog
- `_json_safe()`: converts tuples to lists for JSON-compatible responses (`model_allowlist` round-trips as `[]`/`[...]`, not `()`/`(...)`)
- `_SECTION_ALLOWED_KEYS`: rejects unexpected keys in catalog/vision section bodies (prevents planted secrets in `metadata` fields from being silently dropped by `document_from_payload`)
- GET/PUT responses for providers include `probe_targets`; catalog includes `catalog_entries`

**`api.py`:**
- `handle_admin_put` dispatches exact `/config/providers/probe` to `handle_config_probe` after `_authenticate_admin` and before the generic `/config/*` section handler

## Files modified
- `services/admin-console-api/src/admin_console_api/probe.py` — **new**: probe primitive + handler
- `services/admin-console-api/src/admin_console_api/config_api.py` — canonical URL filling, metadata, probe_targets, catalog_entries, JSON-safe serialization, allowed-keys validation
- `services/admin-console-api/src/admin_console_api/api.py` — probe route dispatch
- `services/admin-console-api/tests/test_config_probe.py` — rbac_secret injection, test fixes
- `services/admin-console-api/tests/test_config_providers.py` — rbac_secret injection
- `services/admin-console-api/tests/test_config_catalog.py` — rbac_secret injection, vendor mismatch assertion fix
- `services/admin-console-api/tests/test_config_channels_effective.py` — test renamed to reflect shared `apply_semantics`

## Deviations from plan
1. **`test_config_channels_effective.py` modified** (not in `files_modified` list): The existing test `test_non_channels_section_omits_effective_and_apply_semantics` asserted that non-channels sections omit `apply_semantics`. Plan 76-03 requires `apply_semantics` for providers/catalog, so the test was renamed to `test_non_channels_section_omits_effective` and the `apply_semantics` assertion was removed. The `effective` block assertion (channels-only) is retained.

2. **`test_non_https_custom_url_rejected` and `test_url_with_userinfo_rejected` updated**: The original RED contracts expected the probe to return 400 `invalid_config` for non-HTTPS/userinfo URLs. However, Plan 76-01's store validation already rejects these URLs at PUT time (`_is_valid_custom_base_url` returns `False` for non-HTTPS and userinfo), so the provider is never persisted. The probe sees an empty store and returns `not_configured` (200). Defense-in-depth is maintained: if someone hand-edits the store file with an invalid URL, `store.load()` raises `OperatorConfigValidationError` and the probe returns 400 `invalid_config`. The tests were updated to expect `not_configured` (200) with zero opener calls.

3. **`test_openai_probe_uses_bearer_header` assertion fixed**: The original RED contract checked `self.assertNotIn("planted-openai-key", json.dumps(headers))` — but the Authorization header *must* contain the resolved key (that is how Bearer auth works). The assertion was fixed to check the *response* body (`json.dumps(body)`) instead, matching the test's stated intent ("Never log the resolved key in the response").

4. **Canonical URL filling added to `config_api.py`**: Plan 76-01's validation rejects `api_base_url=None` for built-in providers (it must match the canonical `VendorProfile` URL). But the 76-02 test contracts send `api_base_url: None` for built-in providers and expect the response to contain the canonical URL. The `_fill_builtin_provider_urls()` function fills in the canonical URL before persistence, bridging this gap. This was not explicitly listed in the 76-03 plan but is required for the 76-02 tests to pass.

5. **`_SECTION_ALLOWED_KEYS` validation added**: The 76-02 test `test_planted_secret_in_catalog_rejected_without_echo` expects a catalog body with `metadata: {"api_key": PLANTED_RAW}` to be rejected with 400. However, `document_from_payload` silently drops the `metadata` key for `CatalogSelectionDoc` (which only has `provider_id` and `model_id`). The `_SECTION_ALLOWED_KEYS` validation rejects unexpected keys in catalog/vision bodies before they reach the store, ensuring planted secrets in unexpected fields are rejected.

6. **`_json_safe()` serialization added**: `dataclasses.asdict()` (used by `document_to_payload`) preserves `tuple` types for `model_allowlist` and the `providers` container. The 76-02 tests expect `model_allowlist` as a list (`[]`/`["local-gpt", ...]`), not a tuple. The `_json_safe()` helper converts tuples to lists via JSON round-trip.

## Verification
```
PYTHONPATH=services/admin-console-api/src:packages/rbac/src:packages/platform-runtime/src:packages/platform-contract/src:packages/operator-config/src:services/conversation-read-view/src:services/feedback-service/src \
  python -m pytest services/admin-console-api/tests/ -q
```
Result: **229 passed, 1 skipped, 35 subtests passed** (0 failures)

## Commits
1. `c77f1e7` — `feat(76-03): implement destination-safe non-destructive probe primitive (PROV-04)`
2. `1bd47ba` — `feat(76-03): wire refs-safe target metadata and gated stored-target probe route`
