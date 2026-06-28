# Phase 03 Hook Order Evidence Gate

**Plan:** 03-02  
**Updated:** 2026-06-28T09:15:50+08:00  
**Scope:** Mandatory Phase 3 gate for D-02 and D-03 before any Phase 4 production `contract_result_recorder` hook work.

EVIDENCE_OUTCOME: source_confirmed
HOOK_ORDER_DECISION: can_run_after_response_filter

## Gate Result

Plan 03-02 can close the hook-order success gate from local Hermes source plus a sanitized temporary probe.

The confirmed rule is narrow and operational:

- Hermes discovers hook directories from the active `HERMES_HOME/hooks` directory in lexicographic directory order.
- For one event, handlers are appended to the event handler list in that discovery order.
- `emit("agent:end", context)` calls the handlers sequentially and passes the same mutable `context` dict to each handler.
- Therefore a separate contract recorder can run after `response_filter` only when its hook directory sorts after `response_filter`.

A hook directory named exactly `contract_result_recorder` would sort before `response_filter` and would not observe fields added by `response_filter`. Phase 4 must either use a directory name that sorts after `response_filter` while keeping the manifest name `contract_result_recorder`, or choose the documented fallback of recording inside/adjacent to `response_filter`.

## Source Evidence

| Source | Evidence | Decision Impact |
|--------|----------|-----------------|
| `/home/sorawatcher/.hermes/hermes-agent/gateway/hooks.py` | `HookRegistry.discover_and_load()` iterates `for hook_dir in sorted(HOOKS_DIR.iterdir())`, registers each declared event by appending its `handle` function, and `emit()` calls resolved handlers in list order with the same `context`. | Same-event order is deterministic by hook directory name. A recorder directory sorted after `response_filter` runs after it. |
| `/home/sorawatcher/.hermes/hermes-agent/hermes_constants.py` | `get_hermes_home()` honors `HERMES_HOME`; profile runtime can therefore load hooks from the lawfirm profile home. | The active lawfirm profile hook root is the runtime source for profile hooks. |
| `/home/sorawatcher/.hermes/profiles/lawfirm/hooks/response_filter/HOOK.yaml` | Declares `name: response_filter` and `events: agent:end`. | `response_filter` is an `agent:end` hook. |
| `/home/sorawatcher/.hermes/profiles/lawfirm/hooks/response_filter/handler.py` | On `agent:end`, rewrites local `response`, generates `message_id`, writes a pending preview, then sets `context["message_id"]` and `context["response"]`. | A later same-event hook can read `message_id` and the response string that `response_filter` wrote into hook context. |
| `/home/sorawatcher/.hermes/hermes-agent/gateway/run.py` | Builds `hook_ctx` before the agent run, then emits `agent:end` with `{**hook_ctx, "response": (response or "")[:500]}`. | `agent:end` hook context contains platform/user/chat/session/message fields plus a response preview capped at 500 characters. |
| `/home/sorawatcher/.hermes/profiles/lawfirm/hooks/admin_notice/HOOK.yaml` | Declares `admin_notice` on `agent:end`. | Current lawfirm `agent:end` hook order begins with `admin_notice`, then `response_filter` by directory sorting. |
| `/home/sorawatcher/.hermes/profiles/lawfirm/hooks/template_card_dispatcher/HOOK.yaml` | Declares `template_card_dispatcher` on `gateway:startup`. | Feedback card dispatch is not in the `agent:end` chain and does not affect recorder ordering. |
| `/home/sorawatcher/.hermes/profiles/lawfirm/hooks/wecom_template_card_shim/HOOK.yaml` | Declares `wecom_template_card_shim` on `gateway:startup`. | WeCom callback shim setup is not in the `agent:end` chain and does not affect recorder ordering. |

## Sanitized Probe Corroboration

A temporary standard-library probe loaded `gateway/hooks.py` with dependency stubs and synthetic hook directories. It recorded only hook names and a boolean showing whether the recorder saw the response value written by `response_filter`.

| Probe Case | Observed Order | Recorder Saw Filtered Context |
|------------|----------------|-------------------------------|
| `admin_notice`, `contract_result_recorder`, `response_filter` | `admin_notice,contract_result_recorder,response_filter` | `False` |
| `admin_notice`, `response_filter`, `zz_contract_result_recorder` | `admin_notice,response_filter,zz_contract_result_recorder` | `True` |

The probe confirms the source reading: directory sort order controls same-event order, and later handlers observe context mutations from earlier handlers.

## D-03 Decision

D-03 requires a hook-order decision that resolves the `response_filter` dependency.

Decision: `can_run_after_response_filter`.

Implementation constraint: the recorder hook directory must sort after `response_filter`; for example, Phase 4 can use a directory such as `response_filter_contract_result_recorder` or `zz_contract_result_recorder` with manifest `name: contract_result_recorder`. A canonical directory named `contract_result_recorder` is not valid for after-filter recording because it sorts before `response_filter`.

## Phase 4 Impact

Phase 4 may implement a separate production recorder hook only if it preserves these constraints:

1. Register on `agent:end`.
2. Install in a hook directory that sorts after `response_filter`.
3. Treat `context["message_id"]` as source-confirmed only after `response_filter` has run.
4. Treat `context["response"]` at `agent:end` as the hook context response, capped by the gateway emission path, not as proof of full outbound text capture.
5. Keep raw payloads reference-first and avoid storing sensitive legal/customer content in contract logs.

Allowed fallback options remain:

- record inside `response_filter`
- record adjacent to `response_filter`
- keep Phase 4 blocked until a deployment-specific hook directory/order is selected

No production hook code was written by this plan.
