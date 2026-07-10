# Phase 69: Runtime Registration / Wiring - Research

**Researched:** 2026-07-10
**Domain:** Host factory flag→config→adapter→`DefaultRunRuntime.channels` wiring; dual default-OFF live-IO refuse path
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
All implementation choices are at the agent's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, Phase 68 host skeleton patterns, and codebase conventions to guide decisions.

### Claude's Discretion
All implementation choices are at the agent's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, Phase 68 host skeleton patterns, and codebase conventions to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
None — discuss phase skipped. Webhook composition deferred to Phase 70.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REG-01 | Host factory maps `RuntimeFeatureFlags.qqbot_channel_enabled` → `QQBotChannelConfig.enabled` and injects token_manager/transport only when live-ready (`_live_io_ready`) | Package README + adapter `_live_io_ready()` already define the contract; host `wiring.py` must perform the mapping and conditional injection. Tests prove flag True + Fake transports → `network_io=True`; flag False → no transports constructed / `_live_io_ready() is False` |
| REG-02 | Host constructs `DefaultRunRuntime` with explicit `channels=(QQBotChannelAdapter,)` injection — no auto-discovery inside platform-runtime | `DefaultRunRuntime.__init__` only stores `tuple(channels)`; no importlib/entry-point discovery exists. Host factory must pass the adapter explicitly. Do not edit `platform-runtime` for registration |
| HOST-03 | When QQBot is disabled (flags/config OFF), webhook refuses live IO with explicit non-success behavior (e.g. 503/refuse) and does not call OpenAPI transports | Adapter already returns `AckResponse(accepted=False, status_code=503)` when `config.enabled=False`. Phase 69 proves this on the **composed factory path** (no HTTP yet — Phase 70). Factory must not construct `TokenManager`/`Urllib*` when disabled so OpenAPI cannot be reached |
</phase_requirements>

## Summary

Phase 68 shipped `services/qqbot-service/` as an empty-deps skeleton (`QQBotHostConfig` refs-only, `resolve_secret_ref`, ADAPTER-04 isolation tests, V2 gate). Phase 69 adds the missing **host composition root**: a factory that maps the dual default-OFF knobs, builds `QQBotChannelAdapter` with transports only when live-ready, and injects that adapter into `DefaultRunRuntime.channels`. Webhook HTTP composition stays in Phase 70; HOST-03 is satisfied here by proving the composed factory path refuses live IO (503 / `accepted=False`) and never constructs or calls OpenAPI transports when disabled. [VERIFIED: codebase; CITED: .planning/research/ARCHITECTURE.md; .planning/research/STACK.md]

All primitives already exist: `RuntimeFeatureFlags.qqbot_channel_enabled` (default `False`), `QQBotChannelConfig.enabled` (default `False`), `QQBotChannelAdapter._live_io_ready()` (`enabled` ∧ `token_manager` ∧ `transport`), `DefaultRunRuntime(channels=...)`, `FakeBackendAdapter`, `FakeTokenTransport`, `FakeMessageTransport`, and disabled-path 503 behavior in `verify_and_ack`. The adapter deliberately does **not** import `RuntimeFeatureFlags` — mapping is host responsibility (documented in package README). [VERIFIED: packages/channels/qqbot/README.md; adapter.py; feature_flags.py; runtime.py]

**Primary recommendation:** Add `services/qqbot-service/src/qqbot_service/wiring.py` exporting a pure factory (e.g. `build_qqbot_host_runtime`) that (1) sets `QQBotChannelConfig.enabled = flags.qqbot_channel_enabled`, (2) injects `TokenManager` + message transport **only** when enabled and secrets resolve, (3) constructs `DefaultRunRuntime(backend=..., channels=(adapter,), feature_flags=flags)`, and (4) is covered by FakeBackend unit tests for enabled vs disabled without network. No new third-party packages; no `platform-runtime` Protocol or auto-discovery changes.

## Project Constraints (from .cursor/rules/)

No `.cursor/rules/` directory present in this repo. Applicable constraints come from `AGENTS.md` and Phase 68/v1.9 research:

- Keep changes scoped to the active GSD phase (wiring only; no webhook HTTP).
- Never commit secrets; config stores `*_ref` only; resolve at process edge.
- Do not import `wecom_service` into qqbot host (ADAPTER-04).
- Do not unfreeze `ChannelAdapter` (6) / `BackendAdapter` (9).
- Feature flags that gate live IO remain default OFF.
- Prefer stdlib + in-repo packages; `dependencies = []` on host and qqbot channel.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Flag→config mapping | API / Backend (host `wiring.py`) | — | Adapter must not import `RuntimeFeatureFlags`; host owns mapping [VERIFIED: qqbot README] |
| Conditional token_manager/transport injection | API / Backend (host factory) | qqbot package | `_live_io_ready` requires both deps; host decides when to inject [VERIFIED: adapter.py] |
| `DefaultRunRuntime.channels` registration | API / Backend (host factory) | platform-runtime (store only) | Explicit constructor DI; runtime does not auto-discover [VERIFIED: runtime.py] |
| Disabled-path refuse (503) | qqbot package (`verify_and_ack`) | Host factory (ensure no transports) | Package already returns 503; host must not inject live deps when OFF [VERIFIED: adapter.py] |
| Secret value resolution for TokenManager | Process edge (host `secrets.py`) | — | Phase 68 resolver; wiring calls it only when enabling live IO [VERIFIED: secrets.py] |
| FakeBackend lifecycle for unit tests | Test tier | platform-runtime fakes | Prove registration without network [VERIFIED: fakes.py] |
| HTTP webhook composition | Deferred → Phase 70 | — | Out of Phase 69 success criteria |
| Smoke Protocol-path CLI | Deferred → Phase 71 | — | Out of Phase 69 |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib (`dataclasses`, `unittest`, `asyncio`) | 3.11+ (env has 3.14.6) | Factory + tests | Empty-deps culture [VERIFIED: local env / pyproject] |
| `inkstatute-channels-qqbot` | 0.1.0 in-repo | `QQBotChannelAdapter`, `QQBotChannelConfig`, `TokenManager`, Fake/Urllib transports | Already owns Protocol IO + `_live_io_ready` [VERIFIED: codebase] |
| `platform-runtime` | in-repo | `DefaultRunRuntime`, `RuntimeFeatureFlags`, `FakeBackendAdapter` | Constructor injection surface; no edits required for REG-02 [VERIFIED: runtime.py] |
| `qqbot_service` (host) | 0.1.0 in-repo | `QQBotHostConfig`, `resolve_secret_ref`, new `wiring.py` | Phase 68 skeleton; Phase 69 adds factory [VERIFIED: services/qqbot-service] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `FakeTokenTransport` / `FakeMessageTransport` | in-repo | Network-free live-ready tests | Enabled-path unit tests only |
| `UrllibTokenTransport` / `UrllibMessageTransport` | in-repo | Production live IO | Factory production branch only when enabled + secrets present; **never** in unit tests |
| `scripts/run_v2_gates.py` gate `qqbot-service` | in-repo | PYTHONPATH already includes host + qqbot + platform-runtime | Reuse; no gate change expected unless new import paths fail |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Host `wiring.py` factory | Put registration inside `platform-runtime` | **Rejected** — REG-02 forbids auto-discovery; embeddable DI stays host-owned [CITED: STACK.md] |
| Always `channels=()` when disabled | Always `channels=(adapter,)` with `enabled=False` | Prefer **always register the adapter** so HOST-03 exercises the same composed object (503 via `verify_and_ack`). Empty `channels` when disabled is acceptable only if a separate refuse helper exists; less useful for Phase 70 |
| Teach adapter to read `RuntimeFeatureFlags` | Keep host mapping | **Rejected** — package README + ADAPTER isolation require host mapping [VERIFIED: README] |
| Construct `TokenManager` always, omit transport | Omit both when disabled | **Required** — `TokenManager()` defaults `transport` to `UrllibTokenTransport()`; constructing it when disabled risks live HTTP [VERIFIED: token_manager.py:128] |
| FastAPI / new deps for factory | Pure functions | **Rejected** — empty deps |

**Installation:**

```bash
# No new third-party packages.
# Existing editable / PYTHONPATH composition (gate already wires):
# services/qqbot-service/src + packages/channels/qqbot/src + packages/platform-runtime/src + ...
```

**Version verification:** Phase installs **zero** external registry packages. Python `3.14.6` available. In-repo packages verified via filesystem and existing V2 gate PYTHONPATH. [VERIFIED: local env / codebase]

## Package Legitimacy Audit

> Phase 69 installs **no** external packages.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| — | — | — | — | — | N/A | No installs |

**Packages removed due to slopcheck [SLOP] verdict:** none  
**Packages flagged as suspicious [SUS]:** none  

*slopcheck 0.6.1 available locally; no candidate packages to audit.* [VERIFIED: local env]

## Architecture Patterns

### System Architecture Diagram

```text
[Operator / Test / Phase 70 webhook]
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│ services/qqbot-service/wiring.py  [NEW — Phase 69]            │
│                                                               │
│  inputs: RuntimeFeatureFlags, QQBotHostConfig, backend,       │
│          env mapping, optional transport overrides            │
│                                                               │
│  1. channel_enabled = flags.qqbot_channel_enabled             │
│     (fail-closed AND with host_config.enabled recommended)    │
│  2. QQBotChannelConfig(enabled=channel_enabled, *_ref=...)    │
│  3. if channel_enabled and secrets resolve:                   │
│        TokenManager(app_id, client_secret, transport=...)     │
│        message_transport = Fake* | Urllib*                    │
│     else:                                                     │
│        token_manager=None; transport=None                     │
│  4. adapter = QQBotChannelAdapter(config, tm, transport)      │
│  5. runtime = DefaultRunRuntime(                              │
│         backend=backend,                                      │
│         channels=(adapter,),   # explicit — no discovery      │
│         feature_flags=flags,                                  │
│     )                                                         │
│  6. return HostRuntimeBundle(runtime, adapter, config, flags) │
└───────────────┬─────────────────────────────┬─────────────────┘
                │                             │
                ▼                             ▼
┌───────────────────────────┐   ┌─────────────────────────────────┐
│ QQBotChannelAdapter       │   │ DefaultRunRuntime               │
│ _live_io_ready()          │   │ self.channels = (adapter,)      │
│ disabled → ACK 503        │   │ (stores only; no auto-deliver)  │
│ no OpenAPI if not ready   │   │ FakeBackendAdapter in unit tests│
└───────────────────────────┘   └─────────────────────────────────┘

UNCHANGED: platform-runtime Protocols, feature flag defaults,
           wecom-service, webhook HTTP (Phase 70)
```

### Recommended Project Structure

```text
services/qqbot-service/
├── src/qqbot_service/
│   ├── __init__.py              # export wiring symbols + existing config/secrets
│   ├── config.py                # REUSE Phase 68 QQBotHostConfig
│   ├── secrets.py               # REUSE Phase 68 resolve_secret_ref
│   └── wiring.py                # NEW: build_qqbot_host_runtime (+ helpers)
├── tests/
│   ├── test_wiring_registration.py   # NEW: REG-01/02 FakeBackend enabled path
│   ├── test_wiring_disabled.py       # NEW: HOST-03 / REG-01 disabled refuse
│   └── (existing Phase 68 safety/secret/skeleton tests)
└── README.md                    # document factory + dual-knob mapping
```

### Pattern 1: Host-owned flag→config mapping (do not teach adapter flags)

**What:** Construct `QQBotChannelConfig(enabled=flags.qqbot_channel_enabled, …refs from host config…)`.  
**When to use:** Every host/smoke/embedder construction site.  
**Example:**

```python
# Source: packages/channels/qqbot/README.md [VERIFIED: codebase]
flags = RuntimeFeatureFlags(qqbot_channel_enabled=True)  # opt-in only in deploy/tests
adapter = QQBotChannelAdapter(
    QQBotChannelConfig(
        enabled=flags.qqbot_channel_enabled,
        app_id_ref=host_config.app_id_ref,
        app_secret_ref=host_config.app_secret_ref,
        token_secret_ref=host_config.token_secret_ref,
        bot_secret_ref=host_config.bot_secret_ref,
    ),
    token_manager=token_manager,  # only when enabling live IO
    transport=transport,
)
```

**Discretion recommendation:** Fail closed with
`enabled = flags.qqbot_channel_enabled and host_config.enabled`
so a desynced host config cannot enable live IO alone. Both currently load from `INKSTATUTE_QQBOT_CHANNEL_ENABLED` — keep that single env source for both objects when loading from env. [ASSUMED: AND is the safer composition; flag→config is the documented minimum]

### Pattern 2: Inject live deps only when intending `_live_io_ready`

**What:** Set `token_manager` and `transport` only when `enabled` and required secret values resolve; otherwise leave both `None`.  
**When to use:** Factory production and test paths.  
**Why:** `_live_io_ready()` is `enabled and token_manager is not None and transport is not None`. [VERIFIED: adapter.py:81-87]

```python
# Source: packages/channels/qqbot/tests/test_adapter_real_io.py::_live_adapter [VERIFIED]
token_manager = TokenManager(
    app_id="fixture-app-id",
    client_secret="fixture-client-secret",
    transport=FakeTokenTransport(
        response={"access_token": "fixture-token", "expires_in": 7200}
    ),
)
message_transport = FakeMessageTransport(response={"id": "msg-ok", "status": 200})
adapter = QQBotChannelAdapter(
    QQBotChannelConfig(enabled=True, bot_secret_ref="ref://qqbot/bot-secret", ...),
    token_manager=token_manager,
    transport=message_transport,
)
assert adapter._live_io_ready() is True
```

### Pattern 3: Explicit `DefaultRunRuntime` channel injection

**What:** Pass `channels=(adapter,)` at construction; never scan packages.  
**When to use:** Host factory and smoke (Phase 71).  
**Example:**

```python
# Source: packages/platform-runtime/src/platform_runtime/runtime.py [VERIFIED]
runtime = DefaultRunRuntime(
    backend=FakeBackendAdapter(),
    channels=(adapter,),
    feature_flags=RuntimeFeatureFlags(
        run_runtime_enabled=True,       # needed only if tests call create_run
        qqbot_channel_enabled=True,
    ),
)
assert runtime.channels == (adapter,)
assert runtime.channels[0] is adapter
```

### Pattern 4: Disabled refuse without HTTP (HOST-03 for Phase 69)

**What:** On the composed factory result, call `adapter.verify_and_ack(raw)` and assert `status_code == 503` / `accepted is False`; assert Fake/Urllib transport call counts stay 0.  
**When to use:** Phase 69 unit tests; Phase 70 webhook will return the same status to QQ.  
**Admin-web-ui analog:** `require_enabled` → HTTP 503 [VERIFIED: admin-web-ui/server.py] — QQBot uses adapter 503 instead of a separate host exception for channel disable.

### Anti-Patterns to Avoid

- **Dual-knob desync:** Setting `flags.qqbot_channel_enabled=True` but constructing `QQBotChannelConfig()` (still `enabled=False`). [CITED: PITFALLS.md Pitfall 3]
- **Constructing `TokenManager` when disabled:** Defaults to `UrllibTokenTransport` — accidental live HTTP. [VERIFIED: token_manager.py]
- **Auto-discovery / plugin registry in platform-runtime:** Violates REG-02 and Phase 10 embeddable DI. [CITED: STACK.md]
- **Importing `wecom_service` for “factory patterns”:** ADAPTER-04; copy structural ideas only. [VERIFIED: test_no_wecom_import.py]
- **Shipping webhook HTTP in this phase:** Deferred to Phase 70; keep factory pure and testable.
- **Flipping flag defaults to True:** Safety culture; opt-in only in tests/deploy env. [CITED: AGENTS.md / STACK.md]
- **Putting raw secrets on `QQBotChannelConfig` or `QQBotHostConfig`:** Resolve into `TokenManager(app_id=..., client_secret=...)` locals only. [VERIFIED: Phase 68 secrets]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Channel Protocol IO | Host verify/normalize/deliver | `QQBotChannelAdapter` | Already 503/live-gated; 321 package tests |
| Token cache / refresh | Host token client | `TokenManager` + injectable transport | Single-flight + TTL already shipped |
| HTTP OpenAPI client | Host urllib wrappers | `Urllib*Transport` / `Fake*Transport` | Lazy urllib; host stays composition-only |
| Run lifecycle | Host run state machine | `DefaultRunRuntime` + `FakeBackendAdapter` | Phase 10 embeddable runtime |
| Feature-flag storage | New flag type | `RuntimeFeatureFlags.qqbot_channel_enabled` | Already default OFF |
| Secret ref parsing | New resolver | `resolve_secret_ref` / `QQBotHostConfig` | Phase 68 SAFE-02 |

**Key insight:** Phase 69 is almost entirely **composition**. The failure mode is forgetting the mapping/injection rules, not missing libraries.

## Common Pitfalls

### Pitfall 1: Dual-knob desync
**What goes wrong:** Platform flag ON, adapter config OFF (or reverse) → operators think channel is live while ACK stays 503 / fixture-only.  
**Why it happens:** Adapter gates only on `QQBotChannelConfig.enabled`.  
**How to avoid:** Single factory sets `config.enabled` from `flags.qqbot_channel_enabled` (optionally AND `host_config.enabled`). Test both knobs.  
**Warning signs:** `capabilities().metadata["fixture_only"] is True` after “enabling” the flag.

### Pitfall 2: `TokenManager` default Urllib transport
**What goes wrong:** Disabled or test path constructs `TokenManager(...)` without `transport=` → first `get_token()` hits network.  
**Why it happens:** `transport or UrllibTokenTransport()` in constructor.  
**How to avoid:** Do not construct `TokenManager` unless enabling live IO; in tests always pass `FakeTokenTransport`.  
**Warning signs:** Unit tests hang/fail on DNS; transport call_count > 0 on disabled tests.

### Pitfall 3: Treating `channels=` registration as webhook complete
**What goes wrong:** REG done, operators still have no callback URL.  
**Why it happens:** `DefaultRunRuntime` is the visible hook; inbound HTTP is Phase 70.  
**How to avoid:** Phase 69 success criteria stop at factory + refuse path; do not mark HOST-01/02 done.  
**Warning signs:** README claims “production webhook” without `webhook.py`.

### Pitfall 4: Editing platform-runtime for discovery
**What goes wrong:** Adds coupling and breaks embeddable DI.  
**Why it happens:** Desire for “register channel once globally.”  
**How to avoid:** Host factory only; assert no new discovery code in `runtime.py`.  
**Warning signs:** `importlib` / entry points under `platform_runtime`.

### Pitfall 5: Enabled without secrets still injects Urllib
**What goes wrong:** Flag ON but missing app_id/secret → factory still builds Urllib transports → noisy failures / partial live.  
**Why it happens:** Checking only the boolean flag.  
**How to avoid:** Inject live deps only when `enabled` **and** resolved `app_id` + `client_secret` (and bot secret for verify path) are present; otherwise leave deps `None` so `_live_io_ready()` is False.  
**Warning signs:** `live_io_ready` True in health with empty secret env.

### Pitfall 6: Requiring `run_runtime_enabled` for registration itself
**What goes wrong:** Factory refuses to construct runtime when only qqbot flag is set.  
**Why it happens:** Confusing channel registration with `create_run`.  
**How to avoid:** Registration does not call `create_run`. Tests that exercise `create_run` opt in `run_runtime_enabled=True` separately. Channel refuse path only needs the adapter.  
**Warning signs:** Factory raises `RuntimeFeatureDisabledError` before returning a bundle.

## Code Examples

### Factory sketch (prescriptive)

```python
# Recommended shape for services/qqbot-service/src/qqbot_service/wiring.py
# Patterns sourced from qqbot README + test_adapter_real_io._live_adapter + runtime.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from inkstatute_channels_qqbot import QQBotChannelAdapter, QQBotChannelConfig
from inkstatute_channels_qqbot.sender import UrllibMessageTransport
from inkstatute_channels_qqbot.token_manager import TokenManager, UrllibTokenTransport
from platform_runtime import DefaultRunRuntime
from platform_runtime.feature_flags import RuntimeFeatureFlags
from platform_runtime.protocols import BackendAdapter

from qqbot_service.config import QQBotHostConfig
from qqbot_service.secrets import resolve_secret_ref


@dataclass(frozen=True, slots=True)
class HostRuntimeBundle:
    runtime: DefaultRunRuntime
    adapter: QQBotChannelAdapter
    channel_config: QQBotChannelConfig
    feature_flags: RuntimeFeatureFlags


def build_qqbot_host_runtime(
    *,
    backend: BackendAdapter,
    feature_flags: RuntimeFeatureFlags | None = None,
    host_config: QQBotHostConfig | None = None,
    env: Mapping[str, str] | None = None,
    token_transport: Any | None = None,
    message_transport: Any | None = None,
) -> HostRuntimeBundle:
    flags = feature_flags or RuntimeFeatureFlags()
    host = host_config or QQBotHostConfig()
    env = env or {}

    channel_enabled = bool(flags.qqbot_channel_enabled and host.enabled)
    channel_config = QQBotChannelConfig(
        enabled=channel_enabled,
        app_id_ref=host.app_id_ref,
        app_secret_ref=host.app_secret_ref,
        token_secret_ref=host.token_secret_ref,
        bot_secret_ref=host.bot_secret_ref,
    )

    token_manager = None
    transport = None
    if channel_enabled:
        app_id = resolve_secret_ref(host.app_id_ref, env)
        client_secret = resolve_secret_ref(host.app_secret_ref, env)
        if app_id and client_secret:
            token_manager = TokenManager(
                app_id=app_id,
                client_secret=client_secret,
                transport=token_transport or UrllibTokenTransport(),
            )
            transport = message_transport or UrllibMessageTransport()

    adapter = QQBotChannelAdapter(
        channel_config,
        token_manager=token_manager,
        transport=transport,
    )
    runtime = DefaultRunRuntime(
        backend=backend,
        channels=(adapter,),
        feature_flags=flags,
    )
    return HostRuntimeBundle(
        runtime=runtime,
        adapter=adapter,
        channel_config=channel_config,
        feature_flags=flags,
    )
```

### Disabled-path assertion (HOST-03 / REG-01)

```python
# Source behavior: adapter.verify_and_ack when enabled=False → 503
# [VERIFIED: packages/channels/qqbot/tests/test_feature_flag.py]

bundle = build_qqbot_host_runtime(
    backend=FakeBackendAdapter(),
    feature_flags=RuntimeFeatureFlags(),  # qqbot_channel_enabled default False
    host_config=QQBotHostConfig(),        # enabled default False
)
assert bundle.adapter._live_io_ready() is False
assert bundle.runtime.channels == (bundle.adapter,)
ack = asyncio.run(bundle.adapter.verify_and_ack(raw_inbound_fixture))
assert ack.accepted is False
assert ack.status_code == 503
```

### Enabled-path assertion (REG-01 / REG-02)

```python
# Mirror test_adapter_real_io._live_adapter; no network
flags = RuntimeFeatureFlags(qqbot_channel_enabled=True)
host = QQBotHostConfig(
    enabled=True,
    app_id_ref="env:APP_ID",
    app_secret_ref="env:APP_SECRET",
    bot_secret_ref="env:BOT_SECRET",
)
fake_token = FakeTokenTransport(response={"access_token": "t", "expires_in": 7200})
fake_msg = FakeMessageTransport(response={"id": "m1", "status": 200})
bundle = build_qqbot_host_runtime(
    backend=FakeBackendAdapter(),
    feature_flags=flags,
    host_config=host,
    env={"APP_ID": "id", "APP_SECRET": "sec", "BOT_SECRET": "bot"},
    token_transport=fake_token,
    message_transport=fake_msg,
)
assert bundle.channel_config.enabled is True
assert bundle.adapter._live_io_ready() is True
assert bundle.runtime.channels[0] is bundle.adapter
caps = bundle.adapter.capabilities()
assert caps.metadata["network_io"] is True
assert fake_token.call_count == 0  # health/capabilities must not fetch token
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Package-only QQBot (v1.8) | Host factory registers adapter into runtime | v1.9 Phase 69 | Closes audit gap “no runtime registration” |
| Leaf smoke only | (Phase 71) Protocol-path smoke using same factory | Later | Factory becomes shared composition root |
| Implicit “flag means live” | Dual knobs + `_live_io_ready` triple gate | v1.8 Phase 65 | Host must inject transports intentionally |

**Deprecated/outdated:**
- Putting HTTP server inside `packages/channels/qqbot` — rejected for v1.9 host unit.
- Auto-discovery of channels inside `platform-runtime` — rejected by REG-02.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Fail-closed `enabled = flags.qqbot_channel_enabled and host_config.enabled` is preferred over flag-only mapping | Pattern 1 | If planner uses flag-only, host_config.enabled becomes decorative — still acceptable if tests lock flag→config |
| A2 | Always register `channels=(adapter,)` even when disabled (vs `channels=()`) | Alternatives / REG-02 | STACK.md mentions empty channels when disabled; either works if HOST-03 still has a refuse API — pick one and test it |
| A3 | Phase 69 does not need a public HTTP 503 helper beyond adapter ACK — Phase 70 maps ACK status to HTTP | HOST-03 | If product wants host-level refuse before adapter construction, add a tiny `qqbot_live_io_allowed()` predicate |

**If this table is empty:** N/A — three discretion assumptions listed for planner confirmation.

## Open Questions

1. **Disabled `channels=` emptiness**
   - What we know: STACK.md says `channels=()` when disabled; REG-02 success criterion shows `channels=(QQBotChannelAdapter,)`.
   - What's unclear: Whether disabled registration should keep the adapter instance for refuse testing.
   - Recommendation: Always `(adapter,)` with `enabled=False` and no transports (A2). Document in PLAN.

2. **Production Urllib default inside factory**
   - What we know: Tests must inject Fakes; production needs Urllib.
   - What's unclear: Whether factory should require explicit transport args (safer) or default to Urllib when enabled (convenient).
   - Recommendation: Default to Urllib only when `channel_enabled` and secrets resolve; tests always pass Fake overrides (sketch above).

3. **Whether factory should also build `QQBotRuntimeIngress`**
   - What we know: ARCHITECTURE registration flow shows ingress after runtime.
   - What's unclear: Phase 69 success criteria mention runtime + adapter only.
   - Recommendation: **Defer ingress wiring to Phase 70** unless a one-liner helper is trivial; keep Phase 69 surface minimal.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | Factory + unittest | ✓ | 3.14.6 | — |
| `packages/channels/qqbot` | Adapter / TokenManager / Fakes | ✓ | 0.1.0 | — |
| `packages/platform-runtime` | DefaultRunRuntime / flags / FakeBackend | ✓ | in-repo | — |
| `services/qqbot-service` Phase 68 skeleton | Host package | ✓ | 0.1.0 | — |
| V2 gate `qqbot-service` PYTHONPATH | Host tests importing qqbot + runtime | ✓ | wired in run_v2_gates.py | — |
| Network / QQ OpenAPI | Not required for Phase 69 | N/A | — | Fakes only |
| slopcheck | Package audit | ✓ | 0.6.1 | N/A (no installs) |

**Missing dependencies with no fallback:** none  

**Missing dependencies with fallback:** none  

Step 2.6: external tools beyond Python stdlib + in-repo packages are not required.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Python unittest (stdlib) |
| Config file | none — explicit PYTHONPATH (same as Phase 68) |
| Quick run command | `PYTHONPATH="services/qqbot-service/src:packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:services/feedback-service/src" python3 -m unittest discover -s services/qqbot-service/tests -v` |
| Full suite command | `python3 scripts/run_v2_gates.py` (at minimum gates `qqbot-service`, `qqbot-channel`, `compileall`) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REG-01 | Flag True → config.enabled True; transports injected only when secrets present; `_live_io_ready` matches | unit | `python3 -m unittest services.qqbot_service.tests.test_wiring_registration -v` (via discover) | ❌ Wave 0 |
| REG-01 | Flag False → no TokenManager/Urllib; `_live_io_ready` False | unit | discover `test_wiring_disabled` | ❌ Wave 0 |
| REG-02 | `runtime.channels == (adapter,)` and adapter is `QQBotChannelAdapter`; no discovery in platform-runtime | unit | discover `test_wiring_registration` | ❌ Wave 0 |
| HOST-03 | Disabled composed path: `verify_and_ack` → 503 / not accepted; Fake transport call_count == 0 | unit | discover `test_wiring_disabled` | ❌ Wave 0 |
| REG-02 (guard) | Optional: AST/source assert `runtime.py` has no importlib entry-point channel loading | unit | can live in wiring tests or safety baseline | ❌ Wave 0 (optional) |

### Sampling Rate

- **Per task commit:** quick unittest discover for `services/qqbot-service/tests`
- **Per wave merge:** `python3 scripts/run_v2_gates.py` (or `qqbot-service` + `qqbot-channel` + `compileall`)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `services/qqbot-service/tests/test_wiring_registration.py` — covers REG-01 enabled + REG-02
- [ ] `services/qqbot-service/tests/test_wiring_disabled.py` — covers REG-01 disabled + HOST-03
- [ ] `services/qqbot-service/src/qqbot_service/wiring.py` — factory under test (implement with TDD)
- [ ] Export wiring symbols from `qqbot_service/__init__.py`
- [ ] Update host README with flag→config + factory usage

*Existing unittest + V2 gate infrastructure is sufficient; no new test framework.*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | partial | QQ callback auth stays in adapter (Ed25519); factory only resolves bot/app secrets at edge |
| V3 Session Management | no | Out of scope |
| V4 Access Control | yes | Dual default-OFF flags; refuse when disabled |
| V5 Input Validation | yes | Secret ref normalization (Phase 68); no raw secrets on config |
| V6 Cryptography | no new | Do not reimplement Ed25519; package owns it |

### Known Threat Patterns for host wiring

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Accidental live OpenAPI from CI/unit tests | Information Disclosure / Elevation | Never construct `TokenManager` without Fake transport in tests; disabled path leaves deps `None` |
| Secret material on config/dataclass dumps | Information Disclosure | Keep `*_ref` only; resolve into locals for TokenManager |
| Flag bypass (config enabled while flag off) | Elevation of Privilege | Map/AND flag → config.enabled in one factory |
| WeCom coupling | Tampering / scope creep | Keep `test_no_wecom_import` green on new `wiring.py` |
| Auto-discovery loading unexpected channels | Tampering | Explicit `channels=(adapter,)` only |

## Sources

### Primary (HIGH confidence)

- `packages/channels/qqbot/README.md` — host flag→config mapping contract
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py` — `_live_io_ready`, disabled 503
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/config.py` — `enabled` default False, `from_env`
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/token_manager.py` — Urllib default transport pitfall
- `packages/platform-runtime/src/platform_runtime/runtime.py` — `channels` constructor storage only
- `packages/platform-runtime/src/platform_runtime/feature_flags.py` — `qqbot_channel_enabled` default False
- `packages/platform-runtime/src/platform_runtime/fakes.py` — `FakeBackendAdapter`
- `services/qqbot-service/` — Phase 68 config/secrets/tests/gate
- `packages/channels/qqbot/tests/test_feature_flag.py` / `test_adapter_real_io.py` — refuse + live-ready patterns
- `.planning/research/ARCHITECTURE.md` / `STACK.md` / `PITFALLS.md` — v1.9 registration design
- `.planning/REQUIREMENTS.md` — REG-01, REG-02, HOST-03
- `.planning/ROADMAP.md` — Phase 69 success criteria

### Secondary (MEDIUM confidence)

- `services/admin-web-ui/src/admin_web_ui/server.py` — feature-flag 503 pattern analog (different flag)
- Phase 68 RESEARCH/VALIDATION — host test PYTHONPATH and gate conventions

### Tertiary (LOW confidence)

- None material; discretion items listed under Assumptions Log (A1–A3)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — reuse only; zero new packages; verified in repo
- Architecture: HIGH — ARCHITECTURE/STACK + shipped adapter/runtime APIs align
- Pitfalls: HIGH — PITFALLS.md dual-knob + verified TokenManager Urllib default

**Research date:** 2026-07-10  
**Valid until:** 2026-08-09 (30 days; stable in-repo APIs)
