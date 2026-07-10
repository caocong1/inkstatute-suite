# Project Research Summary

**Project:** InkStatute v1.10 Operator Config Console
**Domain:** Operator config plane (writable channel / provider / model catalog / vision routing) on an existing channel+adapter platform
**Researched:** 2026-07-10
**Confidence:** HIGH

## Executive Summary

v1.10 is not a greenfield admin product — it is an **InkStatute-owned operator config plane** layered onto shipped read-only admin surfaces, QQ/WeCom hosts, `provider_model`, and default-OFF feature flags. Experts in this niche (Hermes provider UX, OpenWebUI/LiteLLM connections, vision-fallback gateways) ship curated vendor + custom OpenAI-compatible endpoints, selectable model catalogs with capability flags, secret-ref credentials, and explicit vision→main mix for image turns. InkStatute should mirror that UX **without** writing Hermes `~/.hermes` or rebuilding Hermes gateway/router/skill systems.

**Recommended approach:** Add a new `packages/operator-config/` authority (schemas, atomic JSON store, loader, built-in catalog) and a thin vision-router at run-prep; **extend** `admin-console-api` + `admin-web-ui` for flag-gated `/config/*` mutations; materialize docs into existing channel/`ProviderModelBackendConfig` shapes with process-edge `resolve_secret_ref`. Keep `dependencies = []`, stdlib SSR forms, dual-knob channel enablement, and Protocols frozen.

**Key risks:** (1) collapsing the Hermes ownership boundary by editing agent profiles from the console; (2) planting raw secrets in config/API responses; (3) collapsing QQ dual-knob into one toggle; (4) silent image drop or vision meta leaking past the output boundary; (5) auto-claiming live WeCom/QQ acceptance from config smoke. Mitigate with refs-only schemas + ban-list tests, separate write surface + `operator_config_enabled=False`, dual-knob UI/matrix tests, fail-closed vision routing with AttachmentRef privacy, and `not_live_acceptance` honesty on carried human gates.

## Key Findings

### Recommended Stack

Extend existing empty-deps Python hosts rather than introducing FastAPI/React/DB. Writable config lives in `admin-console-api` / `admin-web-ui`; persistence is an atomic JSON file (`INKSTATUTE_OPERATOR_CONFIG_PATH`); secrets remain refs resolved at process edge. Optional `openai>=2.45.0,<3` stays a host-only lazy install for probes — never a hard package dependency. Full detail: [STACK.md](STACK.md).

**Core technologies:**
- **Extend `admin-console-api`:** Writable `/config/*` GET/PUT with allowlist + RBAC — reuses auth; avoids a new mega-service
- **Extend `admin-web-ui`:** Stdlib SSR forms + CSRF — no React/Vite for operator CRUD
- **Python 3.11+ stdlib:** Dataclasses, atomic JSON store, `html.escape`, CSP — preserves `dependencies = []`
- **Existing channel + `ProviderModelBackendConfig`:** Same `*_ref` / `api_key_ref` shapes; additive vision fields
- **`RuntimeFeatureFlags` + `rbac`:** `operator_config_enabled=False`; `/config` for ADMIN/OPERATOR only
- **Built-in catalog JSON + generalized `resolve_secret_ref`:** InkStatute SoT for models; hosts resolve values

### Expected Features

Operators expect a single InkStatute console for channels + providers + vision — not another README scavenger hunt or Hermes CLI. MVP must prove refs-only persistence, dual-knob safety, catalog-backed main model selection, and runtime vision auto-mix. Defer live `/models` refresh, audit trail, hot-reload, and LiteLLM-style budgets. Full detail: [FEATURES.md](FEATURES.md).

**Must have (table stakes):**
- Channel config UI/API (QQ + WeCom) with dual-knob effective state
- Secret-ref-only credential fields (never raw tokens in store/API)
- Provider registry: built-in vendors + custom OpenAI-compatible
- Built-in model catalog with `supports_vision` + main model selection
- Vision routing policy + runtime auto mix for image turns
- RBAC-gated writes, connection probes, operator docs

**Should have (competitive):**
- Effective-config / dual-knob audit view
- Vision capability as first-class catalog metadata + user-safe vision notices
- Backend-mode aware panels (Hermes mode ≠ provider_model editor)
- Config change audit trail; optional live catalog refresh for custom endpoints

**Defer (v2+ / later):**
- Hot-reload without restart; LiteLLM budgets/virtual keys; per-lawyer model switching
- Classical OCR-only vision path; editing Hermes profiles; auto-enable every `/models` entry

### Architecture Approach

Split an **operator plane** (admin UI → admin API → operator-config store) from the **runtime plane** (hosts load docs → dual-knob + secret resolve → VisionRouter at run-prep → BackendAdapter). Do not put catalog CRUD inside `model-gateway`; do not add a 7th ChannelAdapter method for vision; do not invent a second auth stack. Full detail: [ARCHITECTURE.md](ARCHITECTURE.md).

**Major components:**
1. **`packages/operator-config/`** — schemas, store, loader, catalog, refs-only validation
2. **Vision router** — AttachmentRef + capability flags → `main_direct` | `vision_then_main` | `reject_unsupported`
3. **Admin mutate surface** — `/config/*` on existing admin-console-api + SSR pages; flags + RBAC
4. **Host wiring** — QQ/WeCom load operator docs with `from_env` fallback; Protocols frozen
5. **provider_model / gateway** — consume catalog selection; gateway remains composite runtime, not the console

### Critical Pitfalls

Top risks when adding writable config + vision on this platform. Full detail: [PITFALLS.md](PITFALLS.md).

1. **Configuring Hermes from the console** — mutate InkStatute channels/provider_model only; gate tests ban Hermes filesystem/profile writers
2. **Raw secrets in config/API** — refs-only schema; GET returns configured booleans; ban-list tests for `sk-…` / tokens
3. **Collapsing QQ dual-knob** — UI shows platform flag AND host enabled; preserve Phase-69 matrix
4. **Silent image drop / wrong vision capability** — explicit `supports_vision`; fail closed when vision missing; never default unknown→multimodal
5. **Vision/provider meta past output boundary + live-acceptance auto-claim** — same output policy on vision errors; smoke stamps `not_live_acceptance`; carried human gates untouched

## Implications for Roadmap

Based on research, suggested **6-phase** structure starting at **Phase 73** (after v1.9 Phase 72). Aligns with architecture dependency order; folds pitfalls’ SAFETY / PERSIST / DOCS themes into foundation and polish rather than seven thin phases.

### Phase 73: Operator Config Foundation
**Rationale:** Schemas, store, refs-only validation, and default-OFF flags unblock every later surface; safety gates must exist before any write handler.
**Delivers:** `packages/operator-config/` (Channel/Provider/Model/Vision docs), atomic JSON store, secret-ref validators, `operator_config_enabled` (+ optional `vision_routing_enabled`) default False, gate coverage entry.
**Addresses:** Secret-ref persistence contract; Hermes-not-SoT boundary in schema allowlist.
**Avoids:** Raw secrets in store; Hermes `~/.hermes` fields; new DB/queue; Protocol unfreeze.

### Phase 74: Admin Config API + RBAC
**Rationale:** Mutate path needs authz and allowlist before UI or host apply; keep existing read views read-only.
**Delivers:** `/config/channels|providers|catalog|vision` GET/PUT on `admin-console-api`; RBAC matrix for ADMIN/OPERATOR; field allowlist; `require_enabled` on writes; planted-secret → 400 tests.
**Uses:** operator-config package; existing static token + TenantGuard patterns.
**Avoids:** Weakening `/sessions|/tasks|/feedback` read-only contract; UI-only “security.”

### Phase 75: Channel Config Apply (QQ + WeCom)
**Rationale:** Prove ops→runtime end-to-end without models; dual-knob is the highest channel-specific footgun.
**Delivers:** Loader → `QQBotChannelConfig` / `WeComChannelConfig`; host wiring with env fallback; admin-web-ui channel page with dual-knob effective state; CSRF on forms.
**Addresses:** Channel config table stakes; dual-knob visibility.
**Avoids:** Single-toggle bypass; writing Hermes WeCom/QQ gateway creds.

### Phase 76: Provider Registry + Built-in Model Catalog
**Rationale:** Catalog + custom OpenAI-compatible endpoints make provider config usable; vision needs `supports_vision` metadata first.
**Delivers:** Static vendor/model catalog JSON; custom provider docs; wire `ProviderModelBackendConfig`; optional connection probe; provider/model UI pages.
**Uses:** provider_model runners; optional lazy openai probe; model-gateway as optional consumer only.
**Avoids:** Hermes gateway rebuild; auto-enable all `/models`; raw `api_key` fields.

### Phase 77: Vision Routing Runtime
**Rationale:** Core milestone differentiator (GLM text-main + image turns); depends on catalog capabilities and existing AttachmentRef normalize paths.
**Delivers:** VisionRouter plans; `auto|always|never` (or `auto|always_preprocess|main_only`); vision→main mix; fail-closed user notices; privacy fixtures (no image bytes in contract logs); output-boundary on vision/provider errors.
**Addresses:** Vision routing table stakes + capability metadata.
**Avoids:** Silent image drop; vision on every text turn; provider stack traces to lawyers; ChannelAdapter 7th method.

### Phase 78: Console Polish, Docs & Gate Honesty
**Rationale:** Remaining UI polish, README/`.env.example`/runbook parity, and explicit non-acceptance of carried live gates.
**Delivers:** Remaining admin-web-ui polish; operator docs (console ↔ env/ref keys; dual-knob; vision policy; “do not edit Hermes”); smoke/dry-run evidence with `not_live_acceptance`; no auto-close of Phase 5 / Phase 8 / QQ live gates.
**Addresses:** Operator docs; connection-probe UX polish if deferred from 76.
**Avoids:** Claiming live UAT from config CRUD screenshots.

### Phase Ordering Rationale

- Foundation → API → (channel ∥ provider) → vision → docs matches schema/auth/runtime dependencies and FEATURES.md dependency graph.
- After Phase 74, **Phases 75 and 76 can run in parallel waves**; Phase 77 waits on catalog `supports_vision`.
- Safety pitfalls (Hermes boundary, refs-only, flags OFF, read-only admin preserved) are front-loaded in 73–74 so later phases cannot “demo green” by skipping them.
- Persistence audit concerns are enforced from Phase 73 (schema) through 77–78 (vision privacy + docs), not deferred to a late-only audit phase.
- No new top-level HTTP service; no Hermes profile editing; Protocols stay frozen.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 77:** Exact vision→main injection format (structured block vs caption); timeout budgets; provider_model vs dedicated vision call shape — MEDIUM gap in FEATURES/ARCHITECTURE
- **Phase 75–76:** Hot-reload vs restart-to-apply semantics for hosts holding live adapters — pick one in plan-phase
- **Phase 76:** Custom endpoint SSRF allowlist policy details for operator-supplied base URLs

Phases with standard patterns (skip research-phase):
- **Phase 73:** Dataclass schemas + atomic JSON + feature flags — well-established in-repo patterns
- **Phase 74:** admin-console-api route/RBAC/allowlist extension — clear existing patterns
- **Phase 78:** README/runbook alignment — documentation, not novel architecture

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | In-repo empty-deps hosts + PyPI openai 2.45.0 verified; alternatives explicitly rejected |
| Features | HIGH | Hermes/OpenWebUI/LiteLLM + vision-fallback sources; InkStatute shipped surfaces mapped |
| Architecture | HIGH | ADR-0001 + shipped adapters/admin/channels; package names MEDIUM |
| Pitfalls | HIGH | Repo-specific (Hermes, dual-knob, read-only admin, live honesty); ecosystem vision/privacy MEDIUM |

**Overall confidence:** HIGH

### Gaps to Address

- **Hot-reload vs restart:** Architecture allows either; MVP should document restart-to-apply unless a phase plan proves safe in-process reload — resolve in Phase 75/78 planning.
- **Vision injection format:** Structured extract vs caption into main prompt — decide in Phase 77 plan-phase with fixture matrix.
- **Capability on AdapterCapabilitySet vs catalog-only:** Prefer catalog-only `supports_vision` to avoid contract freeze — confirm in Phase 76.
- **Multi-tenant scoped config:** Defer unless `multi_tenant_enabled` is promoted; single-tenant MVP first.
- **Exact package split:** `vision-router` standalone vs submodule of `operator-config` — roadmapper may pick either; keep vision decision testable without HTTP.

## Sources

### Primary (HIGH confidence)
- In-repo: `AGENTS.md`, `.planning/PROJECT.md` (v1.10 decisions), `docs/architecture/adr/ADR-0001-platform-layering.md`
- In-repo: `services/admin-console-api`, `services/admin-web-ui`, `services/qqbot-service` (SAFE-02, dual-knob), channel configs, `provider_model` config, `platform-runtime` feature flags, `.env.example`
- Hermes Agent provider docs — built-in vs custom, catalogs, aux/vision paths
- OpenWebUI OpenAI-compatible connection docs; openai PyPI **2.45.0** (2026-07-09)
- Vision fallback: 9router#1419, OpenCode vision-fallback issues, Fallback Vision gateway patterns

### Secondary (MEDIUM confidence)
- LiteLLM ↔ OpenWebUI model_list / admin patterns
- Multimodal cost routing guidance (text on text models; vision only for image turns)
- ConfigCat feature-flag anti-patterns; legal-AI image residency / ZDR discussions
- Prior `.planning/research/STACK.md` (v1.9 host composition empty-deps pattern)

### Tertiary (LOW confidence)
- Exact InkStatute vision prompt injection productization maturity — validate in Phase 77
- Multi-provider dialect/schema breakage on fallback — validate per chosen vendors in Phase 76–77

---
*Research completed: 2026-07-10*
*Ready for roadmap: yes*
