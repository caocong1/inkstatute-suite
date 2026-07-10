# Phase 75 — UI Review

**Audited:** 2026-07-10
**Baseline:** `75-UI-SPEC.md` (stdlib SSR Channel Config form)
**Screenshots:** not captured (no admin-web-ui dev server on :3000/:5173/:8080/:8765; :8080 is an unrelated auth service)
**Advisory:** scores do not block ship — Phase 75 verification remains authoritative for functional gates

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | UI-SPEC CTA/errors/dual-knob/empty/success strings match; ref labels are raw snake_case field names |
| 2. Visuals | 2/4 | Clear two-panel composition, but host checkbox `<label>` has no visible text (label lives in sibling `.key`) |
| 3. Color | 3/4 | Palette and accent scarcity match contract; routine OFF uses `status-err` (destructive red) |
| 4. Typography | 2/4 | Extra sizes/weights on chrome (`identity` 0.8rem; h1/h2/h3 browser bold 700; h2 1.1rem ≠ 18px) |
| 5. Spacing | 3/4 | 2xl panel gap and 44px targets OK; field stack gap is 8px vs declared md 16px |
| 6. Experience Design | 2/4 | Empty/error/flag-off/disabled submit covered; no client-side effective/ON-OFF update when host checkbox toggles |

**Overall: 15/24**

---

## Top 3 Priority Fixes

1. **Host checkbox does not update ON/OFF or Effective line** — Operators see stale dual-knob status until save/reload, contradicting UI-SPEC “computed client-side for display.” — Add a tiny CSP-safe inline-free script is out of stack lock; prefer either (a) drop the redundant ON/OFF word next to the editable checkbox and show only the derived Effective line after POST, or (b) document server-render-only and recompute Effective from posted values on validation re-render. Best MVP fix: on change, use a same-page progressive enhancement only if CSP allows; otherwise remove the static ON/OFF adjacent to the editable host control so it cannot lie.

2. **Typography lock broken on page chrome / panel titles** — Heading hierarchy looks heavier and smaller than the 18px/600 contract. — In `dashboard.py` styles: set `.header h1 { font-weight: 600 }`, `.section h2, .channel-panel h3 { font-size: 1.125rem; font-weight: 600; line-height: 1.2 }`, and align `.identity` to Label `0.875rem` (or Body) so the page stays within four sizes / two weights.

3. **Host knob accessible name is empty** — Screen readers get an unlabeled checkbox; sighted users rely on a sibling `.key` span. — Put the host label text inside `<label class="field-check" for="…">Host enabled (…)<input …></label>` (or `aria-labelledby` pointing at the `.key` id) so every control has a visible associated label per Accessibility & Safety.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

**Met (exact UI-SPEC strings in `channels.py`):**
- Primary CTA `Save channel config` (L20, L299–300)
- Nav / page title `Channel Config` (`dashboard.py` L78; `channels.py` L19)
- Panel headings `QQBot channel` / `WeCom channel` (L170, L220)
- Dual-knob legend, Effective ON/OFF, REF_HELP, empty heading/body, ERROR_*, SUCCESS_FLASH, RESTART_NOTICE (L21–47, L78–81, L282–287)
- Platform labels use `qqbot_channel_enabled` / `wecom_channel_enabled` — never `channel_delivery_enabled` (L172–173, L222–223; tests assert absence)

**WARNING — raw ref field labels:**
- `_ref_field(..., field, ...)` uses technical names (`app_id_ref`, `encoding_aes_key_secret_ref`) as visible `<label>` text (`channels.py` L186–198, L236–248). Contract tables name fields that way, so this is not a hard miss, but operators get snake_case instead of human copy. Prefer short human labels (e.g. “App ID ref”) while keeping `name=` technical.

**WARNING — unknown GET error path:**
- `render_channels_page` can emit `Error [{code}]: {msg}` for non-mapped API errors (`channels.py` L331) instead of `ERROR_GENERIC`. POST path correctly maps to contract copy (`server.py` L294–301).

No generic “Submit” / “Click Here” / “OK” CTAs on the Channel Config surface.

### Pillar 2: Visuals (2/4)

**Met:**
- Single-purpose page: flash → restart notice → QQ card → WeCom card → Save (`channels.py` `render_channels_form`)
- Index card + nav link present (`dashboard.py` L78, L219–223)
- Cards used only as channel interaction containers (allowed)
- Status uses words `ON`/`OFF` plus color class (not color alone) (`channels.py` L66–69)

**WARNING — host checkbox label association:**
```109:124:services/admin-web-ui/src/admin_web_ui/channels.py
def _knob_row(label: str, on: bool, *, editable: bool, checkbox_name: str | None) -> str:
    ...
        control = (
            f'<label class="field-check" for="{_esc(checkbox_name)}">'
            f'<input type="checkbox" id="{_esc(checkbox_name)}" '
            f'name="{_esc(checkbox_name)}" value="1"{checked}>'
            f"</label>"
        )
        return (
            f'      <p class="field dual-knob-row">'
            f'<span class="key">{_esc(label)}</span> '
            f"{control} "
```
Visible label text is outside `<label>`; UI-SPEC Accessibility requires a visible `<label for=…>` per input. Ref inputs do this correctly (L145–146).

**WARNING — panel title styling:**
- Panels use bare `<h3>` with no Heading-role CSS; visual weight depends on UA default, not the 18px/600 contract.

### Pillar 3: Color (3/4)

**Met:**
- Dominant `#f5f5f5`, sections `#fff`, cards `#fafafa`, header/nav/identity navy stack, text `#222` / muted `#888` / key `#555` (`dashboard.py` L97–118)
- Accent `#aaccff` limited to nav, identity, `:focus-visible` (L101–102, L112, L127–128)
- Primary submit navy `#1a1a2e` + white text — accent not used as fill (L130–132)
- Destructive `#c0392b` / success `#27ae60` for `.error` / `.status-ok`

**WARNING — OFF as destructive:**
- `_bool_status(False)` and Effective OFF use `status-err` (`channels.py` L66–69, L78–81). UI-SPEC allows `status-err` *or* muted OFF; using destructive red for default-disabled knobs makes a healthy “both OFF” matrix look like an error wall. Prefer muted (`#888` / `.empty`) for OFF; reserve `status-err` for Effective OFF only if product wants urgency, or for real errors.

Accent element count on this page stays scarce (nav + identity + focus). No accent submit fill.

### Pillar 4: Typography (2/4)

**Contract:** exactly four sizes (16 / 14 / 18 / 20) and two weights (400 / 600).

| Observed | Source | Verdict |
|----------|--------|---------|
| Body `1rem` / fields | `.field` | Pass |
| Label `0.875rem` / 600 | `.field label`, `.field .key` | Pass |
| Display `1.25rem` header | `.header h1` | Size pass; **weight missing → UA bold ~700** |
| Heading should be `1.125rem` / 600 | `.section h2` is `1.1rem`, no weight; `.channel-panel h3` unstyled | Fail |
| Identity `0.8rem` | `.identity` | **5th size** on Channel Config chrome |
| Nav `0.9rem` | `.nav-link` | ≈ Label — acceptable per UI-SPEC note |

**WARNING:** Shared CSS also declares `.data-table { font-size: 0.85rem }` (extra size in the design language even if unused on this form body).

Channel form body itself stays close to Body/Label; chrome and headings break the lock → **2/4**.

### Pillar 5: Spacing (3/4)

**Met:**
- `.channel-panel { margin-bottom: 3rem }` = 48px = 2xl between QQ/WeCom panels
- Dual-knob row `gap: 0.5rem` / `margin: 0.5rem 0` matches 8px dual-knob exception
- Card/section/main padding match md/lg/xl (`1rem` / `1.5rem` / `2rem`)
- `.field-check` and `.btn-primary` enforce min 44px hit area
- `.ref-input` / button padding `8px` / `8px 16px` on scale

**WARNING — field stack gap:**
- `.field { margin: 0.5rem 0 }` → 8px vertical rhythm between ref fields; UI-SPEC Spacing Scale says **md 16px** for “Default field stack gap”. Bump to `margin: 1rem 0` (or `gap: 1rem` on a field stack) for ref inputs; keep dual-knob rows at 8px.

No arbitrary `[Npx]` Tailwind; values are rem/px aligned to the existing dashboard.

### Pillar 6: Experience Design (2/4)

**Met:**
| State | Evidence |
|-------|----------|
| Empty store copy | `EMPTY_HEADING` / `EMPTY_BODY` when no channel data (`channels.py` L284–287) |
| Success flash + restart notice | `SUCCESS_FLASH` + always-visible `RESTART_NOTICE` (L282, L287–288 in server POST success) |
| Validation / forbidden / flag-off | Mapped copy on POST (`server.py` L294–301); flag-off disables submit (`channels.py` L271–272, L297–300) |
| Refs-only inputs | `type="text"`, `autocomplete="off"`, monospace `.ref-input` |
| CSRF field present | Hidden `csrf_token` (`channels.py` L291–292); full verify deferred Phase 78 (honest) |
| No bypass toggle | Tests forbid `force_enable` / `channel_delivery_enabled` |
| RBAC denial path | Forbidden copy + `/config` guard |

**WARNING / contract gap — client-side effective display:**
- UI-SPEC Dual-Knob §5: Effective “computed client-side for display **and** must match server-provided.” Implementation is server-render only; toggling `qqbot.enabled` / `wecom.enabled` does not update the adjacent ON/OFF span or Effective line until reload. Editable host row therefore shows a checkbox state that can disagree with the status word beside it.

**WARNING — validation re-display:**
- POST prefers `put_data["data"]` when present, else re-GETs (`server.py` L317–319). If PUT error bodies omit echoed section data, host/ref values may reset — weaker than “preserve submitted host checkboxes; ref fields re-filled.”

No SPA loading skeleton expected for stdlib SSR; full-page response is acceptable.

---

## Registry Safety

Skipped — `75-UI-SPEC.md` sets `shadcn_initialized: false`; no `components.json`; no third-party registries.

Registry audit: 0 third-party blocks checked, not applicable.

---

## Files Audited

- `.planning/phases/75-channel-config-apply/75-UI-SPEC.md`
- `.planning/phases/75-channel-config-apply/75-CONTEXT.md`
- `.planning/phases/75-channel-config-apply/75-05-SUMMARY.md`
- `services/admin-web-ui/src/admin_web_ui/channels.py`
- `services/admin-web-ui/src/admin_web_ui/dashboard.py` (nav, index card, shared CSS)
- `services/admin-web-ui/src/admin_web_ui/server.py` (`_handle_channels`)
- `services/admin-web-ui/tests/test_channels_form.py`
- `services/admin-web-ui/README.md` (honesty / CSRF deferral — spot check)

---

## Minor Recommendations (beyond Top 3)

- Use muted styling for platform/host **OFF**; keep `status-err` for Effective OFF and real `.error` flashes only.
- Humanize ref field labels while keeping technical `name` attributes.
- Map unknown GET API errors to `ERROR_GENERIC` (avoid echoing raw `Error [code]: msg`).
- On validation failure, merge parsed POST fields into the re-render model so checkboxes/refs always preserve.
