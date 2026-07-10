# Phase 69: Runtime Registration / Wiring - Research

**Researched:** 2026-07-10
**Domain:** Host factory flag→config→adapter→`DefaultRunRuntime.channels` wiring; dual default-OFF knobs; refuse live IO when disabled
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None — discuss phase was skipped. No D-XX IDs.

### Claude's Discretion
All implementation choices are at the agent's discretion. Use ROADMAP phase goal, success criteria, Phase 68 host skeleton patterns, and codebase conventions.

### Deferred Ideas (OUT OF SCOPE)
- Webhook HTTP composition → Phase 70
- Smoke Protocol-path hardening → Phase 71
- Controlled live `--live` HUMAN GATE → Phase 72
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REG-01 | Host factory maps `RuntimeFeatureFlags.qqbot_channel_enabled` → `QQBotChannelConfig.enabled` and injects token_manager/transport only when live-ready (`_live_io_ready`) | Adapter already gates on `config.enabled` + injected deps via `_live_io_ready()`; host must perform the mapping (adapter must not import flags). [VERIFIED: adapter.py, README] |
| REG-02 | Host constructs `DefaultRunRuntime` with explicit `channels=(QQBotChannelAdapter,)` — no auto-discovery inside platform-runtime | `DefaultRunRuntime.__init__` already accepts `channels: Iterable[ChannelAdapter] = ()`; registration is host construction only. [VERIFIED: runtime.py] |
| HOST-03 | When QQBot disabled (flags/config OFF), composed path refuses live IO with explicit non-success (e.g. 503/refuse) and does not call OpenAPI transports | Disabled adapter returns ACK `503` / `accepted=False` deliver; Fake transports must show `call_count==0`. [VERIFIED: test_feature_flag.py, FakeMessageTransport] |
</phase_requirements>

## Summary

Phase 68 delivered `services/qqbot-service/` (empty deps, refs-only `QQBotHostConfig`, `resolve_secret_ref`, ADAPTER-04 isolation). Phase 69 adds the **composition root** that v1.9 research named `wiring.py`: map dual default-OFF knobs, optionally inject Fake/Urllib transports so `_live_io_ready()` is honest, and construct `DefaultRunRuntime(channels=(adapter,))` with an injected backend (FakeBackend in unit tests).

No Protocol changes, no `platform-runtime` auto-discovery, no webhook HTTP (Phase 70), no smoke/live (71–72). Package `inkstatute_channels_qqbot` already owns Protocol IO; the host only wires.

**Primary recommendation:** Add `services/qqbot-service/src/qqbot_service/wiring.py` exporting a frozen composition result + factory functions; cover REG-01/REG-02/HOST-03 with FakeBackend + FakeTokenTransport + FakeMessageTransport unit tests under the existing `qqbot-service` gate PYTHONPATH.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Flag→config mapping | Host (`wiring.py`) | — | Adapter must not import `RuntimeFeatureFlags` (README + freeze) |
| Secret resolve for TokenManager | Host process edge (`secrets.resolve_secret_ref`) | Env Mapping | Phase 68 SAFE-02; values never on config |
| token_manager + transport injection | Host factory | Package TokenManager / Fake*/Urllib* | `_live_io_ready` requires both when enabled |
| `DefaultRunRuntime.channels` registration | Host factory | platform-runtime constructor | Explicit DI; no auto-discovery |
| Refuse live IO when disabled | Package adapter behavior | Host tests prove composition | 503 ACK / refused deliver; zero transport calls |
| Webhook HTTP | Deferred → Phase 70 | — | Out of Phase 69 success criteria |
| Protocol-path smoke | Deferred → Phase 71 | — | Out of scope |
| Live Urllib production path | Deferred → Phase 72 | Host may accept injectable transports now | Phase 69 tests use Fakes only |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.11+ | Factory + unittest | Host `dependencies = []` [VERIFIED] |
| `platform_runtime.RuntimeFeatureFlags` | in-repo | Platform knob `qqbot_channel_enabled` | Already default False |
| `platform_runtime.DefaultRunRuntime` | in-repo | Explicit `channels=` DI | Constructor already supports it |
| `platform_runtime.fakes.FakeBackendAdapter` | in-repo | Unit-test backend | No network |
| `inkstatute_channels_qqbot.QQBotChannelConfig` / `QQBotChannelAdapter` | in-repo | Channel Protocol | Reuse; do not thicken |
| `TokenManager` + `FakeTokenTransport` | in-repo | Live-ready token path | Inject only when enabled + secrets |
| `FakeMessageTransport` | in-repo | Live-ready message path | Assert `call_count==0` when disabled |
| `qqbot_service.QQBotHostConfig` / `resolve_secret_ref` | Phase 68 | Refs + edge resolve | Copy refs into channel config |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Host `wiring.py` factory | Teach adapter to import `RuntimeFeatureFlags` | **Rejected** — breaks embeddability / dual-knob docs / freeze culture |
| Explicit `channels=(adapter,)` | Auto-register inside `DefaultRunRuntime` when flag True | **Rejected** — REG-02 forbids; hides DI |
| Skip transports until Phase 72 | Always inject Urllib when flag ON | **Rejected for tests** — Phase 69 must prove wiring without network; inject Fakes in tests, optional injectable transports for later live |
| Extend wecom-service | New QQ host wiring | **Rejected** — ADAPTER-04 |

### Package Legitimacy Audit

> Phase 69 installs **no** external packages.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| — | — | — | — | — | N/A | No installs |

## Architecture Patterns

### System diagram (Phase 69 scope)

```text
RuntimeFeatureFlags.qqbot_channel_enabled ──┐
QQBotHostConfig (*_ref, enabled) ───────────┼──► wiring.build_* ──► QQBotChannelConfig(enabled=flag)
                                            │         │
env Mapping ── resolve_secret_ref ──────────┤         ├──► TokenManager + transport
                                            │         │      (only if enabled AND secrets
                                            │         │       AND transports provided)
                                            │         ▼
                                            │   QQBotChannelAdapter
                                            │         │
FakeBackendAdapter (tests) ─────────────────┴──► DefaultRunRuntime(channels=(adapter,), ...)
```

### Recommended factory surface (discretion)

| Symbol | Role |
|--------|------|
| `QQBotWiredRuntime` (frozen dataclass) | Holds `feature_flags`, `host_config`, `channel_config`, `adapter`, `runtime`, `live_io_ready: bool` |
| `build_qqbot_channel_config(*, flags, host_config) -> QQBotChannelConfig` | Maps `enabled=flags.qqbot_channel_enabled`; copies `*_ref` from host config |
| `build_qqbot_wired_runtime(*, flags=None, host_config=None, backend=None, env=None, token_manager=None, transport=None, ...) -> QQBotWiredRuntime` | Composition root; constructs adapter + `DefaultRunRuntime(channels=(adapter,), feature_flags=flags, backend=...)` |

**Live injection rule (REG-01):** Inject `token_manager` and `transport` only when all are true:
1. `flags.qqbot_channel_enabled` is True (mapped into `channel_config.enabled`)
2. Caller supplied both deps **or** factory can build `TokenManager` from resolved `app_id` + `client_secret` via `resolve_secret_ref` **and** a message `transport` is supplied
3. Never construct `Urllib*` transports inside unit tests; tests pass `FakeTokenTransport` / `FakeMessageTransport`

When flag is False: construct adapter with `enabled=False` and **omit** token_manager/transport so `_live_io_ready()` is False; still register that adapter in `channels=(adapter,)` (explicit registration ≠ live IO).

**Authoritative enabled knob:** `RuntimeFeatureFlags.qqbot_channel_enabled` drives `QQBotChannelConfig.enabled`. Host config `enabled` is informational / env-derived; factory must not enable the channel from host_config alone while the platform flag is False (Pitfall 3 dual-knob desync).

### Existing code anchors

| Path | Fact |
|------|------|
| `packages/channels/qqbot/.../adapter.py` | `_live_io_ready()` = enabled ∧ token_manager ∧ transport; disabled ACK → 503 |
| `packages/channels/qqbot/README.md` | Host maps flag→config; adapter does not import flags |
| `packages/platform-runtime/.../runtime.py` | `channels: Iterable[ChannelAdapter] = ()` |
| `services/qqbot-service/.../config.py` | Refs-only `QQBotHostConfig` |
| `scripts/run_v2_gates.py` | `qqbot-service` gate already includes qqbot + platform-runtime PYTHONPATH |

## Don't Hand-Roll

| Problem | Existing solution | Where |
|---------|-------------------|-------|
| Token cache / refresh | `TokenManager` | `token_manager.py` |
| Message HTTP | `FakeMessageTransport` / `UrllibMessageTransport` | `sender.py` |
| Backend for unit tests | `FakeBackendAdapter` | `platform_runtime.fakes` |
| Secret edge resolve | `resolve_secret_ref` | Phase 68 `secrets.py` |
| Disabled refuse semantics | Adapter verify_and_ack / deliver | Do not reimplement 503 in host |

## Common Pitfalls

| Pitfall | Avoidance |
|---------|-----------|
| Dual-knob desync (flag True, config False) | Single factory maps `enabled=flags.qqbot_channel_enabled`; test both directions |
| Flag True without transports → silent fixture-only | Document `live_io_ready` on result; tests assert False when transports omitted |
| Claiming registration done without refuse proof | HOST-03 tests: disabled path 503 + `transport.call_count==0` |
| Auto-discovery in platform-runtime | REG-02 test: grep/AST `platform_runtime` has no `inkstatute_channels_qqbot` / qqbot import for registration |
| Webhook in this phase | Do not add `webhook.py` / `http_server.py` |
| WeCom import | Keep Phase 68 `test_no_wecom_import.py` green |
| Raw secrets on config | Build TokenManager from `resolve_secret_ref` results only; never assign secrets onto `QQBotHostConfig` / `QQBotChannelConfig` |

## Validation Architecture (Nyquist)

| Requirement | Test file (planned) | Automated command |
|-------------|---------------------|-------------------|
| REG-01 | `tests/test_wiring_flag_config.py` | unittest discover host tests |
| REG-02 | `tests/test_runtime_registration.py` | same |
| HOST-03 | `tests/test_wiring_disabled_refuse.py` | same + Fake transport call_count |

Existing infra: unittest + `qqbot-service` V2 gate. No new framework.

## Out of Scope

- HTTP webhook / raw-body capture / ACK-first HTTP semantics (Phase 70)
- Smoke `--dry-run` Protocol path (Phase 71)
- Live Urllib + HUMAN GATE (Phase 72)
- Changing ChannelAdapter / BackendAdapter Protocols
- Modifying `DefaultRunRuntime` to discover channels
- Teaching adapter to import `RuntimeFeatureFlags`

## Discretion Decisions (planning locks)

| ID | Decision |
|----|----------|
| W-01 | Module path `services/qqbot-service/src/qqbot_service/wiring.py` |
| W-02 | Frozen result type `QQBotWiredRuntime` with `live_io_ready` mirror of adapter helper |
| W-03 | Platform flag is sole enable authority for `QQBotChannelConfig.enabled` |
| W-04 | Disabled path still places adapter in `channels=(adapter,)` but without transports |
| W-05 | Unit tests inject Fakes only; factory accepts optional prebuilt `token_manager`/`transport` for live-ready proof without network |
| W-06 | No webhook modules in this phase |

## Sources

- `.planning/ROADMAP.md` Phase 69 success criteria
- `.planning/REQUIREMENTS.md` REG-01, REG-02, HOST-03
- `.planning/research/{SUMMARY,ARCHITECTURE,FEATURES,PITFALLS,STACK}.md` v1.9
- Phase 68 SUMMARYs + host package
- `packages/channels/qqbot` adapter/README/tests
- `packages/platform-runtime` runtime + fakes

**Confidence:** HIGH — all APIs exist; phase is composition + tests only.
