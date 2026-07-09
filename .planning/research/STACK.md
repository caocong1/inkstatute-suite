# Stack Research: v1.9 QQBot Host Composition

**Domain:** Thin production QQBot webhook host, DefaultRunRuntime channel registration, smoke Protocol-path hardening, controlled live integration
**Researched:** 2026-07-09
**Confidence:** HIGH

## Scope Boundary

This research covers **only** stack additions/changes for v1.9 host-composition work. Package-level QQBot capabilities from v1.8 are treated as **already validated** and must not be re-selected as greenfield:

| Already shipped (reuse) | Do not re-research |
|-------------------------|--------------------|
| `packages/channels/qqbot` signature, normalize, TokenManager, egress, rich media | Ed25519 / OpenAPI client choice |
| `QQBotSessionRuntime`, `QQBotRuntimeIngress`, adapter real IO (default-OFF) | Session/ingress orchestration libraries |
| `feedback_ingress.handle_feedback_callback` + feedback-service queue composition | Feedback normalization stack |
| `scripts/smoke_test.py` dry-run leaf helpers + `--live` HUMAN GATE | Smoke CLI framework |
| `services/wecom-service` pure ingress/session host pattern | WeCom SDK / XML crypto |
| Frozen `ChannelAdapter` (6) / `BackendAdapter` (9) / `DefaultRunRuntime` | Protocol redesign |

**v1.8 audit gaps this stack closes:** production webhook host composition; runtime registration into `DefaultRunRuntime.channels`; smoke dry-run across full adapter/session Protocol path; controlled live path (acceptance remains human gate).

---

## Architectural Constraints (Carried Forward)

1. **`dependencies = []`** on every package/service `pyproject.toml` (wecom-service, qqbot, feedback-service, admin-web-ui all empty).
2. **No Protocol unfreeze** — do not modify `packages/platform-runtime/src/platform_runtime/protocols.py` or `feature_flags.py` field defaults.
3. **Feature flags default OFF** — `qqbot_channel_enabled=False`, `QQBotChannelConfig.enabled=False`, `run_runtime_enabled=False`.
4. **Secrets stay outside the repo** — only `*_REF` config keys and env value injection at process start; never commit BotSecret / AppSecret / tokens.
5. **AGENTS rule:** do not introduce a new database, queue, or heavy runtime dependency unless the active plan requires it. A thin host *service* is in scope for v1.9; a new framework is not.

**Critical correction vs v1.8 research draft:** v1.8 did **not** adopt `cryptography` or `httpx`. Production path uses vendored `_ed25519.py` + lazy stdlib `urllib.request` (`UrllibMessageTransport` / `UrllibTokenTransport`). v1.9 must **not** reintroduce those optional extras.

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python 3.11+ stdlib `http.server` (`BaseHTTPRequestHandler` + `ThreadingHTTPServer`) | 3.11+ (CI floor) | Thin production webhook HTTP host for QQ callbacks | Matches existing InkStatute HTTP hosts (`services/admin-web-ui`, `services/lawyer-web-chat`). WeCom service is **library-only** (no server); when a deployable HTTP surface is needed, the repo pattern is stdlib `http.server`, not FastAPI/Starlette. Zero new deps. |
| Existing `inkstatute-channels-qqbot` | 0.1.0 (in-repo) | Adapter Protocol IO + ingress/session/feedback primitives | Host composes `verify_and_ack` → `QQBotRuntimeIngress` / `handle_feedback_callback` → `deliver`. Do not fork or reimplement. |
| Existing `platform-runtime` (`DefaultRunRuntime`, `RuntimeFeatureFlags`, fakes) | in-repo | Channel registration + run lifecycle | Constructor already accepts `channels: Iterable[ChannelAdapter]`. Registration is host wiring, not a runtime API change. |
| Existing `feedback-service` | 0.1.0 (in-repo) | Queue normalize/dedupe after INTERACTION | Host PYTHONPATH-composes `feedback_dict` into `normalize_feedback_inputs` — same pattern as qqbot package tests. |
| Python stdlib `asyncio` + `json` + `argparse` + `os.environ` | 3.11+ | Async adapter calls from sync HTTP handler; smoke CLI; env config | Host handler bridges sync HTTP → `asyncio.run(...)` (or a single shared loop) for Protocol methods. Smoke extends existing `scripts/smoke_test.py`. |

### Supporting Libraries (Reuse Only — No New PyPI Packages)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `QQBotChannelAdapter` + `QQBotChannelConfig.from_env` | in-repo | Flag→config mapping + Protocol surface | Host factory: build config from env; inject `token_manager` + `UrllibMessageTransport` only when enabled + secrets resolved. |
| `QQBotRuntimeIngress` / `QQBotSessionRuntime` | in-repo | Message path after ACK | Host calls after `verify_and_ack` accepts non-challenge payloads. |
| `handle_feedback_callback` / `ensure_interaction_ack` | in-repo | INTERACTION → FeedbackEvent | Host routes `t=INTERACTION_CREATE` here instead of session ingress. |
| `FakeBackendAdapter` / `FakeChannelAdapter` / `FakeMessageTransport` | in-repo | Smoke Protocol-path dry-run | Smoke must construct `DefaultRunRuntime(backend=FakeBackendAdapter(), channels=[adapter], feature_flags=...)` and exercise adapter + session without network. |
| `UrllibMessageTransport` / `UrllibTokenTransport` | in-repo | Live OpenAPI only | `--live` / production host when flag ON; never in CI dry-run. |
| Vendored `_ed25519` | in-repo | Signature verify + op=13 | Already used by adapter `verify_and_ack`; host must pass raw body + headers into `RawInbound.metadata`. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `unittest` (+ existing qqbot/wecom patterns) | Host unit tests with injectable handler core | Prefer a pure `handle_qqbot_webhook_request(...)` function (admin-web-ui pattern) so tests never bind a real port. |
| Existing V2 gate / `compileall` | CI coverage for new `services/qqbot-service` (or chosen host path) | Gate-coverage meta-test requires every `services/*/src` to be gated — new service must get a gate entry. |
| `scripts/smoke_test.py` extension | Protocol-path dry-run + live HUMAN GATE | Add steps that call adapter/session/runtime; keep leaf steps; `--live` remains operator-only. |

---

## Installation

```bash
# No new PyPI packages for v1.9.
# Editable installs remain empty-deps:

pip install -e packages/channels/qqbot
pip install -e packages/platform-runtime
pip install -e packages/platform-contract
pip install -e packages/channel-core
pip install -e services/feedback-service
pip install -e services/qqbot-service   # new thin host (name may vary; deps=[])

# Smoke (stdlib only — already works today):
PYTHONPATH=packages/channels/qqbot/src:packages/platform-contract/src:packages/platform-runtime/src:packages/channel-core/src:services/feedback-service/src:. \
  python3 scripts/smoke_test.py --dry-run
```

---

## Integration Points

### 1. Thin production webhook host (NEW)

**Recommended location:** `services/qqbot-service/` (mirror `wecom-service` package layout + `admin-web-ui` HTTP surface).

| Layer | Responsibility | Pattern source |
|-------|----------------|----------------|
| `handle_qqbot_webhook_request(...)` | Testable core: parse headers/body → `RawInbound` → compose Protocol path → HTTP status/body | `admin_web_ui.server.handle_admin_web_ui_request` |
| `QQBotWebhookServer(BaseHTTPRequestHandler)` | Thin adapter over the pure handler | `AdminWebUiServer` |
| Feature gate | Refuse with 503 when `qqbot_channel_enabled` / config `enabled` is False | RuntimeFeatureFlags + QQBotChannelConfig |
| Composition order | `verify_and_ack` → (op=13 return challenge) → branch message vs INTERACTION → ingress/session or feedback → optional `deliver` | v1.8 audit gap #1; WeCom ingress/session split |

**WeCom parallel (important):** `services/wecom-service` owns **primitives only** (no `http.server`). QQBot package already has the WeCom-equivalent primitives (`QQBotRuntimeIngress`, `QQBotSessionRuntime`). v1.9 adds the **missing HTTP host** that WeCom never needed in-repo for acceptance (WeCom live UAT is a carried human gate). Do not import `wecom_service` from qqbot host (ADAPTER-04 / `test_no_wecom_import`).

**Host → package call sequence (opinionated):**

```
POST /qqbot/callback
  → build RawInbound(payload_ref, metadata={request_body, x_signature_*, bot_secret, payload})
  → ack = await adapter.verify_and_ack(raw)
  → if op=13 challenge: return 200 + validation_challenge_response
  → if not ack.accepted: return ack.status_code
  → return webhook body from ack.metadata["http_callback_ack_body"] ({"op": 12}) ASAP
  → background/follow-up:
       normalized = await adapter.normalize_inbound(raw)
       if feedback: handle_feedback_callback → feedback-service queue
       if message: QQBotRuntimeIngress.handle_callback → session → runtime.create_run
       on AgentResult: await adapter.deliver(ChannelDelivery(...))
```

Tier-1 ACK (`op: 12`) must stay host-local and fast; interaction PUT is already inside adapter when live IO ready.

### 2. Runtime registration / flag→config mapping (NEW wiring, no Protocol change)

| Piece | Existing API | v1.9 host duty |
|-------|--------------|----------------|
| Flag | `RuntimeFeatureFlags.qqbot_channel_enabled` (default `False`) | Host requires flag ON before constructing live adapter / serving |
| Config | `QQBotChannelConfig.from_env` (`INKSTATUTE_QQBOT_CHANNEL_ENABLED`, `*_REF`) | Map flag + env → config; resolve secret *values* from external secret store / env at process start into adapter metadata only (never into config fields) |
| Registration | `DefaultRunRuntime(..., channels=(adapter,), feature_flags=flags)` | Host factory builds runtime with QQBot adapter in `channels` when enabled; otherwise `channels=()` |
| Live IO gate | `adapter._live_io_ready()` needs `enabled` + `token_manager` + `transport` | Host injects `TokenManager` + `UrllibMessageTransport` only when flag ON and credentials present |

**Do not** add a new field to `RuntimeFeatureFlags` unless a distinct host-only lane is required. Prefer composing existing `qqbot_channel_enabled` + `run_runtime_enabled` + `channel_delivery_enabled` (all default OFF). If host needs an explicit process gate, use env `INKSTATUTE_QQBOT_CHANNEL_ENABLED` already consumed by `from_env` — avoid freezing a new Protocol method.

`DefaultRunRuntime` currently **stores** `self.channels` but does not auto-dispatch `deliver`; host (or a thin host orchestrator) remains responsible for calling `adapter.deliver` after runs complete. Registration proves the adapter is the selected channel for the runtime instance — it does not require changing `runtime.py` delivery semantics in v1.9 unless a plan explicitly adds runtime-owned delivery.

### 3. Smoke Protocol-path hardening (EXTEND existing script)

| Today (`scripts/smoke_test.py`) | v1.9 addition |
|---------------------------------|---------------|
| Leaf: signature, `send_message` text/keyboard, `handle_feedback_callback` | Keep |
| Does **not** call `QQBotChannelAdapter` / `QQBotSessionRuntime` / `DefaultRunRuntime` | Add dry-run steps |
| Fake transports only in `--dry-run` | Preserve |
| `--live` HUMAN GATE with Urllib | Preserve; do not auto-claim acceptance |

**Recommended dry-run Protocol steps (stdlib + fakes only):**

1. Build `QQBotChannelAdapter(config=enabled fixture config, token_manager=Fake..., transport=Fake...)`.
2. `verify_and_ack` on signed fixture envelope → assert `http_callback_ack_body.op == 12`.
3. `normalize_inbound` → message or feedback branch.
4. Construct `DefaultRunRuntime(backend=FakeBackendAdapter(), channels=[adapter], feature_flags=RuntimeFeatureFlags(run_runtime_enabled=True, qqbot_channel_enabled=True, ...))`.
5. `QQBotRuntimeIngress.handle_callback` (or session runtime) against sanitized C2C fixture → assert `runtime_create_called` / run_id evidence.
6. `adapter.deliver` with Fake transport → sanitized evidence (no tokens/URLs/content).

Extend `_STEP_KEY_ALLOW` with new step keys (`adapter_ack`, `adapter_normalize`, `session_ingress`, `adapter_deliver`) under the same redaction rules (`EVIDENCE_SCHEMA`, `not_live_acceptance=true` for dry-run).

### 4. Controlled live integration (HUMAN GATE)

| Concern | Stack choice |
|---------|--------------|
| Transport | Existing `Urllib*Transport` only |
| Credentials | Existing `LIVE_ENV_KEYS` in smoke; host uses same value env / secret-ref resolution |
| Acceptance | `--live` may produce evidence with `mode=live` but **must keep** `not_live_acceptance=true` unless a human archive relabel happens outside automation |
| CI | Never invoke `--live` or bind production webhook in gates |

No new live SDK. No WebSocket gateway mode in v1.9.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| New `services/qqbot-service` thin host | Extend `packages/channels/qqbot` with `http.server` module | Only if milestone explicitly forbids a new service directory. Prefer a service so gate-coverage and deploy unit match WeCom/admin patterns; keep package free of server binding. |
| stdlib `http.server` | FastAPI / Starlette / aiohttp | Never for v1.9 — breaks `dependencies=[]`, adds ASGI stack unused elsewhere for channel webhooks. |
| Host-owned composition | Reuse WeCom HTTP (none exists) or Hermes QQ gateway | Never — InkStatute owns channel ingress; Hermes must not be the user-facing boundary. |
| Inject channels into `DefaultRunRuntime` | Auto-discovery / plugin registry | Overkill; constructor injection is the frozen embeddable pattern. |
| Extend `scripts/smoke_test.py` | New pytest-only Protocol suite without CLI | Unit tests are still required; CLI smoke remains the operator one-click path from v1.8 SMOKE-*. |
| Keep vendored `_ed25519` + urllib | Add `cryptography` / `httpx` optional extras | Rejected for v1.9 — v1.8 already shipped stdlib path; adding extras now is churn without host-composition value. |

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `cryptography` / `pynacl` / `httpx` / `aiohttp` | v1.8 already solved Ed25519 + HTTP with vendored `_ed25519` + lazy urllib; new deps violate empty-deps culture for no host benefit | Existing qqbot transports + `_ed25519` |
| FastAPI / Flask / Starlette / uvicorn | Heavy frameworks; not used by channel hosts; would force dependency policy exception | stdlib `http.server` (admin-web-ui pattern) |
| `qq-botpy` / WebSocket gateway mode | Wrong abstraction; mutually exclusive with webhook; stale SDK | Webhook host composing existing adapter |
| New database / queue / Redis | Host composition does not need durable infra in v1.9; feedback queue remains in-process / existing feedback-service primitives | In-memory / existing feedback-service helpers |
| Protocol unfreeze (`ChannelAdapter` / `RunRuntime` method adds) | Contract freeze + gate tests | Compose inside host using existing 6 methods |
| Changing `RuntimeFeatureFlags` defaults to True | Safety culture | Keep defaults False; opt-in via env at deploy |
| Importing `wecom_service` into qqbot host | ADAPTER-04 / no-wecom-import invariant | Copy structural patterns only |
| Committing BotSecret / AppSecret / access tokens / raw payloads | Privacy + AGENTS safety | Env / secret refs; `payload_ref` only |
| Claiming live QQ acceptance from CI or `--live` exit 0 alone | Human gate | Sanitized evidence + operator archive |
| Rebuilding Hermes QQ channel | Out of scope | InkStatute-owned host + Hermes as backend only |

---

## Stack Patterns by Variant

**If production webhook host (primary v1.9 deliverable):**
- New service package with `dependencies = []`
- Pure request handler + optional `BaseHTTPRequestHandler` wrapper
- Compose existing qqbot adapter/ingress/feedback; inject runtime with channels tuple
- Default-OFF: process refuses callbacks when flag/config disabled (503)

**If runtime registration only (library wiring without binding port):**
- Host factory module that returns `(DefaultRunRuntime, QQBotChannelAdapter)` from env
- Still required for embedders; webhook host should call the same factory

**If smoke Protocol-path hardening:**
- Extend `scripts/smoke_test.py` + unit tests under `packages/channels/qqbot/tests` or host tests
- Fake backend + fake transports; never Urllib in dry-run

**If controlled live:**
- Reuse smoke `--live` + host manual deploy behind flag
- No new packages; operator supplies `LIVE_ENV_KEYS`

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| Python 3.11+ | All in-repo packages | CI floor; `http.server` / `asyncio` / `tomllib` available |
| `inkstatute-channels-qqbot` 0.1.0 | `platform-runtime`, `platform-contract`, `channel-core`, `feedback-service` | Already proven by 321 qqbot tests; host adds PYTHONPATH entries only |
| `RuntimeFeatureFlags.qqbot_channel_enabled` | `QQBotChannelConfig.enabled` | Both must be True for production serve; either False → fail closed |
| `DefaultRunRuntime.channels` | `QQBotChannelAdapter` | Adapter satisfies frozen `ChannelAdapter` Protocol; no runtime.py change required for registration |
| stdlib `http.server` | Sync handler + async Protocol methods | Use `asyncio.run` per request or a dedicated loop thread; avoid nesting loops |
| Smoke evidence schema `inkstatute.qqbot.smoke_evidence.v1` | New Protocol steps | Extend allowlists; keep redaction; dry-run forces `not_live_acceptance=true` |

---

## Sources

- `.planning/PROJECT.md` — v1.9 milestone goals (host composition, registration, smoke Protocol path, live HUMAN GATE). Read 2026-07-09. **HIGH**
- `.planning/milestones/v1.8-MILESTONE-AUDIT.md` — gaps_found: no production host; no runtime registration; smoke leaf-only. Read 2026-07-09. **HIGH**
- `services/wecom-service/` — library-only ingress/session pattern; `dependencies=[]`; no HTTP server. Read 2026-07-09. **HIGH**
- `services/admin-web-ui/src/admin_web_ui/server.py` — stdlib `http.server` + pure `handle_*_request` testable core + feature-flag 503. Read 2026-07-09. **HIGH**
- `packages/channels/qqbot/` — adapter, ingress_runtime, config.from_env, urllib transports, vendored `_ed25519`, `dependencies=[]`. Read 2026-07-09. **HIGH**
- `packages/platform-runtime/src/platform_runtime/runtime.py` + `feature_flags.py` + `protocols.py` — channels constructor injection; flags default OFF; ChannelAdapter frozen. Read 2026-07-09. **HIGH**
- `scripts/smoke_test.py` — dry-run leaf helpers; `--live` HUMAN GATE; evidence redaction. Read 2026-07-09. **HIGH**
- `services/feedback-service/pyproject.toml` — empty deps; host PYTHONPATH composition. Read 2026-07-09. **HIGH**
- PyPI `cryptography` 49.0.0 — verified current, but **not recommended for v1.9** given vendored Ed25519 already shipped. Checked 2026-07-09. **HIGH** (version) / **N/A** (adoption)

---

*Stack research for: v1.9 QQBot Host Composition — thin webhook host, runtime channel registration, smoke Protocol-path hardening, controlled live integration*
*Researched: 2026-07-09*
*Supersedes v1.8 STACK.md recommendations for cryptography/httpx optional extras for this milestone's host work*
