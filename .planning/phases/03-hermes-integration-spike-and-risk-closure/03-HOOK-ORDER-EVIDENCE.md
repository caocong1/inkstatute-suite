# Phase 03 Hook Order Evidence Gate

**Plan:** 03-02  
**Created:** 2026-06-27T18:40:29Z  
**Scope:** Mandatory Phase 3 gate for D-02 and D-03 before any Phase 4 production `contract_result_recorder` hook work.

EVIDENCE_OUTCOME: blocking_gap
HOOK_ORDER_DECISION: BLOCKING_VERIFICATION_GAP

## Gate Result

Plan 03-02 cannot close the hook-order success gate from this repository.

The required evidence is one of:

1. Hermes source/runtime evidence proving same-event hook ordering for `agent:end`, including whether `contract_result_recorder` can run after `response_filter`.
2. A sanitized tested hook-order probe that records only event names, hook names, timestamps or order indexes, and redacted context keys.

Neither evidence class is present in this repo. The repo contains PRD and planning descriptions of Hermes hooks, but no source-confirmed hook loader, `HOOK.yaml`, `handler.py`, `response_filter` implementation, runtime hook registration, sanitized probe output, or sanitized runtime trace.

## Evidence Commands

| Command | Purpose | Outcome |
|---------|---------|---------|
| `rg --files \| rg '(^\|/)(HOOK\.yaml\|handler\.py\|feedback\.jsonl\|pending_previews\.jsonl)$\|response_filter\|template_card_dispatcher\|wecom_template_card_shim\|long_task\|agent:end\|gateway:startup\|callback\|session\|task\|gateway\|hermes\|hook\|wecom\|feedback\|preview'` | File-name scan for Hermes hook/runtime/probe artifacts. | Returned only contract fixtures and schema files; no Hermes runtime source, hook files, JSONL runtime data, or probe artifact. |
| `find . -path ./.git -prune -o -maxdepth 5 -type f \( -name 'HOOK.yaml' -o -name 'handler.py' -o -iname '*hermes*' -o -iname '*hook*' -o -iname '*wecom*' -o -iname '*feedback*' -o -iname '*preview*' -o -iname '*session*' -o -iname '*task*' -o -iname '*gateway*' -o -iname '*callback*' \) -print \| sort` | Targeted filesystem inventory for hook, gateway, feedback, session, task, callback, and Hermes evidence. | Returned `03-HERMES-SOURCE-INVENTORY.md` and synthetic fixture files only. |
| `rg -n "response_filter\|template_card_dispatcher\|wecom_template_card_shim\|contract_result_recorder\|HOOK\.yaml\|handler\.py\|agent:end\|gateway:startup\|pending_previews\.jsonl\|feedback\.jsonl" -S . --glob '!.git/**'` | Content scan for hook order and feedback-chain terms. | Matches are in `README.md`, `AGENTS.md`, `docs/requirements/V2-PRD.md`, and planning artifacts. No Hermes implementation or sanitized runtime probe output exists. |

## Available Evidence

| Source | Status | What It Supports | What It Does Not Prove |
|--------|--------|------------------|-------------------------|
| `docs/requirements/V2-PRD.md` | specification evidence | Describes desired `contract_result_recorder` placement on `agent:end` after `response_filter`, and records the hook-order risk in section 13. | Does not prove Hermes hook loader ordering, registration priority, context mutation timing, or same-event execution order. |
| `03-HERMES-SOURCE-INVENTORY.md` | repo-local inventory evidence | Confirms this repository lacks Hermes runtime/profile source and sanitized runtime samples. | Does not close the hook-order gate. |
| `03-INTEGRATION-RISK-MATRIX.md` | decision matrix evidence | Marks hook event ordering and multi-hook same-event order as blocked. | Does not provide source/runtime proof. |

## Phase 3 Verification Gap

The following evidence is missing:

- Hermes hook loader source or runtime documentation that defines same-event hook ordering.
- The `HOOK.yaml` entries for existing `admin_notice`, `response_filter`, and any candidate `contract_result_recorder`.
- The relevant `handler.py` files or runtime hook registration data for the `agent:end` chain.
- Source or sanitized runtime evidence showing whether `response_filter` mutates context before downstream hooks read it.
- A sanitized hook-order probe result with event names, hook names, order indexes or timestamps, and redacted context keys.

Because this evidence is absent, Phase 3 must not assert that `contract_result_recorder` can run after `response_filter`. It must also not assert that a separate recorder hook cannot run after `response_filter`; both yes/no outcomes remain unverified.

## D-03 Decision

D-03 requires a hook-order decision that resolves the `response_filter` dependency. The current decision is:

`BLOCKING_VERIFICATION_GAP`: no source/runtime evidence or sanitized tested probe is available in this repo to prove whether `contract_result_recorder` can run after `response_filter` on `agent:end`.

## Phase 4 Impact

Phase 4 must stop before any separate production `contract_result_recorder` hook is implemented unless one of these happens first:

1. Hermes source/runtime evidence proves same-event hook order and context mutation timing.
2. A sanitized tested probe proves the ordering without raw legal text, customer data, secrets, callback payload bodies, runtime databases, or logs.
3. Phase 4 explicitly chooses a fallback that does not depend on unverified separate-hook ordering.

Allowed fallback options for a future decision are:

- record inside `response_filter`
- record adjacent to `response_filter`
- keep Phase 4 blocked until hook loader/order evidence exists

No production hook code was written by this plan.
