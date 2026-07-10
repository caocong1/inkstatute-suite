# Feature Research

**Domain:** Operator Config Console — multi-channel bot + multi-provider LLM + vision fallback routing
**Milestone:** v1.10 Operator Config Console
**Researched:** 2026-07-10
**Confidence:** HIGH (Hermes provider UX docs, OpenWebUI/LiteLLM admin patterns, vision-fallback industry issues, InkStatute shipped admin/channel/provider surfaces)

## Scope Note

**Already shipped — do not re-scope as new table stakes:**
- Read-only Admin Console API + Admin Web UI (sessions/tasks/feedback/health/gates), RBAC roles, feature flags default OFF
- WeCom + QQBot channel packages/hosts; QQ dual-knob (`flags.qqbot_channel_enabled` AND `host.enabled`) + secret refs at process edge
- `provider_model` backend config shape (`api_base_url`, `api_key_ref`, model name); model-gateway package (circuit breakers) as extension surface
- Hermes remains first production agent backend; InkStatute must **not** become a Hermes config editor

**This document covers NEW operator-facing configuration capabilities for v1.10.**

## Feature Landscape

### Table Stakes (Operators Expect These)

Missing these = console feels incomplete for “configure channels + models without editing Hermes.”

| Feature | Why Expected | Complexity | Notes / Dependencies |
|---------|--------------|------------|----------------------|
| Channel config page (QQ + WeCom) | Operators already deploy hosts via env; they expect a single UI to enable channels, set callback/credential **refs**, and see dual-knob safety state — not another README scavenger hunt. | MEDIUM | Extend `services/admin-web-ui` + write-capable routes on `admin-console-api` (today read-only). Map to `QQBotHostConfig` / WeCom host env shapes. Preserve dual-knob AND + default OFF. Do not reimplement channel crypto. |
| Secret-ref-only credential fields | Industry + InkStatute SAFE baseline: consoles store refs (`env:…`, `secret://…`), never raw tokens in persisted config or API responses. | LOW–MEDIUM | Reuse `qqbot_service.secrets` patterns; WeCom keys same rule. UI: password-masked “set ref” + “configured / missing” status; never echo resolved values. |
| Dual-knob / enable safety visible in UI | QQ already requires platform flag AND host enabled; operators who flip one knob and see “enabled” will ship accidental live IO. | LOW | Show both knobs + effective `enabled = A AND B`. Defaults OFF. Apply same mental model to WeCom feature flags. |
| Provider registry: built-in vendors + custom OpenAI-compatible | Hermes-class UX: curated vendors (base URL, key env, catalog) plus `custom` for any `/v1/chat/completions` endpoint. OpenWebUI/LiteLLM same split. | MEDIUM | InkStatute-owned config — **not** writing `~/.hermes`. Wire toward `ProviderModelBackendConfig` / model-gateway selection. Built-ins = static profiles; custom = `base_url` + `api_key_ref` + optional model list. |
| Built-in selectable model catalog | Operators expect pick-from-list, not free-typing opaque IDs only. Hermes ships `_PROVIDER_MODELS` + optional live `/models`; OpenWebUI uses allowlist when auto-detect fails. | MEDIUM | Ship static catalog per built-in vendor (id, display name, `supports_vision`, context hints). Custom providers: manual model IDs + optional probe. Catalog is InkStatute data, not Hermes. |
| Main model selection | Without a declared main/default model, provider config is inert. | LOW | Persist `provider_id` + `model_id` as runtime selection for provider_model / gateway path. Hermes-mode deployments may show “agent backend owns model” with clear non-edit boundary. |
| Vision routing config + runtime decision | GLM-class text mains cannot consume images; operators expect a dedicated vision model and automatic mix — industry standard (9router/OpenCode/Fallback Vision pattern). | HIGH | See **Vision routing expected behavior** below. Needs catalog `supports_vision`, optional `vision_provider`/`vision_model`, and inbound image-turn policy in channel→agent path (provider_model / runtime), not only UI. |
| Config persistence + reload contract | Env-only edits do not satisfy “console”; operators need save + documented apply semantics (restart vs hot-reload). | MEDIUM | Prefer file/DB config with refs only. MVP may require process restart to apply; must document honesty. Do not plant secrets in contract logs. |
| AuthZ: only admin/operator may mutate config | Read dashboard already splits roles; write config is higher risk. | LOW | Extend `packages/rbac` matrix: config GET for admin/operator; config PUT for admin (or admin+operator with audit). Lawyer/viewer denied. |
| Connection / credential probe (non-destructive) | Operators expect “Test connection” before enabling live channels or switching models (OpenWebUI/LiteLLM norm). | MEDIUM | Probe: resolve ref at process edge → lightweight `/models` or chat ping → return ok/fail without storing response bodies in logs. Fail closed on missing refs. |
| Operator docs aligned with console | README already promises config surface; without runbook, operators fall back to Hermes. | LOW | Update root README + channel READMEs: console fields ↔ env/ref keys; dual-knob; vision policy; “do not edit Hermes for InkStatute providers.” |

### Differentiators (Competitive / Platform Advantage)

Valuable for InkStatute’s owned-channel + backend-neutral story; not required to claim a minimal config console.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Effective-config + dual-knob audit view | Shows resolved enablement, which refs are set (not values), last probe, and which process owns apply — reduces “I set it in UI but host still OFF” incidents. | MEDIUM | Differs from Hermes CLI menus and generic OpenWebUI connections. |
| Vision capability as first-class catalog metadata | Explicit `supports_vision` + routing mode prevents silent image drops (OpenCode pain) and accidental always-on vision cost. | MEDIUM | Differentiator vs consoles that only store model strings. |
| Transparent vision→main mix with user-safe notices | When vision preprocess runs, optional InkStatute service notice (“正在识别图片…”) without leaking provider/gateway meta — aligns with output boundary. | MEDIUM | Differentiator vs silent proxy gateways; must not expose Hermes/admin notices. |
| Backend-mode aware config panels | Hermes mode: channel + output policy + “model owned by agent backend.” Provider_model mode: full provider/catalog/vision. Prevents false expectation that console edits Hermes. | MEDIUM | Matches PROJECT decision: InkStatute config ≠ Hermes gateway. |
| Config change audit trail (who/when/what field) | Legal/ops environments need change history without secret values. | MEDIUM | Store field-level diffs + actor role; redact refs’ resolved values always. |
| Per-channel enable independent of provider | Prove ChannelAdapter portability: QQ can be OFF while WeCom ON with same provider selection. | LOW | Already architecturally true; console should make it obvious. |
| Optional live catalog refresh for custom endpoints | Better DX for Ollama/vLLM where model list changes; static catalog remains fallback. | MEDIUM | Hermes pattern: live `/models` first, static fallback. Cache briefly; never require live fetch for built-ins. |

### Anti-Features (Commonly Requested, Often Problematic)

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| Edit Hermes `~/.hermes` / gateway from this console | “One place to configure everything.” | Couples InkStatute to Hermes private layout; leaks gateway concerns into lawyer product; violates adapter boundary. | InkStatute-owned config for channels + provider_model/gateway; Hermes mode documents external agent config. |
| Persist raw API keys / WeCom tokens in UI or config store | “Easier than refs.” | Secret sprawl, backup leaks, contract-log risk; breaks SAFE-02. | Secret refs only; resolve at process edge. |
| Single enable toggle that bypasses dual-knob | “Too many switches.” | Accidental live QQ/WeCom IO; undoes v1.9 safety. | Keep AND of platform flag + host enabled; UI explains both. |
| Silent image drop when main lacks vision | “Don’t fail the turn.” | Lawyer sends contract photo; bot ignores image → wrong legal answer (OpenCode #24948 class). | Fail closed with clear user/operator message **or** run configured vision preprocess. |
| Always route every turn through vision model | “Simpler routing.” | 5–10× cost on text-only traffic; latency; unnecessary media path. | Image-bearing turns only; text stays on main. |
| Full LiteLLM spend/budget/virtual-key control plane in v1.10 | “Enterprise gateway.” | Scope explosion; rebuilds model gateway product; not needed for operator config MVP. | Defer budgets/virtual keys; reuse existing model-gateway later if promoted. |
| Auto-discover and auto-enable every `/models` entry | “Zero config.” | Untrusted custom endpoints; surprise cost; unsafe models in legal path. | Built-in curated catalog; custom = explicit allowlist. |
| Hot-reload secrets into long-lived processes without restart (as MVP hard req) | “No downtime.” | Partial apply races; dual-knob desync; hard to test. | Document restart-to-apply for MVP; hot-reload as P2. |
| Per-lawyer self-serve model switching in this milestone | “Power users.” | RBAC/tenant blast radius; confuses operator console with lawyer chat. | Operator-global (or tenant-admin) config only; lawyer chat stays consumer. |
| Rebuild Hermes model gateway / router / skill registry | “Need full parity.” | Explicit AGENTS.md / PRD out of scope. | Configure selection that adapters already understand. |
| OCR-only classical pipeline as sole vision path | “Cheaper than VLM.” | Stamps/layout/handwriting fail for legal docs; wrong extraction → wrong advice. | Dedicated VLM describe/OCR hybrid; classical OCR later as optional enhancer, not replacement. |

## Vision Routing — Expected Behavior (Explicit)

Operator-configured policy for inbound **image-bearing** turns (WeCom/QQ image or image+text):

```text
Inbound turn
  └─ has image attachment(s)?
        ├─ NO  → main model only (never call vision model)
        └─ YES
              ├─ main.supports_vision == true
              │     → pass image parts to main (multimodal path)
              └─ main.supports_vision == false
                    ├─ vision_model configured + probe OK
                    │     → call vision model (describe/OCR/structured extract)
                    │     → merge extraction + user text into main prompt
                    │     → main reasons on text-only enriched turn
                    └─ vision_model missing / failed
                          → FAIL CLOSED: do not silently drop image
                          → user: InkStatute-owned service notice
                          → operator/logs: reason code (no raw image bytes in contract log)
```

**Config fields (table stakes):**
- `main_provider` / `main_model` (+ catalog `supports_vision`)
- `vision_routing_mode`: `auto` (recommended) | `always_preprocess` | `main_only` (fail if main lacks vision)
- `vision_provider` / `vision_model` (required when main lacks vision and mode ≠ `main_only`)
- Optional: vision system prompt / max images / max pixels (P2)

**UX expectations:**
- Catalog badges: Vision / Text-only
- Warning when main is text-only and vision model empty
- Probe both main and vision endpoints independently
- Do not show provider stack traces to lawyers; output boundary still applies

**Confidence:** HIGH for the auto vision→main mix pattern (Hermes aux vision, 9router #1419, OpenCode vision fallback, Fallback Vision gateways). MEDIUM for exact InkStatute injection format (structured block vs caption) — decide in plan-phase.

## Feature Dependencies

```
RBAC write matrix + admin auth
    └──requires──> Config API (GET/PUT) with secret-ref validation
                       ├──requires──> Channel config (QQ/WeCom refs + dual-knob)
                       ├──requires──> Provider registry (built-in + custom)
                       │                  └──requires──> Model catalog (supports_vision)
                       │                                     └──requires──> Main model selection
                       │                                            └──requires──> Vision routing policy
                       │                                                   └──requires──> Runtime image-turn router
                       └──enhances──> Connection probes

Admin Web UI config pages ──requires──> Config API
Operator docs ──enhances──> all of the above

Runtime image-turn router ──conflicts──> Silent image drop
Channel enable UI ──conflicts──> Single-knob bypass of dual-knob
Provider console ──conflicts──> Hermes ~/.hermes mutation
```

### Dependency Notes

- **Config API requires RBAC write matrix:** mutating channels/providers is higher privilege than read dashboards; extend `packages/rbac` before exposing PUT.
- **Vision routing requires catalog `supports_vision` + runtime path:** UI-only toggles without provider_model/runtime behavior are incomplete.
- **Channel config depends on existing host config shapes:** `QQBotHostConfig` + WeCom env/ref conventions; UI is a façade over the same refs.
- **Provider registry should target InkStatute `api_key_ref` / `api_base_url`:** already in `ProviderModelBackendConfig`; do not invent a parallel secret model.
- **Hermes-mode panels must not pretend to set Hermes models:** backend-mode awareness avoids false dependencies on Hermes files.

## MVP Definition

### Launch With (v1.10)

Minimum to validate “operators configure InkStatute channels + providers + vision without Hermes.”

- [ ] Channel config UI/API for QQ + WeCom (enable knobs, secret refs, dual-knob effective state) — essential deploy surface
- [ ] Provider config: built-in vendor profiles + custom OpenAI-compatible endpoint — Hermes-like without Hermes coupling
- [ ] Built-in model catalog with `supports_vision` + main model selection — makes provider config usable
- [ ] Vision routing policy + runtime auto mix for image turns when main lacks vision — core milestone differentiator / GLM case
- [ ] Secret-ref persistence + never return raw secrets — safety non-negotiable
- [ ] RBAC-gated config writes + operator docs — operable and auditable

### Add After Validation (v1.10.x / next)

- [ ] Live `/models` refresh for custom endpoints — when operators run Ollama/vLLM often
- [ ] Config change audit trail — when multi-operator teams share one deploy
- [ ] Hot-reload without full restart — when downtime becomes painful
- [ ] Richer vision options (OCR vs full describe, max pixels, multi-image batch) — after auto-mix proven
- [ ] Backend-mode aware Hermes panel (read-only status) — when Hermes-mode deploys confuse operators

### Future Consideration (later milestones)

- [ ] LiteLLM-style budgets, virtual keys, spend dashboards — separate control-plane product
- [ ] Per-tenant / per-lawyer model overrides — needs stronger multi-tenant productization
- [ ] Classical OCR pipeline as cheaper perception tier — only with legal-quality evidence
- [ ] WeChat / additional channels in same console — after QQ/WeCom config stable
- [ ] Editing Hermes agent profile from InkStatute — explicitly out of scope unless milestone redefines boundary

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Channel config (QQ/WeCom) + dual-knob UI | HIGH | MEDIUM | P1 |
| Secret-ref fields + safe API responses | HIGH | LOW–MEDIUM | P1 |
| Built-in + custom provider registry | HIGH | MEDIUM | P1 |
| Built-in model catalog + main selection | HIGH | MEDIUM | P1 |
| Vision routing config + runtime auto mix | HIGH | HIGH | P1 |
| RBAC for config writes | HIGH | LOW | P1 |
| Connection probes | MEDIUM | MEDIUM | P1 |
| Operator docs / README alignment | HIGH | LOW | P1 |
| Effective-config / audit view | MEDIUM | MEDIUM | P2 |
| Live catalog refresh (custom) | MEDIUM | MEDIUM | P2 |
| Config change audit trail | MEDIUM | MEDIUM | P2 |
| Hot-reload | LOW–MEDIUM | HIGH | P3 |
| Spend/budget control plane | LOW (now) | HIGH | P3 |
| Per-lawyer model switching | LOW (now) | HIGH | P3 |

**Priority key:**
- P1: Must have for v1.10 launch
- P2: Should have once P1 works
- P3: Nice to have / future milestone

## Competitor / Ecosystem Feature Analysis

| Feature | Hermes Agent | OpenWebUI + LiteLLM | InkStatute v1.10 approach |
|---------|--------------|---------------------|---------------------------|
| Built-in vendors + custom endpoint | First-class; custom for any OpenAI-compatible; built-in only when catalog/auth UX needed | Connections UI + LiteLLM `model_list` / custom OpenAI URL | Mirror Hermes split in **InkStatute** config; do not write Hermes files |
| Model catalog | Static `_PROVIDER_MODELS` + optional live `/models` | Auto-detect `/models` or manual allowlist | Static built-in catalog + manual/optional probe for custom |
| Channel / bot config | Gateway platform adapters (separate from model menu) | Not a multi-IM bot console | First-class QQ/WeCom pages with dual-knob + secret refs |
| Vision fallback | Aux client / vision helpers for side tasks | Usually “pick a vision-capable chat model” | Explicit main vs vision + auto preprocess when main lacks vision |
| Secrets | Env / `.env` / auth store | Keys in connection settings | Refs only; process-edge resolve (stricter than typical chat UIs) |
| Admin vs user | CLI/`hermes model` operator-oriented | Admin Settings vs user chat | Extend existing admin-web-ui; lawyer chat remains non-config |

## InkStatute Package Dependencies (for REQUIREMENTS.md)

| Area | Depend on | Do not reinvent |
|------|-----------|-----------------|
| UI shell | `services/admin-web-ui` | New SPA framework unless plan says so |
| API | `services/admin-console-api` + `packages/rbac` | Bypass RBAC with a second auth path |
| QQ channel fields | `services/qqbot-service` config/secrets | Host crypto/normalize/send |
| WeCom channel fields | `services/wecom-service` env/ref conventions | Second WeCom stack |
| Provider shape | `packages/backends/provider_model` (`api_key_ref`, `api_base_url`) | Parallel key storage |
| Optional routing infra | `packages/model-gateway` | Full Hermes model gateway rebuild |
| Runtime flags | `packages/platform-runtime` feature flags | Auto-enable channels from UI alone |
| Privacy | platform-contract ref-first logging | Store image bytes / raw keys in config events |

## Sources

- InkStatute: `.planning/PROJECT.md`, root `README.md`, `docs/requirements/V2-PRD.md` (channel ownership, provider_model leave-room, secrets), `services/admin-web-ui/README.md`, `services/qqbot-service` dual-knob + secret refs, `packages/backends/provider_model` config
- Hermes Agent provider UX: [Adding Providers](https://hermes-agent.nousresearch.com/docs/developer-guide/adding-providers), [AI Providers](https://hermes-agent.nousresearch.com/docs/integrations/providers) — built-in vs custom, catalogs, aux/vision side paths (HIGH)
- OpenWebUI OpenAI-compatible connections: [docs.openwebui.com](https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-openai-compatible/) — URL + key + model allowlist (HIGH)
- LiteLLM admin / model_list patterns: [LiteLLM ↔ Open WebUI](https://docs.litellm.ai/docs/tutorials/openweb_ui) (MEDIUM–HIGH)
- Vision fallback pattern: [9router#1419](https://github.com/decolua/9router/issues/1419), OpenCode vision-fallback issues, Fallback Vision gateway READMEs (HIGH for behavior; MEDIUM for productization maturity)
- Multimodal cost routing: production guidance to keep text on text models and only route image-bearing traffic to vision (MEDIUM)

---
*Feature research for: v1.10 Operator Config Console (multi-channel + multi-provider + vision routing)*
*Researched: 2026-07-10*
