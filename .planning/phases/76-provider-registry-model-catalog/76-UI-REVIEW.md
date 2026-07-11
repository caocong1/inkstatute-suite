---
phase: 76
status: needs_attention
pillars:
  visual_hierarchy: 9
  color_contrast: 10
  interaction_design: 8
  accessibility: 9
  content_copy: 8
  security_boundaries: 8
average: 8.7
---

# Phase 76 — UI Review (6-Pillar Retroactive Audit)

> Retroactive 6-pillar visual audit of the Phase 76 Provider Registry + Model
> Catalog SSR frontend. Audited against `76-UI-SPEC.md` (the approved design
> contract). All file:line references point to
> `services/admin-web-ui/src/admin_web_ui/`.

## Files Reviewed

| File | Role |
|------|------|
| `csrf.py` | Signed CSRF tokens (HMAC-SHA256, identity+route bound) |
| `providers.py` | Provider registry SSR page (PROV-01, PROV-02, PROV-04) |
| `catalog.py` | Model catalog SSR page (PROV-03) |
| `server.py` | Route dispatch, CSRF enforcement, POST handlers |
| `dashboard.py` | Page template, nav, CSS, shared primitives |
| `api_client.py` | API client proxy (GET/PUT delegation) |

---

## Pillar 1 — Visual Hierarchy

**Score: 9/10**

### What's Correct

- **Two single-purpose pages** — Provider Registry and Model Catalog are
  separate routes, each inside the existing `.main` → `.section` shell, matching
  the spec's "single composition per page" rule
  (`dashboard.py:157-162`, `providers.py:430-484`, `catalog.py:230-280`).
- **Provider Registry layout** follows the spec's vertical order: flash →
  probe result → restart notice → provider cards → trailing blank card →
  probe section → primary CTA (`providers.py:379-427`).
- **Model Catalog layout** follows the spec: flash → restart notice →
  selection status line → catalog panel card → primary CTA
  (`catalog.py:182-227`).
- **Nav links** added after Channel Config: "Provider Config" →
  `/config/providers`, "Model Catalog" → `/config/catalog`
  (`dashboard.py:79-80`). Existing links preserved.
- **Spacing scale** matches the spec's token table:
  - `.main` padding `2rem` (32px = xl) (`dashboard.py:105`)
  - `.section` padding `1.5rem` (24px = lg) (`dashboard.py:106`)
  - `.card` padding `1rem` (16px = md) (`dashboard.py:112`)
  - `.provider-panel` margin-bottom `3rem` (48px = 2xl) (`dashboard.py:139`)
  - `.probe-result` margin-bottom `1.5rem` (24px = lg) (`dashboard.py:144`)
  - `.catalog-row` padding `1rem 0` (16px = md) (`dashboard.py:142`)
  - `.field` margin `0.5rem 0` (8px = sm) (`dashboard.py:118`)
  - `.field label` margin-bottom `0.25rem` (4px = xs) (`dashboard.py:120`)
  - `.badge-vision-*` padding `4px 8px` (`dashboard.py:140-141`)
- **Typography lock** carried from Phase 75: `.section h2, .card h3` set to
  `1.125rem / 600 / line-height 1.2` (`dashboard.py:138`), overriding the
  earlier `1.1rem` declaration. `.header h1` at `1.25rem` (Display)
  (`dashboard.py:101`). Field labels at `0.875rem / 600` (`dashboard.py:120`).
- **Max content width** `1200px` centered (`dashboard.py:105`).
- **Cards as interaction containers** — provider panels and catalog panel use
  `.card` class (`providers.py:226`, `catalog.py:211`).
- **Trailing blank "New provider" card** rendered server-side, no JS
  (`providers.py:405-415`), matching the spec's "Add provider" MVP approach.

### What Needs Improvement

- **Redundant `.section h2` font-size** — `dashboard.py:107` declares
  `font-size: 1.1rem` and `dashboard.py:138` overrides with `1.125rem`. The
  later rule wins (correct output), but the conflicting declaration is
  confusing. Recommend removing the `font-size: 1.1rem` from line 107 to avoid
  ambiguity. (Inherited from Phase 75, not a Phase 76 regression.)
- **`.nav-link` at `0.9rem`** (`dashboard.py:103`) — spec says Label =
  `0.875rem` (14px). `0.9rem` = 14.4px. Minor inherited Phase 75 deviation.

---

## Pillar 2 — Color & Contrast

**Score: 10/10**

### What's Correct

- **Full palette compliance** — every color value matches the spec's 60/30/10
  palette:
  - Dominant `#f5f5f5` background (`dashboard.py:99`)
  - Secondary `#ffffff` sections, `#fafafa` cards, `#1a1a2e` header,
    `#16213e` nav, `#0f3460` identity (`dashboard.py:100,102,112,114`)
  - Accent `#aaccff` for nav links, identity text, focus outlines only
    (`dashboard.py:103,114,129-131,146`)
  - Destructive `#c0392b` for `.error` and `.status-err` only
    (`dashboard.py:115,117`)
  - Success `#27ae60` for `.status-ok` and vision-capable badge
    (`dashboard.py:116,140`)
  - Muted `#888` for `.empty` states (`dashboard.py:113`)
  - Key muted `#555` for field labels and table keys (`dashboard.py:110,120`)
- **Accent scarcity** — accent `#aaccff` is reserved for nav links, identity
  bar, and `:focus-visible` outlines only. Primary submit and probe buttons use
  navy `#1a1a2e` fill + white text (`dashboard.py:132-135`), not accent. Probe
  buttons reuse `.btn-primary` (`providers.py:334,349`). ✓
- **Carried Phase 75 fix applied** — routine OFF / "not set" / "not configured"
  states use muted `.empty` (`#888`), not destructive red:
  - `_ref_status` returns `"empty"` for not-configured refs (`providers.py:99`)
  - Vision-not-capable badge uses `.badge-vision-no` with `#888`
    (`dashboard.py:141`)
  - Probe `not_configured` status uses `.empty` (`providers.py:119`)
  - Catalog unset selection uses `.empty` (`catalog.py:199`)
- **Flag-off uses `.error` (red)** — correctly reserved for actual errors per
  spec ("Reserve `status-err` red for actual errors: probe failure, invalid
  ref, flag-off") (`providers.py:384-385`, `catalog.py:187-188`).
- **Focus-visible outlines** — `2px solid #aaccff` on ref-inputs, checkboxes,
  btn-primary, and selects (`dashboard.py:129-131,146`).

### What Needs Improvement

- None. Color usage is fully spec-compliant.

---

## Pillar 3 — Interaction Design

**Score: 8/10**

### What's Correct

- **Kind selector** is a `<select>` with `<label for=…>` "Provider kind"
  (`providers.py:196-203`). Options are fixed vendor IDs + "custom"
  (`providers.py:183-192`).
- **Built-in vendor** renders `api_base_url` as read-only `<span>` text, not an
  input (`providers.py:254-262`). ✓
- **Custom provider** renders `api_base_url` as editable `text` input with
  `autocomplete="off"` and placeholder `https://api.openai.com/v1`
  (`providers.py:263-273`). ✓
- **provider_id** always editable text (`providers.py:232-239`). ✓
- **enabled checkbox** defaults unchecked, uses `<label class="field-check">`
  wrapping pattern (`providers.py:244-251`). ✓
- **api_key_ref** is `type="text"` (not password), `autocomplete="off"`,
  placeholder `env:INKSTATUTE_PROVIDER_OPENAI_KEY` (`providers.py:283-285`). ✓
- **Model allowlist** read-only note for built-in, editable text for custom
  (`providers.py:292-312`). ✓
- **Trailing blank card** for adding providers — no JS required
  (`providers.py:405-415`). ✓
- **Single form, no nested forms** — probe buttons use `formaction` attribute
  inside the same `<form>` (`providers.py:333-335,348-350`). ✓
- **Catalog radio rows** use `<label class="field-check">` wrapping radio +
  model_id + vision badge (`catalog.py:119-125`). ✓
- **Provider selector** hidden when one provider, `<select>` when multiple
  (`catalog.py:134-156`). ✓
- **Save buttons disabled** when flag off or read-only (`providers.py:421-424`,
  `catalog.py:221-225`). ✓
- **Full page reload after POST** — no SPA routing, standard form submission.
  ✓

### What Needs Improvement

- **Probe button labels deviate from spec** — spec copy is "Probe connection"
  but implementation renders "Probe connection (main)" and
  "Probe connection (vision)" (`providers.py:335,350`). The `(main)`/`(vision)`
  suffix is not in the copy contract. While functionally necessary to
  distinguish targets, the spec should be amended or the labels should match.
- **Probe `not_configured` status copy** is not in the UI-SPEC copy contract.
  The implementation renders "Probe target '{target}' is not configured.
  Select a main model in Model Catalog first." (`providers.py:118`). This is a
  reasonable addition but should be added to the spec.
- **Probe "target not_configured" inline messages** — "Main probe target:
  not_configured" and "Vision probe target: not_configured"
  (`providers.py:339,354`) use non-spec copy and snake_case identifiers
  (`not_configured`) visible to operators. Should use human-friendly text.
- **CRITICAL: Probe button will always return 403** — The probe button submits
  the providers form (which contains a CSRF token bound to
  `/config/providers`) to `/config/providers/probe` via `formaction`. The
  `_handle_probe` handler validates the CSRF token against `_PROBE_PATH`
  (`server.py:784-785`), but the token was issued for `_PROVIDERS_PATH`
  (`server.py:647`). Since CSRF tokens are route-bound, the validation will
  always fail. The `probe_csrf_token` parameter exists in
  `render_providers_form`/`render_providers_page` (`providers.py:364,436`) but
  is never rendered into the HTML and never passed by the server
  (`server.py` — grep for `probe_csrf_token` returns zero matches). This makes
  the probe feature non-functional. See Pillar 6 for details.

---

## Pillar 4 — Accessibility

**Score: 9/10**

### What's Correct

- **`<html lang="en">`** on every page (`dashboard.py:93`).
- **Viewport meta tag** present (`dashboard.py:96`).
- **Label associations** — every editable input, select, and checkbox has a
  `<label for=…>` with human text:
  - Kind selector: `<label for="providers[N].kind">Provider kind</label>`
    (`providers.py:197-198`)
  - provider_id: `<label for="providers[N].provider_id">Provider ID</label>`
    (`providers.py:235-236`)
  - enabled: `<label class="field-check" for="providers[N].enabled">`
    (`providers.py:246`)
  - api_base_url (custom): `<label for="providers[N].api_base_url">`
    (`providers.py:268`)
  - api_key_ref: `<label for="providers[N].api_key_ref">` (`providers.py:282`)
  - model_allowlist (custom): `<label for="providers[N].model_allowlist">`
    (`providers.py:307`)
  - catalog provider select: `<label for="provider_id">Provider</label>`
    (`catalog.py:151-152`)
- **Radio rows** use `<label class="field-check">` wrapping radio + model name
  + badge — whole row is a single clickable target with accessible name
  (`catalog.py:120-124`). This is the carried Phase 75 fix. ✓
- **Touch targets ≥ 44×44px**:
  - `.field-check` min-height/min-width 44px (`dashboard.py:121`)
  - `.btn-primary` min-height 44px (`dashboard.py:134`)
  - `select` min-height 44px (`dashboard.py:145`)
  - `.catalog-row` min-height 44px (`dashboard.py:142`)
- **Focus indicators** — `:focus-visible` outline `2px solid #aaccff` on
  ref-inputs, checkboxes, btn-primary, and selects (`dashboard.py:129-131,146`).
- **`role="status"`** on flash messages for screen reader announcements
  (`providers.py:106`, `catalog.py:67`).
- **Status uses words plus color** — "Vision: supported" / "Vision: not
  supported" / "Configured (ref stored)" / "Not set" — never color alone
  (`catalog.py:30-31`, `providers.py:39-40`).
- **Checkbox** has both explicit `for`/`id` and implicit wrapping label
  (`providers.py:246-249`).

### What Needs Improvement

- **Read-only field labels lack `for` attributes** — built-in `api_base_url`
  (`providers.py:259`) and built-in model allowlist (`providers.py:295`) use
  `<label>` without `for=` because there is no form control to associate with
  (the value is in a `<span>`). While technically harmless (no control to
  associate), consider using `<span class="field-label">` instead of `<label>`
  for read-only fields to avoid confusing screen readers that expect a
  labelable control.
- **Probe button accessible names** — "Probe connection (main)" and
  "Probe connection (vision)" are descriptive, but the spec copy is just
  "Probe connection". No `aria-label` override is provided.

---

## Pillar 5 — Content & Copy

**Score: 8/10**

### What's Correct

- **Providers page copy** — all exact strings match the UI-SPEC copy contract:
  - "Save provider config" (`providers.py:26`)
  - "Provider Config" title/nav (`providers.py:25,27`)
  - "Custom OpenAI-compatible" (`providers.py:29`, used at `191`)
  - "Choose a built-in vendor profile or define a custom OpenAI-compatible
    endpoint." (`providers.py:30-32`, used at `201`)
  - "API base URL" (`providers.py:33`, used at `259,268`)
  - "API key ref" (`providers.py:34`, used at `282`)
  - "Secret reference only (`env:NAME`, bare `ENV_NAME`, or
    `secret://path/segments`). Never paste raw tokens." (`providers.py:35-38`,
    used at `287,420`)
  - "Configured (ref stored)" / "Not set" (`providers.py:39-40`)
  - "Model allowlist" (`providers.py:41`, used at `295,307`)
  - "Comma-separated model IDs this provider may serve. Built-in vendors ship a
    preset catalog; custom providers require an explicit allowlist."
    (`providers.py:42-45`, used at `310`)
  - "Probe connection" (`providers.py:47`)
  - "Non-destructive connectivity check. Fail-closes on missing refs. Never
    logs response bodies or resolved secrets." (`providers.py:48-51`, used at
    `325`)
  - "Probe succeeded — provider reachable (no response body logged)."
    (`providers.py:52-54`, used at `115`)
  - "No providers configured yet" (`providers.py:64`, used at `393`)
  - "Defaults are OFF. Add a built-in vendor or custom OpenAI-compatible
    provider below, then Save provider config." (`providers.py:65-68`, used at
    `394`)
  - "Provider config saved. Restart runtime to apply (MVP — no hot-reload)."
    (`providers.py:73-75`)
  - All error strings (validation, flag-off, forbidden, generic)
    (`providers.py:76-85`)
  - Restart notice (`providers.py:69-72`, used at `390`)
- **Catalog page copy** — all exact strings match:
  - "Save catalog selection" (`catalog.py:25`)
  - "Model Catalog" title/nav (`catalog.py:24,26`)
  - "Main model selection" (`catalog.py:27`, used at `212`)
  - "Main model: {provider_id} / {model_id}" (`catalog.py:28`, used at
    `194-196`)
  - "No main model selected" (`catalog.py:29`, used at `199`)
  - "Vision: supported" / "Vision: not supported" (`catalog.py:30-31`)
  - "No main model selected" (empty heading) (`catalog.py:32`, used at `214`)
  - "Pick a main model from the built-in catalog below. Vision capability is
    shown per model for Phase 77 routing." (`catalog.py:33-36`, used at `215`)
  - "Catalog selection saved. Restart runtime to apply (MVP — no hot-reload)."
    (`catalog.py:42-44`)
  - All error strings (`catalog.py:45-54`)
- **No live acceptance claims** — both module docstrings explicitly state "No
  live provider, WeCom, QQ, or lawyer-trial acceptance is claimed."
  (`providers.py:10`, `catalog.py:9`).
- **No raw secret fields** — `api_key_ref` is a reference field, never a
  resolved secret. No `api_key`, `token`, or `password` fields in form
  payloads.

### What Needs Improvement

- **`BUILTIN_VENDOR_LABEL` ("Built-in vendor") is defined but never rendered**
  (`providers.py:28`). The kind selector shows vendor IDs (`openai`,
  `anthropic`) directly, not the human label "Built-in vendor". The spec copy
  contract includes this label — it should appear somewhere (e.g., as an
  `<optgroup>` label or a descriptive caption).
- **`PROBE_RESULT_FAIL_MISSING_REF` and `PROBE_RESULT_FAIL_NETWORK` are defined
  but never used** (`providers.py:55-60`). The spec defines three distinct
  probe failure copy variants (missing ref, network, generic), but
  `_probe_result_html` only uses `PROBE_RESULT_FAIL_GENERIC` for all failure
  cases (`providers.py:121-125`). The missing-ref and network-specific
  messages are dead code. Either wire them to the corresponding API status
  codes or remove them and update the spec.
- **Probe button labels** add "(main)"/"(vision)" suffix not in the spec copy
  contract (`providers.py:335,350`). See Pillar 3.
- **Probe `not_configured` copy** ("Probe target '{target}' is not
  configured. Select a main model in Model Catalog first.") is not in the spec
  (`providers.py:118`). Should be added to the copy contract or replaced with
  spec-defined copy.
- **Inline probe target status** uses snake_case "not_configured" visible to
  operators (`providers.py:339,354`). Should use human-friendly text per
  accessibility guidelines.

---

## Pillar 6 — Security Boundaries

**Score: 8/10**

### What's Correct

- **HTML escaping** — all dynamic content is passed through `html.escape()`:
  - `providers.py:92-93` (`_esc` with `quote=True`)
  - `catalog.py:59-60` (`_esc` with `quote=True`)
  - `dashboard.py:18-20` (`_esc`)
  - Every interpolated value in form rendering uses `_esc()` — no raw string
    interpolation into HTML.
- **CSP header** — `default-src 'self'; script-src 'self'; style-src 'self'`
  on every response (`server.py:64,181`). No inline scripts. Styles are in a
  single `<style>` block in the template (CSP-compliant).
- **Additional security headers** — `X-Content-Type-Options: nosniff` and
  `X-Frame-Options: DENY` (`server.py:183-184`).
- **CSRF mechanism** — signed HMAC-SHA256 tokens bound to identity (role +
  tenant) and exact route (`csrf.py:66-81`). Validation uses
  `hmac.compare_digest` for constant-time comparison (`csrf.py:138`). Fails
  closed on non-string, missing, malformed, empty, or extra-part tokens
  (`csrf.py:127-134`).
- **CSRF on all Phase 76 POST routes**:
  - `/config/providers` POST: validates against `_PROVIDERS_PATH`
    (`server.py:650-651`)
  - `/config/providers/probe` POST: validates against `_PROBE_PATH`
    (`server.py:784-785`)
  - `/config/catalog` POST: validates against `_CATALOG_PATH`
    (`server.py:900-901`)
  - All return 403 before proxying on missing/mismatch.
- **POST route allowlist** — only `_POST_ROUTES` accept POST; all others
  return 405 (`server.py:90-95,211-217`).
- **POST body size cap** — `MAX_CHANNELS_POST_BYTES = 64KB` enforced before
  reading body (`server.py:69,1075`).
- **Refs-only fields** — `api_key_ref` is a text reference field, never a
  resolved secret. `autocomplete="off"` on all ref and URL fields
  (`providers.py:271,285,309`). No `api_key`, `token`, or `password` fields in
  form payloads.
- **No secret leakage** — probe result copy is generic; never includes HTTP
  status codes, response snippets, or resolved key material
  (`providers.py:52-63`). Module docstrings confirm "Never logs response
  bodies or resolved secrets" (`providers.py:49-51`).
- **Output boundary** — `AdminUiBoundary` applied to free-text API messages
  in dashboard rendering (`dashboard.py:28-30`). Provider/catalog forms use
  escaped spec copy (not raw API messages).
- **Metadata preservation** — provider metadata merged from current data
  after CSRF passes (`server.py:600-625,695`), preventing the SSR form from
  wiping API-set metadata.
- **RBAC enforcement** — ADMIN/OPERATOR only; lawyer/viewer get 403 with
  forbidden error copy (`server.py:255-274`).
- **Flag gate** — `operator_config_enabled` OFF disables forms and shows
  error (`providers.py:376-377,384-385`, `catalog.py:179-180,187-188`).
- **No cookies/sessions** — CSRF tokens are stateless (nonce+HMAC), no
  persistent nonce store (`csrf.py:22-24`).
- **Cross-process signing key** — production uses `RBAC_TOKEN_SECRET` for
  cross-worker validity; process-local fallback for tests only
  (`csrf.py:8-14,59-63`).

### What Needs Improvement

- **CRITICAL: Probe CSRF token is never rendered into the form** — The
  `probe_csrf_token` parameter exists in `render_providers_form`
  (`providers.py:364`) and `render_providers_page` (`providers.py:436`) but is
  never used in the HTML output. The server never passes it
  (`server.py` — zero matches for `probe_csrf_token`). The providers form
  contains a single hidden `csrf_token` bound to `/config/providers`
  (`providers.py:397-400`). When the probe button submits this form to
  `/config/providers/probe` via `formaction`, the `_handle_probe` handler
  validates the token against `_PROBE_PATH` (`server.py:784-785`). Since the
  token was signed for `_PROVIDERS_PATH`, validation always fails → 403. This
  makes the connection probe feature completely non-functional through the UI.

  **Fix options:**
  1. Issue a separate probe CSRF token in `_handle_providers` GET, pass it as
     `probe_csrf_token`, and render it as a `data-probe-csrf` attribute or a
     separate hidden field that JavaScript swaps in (but spec says no JS).
  2. Render a second `<input type="hidden" name="probe_csrf_token">` inside
     the form and have `_handle_probe` look for `probe_csrf_token` (validated
     against `_PROBE_PATH`) instead of `csrf_token`.
  3. Use a sibling `<form>` (not nested) for the probe buttons with its own
     `csrf_token` hidden field bound to `_PROBE_PATH`.
  4. Validate the probe CSRF token against `_PROVIDERS_PATH` (the page that
     rendered it) instead of `_PROBE_PATH`, accepting that the probe action
     shares the page-level token.

  Option 2 or 3 is recommended — they preserve route binding while making the
  probe functional without JavaScript.

- **Channels route CSRF is deferred** — `_handle_channels` uses a random
  unbound `csrf_token` and does not validate it on POST (`server.py:401-406`).
  This is explicitly deferred to Phase 78 per the spec and code comments, but
  it means the existing channels route is not CSRF-protected. Not a Phase 76
  regression, but noted for Phase 78 follow-through.

---

## Summary

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| Visual Hierarchy | 9 | Layout, spacing, typography all match spec. Minor inherited font-size redundancy. |
| Color & Contrast | 10 | Full palette compliance. Accent scarcity preserved. Phase 75 fixes applied. |
| Interaction Design | 8 | Form fields, selectors, radio rows all correct. Probe button labels deviate; probe is non-functional due to CSRF. |
| Accessibility | 9 | Labels, touch targets, focus indicators, ARIA all present. Read-only field labels lack `for`. |
| Content & Copy | 8 | Most copy exact. Three unused copy constants (BUILTIN_VENDOR_LABEL, probe fail variants). Probe labels and not_configured copy deviate. |
| Security Boundaries | 8 | HTML escaping, CSP, CSRF mechanism, refs-only, no secret leakage all solid. Probe CSRF token never rendered — probe always 403. |

**Average: 8.7/10**

### Critical Issue

The probe CSRF token (`probe_csrf_token`) is plumbed through function
signatures but never rendered into the HTML form and never passed by the
server. Because CSRF tokens are route-bound, the probe button (which submits
the providers form to `/config/providers/probe`) will always fail CSRF
validation and return 403. The connection probe feature is non-functional
through the UI. This requires a fix before the probe can be used by
operators.

### Non-Critical Issues

1. `BUILTIN_VENDOR_LABEL` ("Built-in vendor") — defined but never rendered
   (`providers.py:28`).
2. `PROBE_RESULT_FAIL_MISSING_REF` and `PROBE_RESULT_FAIL_NETWORK` — defined
   but never used; all probe failures show generic copy (`providers.py:55-60`).
3. Probe button labels add "(main)"/"(vision)" suffix not in spec copy
   (`providers.py:335,350`).
4. Probe `not_configured` status copy not in spec (`providers.py:118`).
5. Inline probe target status uses snake_case "not_configured" visible to
   operators (`providers.py:339,354`).
6. Read-only field labels use `<label>` without `for` attribute
   (`providers.py:259,295`).
7. Redundant `.section h2` font-size declaration (`dashboard.py:107` vs
   `:138`) — inherited from Phase 75.
