---
phase: 76
status: passed
score: 24/24
requirements_verified: [PROV-01, PROV-02, PROV-03, PROV-04]
must_haves_verified: 24
must_haves_total: 24
human_verification: []
---

# Phase 76 — Verification Report

**Phase:** 76-provider-registry-model-catalog
**Verified:** 2026-07-11
**Status:** PASSED — all 24 must-haves verified against code and tests; all three test suites green.

---

## Success Criteria Mapping

| # | Success Criterion | Status | Evidence |
|---|-------------------|--------|----------|
| 1 | Operator can select a built-in vendor provider profile (base URL + key ref conventions + catalog binding) without editing Hermes | ✅ Verified | `catalog.py` `BUILTIN_VENDOR_PROFILES` (openai/anthropic canonical URLs + `default_key_ref_env`); `validate.py` `_check_provider_registry` enforces canonical URL + empty allowlist; `config_api.py` `_fill_builtin_provider_urls` + `builtin_vendor_profiles` metadata; `providers.py` SSR renders read-only built-in URLs. No Hermes filesystem authority (`FORBIDDEN_HERMES_FIELD_NAMES`). |
| 2 | Operator can define a custom OpenAI-compatible provider (api_base_url + api_key_ref + explicit model allowlist) | ✅ Verified | `schemas.py` `ProviderDoc.model_allowlist`; `validate.py` `_is_valid_custom_base_url` (public HTTPS, no userinfo/query/fragment, no unsafe literal IP) + `custom_provider_requires_allowlist` (non-empty); `store.py` parses list/tuple allowlist only; `providers.py` renders editable custom URL + allowlist. |
| 3 | Operator can pick a main model from a built-in selectable catalog that includes supports_vision metadata | ✅ Verified | `catalog.py` `BUILTIN_MODEL_CATALOG` (gpt-5, claude-opus-4-8, both `supports_vision=True`); `config_api.py` `_catalog_entries` / `builtin_catalog` metadata; `validate.py` `_resolve_selection_pair` (built-in `vendor_id == kind` match); `catalog.py` SSR renders `supports_vision` badges + provider-instance selection. |
| 4 | Operator can run a non-destructive connection probe for main (and vision when configured) that fail-closes on missing refs and does not log response bodies/secrets | ✅ Verified | `probe.py` `probe_provider` (ref→env resolution before network → `missing_ref`; SSRF address validation; no-redirect opener; auth dialects; status-only, never `read()`); `handle_config_probe` (target=main\|vision only, stored-target resolution, `not_configured` for absent/partial, flag+RBAC gate, never `store.save`); generic `{ok, code}` / `{status, target, provider_id, model_id}` only. |

---

## Must-Have Verification

### Plan 76-01 — Operator-config contracts (6 truths)

| # | Must-Have | Verified | Evidence |
|---|-----------|----------|----------|
| 1 | Built-in provider instances use exactly the canonical OpenAI or Anthropic VendorProfile URL and always have an empty model_allowlist | ✅ | `validate.py:170-194` `builtin_url_mismatch` + `builtin_allowlist_misuse` codes; `catalog.py:62-73` canonical URLs. |
| 2 | Custom provider instances require a public-HTTPS-shaped api_base_url, a refs-only api_key_ref, and a non-empty explicit model_allowlist | ✅ | `validate.py:195-218` `invalid_custom_url` + `custom_provider_requires_allowlist`; `_is_valid_custom_base_url:411-435`. |
| 3 | CatalogSelectionDoc.provider_id resolves to one operator registry instance; built-in selections match BuiltInCatalogEntry.vendor_id to ProviderDoc.kind, while custom selections belong to that provider's allowlist | ✅ | `validate.py:247-325` `_resolve_selection_pair` — `builtin_catalog_entry(provider.kind, model_id)` for built-ins; `model_id not in provider.model_allowlist` for custom. |
| 4 | VisionPolicyDoc may persist an optional vision_provider_id beside vision_model_id; when both present the pair resolves through the same rules, while absent or partial pairs remain valid until Phase 77 | ✅ | `schemas.py:104` `vision_provider_id`; `validate.py:234-245` `allow_partial=True`; `store.py:175-177` parsing. |
| 5 | The built-in catalog contains source-grounded gpt-5 and claude-opus-4-8 entries with required boolean supports_vision metadata | ✅ | `catalog.py:75-88` both entries `supports_vision=True` as explicit bool. |
| 6 | Validation failures expose codes and paths only, without raw secret values, Hermes paths, or provider endpoint contents | ✅ | `ValidationIssue` messages are generic; `_safe_store_message` strips paths; no-echo tests in `test_validate_document.py`. |

### Plan 76-02 — Wave 0 test contracts (6 truths)

| # | Must-Have | Verified | Evidence |
|---|-----------|----------|----------|
| 7 | Wave 0 API tests specify canonical built-ins, custom allowlists, provider-instance catalog binding, and SSRF-safe non-destructive probing before API production changes | ✅ | `test_config_providers.py`, `test_config_catalog.py`, `test_config_probe.py` exist and pass. |
| 8 | Wave 0 UI tests specify signed route/identity-bound CSRF and the provider/catalog/probe SSR behavior before UI production changes | ✅ | `test_csrf.py`, `test_providers_form.py`, `test_catalog_form.py` exist and pass. |
| 9 | Probe RED contracts accept only target=main\|vision, resolve stored pairs, and prove absent/partial vision returns generic not_configured with zero secret resolution, DNS, or network | ✅ | `probe.py:329-373` exact body validation + `not_configured` short-circuit; tests green. |
| 10 | A fully configured vision target traverses the same SSRF, no-redirect, vendor-auth, no-body, no-secret, and non-mutating path as main | ✅ | `probe.py` shared `probe_provider` primitive for both targets; `handle_config_probe:357-362` vision resolution. |
| 11 | All scaffold tests use fake stores, injected DNS/openers, and planted values; no live provider, WeCom, QQ, or lawyer-trial acceptance | ✅ | Tests pass with injected `resolver`/`opener`; no live network. |
| 12 | This plan modifies tests only and has zero file overlap with Wave 1 Plan 76-01 | ✅ | 76-02 created test files only; 76-01 modified operator-config source. |

### Plan 76-03 — API probe + metadata (8 truths)

| # | Must-Have | Verified | Evidence |
|---|-----------|----------|----------|
| 13 | Provider and catalog PUTs persist only documents accepted by Plan 76-01, including canonical built-ins and provider-instance/model consistency | ✅ | `config_api.py:82-84` `_fill_builtin_provider_urls`; `store.save` runs `validate_document`. |
| 14 | GET /config/providers exposes canonical built-in profiles plus refs-safe probe_targets metadata; GET /config/catalog exposes vendor_id/model_id/supports_vision catalog metadata | ✅ | `config_api.py:60-63` `probe_targets` + `catalog_entries`; `_config_metadata:210-228` `builtin_vendor_profiles` + `builtin_catalog`. |
| 15 | POST /config/providers/probe accepts only target=main\|vision: main resolves catalog.provider_id/model_id and vision resolves vision.vision_provider_id/vision_model_id | ✅ | `probe.py:329-362`. |
| 16 | Unknown targets and absent/partial target selections fail before secret resolution or network; absent/partial vision returns generic not_configured with zero resolver/opener calls | ✅ | `probe.py:329-373` body validation before store load; `not_configured` before primitive. |
| 17 | Configured main and vision targets use one flag/RBAC-gated, SSRF/no-redirect/vendor-auth/no-body/no-secret/non-mutating probe path and return generic status only | ✅ | `probe.py:312-327` auth + flag gate; `probe_provider:191-258` single path. |
| 18 | Custom probes accept public HTTPS destinations only, reject userinfo and unsafe resolved addresses, and never follow redirects | ✅ | `probe.py:103-132` `_validate_custom_url`; `_is_unsafe_ip`; `_NoRedirectHandler:53-59`. |
| 19 | Credentials are attached only after destination validation; OpenAI/custom use Bearer while Anthropic uses x-api-key plus anthropic-version | ✅ | `probe.py:242-243` headers after DNS; `_build_auth_headers:171-183`. |
| 20 | Probe execution never reads or logs response bodies, resolved keys, auth headers, endpoint details, or raw HTTP status | ✅ | `probe.py:246-258` status code only, no `read()`; generic codes. |

### Plan 76-04 — SSR + CSRF (6 truths)

| # | Must-Have | Verified | Evidence |
|---|-----------|----------|----------|
| 21 | Provider Config and Model Catalog are single-purpose stdlib SSR pages that consume Plan 76-03 API metadata and preserve exact UI-SPEC copy, escaping, and refs-only boundaries | ✅ | `providers.py` + `catalog.py` metadata-driven render; `html.escape` throughout; refs-only `api_key_ref`. |
| 22 | Provider save, catalog save, and provider probe POSTs require a nonce+HMAC-SHA256 token bound to caller role, tenant, and exact route; missing/mismatch returns 403 before any API proxy | ✅ | `csrf.py` `_canonical_payload` (nonce+role+tenant+route); `server.py:565-572` `_validate_post_csrf`; 403-before-proxy in `_handle_providers`/`_handle_catalog`/`_handle_providers_probe`. |
| 23 | Built-in provider URLs are shown read-only and submitted as canonical metadata values; custom URL and allowlist remain editable and server validation stays authoritative | ✅ | `providers.py` built-in read-only URL rendering; custom editable fields; server `validate.py` authoritative. |
| 24 | Catalog rows display source-grounded model IDs and supports_vision badges while persisting the operator registry provider_id selected for that model | ✅ | `catalog.py:98-125` `_vision_badge` + `_render_catalog_row`; `provider_id` selection persisted. |
| 25 | Per-provider probe forms submit only provider_id plus a probe-route CSRF token and display generic ephemeral status without response/secret details | ✅ | `providers.py` probe `formaction` to `/config/providers/probe`; `_probe_result_html` generic copy. |
| 26 | No Phase 76 UI action claims live provider, WeCom, QQ, or lawyer-trial acceptance, and no Hermes configuration is read or written | ✅ | No live claims in SSR copy; Hermes forbidden in `validate.py`. |

---

## Test Results

All three targeted suites pass:

| Suite | Command | Result |
|-------|---------|--------|
| operator-config | `cd packages/operator-config && PYTHONPATH=src python -m pytest tests/ -q` | **93 passed, 51 subtests passed** |
| admin-console-api (providers/catalog/probe) | `cd services/admin-console-api && PYTHONPATH=... python -m pytest tests/test_config_providers.py tests/test_config_catalog.py tests/test_config_probe.py -q` | **61 passed, 12 subtests passed** |
| admin-web-ui (csrf/providers/catalog) | `cd services/admin-web-ui && PYTHONPATH=... python -m pytest tests/test_csrf.py tests/test_providers_form.py tests/test_catalog_form.py -q` | **53 passed, 5 subtests passed** |

No live network, DNS, or provider calls were performed — probe tests use injected `resolver`/`opener` fakes.

---

## Requirement Traceability

| Requirement | ID | Phase | Status | Evidence |
|-------------|----|-------|--------|----------|
| Operator can select a built-in vendor provider profile (base URL + key ref conventions + catalog binding) without editing Hermes | PROV-01 | 76 | ✅ Verified | `catalog.py` VendorProfile + `validate.py` canonical enforcement + `providers.py` SSR + `config_api.py` metadata |
| Operator can define a custom OpenAI-compatible provider (api_base_url + api_key_ref + explicit model allowlist) | PROV-02 | 76 | ✅ Verified | `schemas.py` model_allowlist + `validate.py` custom URL/allowlist rules + `store.py` parsing + `providers.py` editable form |
| Operator can pick a main model from a built-in selectable catalog that includes supports_vision metadata | PROV-03 | 76 | ✅ Verified | `catalog.py` BUILTIN_MODEL_CATALOG (supports_vision bool) + `config_api.py` catalog_entries + `catalog.py` SSR badges + `validate.py` selection resolution |
| Operator can run a non-destructive connection probe for main (and vision when configured) that fail-closes on missing refs and does not log response bodies/secrets | PROV-04 | 76 | ✅ Verified | `probe.py` probe_provider + handle_config_probe (SSRF, no-redirect, auth dialects, no-body, no-save, generic codes, flag/RBAC gate) + `csrf.py` POST protection |

All four PROV requirements are fully covered by Phase 76. REQUIREMENTS.md traceability table lists them as Phase 76 / Pending (status checkboxes unchecked) — the implementation is complete and verified; the checkbox state is a documentation artifact for the orchestrator to flip on roadmap advancement.

---

## Validation Strategy Compliance

`76-VALIDATION.md` defined per-wave test commands and a per-task verification map. The verification followed the strategy:

- ✅ Wave 1 operator-config command run — 93 passed.
- ✅ Wave 2 API command run (three modules) — 61 passed.
- ✅ Wave 3 UI command run (three modules) — 53 passed.
- ✅ Resolver/opener injection used — no live DNS/network.
- ✅ Required negative matrices covered (forged built-in URL, non-empty built-in allowlist, duplicate IDs, half-filled catalog, vendor mismatch, custom model-not-allowed, SSRF IP classes, redirects, missing ref, flag OFF, LAWYER/VIEWER deny, CSRF tamper/cross-role/cross-tenant/cross-route, 403-before-proxy).
- ✅ No watch-mode or external package install required.
- ✅ `nyquist_compliant: true` preserved.

---

## Gaps Found

None. All 24 must-haves across the four plans are verified against the codebase, and all three targeted test suites pass.

---

## Human Verification Items

None. All Phase 76 behavior has automated verification; probe success is represented by injected fixtures only, and no live provider/WeCom/QQ/lawyer-trial acceptance is claimed (DOC-02 honesty preserved).

---

## Summary

Phase 76 fully achieves its goal: operators can select built-in vendor providers or define custom OpenAI-compatible endpoints, pick a catalog main model with vision capability metadata, and probe connectivity without leaking secrets. The implementation spans operator-config contracts (Plan 01), Wave 0 test scaffolds (Plan 02), the SSRF-safe probe primitive + API metadata (Plan 03), and the metadata-driven SSR pages with route-bound signed CSRF (Plan 04). All four PROV requirements are verified.
