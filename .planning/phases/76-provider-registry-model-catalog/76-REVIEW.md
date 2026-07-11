---
phase: 76
status: findings
depth: standard
files_reviewed: 14
findings:
  critical: 0
  warning: 3
  info: 5
---

# Phase 76 Code Review — Provider Registry & Model Catalog

Reviewed all 14 production source files listed in the phase SUMMARY key-files.
Test files were skimmed for correctness but are not individually listed below
unless they surfaced a source-level concern.

## Findings

### Warning 1 — CSRF signing key uses RBAC secret, contradicting module docstring

- **Severity:** Warning
- **File:** services/admin-web-ui/src/admin_web_ui/csrf.py:9-17, 52-56; services/admin-web-ui/src/admin_web_ui/server.py:641,776,886,564
- **Category:** Security / Quality
- **Description:** The `csrf.py` module docstring states an explicit security
  invariant: *"The signing key is generated once at module import with
  `secrets.token_bytes` and is never derived from or exposed as the RBAC
  secret."* The `issue_csrf_token` docstring further claims the `signing_key`
  parameter *"exists only for deterministic tests — default callers use the
  private process key."* However, every production caller in `server.py`
  (`_handle_providers`, `_handle_probe`, `_handle_catalog`, and
  `_validate_post_csrf`) passes `signing_key=rbac_secret`, so production CSRF
  tokens are HMAC-signed with the RBAC token secret, not the process-local key.
  This is a direct contradiction of the stated invariant. Using a shared secret
  for CSRF signing is cryptographically sound and arguably *more* correct for
  multi-process deployments (see Info 4), but the documentation is misleading
  and could cause a future maintainer to remove the `signing_key` parameter or
  assume the process key is in use.
- **Recommendation:** Reconcile the docstring with the actual production
  behaviour. Either (a) update `csrf.py` to document that `signing_key` is used
  in production to provide cross-process token validity and that the process
  key is only a test/fallback default, or (b) if the invariant is intentional,
  stop passing `rbac_secret` and use the process key (accepting the
  multi-process limitation). Option (a) is recommended.

### Warning 2 — TOCTOU DNS rebinding gap in probe SSRF check

- **Severity:** Warning
- **File:** services/admin-console-api/src/admin_console_api/probe.py:222-249
- **Category:** Security
- **Description:** `probe_provider` resolves the hostname via
  `socket.getaddrinfo`, validates that every resolved address is public-safe
  (`_check_resolved_addresses`), and then passes the **hostname** (not a pinned
  IP) to the urllib opener at line 239. urllib performs its own DNS resolution
  inside `opener.open(...)`, so a DNS rebinding attack can return a public IP
  during the validation resolution and a private/loopback IP during the actual
  HTTP connection, bypassing the SSRF address check. The no-redirect handler
  and credential-after-validation ordering are correct, but the address
  validation is not bound to the connection that actually carries credentials.
- **Recommendation:** Pin the validated resolved IP for the connection. The
  stdlib approach is to connect to the validated IP directly with a synthetic
  `Host` header and SNI set to the original hostname (e.g. via a custom
  `HTTPConnection` or by rewriting the URL to `https://<ip>/models` with
  `Host: <hostname>`). If that is too invasive for Phase 76, document the
  residual DNS-rebinding risk in `76-RESEARCH.md` and plan a fix for the
  Phase 77 probe hardening pass. At minimum, consider re-resolving and
  re-checking immediately before the request, or switching to a single
  `socket.create_connection` with the validated IP.

### Warning 3 — Channels POST route has no CSRF validation

- **Severity:** Warning
- **File:** services/admin-web-ui/src/admin_web_ui/server.py:400,402-509
- **Category:** Security
- **Description:** `_handle_channels` generates `csrf_token =
  secrets.token_urlsafe(16)` (a random, unbound string) and passes it to the
  renderer, but the POST branch (lines 402–509) never calls
  `_validate_post_csrf` and parses the form body directly. The new
  `csrf.py` module — added in this phase — is used correctly by the providers,
  catalog, and probe routes, but the channels route was left with a decorative
  token and no validation. The `csrf.py` docstring notes that *"Phase 78 owns
  the complete existing-surface CSRF audit; this module fully protects the new
  Phase 76 POST routes only,"* so this gap is explicitly deferred, but
  `/config/channels` is a state-changing POST that persists credential refs and
  the gap is present in the same phase that introduced CSRF protection.
- **Recommendation:** If the deferral is intentional, add a code comment in
  `_handle_channels` referencing the Phase 78 audit so the gap is not
  forgotten. If Phase 76 has budget, apply `issue_csrf_token` /
  `_validate_post_csrf` to the channels route now for consistency.

### Info 1 — Double HTML-escaping in probe result rendering

- **Severity:** Info
- **File:** services/admin-web-ui/src/admin_web_ui/providers.py:118,128
- **Category:** Bug
- **Description:** In `_probe_result_html`, the `not_configured` branch builds
  `copy = f"Probe target '{_esc(target)}' is not configured…"` (escaping
  `target` inside the f-string), then line 128 emits
  `f'<p class="{css}">{_esc(copy)}</p>'`, escaping the already-escaped `copy`
  a second time. The literal single quotes around `target` become `&#x27;` in
  the final HTML. This is benign in practice because `target` is always
  `"main"` or `"vision"` (validated upstream), but it is a real double-escape
  defect that would garble output if the target string ever contained special
  characters.
- **Recommendation:** Escape `target` only once. Build `copy` with the raw
  target and let the final `_esc(copy)` handle it:
  `copy = f"Probe target '{target}' is not configured…"`.

### Info 2 — Probe UI handler always returns 200 even on probe error

- **Severity:** Info
- **File:** services/admin-web-ui/src/admin_web_ui/server.py:851-864
- **Category:** Bug / UX
- **Description:** `_handle_probe` extracts `probe_result` from
  `probe_data.get("data")`. When the probe handler returns an error response
  (e.g. 403 forbidden, 500 store error), the response body has no `"data"` key,
  so `probe_result` is `None`. The handler then returns `200` with the
  providers page re-rendered and no probe-result banner, giving the operator
  no indication that the probe failed or why. A successful probe and a
  silently-failed probe produce visually identical pages.
- **Recommendation:** When `probe_status != 200` or `probe_result` is `None`,
  render a generic probe-failure banner (e.g. `PROBE_RESULT_FAIL_GENERIC`) so
  the operator sees feedback. Consider returning the probe HTTP status as the
  page status when it is an auth/flag error.

### Info 3 — probe._validate_custom_url omits literal-IP rejection

- **Severity:** Info
- **File:** services/admin-console-api/src/admin_console_api/probe.py:103-123
- **Category:** Security / Quality
- **Description:** The probe's `_validate_custom_url` checks scheme, hostname,
  userinfo, query, fragment, and port — but does not reject unsafe literal IP
  hostnames (loopback/private/link-local/etc.) the way
  `validate.py`'s `_is_valid_custom_base_url` does (lines 436-449). A custom
  URL like `https://127.0.0.1/v1` would pass `_validate_custom_url` as a
  defense-in-depth layer. The subsequent DNS resolution check
  (`_check_resolved_addresses`) does catch literal IPs because
  `getaddrinfo("127.0.0.1", …)` returns the loopback address, so this is not
  exploitable, but the two validators are inconsistent.
- **Recommendation:** Add the same `ipaddress.ip_address(hostname)` unsafe-IP
  rejection to `_validate_custom_url` so both validation surfaces enforce the
  same rule, or factor the shared URL check into a single helper.

### Info 4 — Process-local CSRF key breaks multi-process when rbac_secret is None

- **Severity:** Info
- **File:** services/admin-web-ui/src/admin_web_ui/csrf.py:35; services/admin-web-ui/src/admin_web_ui/server.py:275-277
- **Category:** Bug
- **Description:** When RBAC is disabled, `server.py` sets
  `identity = Identity(role=Role.ADMIN, tenant_id="default")` and `secret` is
  `None`. CSRF tokens are then signed and validated with the module-level
  `_PROCESS_KEY`, which is a fresh `secrets.token_bytes(32)` per process. In a
  multi-worker deployment (e.g. gunicorn with multiple workers), a GET request
  served by worker A issues a token under `_PROCESS_KEY_A`; if the subsequent
  POST lands on worker B, validation uses `_PROCESS_KEY_B` and the token fails.
  This only manifests when `rbac_secret` is `None` (RBAC disabled) and the
  server runs multi-process.
- **Recommendation:** Document this limitation, or derive a stable
  non-secret-derived key (e.g. from a dedicated `CSRF_SIGNING_KEY` env var)
  when `rbac_secret` is `None`. The current production path (RBAC enabled,
  `rbac_secret` set) is unaffected because the shared secret is used.

### Info 5 — Empty provider_id duplicates not flagged by validator

- **Severity:** Info
- **File:** packages/operator-config/src/inkstatute_operator_config/validate.py:147-159
- **Category:** Quality
- **Description:** `_check_provider_registry` only adds non-empty `provider_id`
  values to the `seen` set and checks for duplicates. Multiple providers with
  an empty `provider_id` coexist without a duplicate (or emptiness) error. The
  SSR form parser drops blank `provider_id` cards, so this is unlikely to
  reach the store in practice, but a direct API PUT with two empty-id
  providers would be accepted.
- **Recommendation:** Consider adding an explicit `empty_provider_id` validation
  issue, or document that empty IDs are intentionally permitted (they are
  inert for catalog/vision resolution).

## Summary

The phase introduces a well-structured provider registry, model catalog, and
non-destructive connection probe with strong refs-only discipline, HTML
escaping on all SSR surfaces, CSP headers, body-size caps, and generic
no-secret error codes. The CSRF module is correctly implemented (HMAC-SHA256,
`compare_digest`, identity+route binding, fail-closed validation) and is
applied to all new POST routes. The probe primitive correctly orders
destination validation before credential construction, disables redirects, and
never reads response bodies.

The three warnings are: (1) a documentation/invariant contradiction around the
CSRF signing key that should be reconciled, (2) a DNS-rebinding TOCTOU gap in
the probe SSRF check that should be documented or pinned, and (3) the channels
POST route retaining no CSRF validation while sibling routes now enforce it.
None are critical, but all three should be addressed before the phase is
considered production-hardened.
