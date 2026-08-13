# Project Milestones: 墨律 InkStatute

## v4.0 Flutter Native + DSH Engine (In progress — started 2026-08-13)

**Planned:** Flutter 原生桌面 app（无 WebView）经 ACP over stdio 驱动本地嵌入的 DeepSeek Harness（DSH）引擎；分域法律预设（core ≤30 + 四域）+ 技能内容包自动更新；六条法律护栏双层落地；Word 原生修订导出（便携 Python 执行既有 track-changes 脚本）；单 exe 安装包 + 三层更新。v3.x 平台冻结、验收后退役。

**Spec:** [V4-PRD.md](../docs/requirements/V4-PRD.md) · **Evidence:** [V4-SELECTION.md](research/V4-SELECTION.md) · **Requirements:** 33 条（100% 映射 Phases 112-120）

**Human gates:** HG-1 法律质量（120）、HG-4 修订稿质量（118）、HG-3 律师试运行（120）——永不自动关闭。

---

## v3.1 Legal AI Arena (Shipped: 2026-08-09)

**Delivered:** Arena 生命周期契约（CONTRACT-01..04）、ACP fs/read_text_file 入站处理器（五重路径沙箱）、四模式竞技引擎（并行 / 自评迭代 / 交叉评审 / 对抗竞技，编排器不产内容、护栏不可绕过）、本地 HTTP+SSE 竞技服务（多流复用 + 权限安全 + 子进程受控）、桌面竞技 UI、Word 导出端点、v3.1 Closure（6 plans）。归档待 `/gsd-complete-milestone`。

**Phases completed:** 105-111 (7 phases, 38 plans)

---

## v3.0 Unified Legal Core (Shipped: 2026-08-08)

**Delivered:** Unified legal capability core with one event vocabulary, one ACP backend seam, one Gateway, one UI core across web/desktop/WeCom/QQ, 396 real legal skills indexed and materialized, and a self-built Python agent core with legal guardrails ported from Rust. Legacy backends (hermes, codex), legacy channels (web_sse), and legacy services (lawyer-web-chat, hermes-contract-layer) retired. ~10,483 lines of legacy code removed. 34 V2 gates green, 937 tests passing.

**Phases completed:** 88-104 (17 phases, 69 plans, 192 tasks)

**Archive:** [v3.0-ROADMAP.md](milestones/v3.0-ROADMAP.md) | [v3.0-REQUIREMENTS.md](milestones/v3.0-REQUIREMENTS.md) | [v3.0-phases](milestones/v3.0-phases/)

**Key accomplishments:**

- **Stage A — Protocol foundation (88-90):** 13-category unified event vocabulary (15 JSON Schemas, 18 Python dataclasses, 18 TypeScript interfaces) isomorphic to ACP v1 session/update. Python ACP client drives Hermes via stdio subprocess. Bidirectional event bridge with output boundary enforced twice (ACP bridge + Gateway). Permission requests never auto-approved.
- **Stage B — Channel unification (91-95):** Single multi-tenant HTTP+SSE Gateway replaces platform_api + lawyer-web-chat overlap. @inkstatute/ui-core extracted from lawyer-desktop (23 components, 3 themes). Responsive web client (desktop + mobile browser). Tauri desktop shell reusing invoke()→Gateway. WeCom/QQ bots refactored as Gateway consumers with non-streaming degradation.
- **Stage C — Capability layer (96-99):** 396 real Chinese legal skills indexed from ai-for-china-legal (345) + legal-skills (51), read-only vendored. Per-backend materialization with three-way separation (manifest/materializer/runtime). Strong-signal router ported from lawfirm-profile. CLAUDE.md practice profile multi-tenantized with cold-start interview.
- **Stage D — Self-built core (100-104):** Python async streaming turn loop with context budget and model layer. Tool layer + Word-native track-changes docx (41,185 bytes ported). Legal guardrails ported from Rust: tool_leak, prompt assembly, citation audit, 4 guardrails (research-gate, ask-user, citation audit, de-AI polish). Dual entry points: in-process BackendAdapter + `inkstatute-agent acp` CLI. Legacy convergence: ~10,483 lines retired, multi-agent-adapter frozen, gate system updated (38→34 gates).

**Stats:**

- 17 phases, 69 plans, 192 tasks
- Timeline: 2026-06-27 → 2026-08-08 (43 days)
- Git range: feat(88-01) → docs(104): transition complete
- 937 tests passing, 34 V2 gates green
- ~174K LOC Python across packages + services

**Closeout type:** override_closeout — 10 phases (91-99, 101) completed in prior sessions lack formal VERIFICATION.md metadata but have SUMMARY.md files and are verified by tests+gates.

**Known Gaps / Deferred at close:**

- HG-1 法律质量: Ported prompt assembly and legal guardrails require lawyer sampling — NOT auto-closable
- HG-4 修订稿质量: Word-native track-changes docx requires lawyer confirmation for external negotiation — NOT auto-closable
- HG-2 真机通道: Live WeCom send/receive acceptance — carried from V2
- HG-3 律师试运行: Five-workday / 15-real-task lawyer trial — carried from V2
- Operator `--live` QQ OpenAPI acceptance — carried from v1.9
- 10 phases (91-99, 101) lack VERIFICATION.md metadata — verification override recorded

**Follow-up:** Start next milestone with `/gsd-new-milestone`.

---

## v1.11 Product Console (Shipped: 2026-07-15)

**Phases completed:** 9 phases, 11 plans, 21 tasks

**Key accomplishments:**

- Runnable `python -m` entry points for `admin-web-ui` and `admin-console-api` on `ThreadingHTTPServer`, with a thread-safety audit and guarded shared mutable state.
- Make `wecom_service` and `qqbot_service` runnable HTTP hosts, and integrate process control into the admin console and web UI.
- 81-reports-dashboard
- Dedicated 404/500/413 SSR error pages with nav, HTML-escaped content, and CSP headers; responsive CSS fix removing fixed 200px width
- Active-state nav indication on all 16 pages, auth-state-aware Login/Logout links, and elimination of the duplicated `_logs_page_template` in logs.py
- One-click bash startup script for admin-web-ui + admin-console-api with env loading, JSON PID tracking, trap cleanup, and complete .env.example auth var documentation
- E2e smoke test that boots admin-web-ui via create_server, logs in via session auth, starts a channel host subprocess, views scrubbed logs, browses reports, and audits a contract trace — all stdlib-only with not_live_acceptance=true stamping

---

## v1.10 v1.10 (Shipped: 2026-07-12)

**Phases completed:** 7 phases, 26 plans, 58 tasks

**Key accomplishments:**

- Empty-deps `inkstatute-operator-config` with frozen refs-only OperatorConfigDocument schemas and shape-only secret-ref normalize (no qqbot-service dependency)
- Fail-closed `validate_document` rejects Hermes filesystem/profile authority and planted raw secrets without echo, while accepting refs-only OperatorConfigDocument payloads
- Default-OFF `operator_config_enabled` plus atomic JSON `OperatorConfigStore` that refuses writes when OFF, with V2 gate coverage and gitignored runtime store paths
- Admin contract freeze unblocked for `operator_config_enabled`, `/config` registered as ADMIN+OPERATOR in matrix and route table, and operator-config on admin-related V2 gate PYTHONPATHs.
- Admin/operator can GET and PUT `/config/{channels,providers,catalog,vision}` through pure store-backed handlers; operational PUT returns 405 after auth; flag-OFF PUT maps to 403 `operator_config_disabled` without bypassing `OperatorConfigStore.save`.
- Default-OFF `wecom_channel_enabled` with freeze + host-gate PYTHONPATH, plus five failing Wave 0 scaffolds for Plans 02–05.
- Additive `effective` dual-knob read model and `restart_required` apply semantics on GET/PUT `/config/channels` without collapsing host enabled or resolving secrets.
- QQ host compose loads operator-config store when the file exists (else env), preserves dual-knob AND, and documents restart-to-apply.
- WeCom host/doc materializer plus dual-knob AND wiring with store-wins-if-exists load, matching QQ apply parity.
- Incremental admin-web-ui `/config/channels` SSR form with dual-knob QQ/WeCom panels, secret-ref fields, and POST→`handle_admin_put` proxy (restart-to-apply; CSRF audit deferred to Phase 78)
- Frozen vendor/model catalog, model_allowlist + vision_provider_id linkage, and server-enforced provider/catalog/vision consistency validation in operator-config
- Six RED test-only modules specifying canonical built-ins, custom allowlists, catalog binding, SSRF-safe probing, signed CSRF, and SSR provider/catalog flows before either service implementation changes
- Stdlib SSR provider/catalog/probe surface with nonce+HMAC-SHA256 route-bound CSRF on every new POST route
- Operator-config `routing_mode` enum validation and vision pair completeness enforcement gated by routing mode
- Admin-console-api vision GET/PUT metadata (routing_modes, vision_configured, vision_status), empty-string normalization, and vision probe integration proof after a Phase 77 routing_mode save
- Vision Config SSR page with routing-mode selector, provider/model selects, route-bound CSRF, and probe re-render, consuming Phase 77-02 API metadata.
- Added shared gate-honesty UI chrome and dashboard/gate-status cards per the 78-UI-SPEC, plus Phase 78 typography/spacing fixes.
- Upgraded `/config/channels` to signed, route-bound CSRF protection and added the gate-honesty banner to the channel form.
- Integrated the shared gate-honesty banner into the Provider, Catalog, and Vision config forms and verified each page in tests.
- Updated operator documentation and the example environment to describe the SSR config pages, CSRF model, and gate-honesty policy.
- Make `DefaultRunRuntime` the consumer of `VisionRouter` for image-bearing turns.
- Provide the resolver builder and backend capabilities so services can inject a production-ready vision routing pipeline.
- Wire the vision resolver/runner into the real QQBot and WeCom service runtime compositions so image-bearing turns call `VisionRouter.decide()`.

---

## v1.9 QQBot Host Composition (Shipped: 2026-07-10)

**Delivered:** Assembled the v1.8 QQBot package-level channel into a deployable thin production webhook host (`services/qqbot-service/`), dual-knob runtime registration into `DefaultRunRuntime.channels`, Protocol-path smoke dry-run hardening, and controlled live HUMAN GATE honesty/runbook. Audit passed 11/11 requirements. Closed v1.8 accepted host-composition gaps without claiming live QQ OpenAPI acceptance.

**Phases completed:** 68–72 (5 phases, 14 plans, 29 tasks)

**Archive:** [v1.9-ROADMAP.md](milestones/v1.9-ROADMAP.md) | [v1.9-REQUIREMENTS.md](milestones/v1.9-REQUIREMENTS.md) | [v1.9-MILESTONE-AUDIT.md](milestones/v1.9-MILESTONE-AUDIT.md) | [v1.9-phases](milestones/v1.9-phases/)

**Key accomplishments:**

- Empty-deps `services/qqbot-service/` package registered in V2 gates (27 gates) with compileall and contract PYTHONPATH coverage
- Host secret refs resolve only at process edge; ADAPTER-04 freeze + no-wecom + flags default OFF
- Dual-knob flag→config factory + explicit `channels=(QQBotChannelAdapter,)` injection; disabled path refuses live IO
- ACK-first stdlib webhook composing verify_and_ack → ingress/feedback → deliver with Fake transports
- Smoke `--dry-run` Protocol-path via host helpers; sanitized evidence with `not_live_acceptance=true`
- Controlled `--live` fail-closed + runbook; CI never auto-claims live acceptance

**Stats:**

- 5 phases, 14 plans, 29 tasks
- Timeline: 2026-07-10 (same-day ship)
- Git range: feat(68-01) → docs(v1.9): milestone audit passed
- Audit: passed (11/11 requirements, 5/5 phases, Nyquist compliant)

**Known Gaps / Deferred at close:**

- Operator `--live` against real QQ OpenAPI — HUMAN GATE (by design)
- Phase 5 live WeCom UAT; Phase 8 five-workday lawyer trial — carried human gates
- Info-tier tech debt from audit (AST dynamic-import miss, CALLBACK_PATH duplication, leaf `--live` path)

**Follow-up:** Start next milestone with `$gsd-new-milestone`.

---

## v1.8 QQBot Channel Production (Shipped: 2026-07-09)

**Delivered:** Promoted the QQBot channel from v1.6 fixture-only proof to a complete V2 production-grade channel loop (Ed25519 signature + validation challenge, event normalization, access-token manager, text/markdown/keyboard egress, rich-media inbound/egress, session+ingress runtime, adapter real IO behind default-OFF flag, feedback loop parity + is_wakeup recall, and one-click dry-run smoke toolkit). Package-level 28/28 requirements satisfied; 321 qqbot unit tests green. Audit status `gaps_found` — production host webhook composition deferred; live QQ smoke remains a human gate.

**Phases completed:** 58–67 (10 phases, 25 plans, 53 tasks)

**Archive:** [v1.8-ROADMAP.md](milestones/v1.8-ROADMAP.md) | [v1.8-REQUIREMENTS.md](milestones/v1.8-REQUIREMENTS.md) | [v1.8-MILESTONE-AUDIT.md](milestones/v1.8-MILESTONE-AUDIT.md)

**Key accomplishments:**

- Safety baseline + Protocol/deps freeze (ADAPTER-04) before feature work
- Ed25519 signature verification + op=13 validation challenge (INGRESS-01/02)
- Gateway envelope normalization → AgentTurn / FeedbackEvent (INGRESS-03..05)
- TokenManager with TTL cache, 60s pre-expiry refresh, asyncio.Lock single-flight (EGRESS-01)
- Text / markdown / keyboard egress + passive-reply windows + output boundary (EGRESS-02/03/04/07)
- Rich-media AttachmentRef inbound + two-step upload msg_type=7 (EGRESS-05/06)
- QQBotSessionRuntime + QQBotRuntimeIngress composing platform_runtime (SESS-01..03)
- Adapter real IO across 6 Protocol methods + two-tier ACK (ADAPTER-01..03, INGRESS-06)
- Feedback-service composition + ACK no-op-if-sent + C2C is_wakeup period gate (FEEDBACK-01..03, RECALL-01)
- `scripts/smoke_test.py --dry-run` + runbook + sanitized evidence (SMOKE-01..04)

**Stats:**

- 10 phases, 25 plans, 53 tasks
- 321 qqbot unit tests OK; smoke `--dry-run` exit 0
- Audit: gaps_found (host composition deferred; accepted at close)

**Known Gaps / Deferred at close:**

- Production host webhook composing `verify_and_ack` → ingress/session / feedback → `deliver` (next-milestone candidate)
- Smoke dry-run skips full adapter Protocol + session path (optional hardening)
- Live QQ smoke (`--live`) — HUMAN GATE
- Carried: Phase 5 live WeCom UAT; Phase 8 five-workday lawyer trial

**Follow-up:** Start next milestone with `$gsd-new-milestone`.

---

## v1.7 M3 Platform Extensions (Shipped: 2026-07-06)

**Delivered:** Promoted adapter prototypes to production-grade (streaming, artifacts, multi-provider, session memory), extended platform surface (MCP registry, model gateway, multi-agent, skill write + hybrid routing), added operator and lawyer-facing Web UI, and introduced RBAC + multi-tenant isolation. Gap closure phase 57.1 wired TenantGuard into Web UI data access paths. All 9 feature flags default False, no frozen Protocol surfaces modified, 24 V2 gates green (1,547+ tests).

**Phases completed:** 45-57 + 57.1 gap closure (14 phases, 34 plans, 132 commits, 36,741 LOC inserted)

**Archive:** [v1.7-ROADMAP.md](milestones/v1.7-ROADMAP.md) | [v1.7-REQUIREMENTS.md](milestones/v1.7-REQUIREMENTS.md) | [v1.7-MILESTONE-AUDIT.md](milestones/v1.7-MILESTONE-AUDIT.md)

**Key accomplishments:**

- Adapter Productization (A1-A4): Codex + provider_model adapters promoted to production with frozen stream_events(), collect_artifacts(), multi-provider runners (Anthropic, Ollama), and session memory wiring via ContextBundle
- Platform Extensions (B1-B5): MCP Connector Registry, Skill Registry Write (with two-person rule), Hybrid Routing (Rule→Skill→Model cascade), Model Provider Gateway (rate limiting + circuit breakers + cost tracking), Multi-Agent Runtime Adapter
- Security & Compliance (C1-C2): RBAC with 4 roles + token-based auth + CI scan, Multi-Tenant Isolation with TenantScopeResolver + TenantGuard + Hindsight bank isolation
- Operator & UX Layer (C3-C4): Admin Web UI (dashboard, session/task inspection, feedback review) + Lawyer Web Chat (real SSE, session auth, file upload, feedback)
- Gap Closure (57.1): Wired TenantGuard into admin-console-api and lawyer-web-chat data access paths, closing HIGH-severity tenant isolation gap (+46 tests)
- Safety: All 9 feature flags default False, no frozen Protocol surfaces modified, 24 V2 gates green throughout (1,547+ tests, zero regressions)

---

## v1.4 Long-Term Memory Productization (Shipped: 2026-07-03)

**Delivered:** Replaced the evaluation-only memory approach with a single, productized long-term memory layer (Hindsight backend) so the bot feels like one continuous companion. The unified `Memory` interface, Hindsight adapter, focus/retention policies, WeCom runtime integration, retry/observability, and live validation are all shipped. Singleton memory wiring and contract event observability closed via Phase 32 gap closure.

**Phases completed:** 26-32 (7 phases, 1 gap closure)

**Archive:** [v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md) | [v1.4-REQUIREMENTS.md](milestones/v1.4-REQUIREMENTS.md) | [v1.4-MILESTONE-AUDIT.md](milestones/v1.4-MILESTONE-AUDIT.md)

**Key accomplishments:**

- Evaluated 7 external memory providers (Hindsight, Mem0, Zep, Letta, LangMem, Supermemory, Honcho) and selected Hindsight with documented rationale and live smoke test.
- Defined a backend-agnostic `Memory` Protocol with async `aretain`/`arecall`/`areflect` operations and privacy-safe metadata validation.
- Implemented `HindsightMemory` adapter using `hindsight-client` with BGE-M3 embeddings and BGE-Reranker-V2-M3.
- Implemented deterministic `MemoryContentClassifier` and `MemoryRetentionPolicy`/`MemoryFocusPolicy` for durable vs transient classification (LLM-free, CI-safe).
- Wired pre-turn recall and post-turn retention into `WeComSessionRuntime` with fail-open graceful degradation.
- Added `RetryableMemory` with exponential backoff, failure classification (`MemoryFailureCategory`), and `MemoryOperationEvent` contract events.
- Validated with live Hindsight multi-turn tests (preference retention, cross-task recall) and CI-safe skip when provider unreachable.
- Closed audit gaps: `build_memory_from_env()` singleton factory, `ContractLogMemoryObserver` for production observability, `WeComRuntimeIngress` memory/observer pass-through.
- Fixed V2 gate PYTHONPATH regression (v1.2-v1.4) that was hiding 3 broken gates.

**Audit result:** `passed`. 20/20 requirements satisfied; 10/10 integration points confirmed; 2/2 flows complete.

**Known deferred items at close:**

- Live Hindsight test fails when Gemini API free-tier quota is exhausted (429) — external quota issue, not a code defect.
- REQUIREMENTS.md traceability table was not updated during execution (fixed during audit).
- No SUMMARY.md files for v1.4 phases (only CONTEXT/PLAN/VERIFICATION produced).
- Phase 8 (Lawyer Trial Acceptance) and Phase 5 live WeCom UAT remain parallel human gates, not v1.4 dependencies.

**Follow-up:** Next milestone to be defined via `/gsd-new-milestone`.

---

## v1.3 Production Memory System and Evaluation Spikes (Shipped: 2026-07-02)

**Delivered:** Platform-native memory is production-capable, rolling summaries are safe and reference-first, recall orchestration is wired into ordinary WeCom/runtime flows, feedback-to-memory learning is wired at the service level, evaluation gates prove durable SQLite baseline and export evidence, and external memory adapters are evaluated as sanitized spikes with a defer-all recommendation.

**Phases completed:** 20-25, 25.1 (7 phases, 19 plans, 18 summaries)

**Archive:** [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md) | [v1.3-REQUIREMENTS.md](milestones/v1.3-REQUIREMENTS.md) | [v1.3-MILESTONE-AUDIT.md](milestones/v1.3-MILESTONE-AUDIT.md) | [v1.3-phases](milestones/v1.3-phases/)

**Key accomplishments:**

- Durable native memory store (`SQLiteMemoryStore`) with ref-first privacy, TTL/deletion/export, review state, and scoped query behavior.
- Policy-driven rolling summaries stored as refs, hashes, lengths, and structured evidence.
- Pre-run recall orchestration wired into WeCom/runtime ordinary continue/start flows, with interrupt/active-task behavior preserved and MemoryUse evidence fail-closed in legal production mode.
- Feedback-to-memory review loop at the service level: same-session correction refs, repeated-negative pending candidates, explicit human review actions, and no auto-modify for high-risk legal/route/skill candidates.
- Repeatable memory evaluation harness with hard gates, native baseline, and durable SQLite baseline/export evidence.
- Sanitized adapter spikes for Zep/Hindsight, OpenViking/ReMe, and Mem0-style candidates, with a final `defer_all_external` recommendation.
- Formal verification artifacts for phases 20-25 and validation artifacts for phases 22-25 and 25.1; deterministic audit closure script.

**Audit result:** `closed`. 28/28 requirements satisfied; 6/6 phase verification reports present; 7/7 cross-phase integration flows verified; 0 broken flows.

**Known deferred items at close:**

- Phase 20: file-backed `SQLiteMemoryStore` requires host `db_path` injection in production (deployment configuration, not code gap).
- Phase 24: `MemoryEvalRunner` can use fast in-memory or durable SQLite baseline; both modes are tested.
- Phase 25: external adapter spikes remain sanitized manifest/spec simulations; no live provider integration claimed.
- Phase 8 (Lawyer Trial Acceptance) and Phase 5 live WeCom UAT remain parallel human gates, not v1.3 dependencies.

**Follow-up:** Next milestone to be defined via `/gsd-new-milestone`.

---

## v1.2 Conversational Context and Memory Foundation (Shipped: 2026-07-02)

**Delivered:** Invisible WeCom conversation continuity, bounded context, interrupt resume, platform-native memory, feedback-informed learning, external-memory adapter evaluation, and the Phase 19 E2E session-runtime closure.

**Phases completed:** 14-19 (16 plans total)

**Archive:** [v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md) | [v1.2-REQUIREMENTS.md](milestones/v1.2-REQUIREMENTS.md) | [v1.2-MILESTONE-AUDIT.md](milestones/v1.2-MILESTONE-AUDIT.md) | [v1.2-phases](milestones/v1.2-phases/)

**Key accomplishments:**

- Backend-neutral memory/context/interrupt schemas, Python bindings, and sanitized contract fixtures for the v1.2 vocabulary.
- Scoped session resolver and interrupt lifecycle support with ref/hash-only decision and resume evidence.
- WeCom session runtime behavior for pending clarification resume, active-task precedence, session continuation, and session splitting.
- Deterministic short-term context bundles with protected sections, rolling summaries, feedback corrections, memory refs, artifact refs, and budget trimming.
- Platform-native memory store and feedback learning policy with human-reviewed candidates and no automatic legal skill modification.
- Sanitized external memory adapter contract, capability manifest, fixture evidence, and production recommendation.
- Phase 19 closure of the v1.2 audit gaps: ordinary WeCom continue/start turns now call `RunRuntime.create_run()`, and sanitized callback ingress reaches `WeComSessionRuntime.handle_turn()`.

**Audit result:** `tech_debt`. Requirements 24/24 satisfied; phases 6/6 verified; critical integration and flow gaps closed by Phase 19.

**Known deferred items at close:**

- 2 open artifact-audit human gates acknowledged and carried forward in `.planning/STATE.md`.
- Nyquist validation artifacts for Phases 14, 15, 16, 18, and 19 are accepted validation debt.
- Service-level feedback-to-memory automation remains future integration work; Phase 17 delivered library surfaces and fixture evidence.
- Live WeCom UAT and the five-workday lawyer trial remain human gates and are not claimed as autonomous production acceptance.

**Follow-up:** v1.3 Production Memory System and Evaluation Spikes is active.

---

[Entries in reverse chronological order - newest first]

## v1.1 Platform Foundation (Shipped: 2026-06-30)

**Delivered:** Four-contract North Star platform architecture (ChannelAdapter, BackendAdapter, SolutionLoader, RunRuntime) with embeddable runtime, Hermes backend adapter, multi-channel interface, and backend-portable solution loader — all default-OFF.

**Phases completed:** 09-13 (20 plans total)

**Key accomplishments:**

- Locked four North Star contracts with signature-only Protocol stubs, boundary allowlist, and privacy scan allowlist
- Embeddable DefaultRunRuntime — library-only, dependency-injected, fake backend, output boundary with allowlist policy
- Hermes BackendAdapter — subprocess one-shot adapter, non-mutating capability probe, fixture-based `/v1/runs` parity spike
- Channel interface + WeCom wrapper + Web/SSE channel + Platform API server + TypeScript SDK + embeddable web chat renderer — all default-off
- SolutionLoader library + lawfirm neutral manifest + sanitizing Hermes materializer + demo_non_legal pack + privacy scanner + aggregate contract evidence

**Stats:**

- 195 files changed
- 25,368 lines added
- 5 phases, 20 plans, 20 summaries
- 99 commits (1d3fe58 → 24f70e9)
- V2 gate: 8/8 pass, 287 tests, exit 0
- Audit: passed (re-audited 2026-06-30)
- 2 days from start to ship (2026-06-28 → 2026-06-29 execution, 2026-06-30 audit+archive)

**Git range:** `1d3fe58` → `24f70e9`

**Known deferred items:**

- Phase 8 (Lawyer Trial Acceptance) — parallel human gate, NOT an autonomous-completable gap
- Phase 5 live WeCom UAT — human gate, fixture-satisfied
- `/v1/runs` lane — route mismatch evidence reported; remains default-off
- All v1.1 runtime lanes default-OFF — live cutover is a separate human gate

**Follow-up:** v1.2 Conversational Context and Memory Foundation shipped 2026-07-02; see the v1.2 entry above.

---
