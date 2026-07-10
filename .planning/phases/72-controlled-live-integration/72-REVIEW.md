---
phase: 72-controlled-live-integration
reviewed: 2026-07-10T05:30:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - scripts/smoke_test.py
  - packages/channels/qqbot/tests/test_smoke_toolkit.py
  - runbook/SMOKE_TEST_RUNBOOK.md
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
fix_recommended: true
---

# Phase 72: Code Review Report

**Reviewed:** 2026-07-10T05:30:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Phase 72 honesty core holds: structured evidence always forces `not_live_acceptance=True`, `_run_smoke_live` stamps True and never False, `--help` marks HUMAN GATE, `run_v2_gates.py` does not invoke `--live`, runbook documents dual-knob / ACK / passive-reply windows, Phase 72 archival path, and Phase 5/8 as carried (not v1.9 done). No critical blockers. Three warnings remain: whitespace-only env bypasses fail-closed before Urllib construction, the Phase 5/8 cue assertion is too weak to lock carried-gate language, and the dual-knob comparison table abbreviates smoke value env names. `--fix` recommended.

## Warnings

### WR-01: Whitespace-only live env bypasses fail-closed before network

**File:** `scripts/smoke_test.py:281-288`
**Issue:** `load_live_credentials` treats any non-empty string as present (`not os.environ.get(k)`). Whitespace-only values (`"   "`) pass validation, then `_run_smoke_live` constructs `UrllibTokenTransport` / `UrllibMessageTransport` and attempts live OpenAPI. That weakens the LIVE-01 / T-67-01 / T-72-01 fail-closed-before-network guarantee (operators or shell exports can “satisfy” keys without real credentials).
**Fix:** Reject blank/whitespace values the same as missing keys:

```python
def load_live_credentials() -> dict[str, str]:
    """Load live value env vars. Fail closed on missing keys; never log values."""
    missing = [
        k for k in LIVE_ENV_KEYS
        if not (os.environ.get(k) or "").strip()
    ]
    if missing:
        raise SystemExit(
            "live mode requires env vars (values not shown): " + ", ".join(missing)
        )
    return {
        "bot_secret": os.environ["INKSTATUTE_QQBOT_BOT_SECRET"].strip(),
        "user_openid": os.environ["INKSTATUTE_QQBOT_USER_OPENID"].strip(),
        "msg_id": os.environ["INKSTATUTE_QQBOT_REPLY_MSG_ID"].strip(),
        "app_id": os.environ["INKSTATUTE_QQBOT_APP_ID"].strip(),
        "client_secret": os.environ["INKSTATUTE_QQBOT_CLIENT_SECRET"].strip(),
    }
```

Add a `TestLiveEnvFailClosed` case that plants whitespace-only values and asserts non-zero exit with key names only (no network).

### WR-02: Phase 5/8 carried-gate cue assertion is operator-precedence weak

**File:** `packages/channels/qqbot/tests/test_smoke_toolkit.py:598-601`
**Issue:** The carried-gate lock is:

```python
"carried" in lower or "remain" in lower or "not" in lower and "v1.9 done" in lower
```

Because `and` binds tighter than `or`, this is effectively `"carried" … or "remain" … or ("not" … and "v1.9 done" …)`. The runbook already contains incidental `"remain"` / `"not"` elsewhere (e.g. “coverage remains…”, “must **not** auto-claim”). A document that still mentions Phase 5/8 + WeCom + lawyer trial but marks them complete (or drops “carried human gate”) can still pass. That undermines LIVE-02 honesty for the Phase 5/8 focus area.
**Fix:** Require explicit carried-gate phrases and parenthesize:

```python
self.assertIn("carried human gate", lower)
self.assertIn("not v1.9 done", lower)
# or:
self.assertTrue(
    ("carried" in lower and "human gate" in lower)
    and ("not v1.9 done" in lower or "not redefined" in lower),
    "runbook must state Phase 5/8 remain carried human gates (not v1.9 done)",
)
```

### WR-03: Dual-knob comparison table abbreviates smoke value env names

**File:** `runbook/SMOKE_TEST_RUNBOOK.md:42`
**Issue:** The smoke-vs-host credentials row lists `INKSTATUTE_QQBOT_APP_ID`, `CLIENT_SECRET`, `BOT_SECRET`, `USER_OPENID`, `REPLY_MSG_ID`. Operators scanning the LIVE-02 enablement table first may export bare `CLIENT_SECRET` / `BOT_SECRET` instead of `INKSTATUTE_QQBOT_*`. Fail-closed then lists the real names, but the enablement docs themselves invite the mis-set.
**Fix:** Use full key names (or an explicit `INKSTATUTE_QQBOT_*` prefix note):

```markdown
| Credentials | Value env: `INKSTATUTE_QQBOT_APP_ID`, `INKSTATUTE_QQBOT_CLIENT_SECRET`, `INKSTATUTE_QQBOT_BOT_SECRET`, `INKSTATUTE_QQBOT_USER_OPENID`, `INKSTATUTE_QQBOT_REPLY_MSG_ID` | `INKSTATUTE_QQBOT_*_REF` only (resolved at process edge) |
```

## Info

### IN-01: “Relabel” wording can be read as flipping `not_live_acceptance`

**File:** `scripts/smoke_test.py:790-791`, `runbook/SMOKE_TEST_RUNBOOK.md:74`
**Issue:** “operators may relabel a sanitized archive” is ambiguous — some readers may think they should set `not_live_acceptance=false` in the archived JSON. Intent appears to be human archival as acceptance evidence while the script stamp stays True.
**Fix:** Prefer “human may archive sanitized evidence as operator acceptance proof; do not flip `not_live_acceptance` in the JSON.”

### IN-02: CI honesty scan covers only `run_v2_gates.py`

**File:** `packages/channels/qqbot/tests/test_smoke_toolkit.py:513-522`
**Issue:** `test_ci_gates_do_not_invoke_live` only reads `scripts/run_v2_gates.py`. `.github/workflows/v2-contract-gates.yml` currently has no smoke/`--live` invocation, so risk is low, but a future workflow could reintroduce live smoke without failing this test.
**Fix:** Optionally also assert workflow YAML / Makefile sources lack `smoke_test.py --live` (same regex).

---

## Focus-area verdict

| Focus | Verdict |
|-------|---------|
| Live HUMAN GATE honesty | Pass — help/docstring, stamp True, sanitize force-True, tainted payload cannot emit False |
| Fail-closed env | Mostly pass — missing keys fail closed with names only; **WR-01** whitespace gap |
| Runbook dual-knob / ACK docs | Pass — dual-knob AND mapping matches `wiring.py`; ACK PUT + passive-reply windows documented; **WR-03** name abbreviation |
| No auto-claim of live acceptance | Pass — script + sanitize + CI gate scan; archive never required for phase complete |
| Phase 5/8 remain carried | Docs pass; **WR-02** cue test too weak to lock the language |

**`--fix` recommended:** yes (WR-01..WR-03).

---

_Reviewed: 2026-07-10T05:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
