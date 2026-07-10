# Architecture Research

**Domain:** Operator Config Console + vision routing on existing InkStatute platform
**Milestone:** v1.10 Operator Config Console
**Researched:** 2026-07-10
**Confidence:** HIGH (sourced from ADR-0001, shipped ChannelAdapter/BackendAdapter/RunRuntime, admin-console-api read-only surface, channel `*_REF` configs, provider_model + model-gateway, QQ/WeCom attachment ref-only normalization, PROJECT.md v1.10 decisions)

## Verdict (roadmap-facing)

**Extend InkStatute-owned admin surfaces with a config authority layer.** Do **not** make Hermes `~/.hermes` (or any Hermes profile) the config source of truth. Channel enablement, provider/model catalog, and vision routing are platform concerns that feed hosts and backends through existing injection seams.

| Decision | Choice | Why |
|----------|--------|-----|
| Config authority | **NEW** InkStatute operator-config package + store | README already: Hermes owns agent logic; InkStatute owns channel/provider ops config |
| Admin mutations | **MODIFY** `admin-console-api` + `admin-web-ui` | Reuse auth/RBAC/flag gates; avoid a second operator HTTP surface |
| Channel config | **MODIFY** host wiring + channel `*Config` loaders | Keep frozen secret-ref dataclasses; add store→config materialization beside `from_env` |
| Provider/model catalog | **NEW** catalog + **MODIFY** provider_model / gateway wiring | Catalog is data; runners already take `api_key_ref` / `api_base_url` / `model_name` |
| Vision routing | **NEW** vision-router at run-prep edge | Image turns already produce `AttachmentRef`; routing decides vision→main mix before backend submit |
| Protocol freeze | **Unchanged** | ChannelAdapter stays 6 methods; BackendAdapter stays 9; no Hermes core rebuild |
| Secrets | **Refs only** | Resolve at process edge (`resolve_secret_ref`); never persist raw tokens in store/API/logs |
| Feature flags | **Default OFF** | New write/vision lanes join `RuntimeFeatureFlags`; dual-knob channel pattern preserved |

## Standard Architecture

### System Overview

v1.10 adds an **operator config plane** beside the existing **runtime plane**. Config writes never cross into Hermes filesystem; runtime hosts pull InkStatute config and inject adapters as today.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         Operator Plane (v1.10)                               │
│  ┌────────────────────┐    ┌─────────────────────┐    ┌──────────────────┐  │
│  │ admin-web-ui       │───▶│ admin-console-api   │───▶│ operator-config  │  │
│  │ [MODIFY] config UI │    │ [MODIFY] R/W routes │    │ [NEW] schemas +  │  │
│  │ channels/providers │    │ RBAC + allowlist    │    │ store (refs only)│  │
│  │ models / vision    │    │ flag-gated writes   │    │                  │  │
│  └────────────────────┘    └──────────┬──────────┘    └────────┬─────────┘  │
│                                       │                        │            │
│                                       │ read/apply             │            │
├───────────────────────────────────────┼────────────────────────┼────────────┤
│                         Runtime Plane (existing + hooks)                     │
│  ┌────────────────────┐    ┌──────────▼──────────┐    ┌────────▼─────────┐  │
│  │ wecom-service      │    │ ConfigLoader /      │    │ Built-in model   │  │
│  │ qqbot-service      │◀───│ Host wiring         │◀───│ catalog (static) │  │
│  │ [MODIFY] load cfg  │    │ flag→config dual    │    │ + custom providers│ │
│  └─────────┬──────────┘    │ knob preserved      │    └──────────────────┘  │
│            │               └──────────┬──────────┘                          │
│            ▼                          ▼                                     │
│  ┌──────────────────┐      ┌─────────────────────┐                          │
│  │ ChannelAdapter   │      │ VisionRouter [NEW]  │                          │
│  │ (6 methods FROZEN)│     │ image-turn →        │                          │
│  │ normalize →      │─────▶│ vision model? →     │──▶ RunRequest prep       │
│  │ AttachmentRef    │      │ main model mix      │                          │
│  └──────────────────┘      └──────────┬──────────┘                          │
│                                       ▼                                     │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ DefaultRunRuntime ──▶ BackendAdapter (Hermes | provider_model | …)   │   │
│  │                    ──▶ ModelProviderGateway (optional composite)     │   │
│  │ Hermes = agent logic ONLY — not config authority                     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│  Secret resolution: process edge only (env / secret:// → values)            │
│  Contract logs: refs / hashes — never raw keys or image bytes               │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Status | Location |
|-----------|----------------|--------|----------|
| Operator config schemas | Channel / provider / model / vision documents; secret-ref fields; validation | **NEW** | `packages/operator-config/` (or equivalent) |
| Config store | Persist operator documents outside git; version/etag; no raw secrets | **NEW** | under operator-config (file/JSONL first; DB only if plan requires) |
| Built-in model catalog | Vendor→selectable models + capability flags (`supports_vision`, etc.) | **NEW** | catalog data in operator-config or `packages/model-catalog/` |
| Config apply / loader | Materialize store → `WeComChannelConfig` / `QQBotChannelConfig` / `ProviderModelBackendConfig` | **NEW** | operator-config + host wiring |
| Vision router | Given inbound attachments + main/vision model caps, decide vision→main mix | **NEW** | `packages/vision-router/` or operator-config submodule used by hosts/runtime |
| Admin Console API write routes | Authenticated mutate/get for config resources; field allowlist | **MODIFY** | `services/admin-console-api/` |
| Admin Web UI config pages | Operator forms for channels, providers, models, vision | **MODIFY** | `services/admin-web-ui/` |
| RBAC matrix | Annotate new `/config/*` (or similar) prefixes; admin/operator write | **MODIFY** | `packages/rbac/` |
| Feature flags | `operator_config_enabled`, `vision_routing_enabled` (names TBD) default `False` | **MODIFY** | `packages/platform-runtime/.../feature_flags.py` |
| QQ/WeCom host wiring | Load operator config (or env fallback); keep dual-knob + secret resolve | **MODIFY** | `services/qqbot-service/`, `services/wecom-service/` |
| Channel configs | Remain frozen secret-ref dataclasses; optional `from_operator_doc` | **MODIFY** | `packages/channels/{qqbot,wecom}/.../config.py` |
| provider_model | Construct runners from catalog selection + custom endpoint docs | **MODIFY** | `packages/backends/provider_model/` |
| ModelProviderGateway | Optional: select/fallback among catalog-backed sub-adapters | **REUSE/light MODIFY** | `packages/model-gateway/` |
| Channel normalize | Already emits image `AttachmentRef` (ref-only) | **REUSE** | wecom normalization, qqbot normalize |
| Hermes backend | Agent execution only; do not read/write `~/.hermes` for ops config | **REUSE** | `packages/backends/hermes/` |
| ChannelAdapter / BackendAdapter Protocols | Unchanged method counts | **FROZEN** | `packages/platform-runtime/.../protocols.py` |
| platform-contract event schemas | Prefer no freeze break; vision metadata in run metadata / industry_context if needed | **FROZEN preference** | `packages/platform-contract/` |

## Recommended Project Structure

```
packages/
├── operator-config/                 # NEW — schemas, store, loader, validation
│   ├── src/inkstatute_operator_config/
│   │   ├── schemas.py               # ChannelDoc, ProviderDoc, ModelRef, VisionRoutingDoc
│   │   ├── catalog.py               # built-in vendor/model catalog
│   │   ├── store.py                 # persistence (refs only)
│   │   ├── loader.py                # doc → *ChannelConfig / ProviderModelBackendConfig
│   │   ├── secrets.py               # re-export / wrap resolve_secret_ref policy
│   │   └── validate.py
│   └── tests/
├── vision-router/                   # NEW — or submodule of operator-config if kept small
│   ├── src/inkstatute_vision_router/
│   │   ├── router.py                # decide(main_caps, vision_model, attachments) → plan
│   │   └── plans.py                 # VisionPlan: passthrough | describe_then_main | reject
│   └── tests/
├── backends/provider_model/         # MODIFY — wire catalog-selected configs
├── model-gateway/                   # REUSE — composite backend; not the catalog UI
├── channels/qqbot|wecom/            # MODIFY — from_operator_doc beside from_env
├── platform-runtime/                # MODIFY — new default-OFF flags only
├── rbac/                            # MODIFY — new route permissions
services/
├── admin-console-api/               # MODIFY — GET/PUT config routes + allowlist
├── admin-web-ui/                    # MODIFY — config pages (still CSP / html.escape)
├── qqbot-service/                   # MODIFY — ConfigLoader in wiring
└── wecom-service/                   # MODIFY — ConfigLoader in wiring
```

### Structure Rationale

- **`operator-config` package:** Keeps schemas/store out of HTTP services so hosts, smoke, and API share one authority; mirrors how channel logic lives in packages and hosts only compose.
- **`vision-router` separate (or thin submodule):** Vision decision is run-prep logic, not admin CRUD; testable without HTTP.
- **Modify admin services, don’t fork a new console:** Auth, RBAC scan (`ROUTE_PREFIXES` ↔ `PERMISSIONS_MATRIX`), health allowlist, and flags already exist.
- **Do not put catalog inside Hermes or `~/.hermes`:** Aligns with README + AGENTS.md ownership boundary.
- **Do not invent a new queue/DB** unless a phase plan requires it — file/JSON store is enough for operator config MVP.

## Architectural Patterns

### Pattern 1: Config Authority Outside Hermes

**What:** InkStatute persists operator documents (channels, providers, models, vision). Hermes remains an injected `BackendAdapter` for agent turns.
**When to use:** Always for v1.10 ops configuration.
**Trade-offs:** Operators configure two planes (InkStatute ops vs Hermes agent internals) — intentional; avoids coupling product config to Hermes upgrades.

**Example:**
```python
# Host wiring — load InkStatute config, never Path.home() / ".hermes"
docs = config_store.load()
qq_cfg = QQBotChannelConfig.from_operator_doc(docs.channels["qqbot"])
# enabled = flags.qqbot_channel_enabled AND doc.enabled  (dual-knob)
adapter = QQBotChannelAdapter(qq_cfg, ...)
runtime = DefaultRunRuntime(backend=hermes_adapter, channels=(adapter,), feature_flags=flags)
```

### Pattern 2: Secret-Ref Documents + Process-Edge Resolution

**What:** Stored/API fields are `*_ref` / `env:VAR` / `secret://…` only. Hosts call `resolve_secret_ref(ref, env)` at the edge (same SAFE-02 pattern as qqbot-service).
**When to use:** Every credential field (WeCom token/AES, QQ app secrets, provider API keys).
**Trade-offs:** Operators must plant value env vars separately; UI never displays raw secrets (show configured=true / last-4 optional later — not MVP).

**Example:**
```python
@dataclass(frozen=True, slots=True)
class ProviderDoc:
    provider_id: str
    kind: str  # "builtin_openai" | "custom_openai_compatible" | ...
    api_base_url: str | None
    api_key_ref: str | None  # NEVER raw key
    enabled: bool = False
```

### Pattern 3: Dual-Knob Channel Enablement (Preserved)

**What:** Platform `RuntimeFeatureFlags.*_channel_enabled` AND channel/doc `enabled` must both be true; adapters still do not import feature flags.
**When to use:** QQBot and WeCom live IO.
**Trade-offs:** Two places to flip — prevents accidental live IO from UI alone or flag alone.

### Pattern 4: Vision Routing at Run-Prep (Not Inside ChannelAdapter)

**What:** Channels keep normalizing images to `AttachmentRef`. A vision router inspects message_type/attachments + model capability flags and produces a `VisionPlan` attached to run metadata / backend request prep.
**When to use:** Inbound image (or multimodal) turns when main model may lack vision.
**Trade-offs:** Extra hop for dedicated vision models (describe/caption → main); multimodal mains skip the hop.

**Example:**
```python
plan = vision_router.plan(
    attachments=turn.attachments,
    main_model=catalog.get(docs.vision.main_model_id),
    vision_model=catalog.get(docs.vision.vision_model_id),  # may be None
)
# plan.mode: "main_direct" | "vision_then_main" | "reject_unsupported"
# Bytes stay behind media refs; vision call resolves media at process edge only
```

### Pattern 5: Catalog as Data, Gateway as Composite Runtime

**What:** Built-in model catalog is static selectable data (vendor, model id, caps). `ModelProviderGateway` remains a composite `BackendAdapter` (rate limit / circuit / fallback) — not the operator catalog UI.
**When to use:** Provider/model selection in console; gateway only when `model_gateway_enabled`.
**Trade-offs:** Clear separation avoids stuffing CRUD into gateway config dataclasses.

## Data Flow

### Config Load / Apply Flow

```
Operator (admin-web-ui)
    ↓ PUT /config/channels|providers|models|vision  (RBAC + flag)
admin-console-api
    ↓ validate (refs-only, schema)
operator-config store  (persist document, no raw secrets)
    ↓
Host startup / hot-reload hook (phase-defined)
    ↓ loader.materialize(doc) → *ChannelConfig / ProviderModelBackendConfig
    ↓ resolve_secret_ref at process edge
ChannelAdapter / BackendAdapter / VisionRouter injected into DefaultRunRuntime
```

### Image-Turn Vision Routing Flow

```
Channel webhook (WeCom | QQ)
    ↓ verify_and_ack → normalize_inbound
Normalized turn + AttachmentRef[]  (qqbot-media:// or wecom media ref — no bytes in contract log)
    ↓ ingress / session → create_run prep
VisionRouter.plan(main_caps, vision_model, attachments)
    ├─ main supports_vision → attach image refs to main RunRequest (main_direct)
    ├─ main lacks vision + vision_model set → vision describe/OCR → text context → main (vision_then_main)
    └─ neither → fail-closed / user-safe notice (reject_unsupported) — no Hermes meta leak
    ↓
BackendAdapter.submit_run (Hermes | provider_model | gateway)
    ↓
output_boundary → ChannelAdapter.deliver
```

### Key Data Flows

1. **Channel config apply:** Store doc → dual-knob AND → `QQBotChannelConfig` / `WeComChannelConfig` → host wiring strips live transports when OFF.
2. **Provider/model select:** Catalog entry or custom OpenAI-compatible doc → `ProviderModelBackendConfig(model_name, api_base_url, api_key_ref)` → runner.
3. **Vision mix:** Attachment refs + capability flags → `VisionPlan` → optional vision provider call → main agent turn with text/context only or multimodal payload.
4. **Health/admin read:** Continue field allowlist — expose `secret_refs_configured` booleans, never ref target values or `api_key`.

## New vs Modified (explicit)

### NEW

| Piece | Why new |
|-------|---------|
| Operator config schemas + store + loader | No config authority package exists; admin API is read-only today |
| Built-in model catalog data | provider_model has single `model_name`; no selectable vendor catalog |
| Vision router | No component decides vision→main mix; channels only produce refs |
| Admin config write routes + UI pages | Current routes: sessions/tasks/feedback/health/gates only |
| Feature flags for config write / vision routing | All existing flags default OFF; new lanes need the same gate |

### MODIFIED

| Piece | Change |
|-------|--------|
| `admin-console-api` | Add config GET/PUT (or PATCH); extend `ROUTE_PREFIXES`; keep allowlist |
| `admin-web-ui` | Config navigation + forms; still SSR + CSP |
| `packages/rbac` | Matrix entries for config routes (admin/operator write; deny lawyer/viewer mutate) |
| `RuntimeFeatureFlags` | Add default-OFF flags |
| `qqbot-service` / `wecom-service` wiring | Prefer operator-config loader with env `from_env` fallback |
| Channel `config.py` | Optional `from_operator_doc`; keep `from_env` |
| `provider_model` construction sites | Build config from catalog/custom docs |
| `model-gateway` (light) | Optional sub-adapter map from catalog-enabled providers |
| READMEs / `.env.example` | Document console + refs (already partially noted) |

### UNCHANGED (do not touch unless a phase explicitly requires)

| Piece | Reason |
|-------|--------|
| ChannelAdapter 6 / BackendAdapter 9 Protocols | Freeze + gate coverage |
| Hermes core / `~/.hermes` as config store | Ownership boundary |
| platform-contract five event schemas (prefer) | Avoid freeze break; put vision plan in metadata |
| Contract-log raw payload policy | Keep `raw_payload_ref` / attachment refs |
| Rebuilding model-gateway as “the console” | Wrong layer |

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Single-operator / one firm | File or JSONL config store beside runtime; reload on write or process restart |
| Multi-operator same deploy | Add etag/optimistic concurrency on PUT; RBAC already splits roles |
| Multi-tenant | Reuse `multi_tenant_enabled` + TenantGuard; scope config docs by tenant_id when that flag is on — not required to unblock single-tenant MVP |

### Scaling Priorities

1. **First bottleneck:** Accidental secret persistence in store/API responses — prevent with schema validators + allowlist tests before scale.
2. **Second bottleneck:** Vision media fetch latency — keep refs until process edge; bound vision call timeouts; don’t block webhook ACK (ACK-first already in QQ host).

## Anti-Patterns

### Anti-Pattern 1: Hermes `~/.hermes` as Operator Config Authority

**What people do:** Point the console at Hermes config files or write model/channel settings into the lawfirm profile.
**Why it's wrong:** Violates InkStatute channel ownership; couples ops UI to Hermes layout; secrets/logs risk; README forbids it.
**Do this instead:** InkStatute operator-config store; Hermes adapter only executes agent turns.

### Anti-Pattern 2: Storing Raw API Keys in Config Documents

**What people do:** PUT `{"api_key": "sk-..."}` into the store for “simpler DX.”
**Why it's wrong:** Breaks AGENTS.md / SAFE-02; leaks via backups, contract logs, health dumps.
**Do this instead:** `api_key_ref` only; resolve at process edge.

### Anti-Pattern 3: Teaching ChannelAdapter a 7th Method for Vision

**What people do:** Add `route_vision` onto ChannelAdapter.
**Why it's wrong:** Unfreezes Protocol; every channel pays tax; vision is backend/model concern.
**Do this instead:** Normalize to attachments; vision-router at run-prep.

### Anti-Pattern 4: Bypassing Dual-Knob via UI “Enable Channel”

**What people do:** UI sets `enabled=True` and host ignores `RuntimeFeatureFlags`.
**Why it's wrong:** Accidental live IO; desync already documented as a pitfall for QQ.
**Do this instead:** AND of platform flag and config doc; document both in operator README.

### Anti-Pattern 5: New Mega Config Microservice

**What people do:** Spin `services/config-service` with its own auth stack.
**Why it's wrong:** Duplicates admin auth/RBAC/flags; AGENTS.md says no new service unless plan requires.
**Do this instead:** Package for schemas/store + mutate through admin-console-api.

### Anti-Pattern 6: Putting Image Bytes in Contract Logs or Run Metadata

**What people do:** Base64 images into AgentTurn for “easier vision.”
**Why it's wrong:** Privacy / legal payload rules; log bloat.
**Do this instead:** Keep `AttachmentRef`; resolve media only inside vision/main call path.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| WeCom callback / send API | Existing wecom-service + ChannelAdapter | Config supplies refs + enable; not protocol rewrite |
| QQ OpenAPI | Existing qqbot-service composition | Same; dual-knob + SAFE-02 refs |
| OpenAI-compatible providers | provider_model runners (`api_base_url` + `api_key_ref`) | Custom endpoints = first-class ProviderDoc |
| Built-in vendors (OpenAI/Anthropic/Ollama/…) | Catalog ids → known base URL defaults + runner kind | Keys still refs |
| Hermes agent backend | BackendAdapter only | Probe `/v1/models` may inform display; not write-back to Hermes |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| admin-web-ui ↔ admin-console-api | In-process proxy / HTTP GET+PUT | Writes flag-gated; RBAC annotated |
| admin-console-api ↔ operator-config | Direct package calls | No raw secrets in responses |
| operator-config ↔ host wiring | Loader at startup / reload | Env `from_env` remains fallback |
| ChannelAdapter ↔ VisionRouter | Normalized turn / attachments in | Router must not import wecom↔qqbot |
| VisionRouter ↔ provider_model / gateway | VisionPlan + resolved media at edge | Prefer provider_model for dedicated vision call |
| RunRuntime ↔ BackendAdapter | Existing submit/stream | Vision prep happens before submit |
| Health / gates views ↔ config | Allowlisted booleans only | Exclude secret ref names/values per existing health policy |

## Suggested Build Order (phases starting at 73)

Dependency-respecting order for roadmap authors:

1. **Phase 73 — Operator config foundation**  
   Schemas (channel/provider/model/vision docs), refs-only validation, store, default-OFF flags, gate coverage for new package.  
   *Unblocks everything; no UI yet.*

2. **Phase 74 — Admin config API (read/write) + RBAC**  
   Extend `admin-console-api` with config routes; matrix + allowlist tests; still no Hermes coupling.  
   *Depends on 73.*

3. **Phase 75 — Channel config apply path**  
   Loader → WeCom/QQ `*Config`; modify host wiring (env fallback); dual-knob preserved; UI channel page.  
   *Depends on 73–74; proves end-to-end ops→runtime without models.*

4. **Phase 76 — Provider + built-in model catalog**  
   Catalog data; custom OpenAI-compatible providers; wire `ProviderModelBackendConfig` / optional gateway sub-adapters; UI.  
   *Depends on 73–74; can parallelize UI with 75 after API exists.*

5. **Phase 77 — Vision routing**  
   VisionRouter + capability flags on catalog; image-turn plan; provider_model (or gateway) vision hop; fail-closed UX; tests with AttachmentRef fixtures (no bytes in logs).  
   *Depends on 76 (catalog caps) and benefits from 75 (real inbound image normalization already shipped).*

6. **Phase 78 — Admin Web UI polish + operator docs**  
   Remaining console pages, README/`.env.example` alignment, smoke/dry-run evidence that config load + vision plan appear in sanitized form.  
   *Depends on 74–77.*

**Parallelism note:** After Phase 74, channel apply (75) and provider catalog (76) can proceed in parallel waves; vision (77) waits on catalog capabilities.

**Explicit non-goals in this order:** live WeCom UAT / lawyer trial / QQ `--live` acceptance (carried human gates); Hermes profile editing; unfreezing Protocols.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Layering / ownership | HIGH | ADR-0001 + PROJECT.md + README Hermes boundary |
| Admin mutate-via-existing API | HIGH | Read-only today; RBAC/route scan pattern is clear |
| Secret-ref preservation | HIGH | QQ host SAFE-02 + channel configs already ref-only |
| Vision at run-prep | HIGH | AttachmentRef already on QQ/WeCom normalize paths |
| Catalog vs model-gateway split | HIGH | Gateway is composite BackendAdapter, not CRUD |
| Hot-reload vs restart | MEDIUM | Phase plan should pick one; architecture allows either |
| Exact package names | MEDIUM | `operator-config` / `vision-router` are recommendations |

## Gaps to Address in Phase Research

- Hot-reload semantics (in-process reload vs restart-required) for hosts already holding adapters.
- Whether vision describe uses a short provider_model call vs a future dedicated tool — recommend provider_model first.
- Whether `AdapterCapabilitySet` gains `supports_vision` (contract change) vs catalog-only capability flags (prefer catalog-only to avoid contract freeze).
- Multi-tenant scoped config: defer unless `multi_tenant_enabled` promotion is in-scope.

## Sources

- `.planning/PROJECT.md` — v1.10 goal, secret-ref + vision decisions (2026-07-10)
- `docs/architecture/adr/ADR-0001-platform-layering.md` — ChannelAdapter / BackendAdapter / RunRuntime
- `services/admin-console-api/README.md` — read-only API, allowlist, `admin_api_enabled`
- `services/admin-web-ui/README.md` — SSR dashboard, proxies GET only today
- `packages/platform-runtime/README.md` + `feature_flags.py` — embeddable runtime, default-OFF flags
- `packages/channels/{qqbot,wecom}/.../config.py` — frozen secret-ref channel configs + `from_env`
- `services/qqbot-service/README.md` — SAFE-02 resolve_secret_ref, dual-knob wiring
- `packages/backends/provider_model/.../config.py` — `api_key_ref` / `api_base_url` / `model_name`
- `packages/model-gateway/` — composite BackendAdapter (rate limit / circuit / fallback), not catalog UI
- `AGENTS.md` — InkStatute owns channel boundary; Hermes is agent backend; no secrets in git
- Root `README.md` — admin is read-only ops board; provider_model without editing Hermes

---
*Architecture research for: v1.10 Operator Config Console + vision routing*
*Researched: 2026-07-10*
