# Phase 68: Host Skeleton + Safety Baseline - Research

**Researched:** 2026-07-10
**Domain:** Deployable QQBot host service skeleton, ADAPTER-04 isolation, secret-ref discipline, V2 gate coverage
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
All implementation choices are at the agent's Discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Claude's Discretion
All implementation choices are at the agent's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
None — discuss phase skipped.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SAFE-01 | Host layer preserves ADAPTER-04 invariants: Protocol freeze (ChannelAdapter 6 methods), no `wecom_service` import into qqbot host/package path, feature flags default OFF | Reuse v1.8 tests (`test_v1_8_safety_baseline.py`, `test_no_wecom_import.py`, `test_feature_flag.py`); extend host-scoped AST scan + Protocol count + flag default assertions under `services/qqbot-service/tests/` |
| SAFE-02 | Secrets remain refs in config; values resolve only at process edge — never committed; evidence/logs stay reference-first | Mirror `QQBotChannelConfig` `*_ref` fields + `test_config_keeps_secret_refs_only`; add host `config.py` (refs only) + `secrets.py` (edge resolver); tests prove `asdict(config)` has no raw values and resolver never writes values into config |
</phase_requirements>

## Summary

Phase 68 closes the v1.8 audit gap of “no in-repo host” **without** shipping webhook composition (Phase 70) or runtime registration (Phase 69). Today `services/qqbot-service/` does not exist; `packages/channels/qqbot/` already owns Protocol methods, crypto, normalize, token, egress, and dual default-OFF knobs. The host must be a new thin service with `dependencies = []`, a dedicated V2 gate PYTHONPATH entry (required by `test_gate_coverage.py`), and safety tests that reaffirm ADAPTER-04 + secret-ref discipline before any HTTP path lands. [VERIFIED: codebase]

v1.9 research (`ARCHITECTURE.md`, `STACK.md`, `PITFALLS.md`) already prescribed `services/qqbot-service/` as composition-only, forbidding WeCom route extension and Protocol unfreeze. Phase 68 should create the **minimum deployable skeleton**: package layout, empty deps, host config/secrets modules, safety tests, gate + compileall wiring, and a Phase-08 presence check — leaving `wiring.py` / `webhook.py` / `http_server.py` stubs optional or deferred to 69–70 so success criteria stay honest. [CITED: .planning/research/ARCHITECTURE.md; .planning/ROADMAP.md]

**Primary recommendation:** Create `services/qqbot-service/` mirroring wecom/admin `pyproject.toml` (`dependencies = []`, setuptools `src/` layout), add host `config.py` (refs only) + `secrets.py` (resolve at process edge), wire a new `qqbot-service` V2 gate + compileall path, and ship host tests that freeze Protocols, ban `wecom_service`, assert flags OFF, prove secret-ref discipline, and assert `.planning/phases/08-lawyer-trial-acceptance/` still exists.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Host package layout + empty deps | API / Backend (service package) | — | Deployable unit under `services/`; matches wecom/admin/feedback pattern |
| V2 gate PYTHONPATH + compileall coverage | CI / Backend tooling | — | `test_gate_coverage.py` fails if any `services/*/src` lacks gate coverage |
| ADAPTER-04 Protocol freeze assertions | API / Backend (tests) | platform-runtime | Runtime introspection of frozen Protocols; do not edit Protocols |
| No-wecom import isolation (host + package) | API / Backend (tests) | — | AST/string scan; host must not import `wecom_service` |
| Feature-flag default OFF | platform-runtime | Host tests | Flag already exists default `False`; host tests reaffirm, do not flip defaults |
| Host config secret refs | API / Backend (host config) | — | Config stores `*_ref` only; never raw secrets |
| Secret value resolution | Process edge (host secrets module) | Env / secret store | Values read from env/mapping at edge; never committed or stored in config |
| Phase 08 human-gate preservation | Planning artifacts | CI assertion | Explicit success criterion; do not delete carried UAT templates |
| Webhook HTTP composition | Deferred → Phase 70 | — | Out of Phase 68 success criteria |
| Flag→config→adapter factory / DefaultRunRuntime | Deferred → Phase 69 | — | Out of Phase 68 success criteria |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib (`dataclasses`, `unittest`, `ast`, `pathlib`, `os`) | 3.11+ (repo `requires-python`) | Host skeleton, tests, secret edge resolver | Entire channel/service culture is `dependencies = []` [VERIFIED: codebase] |
| setuptools | `>=68` (match wecom/admin) | Editable package layout | Same as `services/wecom-service/pyproject.toml` [VERIFIED: codebase] |
| `inkstatute-channels-qqbot` | 0.1.0 in-repo | Channel Protocol implementation (import later phases; Phase 68 may only reference for isolation tests) | Already shipped v1.8; host composes, does not reimplement [VERIFIED: codebase] |
| `platform-runtime` | in-repo | `RuntimeFeatureFlags`, `ChannelAdapter` / `BackendAdapter` Protocols | Freeze + flag assertions [VERIFIED: codebase] |
| `platform-contract` | in-repo | Enums if needed for freeze checks | Existing freeze tests use it [VERIFIED: codebase] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `scripts/run_v2_gates.py` | in-repo | Register `qqbot-service` gate + compileall | Required when `services/qqbot-service/src` appears [VERIFIED: codebase] |
| `packages/contract-test-suite/tests/test_gate_coverage.py` | in-repo | Meta-test that every `services/*/src` is gated | Will fail until gate entry exists [VERIFIED: codebase] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| New `services/qqbot-service/` | Extend `services/wecom-service` with QQ routes | **Rejected** — ADAPTER-04 / no-wecom; WeCom crypto/XML ≠ QQ Ed25519/gateway [CITED: .planning/research/ARCHITECTURE.md] |
| New `services/qqbot-service/` | Put `http.server` inside `packages/channels/qqbot` | **Rejected for host unit** — package stays library-pure; gate/deploy unit should be a service [CITED: .planning/research/STACK.md] |
| `dependencies = []` | FastAPI / Starlette | **Rejected** — breaks empty-deps culture; unused ASGI stack for channel webhooks [CITED: .planning/research/STACK.md] |
| Host secret resolver | Store raw secrets in config dataclass | **Rejected** — violates SAFE-02 / AGENTS.md |

**Installation:**

```bash
# No new third-party packages. Editable install optional for local ops:
pip install -e services/qqbot-service
```

**Version verification:** Phase installs **zero** external registry packages. Existing stack verified via repo `pyproject.toml` files (`dependencies = []`) and Python `3.14.6` available in the research environment. [VERIFIED: local env / codebase]

## Package Legitimacy Audit

> Phase 68 installs **no** external packages. Host and package remain `dependencies = []`.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| — | — | — | — | — | N/A | No installs |

**Packages removed due to slopcheck [SLOP] verdict:** none  
**Packages flagged as suspicious [SUS]:** none  

*slopcheck 0.6.1 was available locally; no candidate packages to audit because the phase adds none.* [VERIFIED: local env]

## Architecture Patterns

### System Architecture Diagram

```text
┌─────────────────────────────────────────────────────────────────┐
│ CI / Operator                                                       │
│   scripts/run_v2_gates.py ──► Gate("qqbot-service")                 │
│   compileall includes services/qqbot-service/src                    │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ services/qqbot-service/  [NEW — Phase 68 skeleton]                  │
│                                                                     │
│  config.py ── stores *_ref only (no raw secrets)                    │
│  secrets.py ── resolve(ref) at process edge from env/mapping        │
│  __init__.py ── package export surface (minimal)                    │
│                                                                     │
│  tests/                                                             │
│    ├── Protocol freeze (6 / 9 methods)                              │
│    ├── no wecom_service import (host src AST scan)                  │
│    ├── RuntimeFeatureFlags.qqbot_channel_enabled is False           │
│    ├── secret refs only + edge resolve                              │
│    ├── dependencies = []                                            │
│    └── Phase 08 directory still present                             │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ imports allowed later (69+)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ packages/channels/qqbot/  [REUSE — do not thicken]                  │
│   QQBotChannelConfig (*_ref), QQBotChannelAdapter (6 methods)       │
│   test_no_wecom_import / test_v1_8_safety_baseline (keep green)     │
└─────────────────────────────────────────────────────────────────┘

UNCHANGED: services/wecom-service/, platform-runtime Protocols,
           platform-contract schemas, channel-core modules
DEFERRED:  wiring / webhook / http_server (Phases 69–70)
```

### Recommended Project Structure

```text
services/qqbot-service/
├── pyproject.toml                 # name=inkstatute-qqbot-service, dependencies=[]
├── README.md                      # host owns HTTP/secrets later; Phase 68 = skeleton + safety
├── src/qqbot_service/
│   ├── __init__.py                # minimal exports (config + secrets helpers)
│   ├── config.py                  # HostConfig / QQBotHostConfig — refs + enabled default False
│   └── secrets.py                 # resolve_secret_ref(ref, env) — values only at edge
├── tests/
│   ├── test_safety_baseline.py    # Protocol 6/9, flag OFF, deps=[], Phase 08 present
│   ├── test_no_wecom_import.py     # AST scan of host src (mirror package test)
│   └── test_secret_refs.py        # config refs-only; resolver does not mutate config
└── (optional stubs — prefer defer to 69/70 unless needed for import surface)
    # wiring.py, webhook.py, http_server.py  → Phase 69–70
```

### Pattern 1: Empty-deps service skeleton (wecom / admin analog)

**What:** setuptools project under `services/<name>/` with `dependencies = []`, `package-dir = {"" = "src"}`, and unittest discover under `tests/`.  
**When to use:** Every new InkStatute service in V2/v1.x.  
**Example:**

```toml
# Source: services/wecom-service/pyproject.toml [VERIFIED: codebase]
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "inkstatute-qqbot-service"
version = "0.1.0"
description = "InkStatute-owned QQBot webhook host skeleton (composition-only)."
requires-python = ">=3.11"
dependencies = []

[tool.setuptools]
package-dir = { "" = "src" }

[tool.setuptools.packages.find]
where = ["src"]
```

### Pattern 2: V2 gate + compileall coverage (mandatory)

**What:** Add a dedicated `Gate` whose PYTHONPATH includes `services/qqbot-service/src` (plus qqbot/platform paths as tests need), and add the same `src` path to the `compileall` gate command list.  
**When to use:** Immediately when creating any new `services/*/src`.  
**Why:** `test_all_services_src_covered` fails otherwise. [VERIFIED: packages/contract-test-suite/tests/test_gate_coverage.py]

```python
# Source: scripts/run_v2_gates.py pattern [VERIFIED: codebase]
Gate(
    "qqbot-service",
    (py, "-m", "unittest", "discover", "-s", "services/qqbot-service/tests"),
    (
        qqbot_service_src,   # services/qqbot-service/src
        qqbot_src,           # packages/channels/qqbot/src (if tests import package)
        channel_core_src,
        platform_src,
        platform_runtime_src,
        # feedback_src only if a Phase 68 test imports it — prefer not yet
    ),
),
# Also append "services/qqbot-service/src" to compileall args.
```

### Pattern 3: Secret refs in config; values at process edge

**What:** Config dataclass fields end in `_ref` and hold opaque reference strings (`secret://…` / `ref://…`). A separate resolver reads **value** env vars (or a provided mapping) and returns the secret string for injection into adapter metadata / transports — never assigning raw values onto the config object.  
**When to use:** Host boot and tests proving SAFE-02.  
**Existing analogs:**

- Package: `QQBotChannelConfig.app_secret_ref` / `bot_secret_ref` via `from_env` reading `*_REF` keys only. [VERIFIED: packages/channels/qqbot/src/inkstatute_channels_qqbot/config.py]
- Adapter: raw `bot_secret` injected on `RawInbound.metadata` at call time, not stored on config. [VERIFIED: packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py]
- Smoke live: value env vars `INKSTATUTE_QQBOT_BOT_SECRET`, `INKSTATUTE_QQBOT_CLIENT_SECRET` distinct from `*_REF`. [CITED: runbook/SMOKE_TEST_RUNBOOK.md]
- Admin edge: `resolve_admin_token(env)` reads `ADMIN_API_TOKEN` from mapping/env. [VERIFIED: services/admin-console-api/src/admin_console_api/auth.py]

**Recommended host resolver contract (discretion):**

```python
# Recommended pattern for services/qqbot-service/src/qqbot_service/secrets.py
# [ASSUMED] exact env key map — align with smoke value vars where possible

REF_TO_VALUE_ENV = {
    "secret://qqbot/bot-secret": "INKSTATUTE_QQBOT_BOT_SECRET",
    "secret://qqbot/app-secret": "INKSTATUTE_QQBOT_CLIENT_SECRET",
    "secret://qqbot/app-id": "INKSTATUTE_QQBOT_APP_ID",
    # token secret if needed later
}

def resolve_secret_ref(ref: str | None, env: Mapping[str, str]) -> str | None:
    """Return secret value for ref from env; never log the value."""
    if not ref:
        return None
    key = REF_TO_VALUE_ENV.get(ref)
    if key is None:
        # Allow ref that is itself an env var name, or fail closed
        key = ref if ref.isidentifier() or ref.startswith("INKSTATUTE_") else None
    if key is None:
        return None
    value = env.get(key, "")
    return value or None
```

### Pattern 4: Host-scoped ADAPTER-04 safety tests

**What:** Copy the proven assertion style from v1.8 package tests into the host test suite (do not weaken package tests).  
**When to use:** Phase 68 exit criteria.  
**Assertions to include:**

| Check | Source pattern |
|-------|----------------|
| ChannelAdapter method count == 6 | `test_v1_8_safety_baseline.py` / `test_contract_freeze_not_violated.py` |
| BackendAdapter method count == 9 | same |
| `RuntimeFeatureFlags().qqbot_channel_enabled is False` | `test_feature_flag.py` |
| `dependencies = []` in host `pyproject.toml` | `test_qqbot_pyproject_has_empty_dependencies` |
| No `wecom_service` in host `src/**/*.py` | extend AST scan from `test_no_wecom_import.py` |
| Phase 08 path exists | `Path(".planning/phases/08-lawyer-trial-acceptance").is_dir()` |
| Config `asdict` has no raw secret substrings | `test_config_keeps_secret_refs_only` |

### Anti-Patterns to Avoid

- **Fat host in Phase 68:** Implementing webhook/ACK/ingress composition now — belongs in Phase 70. [CITED: .planning/ROADMAP.md]
- **Extending wecom-service:** Violates ADAPTER-04 and couples channels. [CITED: .planning/research/ARCHITECTURE.md]
- **Editing Protocols / feature_flags defaults / channel-core:** Freeze surface; only assert. [VERIFIED: ADAPTER-04 / Phase 58]
- **Putting raw secrets in config or fixtures committed to git:** SAFE-02 / Pitfall 13. [CITED: .planning/research/PITFALLS.md]
- **Deleting Phase 08:** Explicit out-of-scope / success criterion 5. [CITED: .planning/REQUIREMENTS.md]
- **Skipping gate PYTHONPATH:** Instant `gate-coverage-meta-test` failure. [VERIFIED: test_gate_coverage.py]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Channel Protocol surface | New 7th ChannelAdapter method | Existing 6 methods + host HTTP glue later | Freeze tests + all channel implementers [VERIFIED: protocols.py] |
| QQ crypto / normalize / send | Copy into host | `inkstatute_channels_qqbot` | Already 321 package tests; host is composition [CITED: v1.8 audit] |
| WeCom helpers for QQ | Import `wecom_service` | `channel_core` + qqbot package | ADAPTER-04 isolation [VERIFIED: test_no_wecom_import.py] |
| Secret storage framework | Custom vault client / new dep | Env mapping resolver at process edge | Matches smoke + admin token pattern; keeps `dependencies=[]` |
| HTTP framework | FastAPI etc. | Deferred stdlib `http.server` (Phase 70) | Empty-deps culture [CITED: STACK.md] |
| Gate discovery | Ad-hoc CI scripts only | `run_v2_gates.py` Gate entry | Meta-test enforces coverage [VERIFIED: codebase] |

**Key insight:** Phase 68 is a **safety fence + empty deployable unit**, not a second channel implementation. Reuse package invariants; add host-scoped copies of the same checks; wire CI coverage before any live IO composition.

## Common Pitfalls

### Pitfall 1: Creating `services/qqbot-service/src` without a gate entry
**What goes wrong:** `gate-coverage-meta-test` fails; CI red before any host logic ships.  
**Why it happens:** Gate list is hand-maintained; new service directories are auto-discovered by the meta-test.  
**How to avoid:** In the same change set: add `Gate("qqbot-service", …)`, append compileall path, run `python3 -m unittest packages.contract-test-suite.tests.test_gate_coverage` (via gate).  
**Warning signs:** PR adds `services/qqbot-service/` but does not touch `scripts/run_v2_gates.py`.

### Pitfall 2: Shipping webhook composition under “skeleton”
**What goes wrong:** Phase 68 balloons into Phase 70; review/verification blur; dual-knob wiring incomplete.  
**Why it happens:** ARCHITECTURE.md shows full tree including `webhook.py`.  
**How to avoid:** Treat ARCHITECTURE tree as milestone target; Phase 68 only needs layout + config/secrets + safety tests + gate. Defer wiring/webhook.  
**Warning signs:** Host files contain `verify_and_ack` orchestration or `BaseHTTPRequestHandler`.

### Pitfall 3: Narrowing no-wecom scans to old package files only
**What goes wrong:** Host imports `wecom_service` while package tests stay green.  
**Why it happens:** Existing `test_no_wecom_import.py` only scans `packages/channels/qqbot/src`.  
**How to avoid:** Host-local AST scan over `services/qqbot-service/src/qqbot_service/**/*.py`; keep package scan intact.  
**Warning signs:** Host `from wecom_service…` or string `wecom_service` in host src.

### Pitfall 4: Resolving secrets into config fields
**What goes wrong:** `HostConfig.bot_secret = "raw…"` ends up in logs/`asdict`/commits.  
**Why it happens:** Convenience at boot.  
**How to avoid:** Config only has `*_ref`; resolver returns ephemeral strings for call-site injection; tests assert config serialization never contains value env contents.  
**Warning signs:** Config field names without `_ref` holding credentials.

### Pitfall 5: Flipping `qqbot_channel_enabled` default to True
**What goes wrong:** Accidental live IO; ADAPTER-02 / SAFE-01 break.  
**Why it happens:** “Host exists so enable the channel.”  
**How to avoid:** Never edit `feature_flags.py` defaults in this phase; only assert `False`.  
**Warning signs:** Diff in `packages/platform-runtime/.../feature_flags.py`.

### Pitfall 6: Deleting or relocating Phase 08 artifacts
**What goes wrong:** Carried human-gate evidence template disappears.  
**Why it happens:** Planning hygiene during new milestone.  
**How to avoid:** Explicit test that `.planning/phases/08-lawyer-trial-acceptance/` exists (and ideally that `08-TRIAL-EVIDENCE-TEMPLATE.json` is present).  
**Warning signs:** Git status shows deleted `08-*` paths.

### Pitfall 7: Adding package dependencies “just for the host”
**What goes wrong:** Breaks `dependencies = []` invariant expected by ADAPTER-04 / v1.8 safety.  
**Why it happens:** Temptation to add HTTP/crypto libs.  
**How to avoid:** Host `pyproject.toml` stays empty; compose via PYTHONPATH like other services.  
**Warning signs:** Non-empty `dependencies = [` in host or qqbot package pyproject.

## Code Examples

### Protocol freeze introspection

```python
# Source: packages/channels/qqbot/tests/test_v1_8_safety_baseline.py [VERIFIED: codebase]
from platform_runtime.protocols import BackendAdapter, ChannelAdapter
from platform_runtime.feature_flags import RuntimeFeatureFlags

methods = [m for m in dir(ChannelAdapter) if not m.startswith("_")]
assert len(methods) == 6
assert set(methods) == {
    "channel_id", "capabilities", "verify_and_ack",
    "normalize_inbound", "deliver", "health",
}

backend_methods = [m for m in dir(BackendAdapter) if not m.startswith("_")]
assert len(backend_methods) == 9

assert RuntimeFeatureFlags().qqbot_channel_enabled is False
```

### Config secret-refs-only assertion

```python
# Source: packages/channels/qqbot/tests/test_qqbot_channel_adapter.py [VERIFIED: codebase]
from dataclasses import asdict
from inkstatute_channels_qqbot import QQBotChannelConfig

config = QQBotChannelConfig.from_env({
    "INKSTATUTE_QQBOT_CHANNEL_ENABLED": "1",
    "INKSTATUTE_QQBOT_APP_ID_REF": "secret://qqbot/app-id",
    "INKSTATUTE_QQBOT_APP_SECRET_REF": "secret://qqbot/app-secret",
    "INKSTATUTE_QQBOT_TOKEN_SECRET_REF": "secret://qqbot/token",
})
rendered = str(asdict(config))
assert "access_token" not in rendered
assert "BEGIN PRIVATE KEY" not in rendered
```

### Host no-wecom AST scan (adapt package test)

```python
# Source pattern: packages/channels/qqbot/tests/test_no_wecom_import.py [VERIFIED: codebase]
import ast
from pathlib import Path

HOST_SRC = Path(__file__).resolve().parents[1] / "src" / "qqbot_service"

def imported_modules(source: str) -> list[str]:
    tree = ast.parse(source)
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules

offenders = []
for path in HOST_SRC.rglob("*.py"):
    source = path.read_text(encoding="utf-8")
    if "wecom_service" in source:
        offenders.append(path.name)
    for module in imported_modules(source):
        if module.startswith("wecom_service"):
            offenders.append(f"{path.name}:{module}")
assert offenders == []
```

### Process-edge token resolve analog

```python
# Source: services/admin-console-api/src/admin_console_api/auth.py [VERIFIED: codebase]
def resolve_admin_token(env: Mapping[str, str] | None = None) -> str | None:
    source = env if env is not None else os.environ
    token = source.get("ADMIN_API_TOKEN", "")
    return token if token else None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| QQBot fixture-only package proof (v1.6 Phase 43) | Production-grade package loop, still no host (v1.8) | 2026-07 | Package green ≠ deployable webhook |
| v1.8 audit `gaps_found`: no host composition | v1.9 Phases 68–72 close host gap | 2026-07-09 | Phase 68 = skeleton + safety first |
| WeCom as only channel host reference | Separate `qqbot-service` host; no wecom import | v1.9 research | Isolation preserved |

**Deprecated/outdated:**
- Extending `wecom-service` for QQ routes — rejected by architecture research.
- Adding `qq-botpy` SDK — rejected in v1.8 (stale, breaks empty deps).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Exact `REF_TO_VALUE_ENV` map for host `secrets.py` (secret:// → INKSTATUTE_QQBOT_* value vars) | Pattern 3 | Ops env naming mismatch with smoke/runbook; fix by aligning keys in Phase 68 tests + README |
| A2 | Phase 68 should **not** implement `webhook.py` / `wiring.py` even though ARCHITECTURE.md lists them | Architecture Patterns | If planner includes them, scope creeps into 69/70; keep success-criteria-scoped |
| A3 | Host package top-level name `qqbot_service` (underscore) matching `wecom_service` / `admin_web_ui` style | Recommended Structure | Import path bikeshed only; pick one and stick to gate PYTHONPATH |

**If this table is empty:** N/A — three assumed items above need planner confirmation only if they conflict with later discuss input (discuss was skipped).

## Open Questions

1. **How much of the ARCHITECTURE.md tree lands in Phase 68?**
   - What we know: Success criteria require skeleton, gate, safety, secret-refs, Phase 08 — not webhook composition.
   - What's unclear: Whether empty stub modules for wiring/webhook help or confuse.
   - Recommendation: **Omit** wiring/webhook/http_server until Phases 69–70; only add `config.py` + `secrets.py` + tests + gate.

2. **Should host config duplicate `QQBotChannelConfig` or wrap it?**
   - What we know: Package config already has refs + `from_env`; README says host maps flags→config.
   - What's unclear: Whether Phase 68 needs a separate `QQBotHostConfig` or only re-exports/tests package config + a thin secrets helper.
   - Recommendation: Prefer a thin `QQBotHostConfig` (or `HostSettings`) that holds `enabled: bool = False` + the same `*_ref` fields **or** embeds/constructs `QQBotChannelConfig` without storing raw secrets; avoid divergent ref field names.

3. **Gate PYTHONPATH breadth for Phase 68**
   - What we know: Host tests need `platform_runtime` for Protocol/flag asserts; may not need `feedback_service` yet.
   - What's unclear: Whether early import of `inkstatute_channels_qqbot` is required in Phase 68 tests.
   - Recommendation: Include `qqbot_src` + `platform_runtime_src` + `platform_src` + `channel_core_src` in the new gate; add feedback only when a test imports it.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | Host + unittest | ✓ | 3.14.6 | — |
| pip / setuptools | Editable install optional | ✓ | present | PYTHONPATH without install |
| `scripts/run_v2_gates.py` | Gate registration | ✓ | in-repo | — |
| External QQ / WeCom network | Phase 68 | ✗ not required | — | N/A — no live IO in this phase |
| New PyPI packages | Phase 68 | N/A | — | Do not install |

**Missing dependencies with no fallback:** none  

**Missing dependencies with fallback:** none  

Step 2.6: external tools beyond Python/stdlib are not required for Phase 68 execution.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Python `unittest` (stdlib) |
| Config file | none — discover via `python3 -m unittest discover` |
| Quick run command | `PYTHONPATH=services/qqbot-service/src:packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src python3 -m unittest discover -s services/qqbot-service/tests -v` |
| Full suite command | `python3 scripts/run_v2_gates.py` (includes new `qqbot-service` + `gate-coverage-meta-test` + existing `qqbot-channel`) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SAFE-01 | ChannelAdapter has 6 methods; BackendAdapter has 9 | unit | `… test_safety_baseline.py` | ❌ Wave 0 |
| SAFE-01 | No `wecom_service` in host src | unit | `… test_no_wecom_import.py` | ❌ Wave 0 |
| SAFE-01 | `qqbot_channel_enabled` defaults False | unit | `… test_safety_baseline.py` | ❌ Wave 0 (package tests ✅) |
| SAFE-01 | Host `dependencies = []` | unit | `… test_safety_baseline.py` | ❌ Wave 0 |
| SAFE-01 | Phase 08 directory present | unit | `… test_safety_baseline.py` | ❌ Wave 0 |
| SAFE-02 | Host config stores refs only | unit | `… test_secret_refs.py` | ❌ Wave 0 |
| SAFE-02 | Resolver returns values without mutating config | unit | `… test_secret_refs.py` | ❌ Wave 0 |
| Gate | `services/qqbot-service/src` covered | meta | `gate-coverage-meta-test` | ✅ exists; needs gate entry |
| ADAPTER-04 | Package freeze still green | unit | existing `qqbot-channel` gate | ✅ |

### Sampling Rate

- **Per task commit:** host unittest discover (quick command above)
- **Per wave merge:** `python3 scripts/run_v2_gates.py` at least through `qqbot-service` + `qqbot-channel` + `gate-coverage-meta-test`
- **Phase gate:** Full V2 gates green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `services/qqbot-service/` package tree (does not exist today)
- [ ] `services/qqbot-service/tests/test_safety_baseline.py` — SAFE-01 + Phase 08
- [ ] `services/qqbot-service/tests/test_no_wecom_import.py` — host AST isolation
- [ ] `services/qqbot-service/tests/test_secret_refs.py` — SAFE-02
- [ ] `scripts/run_v2_gates.py` — add `qqbot-service` Gate + compileall path
- [ ] Framework install: none — stdlib unittest only

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (Phase 68) | Live webhook auth deferred to Phase 70; package Ed25519 already exists |
| V3 Session Management | no | — |
| V4 Access Control | no | Feature flags default OFF |
| V5 Input Validation | yes | Config/env parsing; fail-closed missing refs |
| V6 Cryptography | no new crypto | Do not hand-roll; package owns Ed25519 |
| V7 Error Handling / Logging | yes | Never log resolved secret values; reference-first evidence |
| V8 Data Protection | yes | Secrets as refs; values only at process edge; no commit of `.env` values |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secret committed in config/fixtures | Information Disclosure | `*_ref` only; tests scan `asdict` / repo for value patterns |
| WeCom coupling leak | Elevation / Tampering of boundaries | Host + package no-wecom AST tests |
| Accidental live IO | Tampering / Abuse | Flags + config default OFF; no transport injection in Phase 68 |
| Protocol unfreeze | Tampering of shared contract | Runtime method-count freeze tests; do not edit `protocols.py` |
| Gate blind spot | Repudiation / CI bypass | `test_gate_coverage` requires PYTHONPATH entry |

## Project Constraints (from .cursor/rules/)

No `.cursor/rules/` directory is present in this workspace. Apply `AGENTS.md` as project law:

- Keep changes scoped to the active GSD phase (skeleton + SAFE-01/02 only).
- Never commit secrets, tokens, runtime DBs, logs, customer documents, or raw legal payloads.
- Prefer refs (`raw_payload_ref`, secret refs); do not store sensitive full text by default.
- Do not introduce new services/DBs/queues/runtime deps unless PRD/plan requires — **this phase explicitly requires** `services/qqbot-service/`.
- Do not rebuild Hermes core; do not leak Hermes gateway/meta notices (relevant when deliver path lands later).
- Add tests with behavior changes (schemas, isolation, dedupe, freeze).

## Sources

### Primary (HIGH confidence)

- `services/wecom-service/pyproject.toml` — empty-deps service skeleton
- `services/admin-web-ui/pyproject.toml` / `server.py` — stdlib HTTP host pattern (for later phases)
- `packages/channels/qqbot/` — config refs, adapter `_live_io_ready`, safety tests
- `packages/platform-runtime/src/platform_runtime/feature_flags.py` — `qqbot_channel_enabled: bool = False`
- `packages/platform-runtime/src/platform_runtime/protocols.py` — ChannelAdapter 6 / BackendAdapter 9
- `scripts/run_v2_gates.py` — gate + compileall registration
- `packages/contract-test-suite/tests/test_gate_coverage.py` — services/*/src coverage rule
- `.planning/REQUIREMENTS.md` — SAFE-01, SAFE-02
- `.planning/ROADMAP.md` — Phase 68 success criteria
- `.planning/phases/08-lawyer-trial-acceptance/` — present (`08-TRIAL-EVIDENCE-TEMPLATE.json`)
- `.planning/research/{ARCHITECTURE,STACK,PITFALLS,SUMMARY}.md` — v1.9 host composition research
- `services/admin-console-api/src/admin_console_api/auth.py` — process-edge secret resolve analog
- `AGENTS.md` — safety / privacy / coding rules

### Secondary (MEDIUM confidence)

- `.planning/milestones/v1.8-*` — ADAPTER-04 completion evidence and freeze methodology
- `runbook/SMOKE_TEST_RUNBOOK.md` — value env var names for live secrets

### Tertiary (LOW confidence)

- Exact host `REF_TO_VALUE_ENV` table — align during implementation with smoke/runbook [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — empty-deps + unittest + existing packages verified in-repo
- Architecture: HIGH — v1.9 research + ROADMAP success criteria align; Phase 68 scope narrower than full ARCHITECTURE tree
- Pitfalls: HIGH — drawn from verified gate-coverage behavior and v1.8/v1.9 pitfall docs

**Research date:** 2026-07-10  
**Valid until:** 2026-08-09 (30 days — stable in-repo patterns)
