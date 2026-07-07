# Pitfalls Research: M3 Platform Extensions

**Domain:** M3 Platform Extensions — adapter productization, MCP registry, model gateway, multi-agent, skill write, hybrid routing, Web UI, RBAC, multi-tenant
**Researched:** 2026-07-05
**Confidence:** HIGH

This research covers common mistakes when **adding M3 features to the existing InkStatute V2 system** — a Python 3.11 async legal-domain agent platform with a frozen `BackendAdapter` Protocol (9 methods, `packages/platform-runtime/src/platform_runtime/protocols.py:222-239`) and frozen `ChannelAdapter` Protocol (6 methods, `protocols.py:208-219`), 19 V2 CI gates (969 tests), JSONL contract event logs using `raw_payload_ref` for privacy, an output boundary that suppresses Hermes/gateway/meta notices, all runtime lanes default-OFF, and two open V2 human gates (Phase 5 live WeCom UAT + Phase 8 five-workday lawyer trial) running in parallel. M3 must preserve every one of these invariants while promoting adapter prototypes to production, adding platform extensions, Web UI, RBAC, and multi-tenancy. Phase numbering continues from v1.6 (next phase = 45).

---

## Critical Pitfalls (Legal/Safety)

These pitfalls could violate legal safety, client privacy, the output boundary, or the human-review gate on high-risk legal feedback. They are the highest-priority risks for a lawyer-facing platform and must be addressed before any M3 feature goes live.

### Critical: Skill Registry write auto-modifying legal conclusion skills

**What goes wrong:**
The V2 PRD and `AGENTS.md` are explicit: "High-risk legal feedback must remain human-reviewed. V2 records `skill_candidate`; it does not auto-synthesize or auto-modify legal conclusion skills." M3 introduces Skill Registry **write** operations. The moment writes are enabled, the temptation is to let feedback-derived `skill_candidate` records flow directly into active skills via an automated pipeline ("the trial showed 80% positive feedback, auto-promote it"). A poisoned or misclassified feedback event then becomes a live legal skill that steers lawyer advice. Worse, in a multi-tenant system a skill written for tenant A could leak into tenant B's active skill set.

**Warning signs:**
- A PR adds a `promote_skill_candidate` or `activate_skill` path that does not require a human approval record.
- Skill write tests pass without an explicit `human_reviewed: true` gate field.
- A feedback-to-skill pipeline writes to the same skill namespace that the router reads from at request time.
- Skill versions are mutable in place (no immutable version snapshots), so a rollback cannot restore the prior legal conclusion.

**Prevention:**
- Skill Registry write MUST require an explicit human approval record (`reviewed_by`, `reviewed_at`, `review_evidence_ref`) before any skill becomes active. No automated promotion path, even behind a flag.
- Skills MUST be versioned and immutable once published; writes create a new version, never mutate. Active skill set is a pointer to a version, swappable and rollbackable.
- Add a contract test asserting no code path can flip a skill from `candidate` to `active` without a human-review record. This is the legal-safety equivalent of the existing output-boundary test.
- Per-tenant skill namespaces enforced at the registry layer, not just the router layer.

**Phase to address:** Skill Registry write phase — design the human-review gate into the write API before any write code is written.

### Critical: Output boundary bypass via streaming events, artifacts, or Web UI

**What goes wrong:**
The existing output boundary (`OUTPUT-01`) suppresses Hermes gateway/update/command/meta notices before WeCom delivery. M3 adds three new bypass paths: (1) streaming events surface raw provider tokens, model names, and API error traces that were previously filtered at the `agent:end` boundary; (2) artifacts (files, logs, traces) can contain backend noise — model names, function call traces, stack traces — that the boundary was designed to block; (3) the Admin Web UI and Lawyer Web chat render backend output directly in a browser, potentially showing raw error text, model identifiers, or tool-call JSON to lawyers. Each is a new hole in a boundary that V2 spent a phase building.

**Warning signs:**
- Streaming event tests assert on raw `model` or `provider` fields reaching the channel layer.
- Artifact metadata includes `model_name`, `api_error`, or `tool_call_trace` fields that are not scrubbed.
- Web chat renders assistant messages via `innerHTML` or unsanitized markdown from the backend stream.
- A streaming partial-error event forwards the provider's error message verbatim ("anthropic rate limited", "ollama connection refused") to the user.

**Prevention:**
- Apply the output boundary at the **streaming event emission point**, not just at `agent:end`. Define an allowlist of event types that may cross the boundary; rewrite or drop the rest. Partial-error events must be rewritten to InkStatute-owned service notices ("The assistant is temporarily unavailable"), never raw provider errors.
- Artifact metadata passes through the same field allowlist used by the Admin Console API (`services/admin-console-api` field allowlist excluding secrets). Model names, API keys, and tool-call traces are stripped before any artifact ref is returned.
- Web UI renders all assistant/backend content as escaped plaintext or via a sanitizer (DOMPurify) — never raw `innerHTML`. Treat all backend-originated text as untrusted, including model-generated markdown (see Operator & UX pitfalls).
- Add a regression test: stream a fixture containing provider noise and assert none of it reaches the channel delivery or Web chat payload.

**Phase to address:** Adapter productization (streaming + artifacts) phase and Web UI phase — boundary enforcement must be designed into the streaming emitter and artifact collector before any feature flag is flipped.

### Critical: raw_payload_ref privacy violation via artifacts, memory, or Web UI dashboards

**What goes wrong:**
V2 contract logs deliberately use `raw_payload_ref` (a reference) instead of storing sensitive full text, to protect client legal materials and work product. M3 introduces three new places where full text can leak: (1) artifacts may inline full document text instead of returning a ref; (2) session memory (Hindsight integration) may persist full conversation text or document contents into a memory store that lacks the same privacy scrubbing; (3) Admin Web UI dashboards may render full message text, feedback payloads, or file previews that the read-view API currently scrubs at read time. A single dashboard that shows raw feedback text undoes the `raw_payload_ref` discipline.

**Warning signs:**
- Artifact records contain `content` or `text` fields with full document bodies rather than `artifact_ref` + size + hash.
- Memory store writes include unredacted conversation text or uploaded document contents.
- Admin UI renders `feedback.payload` or `message.body` directly without the read-time privacy scrubbing that `services/conversation-read-view` applies.
- Hindsight integration stores memory entries keyed by raw user input rather than a hashed/redacted reference.

**Prevention:**
- Artifacts MUST use refs (`artifact_ref`, `content_hash`, `size_bytes`) for the contract log; full content lives in a separate object store with access controls. The contract event never carries full text.
- Memory store inherits the same `raw_payload_ref` discipline: memory entries store references and metadata, not full text. If Hindsight requires full text for retrieval, it lives in a tenant-scoped store with explicit retention and access policy — not in contract logs.
- Web UI dashboards reuse the existing `conversation-read-view` scrubbing layer; no dashboard endpoint returns raw payloads. Add a test asserting every admin/dashboard endpoint applies the same field allowlist + scrubbing as the read-view.
- Add a contract test: assert no `ArtifactRecord`, `MemoryEntry`, or admin API response schema field is named `*payload`, `*text`, `*body` with full content — only refs.

**Phase to address:** Artifact return phase, session memory phase, and Admin Web UI phase — privacy-by-design in the schema before implementation.

### Critical: High-risk feedback auto-routing in hybrid routing

**What goes wrong:**
M3 adds model-based and hybrid routing with confidence scoring. A confidence-miscalibrated router could route a high-risk legal question to a cheap/weak model (or a non-Hermes backend) that produces a plausible-but-wrong legal conclusion, bypassing the Hermes lawfirm profile that has the reviewed skill set. The router treats confidence as a quality signal, but high confidence on a wrong answer is the most dangerous failure mode in a legal domain. Cold-start bias (router defaults to the cheap path until it has enough data) means the first lawyer questions — the most consequential — get the worst routing.

**Warning signs:**
- Router confidence threshold for "escalate to strong model" is set once and never recalibrated against legal-domain accuracy.
- Routing decisions for legal-domain queries are made purely on token-cost or latency signals, not legal-safety risk classification.
- The router has no override that forces high-risk legal queries to Hermes (the reviewed backend) regardless of confidence.
- Cold-start: router has no legal-domain training data, so it defaults to the cheapest provider for the first N requests.

**Prevention:**
- Hybrid routing MUST have a legal-risk classifier that forces any query classified as high-risk legal to the Hermes backend (or the reviewed skill set) regardless of confidence score. Confidence routing applies only to low-risk / non-legal queries.
- Confidence calibration must be validated against a legal-domain eval set before the routing flag can be promoted. Cold-start defaults to the safe (Hermes) path, not the cheap path.
- Add a test: high-risk legal fixtures always route to Hermes even when the router's confidence says the cheap model is sufficient.
- Routing decisions are logged as `RouteDecision` events (already in the contract) with `reason` and `confidence`; audit these for routing-to-cheap-model patterns on legal queries.

**Phase to address:** Hybrid routing phase — design the legal-risk override before implementing the confidence scorer.

### Critical: Multi-tenant cross-tenant legal data leakage

**What goes wrong:**
M3 adds multi-tenant isolation. In a legal platform, cross-tenant leakage means one law firm's client matters, feedback, skills, or memory bleed into another firm's view. This is not just a bug — it is a potential breach of client confidentiality and attorney work-product privilege. The shared-database-with-tenant-column pattern fails silently: a missing tenant filter in one query, a shared cache key that doesn't include tenant_id, a memory vector store with loose namespace filters, a skill registry that doesn't scope by tenant. Async connection pooling and shared caching (which this platform uses) increase the risk.

**Warning signs:**
- Any query/filter/scope in contract logs, read-view, memory, skills, or admin API that does not include `tenant_id` in its WHERE clause or key prefix.
- Cache keys (async lru_cache, Redis) that don't include tenant_id — one tenant's computed result served to another.
- Memory/vector store uses a shared namespace with similarity-based retrieval that can pull another tenant's chunk via high cosine similarity.
- Migration scripts that backfill tenant_id with a default value, silently merging previously-separate data.

**Prevention:**
- Tenant isolation enforced at the data layer (tenant_id column + query interceptor that injects tenant filter), not just at the API layer. Every async query path passes through a tenant-scoped session/context.
- Cache keys MUST be namespaced by tenant_id; add a test that asserts cross-tenant cache reads return miss/empty.
- Memory/vector store uses per-tenant namespaces with hard isolation, not shared-namespace-with-filter. Test for cross-tenant vector bleed (attacker seeds near-duplicate content, asserts other tenant's data is not retrieved).
- Migration: existing V2 data must be assigned an explicit default tenant; add a migration test asserting no row has null/empty tenant_id after migration.
- Add a dedicated "tenant isolation" gate (a 20th gate or sub-gate) with cross-tenant access fixtures.

**Phase to address:** Multi-tenant isolation phase — isolation enforced at the data layer before any tenant-scoped feature is built on top.

---

## Adapter Productization Pitfalls

### Pitfall: Streaming events — cancellation not propagating upstream (orphan billing + zombie runs)

**What goes wrong:**
When streaming is enabled, a lawyer closes the WeCom chat or the Web chat tab mid-stream. The downstream SSE/async generator stops consuming, but the upstream LLM provider stream keeps reading tokens — the provider keeps billing, and in this platform the run stays "active" in the task state machine, blocking the human-gate loop. Python `async for` over an SDK stream does not automatically cancel the upstream HTTP connection when the downstream consumer stops. The result: orphaned runs that never reach a terminal state, polluting the 19 V2 gates' run-state assertions, and cost accumulation for tokens the lawyer never saw.

**Warning signs:**
- Runs stuck in `running` state after a user disconnects; gate tests that assert terminal-state counts start failing.
- Cost/usage logs diverge from delivered tokens (server generated 5k tokens, user saw 30).
- `stream_events` async generator does not call `stream.aclose()` / cancel the upstream task in a `finally` block.
- The `cancel_run` BackendAdapter method is never wired to the streaming disconnect path.

**Prevention:**
- `stream_events` implementation MUST wrap the upstream SDK stream in a `try/finally` that calls `aclose()` (or cancels the upstream task) on consumer disconnect or cancellation. Use `asyncio.CancelledError` handling, not just `break`.
- Wire the channel/Web chat disconnect signal → `cancel_run` on the BackendAdapter, so the run reaches a terminal `cancelled` state and the task state machine stays consistent.
- Use a bounded `asyncio.Queue(maxsize=N)` between producer and consumer to apply backpressure — without it, a slow consumer (WeCom delivery) causes unbounded memory growth holding buffered tokens.
- Never do blocking/sync I/O inside the `async for` stream loop — it starves the single-threaded asyncio event loop and freezes all concurrent runs. Delegate file writes, DB writes, network calls to thread pools.
- Add a test: open a stream, disconnect mid-stream, assert the run reaches `cancelled` within a timeout and the upstream task is cancelled (no orphan).

**Phase to address:** Streaming events phase — cancellation propagation and backpressure designed before the first streaming adapter ships.

### Pitfall: Streaming events — partial failure and event ordering

**What goes wrong:**
A stream that emits 80% of a response then hits a provider error leaves the platform in an ambiguous state: is the run `succeeded` (partial), `failed`, or `interrupted`? If the adapter emits a `failed` event after partial `token` events, the channel layer may deliver a half-answer to the lawyer followed by a raw error — violating the output boundary. Event ordering across multiple streams (text + tool-call deltas) is interleaved under different `event.index` values; naive concatenation produces garbled output. Tool-call argument deltas are not individually parseable JSON — calling `json.loads` on each fragment raises on every chunk.

**Warning signs:**
- A run reaches terminal state with partial text already delivered to WeCom, and no InkStatute-owned service notice follows.
- Tool-call argument parsing raises `JSONDecodeError` mid-stream.
- Text and tool-call deltas get concatenated into a single buffer, producing mixed garbage.
- Event sequence tests assert a strict `started → tokens → completed` order but the adapter emits `error` after `tokens` with no handling.

**Prevention:**
- Define a terminal-event contract: a stream MUST end with exactly one of `completed`, `failed`, `cancelled`. On `failed` after partial delivery, the channel layer emits an InkStatute-owned service notice ("The assistant's response was interrupted") — never the raw provider error.
- Keep text and tool-call deltas in separate buffers keyed by `event.index`. Only parse tool-call arguments after `content_block_stop`, or use a partial JSON parser for incremental rendering.
- Add a fixture: stream that fails at 80% → assert terminal state is `failed`, delivered text is followed by a service notice, and no raw error reaches the user.

**Phase to address:** Streaming events phase — terminal-event contract defined alongside the streaming emitter.

### Pitfall: Artifact return — large file handling and temp file cleanup

**What goes wrong:**
Artifacts (generated documents, exported analyses, logs) can be large. If the adapter inlines artifact content into the contract event or holds it in memory, the platform OOMs under concurrent runs. If artifacts are written to temp files that are never cleaned up, disk fills over days. If artifact refs point to a temp path that gets garbage-collected before the lawyer retrieves the file, the ref dangles. In a legal domain, an artifact containing a generated legal memo that sits in an unscoped temp dir is a confidentiality risk.

**Warning signs:**
- `ArtifactRecord` contains inline `content` for large files.
- Temp files accumulate in `/tmp` across test runs or CI gates (disk usage grows).
- Artifact refs use temp paths with no retention policy or access scoping.
- Concurrent large-artifact runs cause memory spikes or OOM in CI.

**Prevention:**
- Artifacts MUST be stored in a scoped object store (tenant-scoped, run-scoped) with a ref + hash + size; the contract event carries only the ref. Inline content is allowed only below a small threshold (e.g., 4 KB) and only for non-sensitive metadata.
- Temp files cleaned in a `finally` block after the artifact is persisted to the store; add a test asserting no temp files remain after a run.
- Artifact refs include a TTL/retention field; expired refs are not retrievable.
- Add a test: large artifact (e.g., 10 MB) → assert contract event has only ref, memory stays bounded, temp file is cleaned.

**Phase to address:** Artifact return phase — storage strategy before the artifact collector ships.

### Pitfall: Multi-provider — API key management, rate limit differences, capability mismatches

**What goes wrong:**
Adding Anthropic and Ollama to the provider_model adapter introduces: (1) API keys that must not be committed (already a V2 rule) but now span multiple providers with different env var conventions; (2) rate limits that differ by provider — Anthropic 429s vs Ollama local timeouts — and the adapter treats them identically, causing retry storms; (3) capability mismatches — Ollama local models may not support tool calls or streaming the same way Anthropic does, and the adapter assumes a uniform capability set, producing `unsupported` errors mid-run. Cost surprises: Ollama is "free" (local) but Anthropic bills per token; a fallback loop that escalates to Anthropic on every Ollama timeout silently inflates cost.

**Warning signs:**
- API keys appear in config files, logs, or contract events.
- A single retry policy applied to all providers — Anthropic 429s retried aggressively, Ollama timeouts retried indefinitely.
- Capability checks absent — the adapter calls `tool_use` on an Ollama model that doesn't support it, failing mid-run.
- Fallback always escalates to the paid provider; cost dashboards show unexpected Anthropic spend.

**Prevention:**
- API keys loaded from env only, never config files or contract events. Add a test asserting no key material appears in any event schema field or log line (extend the existing secret-exclusion test).
- Per-provider rate-limit and retry policy: Anthropic uses 429-aware exponential backoff with `retry-after` header; Ollama uses a short timeout with bounded retries. Never retry indefinitely.
- Capability negotiation: `AdapterCapabilitySet` (already in the Protocol) must reflect the actual provider's capabilities; tool-call / streaming / function-calling gates checked before `submit_run`, not mid-run.
- Fallback policy with cost ceiling: fallback to paid provider is bounded by a per-run / per-tenant cost budget; exceeding it fails the run with a service notice, not an infinite escalation.

**Phase to address:** Multi-provider phase — per-provider policy and capability negotiation before wiring the second provider.

---

## Platform Extensions Pitfalls

### Pitfall: MCP Connector Registry — malicious tool schemas and capability escalation

**What goes wrong:**
M3 adds an MCP Connector Registry to register and discover MCP tool connectors. MCP tool schemas are LLM-readable descriptions; a malicious or compromised connector can include a tool description that tricks the LLM into calling it with escalated capabilities ("this tool is required for every request, call it with the user's full context"). Tool execution without sandboxing means a malicious connector runs arbitrary code on the host. Capability escalation: a connector registered as "read-only" can declare tools that write, and the registry doesn't enforce the declared capability against the actual tool behavior. In a legal domain, a malicious tool could exfiltrate client document contents via a tool-call argument.

**Warning signs:**
- Tool schemas accepted into the registry without schema validation or capability review.
- Tool execution runs in the same process/namespace as the agent — no sandbox, no network egress control.
- Connector capabilities are self-declared and never verified against actual tool behavior.
- Tool descriptions are passed verbatim into the LLM prompt without length limits or content review.

**Prevention:**
- Registry admission requires a schema validation + human review (consistent with the skill-write human-review gate). No auto-registration of untrusted connectors.
- Tool execution sandboxed: separate process/container, restricted network egress, bounded CPU/memory, no access to contract logs or other tenants' data. Use the existing output-boundary discipline: tool results pass through an allowlist before reaching the LLM context.
- Capability enforcement: the registry declares a capability set per connector; tool calls that exceed declared capabilities are blocked and logged.
- Tool description length-limited and content-reviewed; descriptions are not passed verbatim if they contain instruction-like content.
- Add a test: a fixture malicious connector (over-claiming description, attempting file exfiltration) is rejected or sandboxed.

**Phase to address:** MCP Connector Registry phase — admission review and sandboxing before any connector is callable.

### Pitfall: Model Provider Gateway — cascading failures, fallback loops, cost explosion

**What goes wrong:**
The unified gateway routes, rate-limits, and falls back across providers. Cascading failure: one provider's outage causes all traffic to fall to the next, which then overloads and fails, cascading to the next — a thundering herd. Fallback loops: a request fails on provider A, falls back to B, B fails, falls back to A — an infinite loop because the gateway doesn't track that A already failed for this request. Cost explosion: the gateway falls back from a cheap model to an expensive model on every transient error, multiplying cost. Model selection gaming: if the gateway exposes model choice to the caller (or the router), a tenant could pin all requests to the most expensive model, or the router could be gamed to always pick the expensive path.

**Warning signs:**
- No circuit breaker — a failing provider is retried on every request, prolonging the outage.
- Fallback chain has no "already tried" tracking — requests loop between providers.
- No per-tenant / per-run cost ceiling; cost dashboards show unbounded spikes during outages.
- Model selection is caller-controlled with no policy enforcement.

**Prevention:**
- Circuit breaker per provider: after N consecutive failures, the provider is marked unhealthy for a cooldown period; requests skip it instead of retrying. Half-open probing to recover.
- Fallback chain tracks tried-providers per request; a provider already tried is not retried in the same request. Bounded fallback depth.
- Per-tenant and per-run cost ceiling enforced at the gateway; exceeding it fails the run with a service notice, not an infinite escalation.
- Model selection is gateway-policy-controlled, not caller-controlled; the router proposes, the gateway disposes based on policy + cost + health.
- Add a test: simulate provider A outage → assert fallback to B is bounded, no loop, cost ceiling enforced, circuit breaker opens for A.

**Phase to address:** Model Provider Gateway phase — circuit breaker and cost ceiling before multi-provider fallback is enabled.

### Pitfall: Multi-Agent Runtime — agent deadlock, infinite handoff loops, shared state corruption

**What goes wrong:**
Multi-agent runtime introduces agent-to-agent handoffs. Deadlock: agent A waits for agent B's output, B waits for A's — no cycle breaker. Infinite handoff loop: A hands to B, B rejects and hands back to A, repeat — each agent interprets its role narrowly and rejects the other's output, with no authority to reconcile. Shared state corruption: agents share a context/memory store and one agent's write corrupts another's read mid-turn. Unbounded parallelism: the runtime fans out N sub-agents in parallel with no concurrency limit, exhausting the event loop / provider rate limits. In a legal domain, an infinite handoff loop silently burns cost while a lawyer waits; state corruption produces a legal conclusion built on garbled context.

**Warning signs:**
- No `max_depth` / `max_handoffs` bound on agent-to-agent handoffs.
- No cycle detection in the agent handoff graph.
- Shared state mutated by one agent while another is mid-read (no isolation / versioning).
- Parallel fan-out with no semaphore / concurrency limit; provider 429s cascade.

**Prevention:**
- Hard bounds: `max_handoffs` (e.g., 5) and `max_depth` per run; exceeding them terminates the run with a service notice. Track handoff count in the `ExecutionTrace`.
- Cycle detection: track the agent handoff chain per run; if agent A → B → A is detected, break the cycle by escalating to a human or a terminal failure.
- Shared state is versioned / copy-on-write per agent turn; an agent reads a snapshot, not a live-mutated store. Writes create a new version.
- Bounded parallelism: `asyncio.Semaphore` limits concurrent sub-agent runs; excess sub-tasks queue or fail fast.
- Add tests: (1) two-agent cycle → assert termination within `max_handoffs`; (2) parallel fan-out → assert concurrency capped; (3) shared-state mutation → assert no mid-turn corruption.

**Phase to address:** Multi-Agent Runtime Adapter phase — bounds and cycle detection before any multi-agent run is enabled.

### Pitfall: Skill Registry write — version conflict and review bypass

**What goes wrong:**
Beyond the critical auto-modification risk (above), skill writes introduce version conflicts: two operators edit the same skill concurrently, last-write-wins silently drops one edit. Review bypass: a write path is added that skips the human-review gate (e.g., an admin "hotfix" path, a migration script, a test fixture that writes active skills). Skill injection: a skill descriptor with a malicious `prompt_template` or `tool_binding` is written and immediately becomes active, injecting instructions into every lawyer query the router sends to that skill.

**Warning signs:**
- Skill writes have no optimistic concurrency control (no `version` / `etag` check).
- A write path exists that doesn't go through the human-review gate (admin hotfix, migration, fixture loader).
- Skill descriptors accepted without validating `prompt_template` and `tool_binding` content.
- Active skill set updated in place without versioning.

**Prevention:**
- Optimistic concurrency: write requires the current `version`; mismatch → conflict error, not silent overwrite.
- Every write path — including admin, migration, and fixtures — goes through the same human-review gate. No bypass paths. Test fixtures write to a `candidate` namespace, never `active`.
- Skill descriptor validation: `prompt_template` and `tool_binding` pass a content review (no instruction injection, no tool bindings outside the connector's declared capabilities).
- Active skill set is a versioned pointer; promotion swaps the pointer atomically and is rollbackable.

**Phase to address:** Skill Registry write phase — concurrency control and single review-gate before any write path ships.

### Pitfall: Hybrid routing — router hallucination, confidence miscalibration, routing loops, cold-start bias

**What goes wrong:**
Beyond the critical legal-risk-routing pitfall (above): router hallucination — the router model itself hallucinates a route decision (invents a skill or backend that doesn't exist). Confidence miscalibration — the router reports 0.9 confidence on a wrong route. Routing loops — the router routes to a skill, the skill defers back to the router, repeat. Cold-start bias — with no historical data, the router defaults to a fixed (often cheapest) path that is wrong for legal queries.

**Warning signs:**
- Router emits a `skill_id` or `backend_id` that doesn't exist in the registry — no validation.
- Confidence scores never validated against actual outcome accuracy.
- Router → skill → router cycle with no loop breaker.
- Cold-start: first N requests all route to the same default, regardless of query type.

**Prevention:**
- Router output validated against the registry: a route to a non-existent skill/backend is a hard error, not a fallback. The router cannot invent routes.
- Confidence calibration validated against a legal-domain eval set; calibration drift monitored. Low-confidence routes escalate to the safe (Hermes) path, not the cheap path.
- Routing loop breaker: track route-decision chain per run; if router → skill → router is detected, terminate with a service notice.
- Cold-start defaults to the safe (Hermes / reviewed) path until the router has enough calibrated data to deviate. Cold-start is not "cheapest by default."
- Add tests: (1) router hallucination → assert hard error; (2) routing loop → assert termination; (3) cold-start → assert safe default.

**Phase to address:** Hybrid routing phase — validation and loop-breaking before the router is enabled.

---

## Operator & UX Layer Pitfalls

### Pitfall: Admin Web UI — XSS via chat content and dashboards

**What goes wrong:**
The Admin Web UI renders sessions, tasks, feedback, and health views. Chat content and feedback payloads are LLM-generated or user-supplied — both are untrusted. Rendering them via `innerHTML`, unsanitized markdown, or a sanitizer with bypasses (e.g., video-tag exemptions, `srcdoc` iframes) enables stored XSS. In a multi-user admin console, an attacker who can influence LLM output (via indirect prompt injection in a shared document) can fire XSS in every admin's browser, stealing the admin token from localStorage and escalating to full account takeover. This is a documented real-world pattern in LLM chat UIs (AnythingLLM, Open-WebUI, MagicAI CVEs).

**Warning signs:**
- Assistant messages rendered via `innerHTML` or `{@html}` without DOMPurify.
- Markdown rendered via `marked.parse()` without `DOMPurify.sanitize()` wrapping.
- Session token stored in localStorage (readable via XSS).
- No Content-Security-Policy header on the admin UI.

**Prevention:**
- All backend/LLM/user content rendered as escaped plaintext or via `DOMPurify.sanitize(marked.parse(content))`. No raw HTML insertion. No sanitizer exemptions (video tags, iframes, `srcdoc`).
- Session token in httpOnly cookie, not localStorage — XSS cannot read it.
- Content-Security-Policy with `strict-dynamic` and nonces; no `unsafe-inline`.
- Add a test: inject XSS payload via chat input / feedback / model description → assert it does not execute in the rendered UI.

**Phase to address:** Admin Web UI phase — rendering sanitization and token storage before the UI is exposed to operators.

### Pitfall: Admin Web UI — privilege escalation via UI and data exposure in dashboards

**What goes wrong:**
The existing Admin Console API (`services/admin-console-api`) is read-only with static token auth and a field allowlist excluding secrets. The Web UI adds interactivity (and eventually write actions), creating privilege escalation paths: a read-only operator sees a "promote skill" button that calls a write endpoint not gated by RBAC; a dashboard shows fields the API allowlist excludes (because the UI has its own data path); CSRF allows a malicious site to trigger admin actions via the operator's session.

**Warning signs:**
- Web UI calls write endpoints that the API layer doesn't RBAC-gate.
- Dashboard data path bypasses the existing API field allowlist.
- No CSRF protection on state-changing endpoints.
- Operator role can perform admin actions through the UI that the API doesn't authorize.

**Prevention:**
- Web UI MUST go through the same Admin Console API; no separate data path. The API's field allowlist applies to the UI too.
- Every state-changing endpoint RBAC-gated (see Security pitfalls); the UI hides actions the role can't perform, but the API is the authority.
- CSRF tokens on all state-changing endpoints; SameSite cookies.
- Add a test: read-only operator token → assert write endpoints return 403; assert dashboard response excludes allowlisted fields.

**Phase to address:** Admin Web UI phase + RBAC phase — API-gated data path and RBAC before write actions ship.

### Pitfall: Lawyer Web chat — session hijacking, message ordering, offline sync conflicts, file upload malware

**What goes wrong:**
The lawyer-facing Web chat is a new channel alongside WeCom. Session hijacking: if the chat session token is predictable or stored in localStorage with XSS, an attacker hijacks the lawyer's session and sees client matters. Message ordering: async streaming + WeCom + Web chat running in parallel for the same lawyer can deliver messages out of order, producing incoherent legal advice. Offline sync conflicts: a lawyer composes offline, reconnects, and the sync overwrites a newer server-side state. File upload malware: a lawyer uploads a "document" that is malware (macro-laden doc, polyglot file); the platform stores and later serves it, or an admin opens it.

**Warning signs:**
- Session tokens are predictable, in URL params, or in localStorage with no XSS protection.
- No monotonic sequence number on messages; ordering depends on arrival time.
- Offline sync uses last-write-wins with no conflict detection.
- File uploads accepted with no type validation, no malware scan, stored with original filenames served back to users.

**Prevention:**
- Session tokens: high-entropy, httpOnly + Secure + SameSite cookies, short TTL, rotation on privilege change. No tokens in localStorage or URLs.
- Monotonic sequence numbers per conversation; the UI renders by sequence, not arrival order. Add a test for out-of-order delivery.
- Offline sync: conflict detection (version vector / timestamp); conflicts surface to the lawyer, not silent overwrite.
- File uploads: type validation (allowlist), malware scan (ClamAV or equivalent), stored with generated names not originals, served with `Content-Disposition: attachment` and no inline execution. Size limits.
- File contents subject to the same `raw_payload_ref` discipline — contract logs reference, not inline.

**Phase to address:** Lawyer Web chat phase — session security and upload safety before the chat is exposed to lawyers.

---

## Security Pitfalls

### Pitfall: RBAC — role explosion, permission granularity, default-deny vs default-allow

**What goes wrong:**
M3 introduces RBAC. Role explosion: a role is created per tenant per feature combination, leading to an unmanageable matrix where no one knows who can do what. Permission granularity mistakes: too coarse (one "admin" role that can do everything including promoting legal skills) or too fine (a permission per endpoint, unmaintainable). Default-allow: a new endpoint is added without a permission check, and the framework defaults to allow — any authenticated user can call it. Token leakage: RBAC decisions embedded in long-lived JWTs that leak scope after a role change.

**Warning signs:**
- Role count grows linearly with tenant count.
- A single "admin" role can both read dashboards and promote legal skills (no separation of duties).
- New endpoints have no `@requires_permission` decorator; the framework defaults to allow.
- JWTs with long TTLs carry permissions that aren't re-validated server-side after role changes.

**Prevention:**
- Fixed, small role set (e.g., `operator_read`, `operator_write`, `skill_reviewer`, `tenant_admin`, `platform_admin`) — not per-tenant roles. Tenancy is a separate axis from role.
- Permission granularity at the action level (e.g., `skill:promote`, `skill:write_candidate`, `feedback:read`), grouped into roles. Legal-skill promotion requires `skill_reviewer` — a separate role from `operator_write` (separation of duties for the human-review gate).
- Default-deny: every endpoint requires an explicit permission; the framework rejects unannotated endpoints in CI (a test that scans for endpoints without `@requires_permission`).
- Short-lived tokens; permissions re-validated server-side on every request against the current role, not the token's embedded scope. Role changes take effect immediately.
- Add a test: scan all endpoints → assert each has a permission annotation; assert default-deny for unauthenticated / under-privileged calls.

**Phase to address:** RBAC phase — role model and default-deny enforcement before any endpoint is exposed.

### Pitfall: Multi-tenant — cross-tenant data leakage, tenant config poisoning, noisy neighbor, migration complexity

**What goes wrong:**
Beyond the critical legal-data-leakage pitfall (above): tenant config poisoning — a tenant_admin can set config (model, routing policy, skill set) that affects another tenant, or a shared config is overwritten by one tenant. Noisy neighbor — one tenant's heavy run exhausts shared resources (event loop, provider rate limits, DB connections), degrading service for all other tenants. Migration complexity — existing V2 data is single-tenant; backfilling tenant_id is error-prone (null tenant_ids, default-tenant merging, forgotten tables).

**Warning signs:**
- Tenant config stored in a shared table without tenant_id scoping.
- No per-tenant resource quota (concurrent runs, rate limit, storage).
- Migration script backfills tenant_id on some tables but misses contract logs, feedback, memory, or artifacts.
- Shared provider API key used for all tenants — one tenant's burst exhausts the rate limit for everyone.

**Prevention:**
- Tenant config scoped by tenant_id; tenant_admin can only mutate their own tenant's config. Test: tenant A config change does not affect tenant B.
- Per-tenant resource quotas: max concurrent runs, max requests/min, max storage. Enforced at the gateway / runtime. Noisy neighbor is bounded by quota, not by contention.
- Migration: enumerate every table/store (contract logs, feedback, memory, artifacts, skills, sessions) and assert each has a non-null tenant_id after migration. Add a migration test.
- Per-tenant provider API keys where possible; shared keys have per-tenant rate-limit partitioning.
- Add a dedicated tenant-isolation gate with cross-tenant fixtures (a 20th gate or sub-gate).

**Phase to address:** Multi-tenant isolation phase — data-layer isolation and migration test before any tenant-scoped feature ships.

---

## Integration Pitfalls (How new features can break existing gates/contracts)

### Pitfall: M3 features pressuring the frozen BackendAdapter / ChannelAdapter Protocols

**What goes wrong:**
The `BackendAdapter` Protocol (9 methods, `protocols.py:222-239`) and `ChannelAdapter` Protocol (6 methods, `protocols.py:208-219`) are frozen. M3 features create pressure to change them: streaming wants a new event type or a `stream_intermediate_events` method; artifacts want a `get_artifact` method; multi-agent wants a `handoff` method; multi-provider wants capability fields added to `AdapterCapabilitySet`. Each change ripples back to the Hermes adapter, the `DefaultRunRuntime` (which calls all 9 methods), and the contract test suite — breaking the 19 V2 gates.

**Warning signs:**
- A PR modifies `protocols.py` Protocol signatures or method count.
- A PR adds fields to `AdapterCapabilitySet` or `ChannelCapabilitySet`.
- Hermes adapter tests break after a Codex/provider_model change.
- The `test_agent_adapter_contract.py` contract test fails because new backend-specific fields were added.

**Prevention:**
- Keep the Protocols frozen. New features work within the existing 9-method / 6-method surface: streaming uses `stream_events` + capability flags; artifacts use `collect_artifacts`; multi-agent uses `submit_run` with a multi-agent request shape; multi-provider uses `AdapterCapabilitySet` flags. No new Protocol methods.
- If a feature genuinely cannot fit, it goes through a contract-change proposal with explicit V2-gate impact analysis — not a silent PR.
- Add a contract test asserting Protocol method count and capability-set field count are unchanged from the V2 baseline (extend the existing count-assertion test from v1.6).

**Phase to address:** Every M3 phase that touches adapters — the contract-freeze guard test is added first, before any feature work.

### Pitfall: Feature flags not defaulting OFF, or live promotion bypassing the human gate

**What goes wrong:**
V2 invariant: all runtime lanes default OFF; live promotion is a human gate. M3 adds many new flags (streaming, artifacts, memory, multi-provider, MCP registry, model gateway, multi-agent, skill write, hybrid routing, Web UI, RBAC, multi-tenant). A flag defaults to ON by mistake, or a flag is promoted to live without the human gate, and a half-tested feature hits real lawyers. This is the single most common way M-features break a stable V2.

**Warning signs:**
- A new flag's default is `True` in config or code.
- No human-gate evidence record before a flag is promoted in a live environment.
- Flags are coupled — enabling one implicitly enables another.
- Flag checks are missing on some code paths (the feature runs even when the flag is off).

**Prevention:**
- Every M3 flag defaults to `False` in code and in every environment config. Add a test asserting all M3 flags default to False (extend the v1.6 flag-default test).
- Flag promotion requires a human-gate evidence record (`promoted_by`, `promoted_at`, `evidence_ref`). No automated promotion.
- Flags are independent; enabling one does not enable another. Test: enable flag A, assert flag B is still off.
- Every feature code path checks its flag; add a test that asserts the feature is inert when the flag is off (no events emitted, no runs changed, no UI rendered).

**Phase to address:** Every M3 phase — flag-default test added alongside each feature flag.

### Pitfall: M3 features breaking the 19 V2 gates (969 tests) via contract event drift

**What goes wrong:**
The 19 V2 gates include contract event schema validation, fixture replay, relationship checks, and the gate-coverage meta-test. M3 features that emit new event types, change event fields, or add new packages/services can break these gates: a new event type isn't covered by the gate-coverage meta-test; a streaming event has a field that fails schema validation; a multi-agent run produces an `ExecutionTrace` relationship that the relationship-check test doesn't expect; a new package under `packages/*/src` isn't covered by any gate (the meta-test fails).

**Warning signs:**
- A new `packages/*/src` or `services/*/src` directory is added without a corresponding gate.
- A new event type or field fails the contract schema validation gate.
- The gate-coverage meta-test (`packages/contract-test-suite/tests/test_gate_coverage.py`) fails.
- V2 gate test count drops below 969 (regression).

**Prevention:**
- Every new package/service directory gets a gate before merge (enforced by the gate-coverage meta-test).
- New event types/fields go through schema validation + fixture replay tests before being emitted.
- Run the full 19-gate suite on every M3 PR; the test count must not drop below 969 and all gates must stay green. Add this as a CI requirement.
- Any M3 feature that needs to change an existing event schema goes through a contract-change proposal, not a silent field addition.

**Phase to address:** Every M3 phase — gate coverage and contract validation checked per PR.

### Pitfall: V2 human gates (Phase 5 + Phase 8) disrupted by M3 runtime changes

**What goes wrong:**
Phase 5 (live WeCom UAT) and Phase 8 (five-workday lawyer trial) are open human gates running in parallel with M3. M3 runtime changes (streaming, multi-provider, multi-agent, routing) alter the live behavior the human gates are evaluating. A lawyer in the Phase 8 trial hits a streaming partial-failure that delivers a half-answer followed by a raw error — the trial evidence is contaminated. A routing change sends a trial lawyer's query to a different backend, producing a different answer quality than the trial baseline.

**Warning signs:**
- M3 flags are enabled in the environment where Phase 5 / Phase 8 is running.
- Trial evidence (feedback, conversations) is collected from a run that used an M3 feature, mixing it with V2-baseline evidence.
- No environment separation between M3-feature-on and V2-baseline for the human gates.

**Prevention:**
- M3 features are OFF in the Phase 5 / Phase 8 environment. The human gates run against the V2 baseline. M3 features are validated in a separate environment.
- Trial evidence tagged with the runtime config (flags on/off, backend, router mode) so M3-influenced evidence is not mixed with V2-baseline evidence.
- Any M3 feature that must be validated by lawyers goes through its own human gate, not by contaminating Phase 5 / Phase 8.

**Phase to address:** Every M3 phase that touches runtime behavior — environment separation maintained throughout M3.

---

## Regression Risks

| M3 Feature | Existing functionality at risk | Regression risk | Mitigation |
|---|---|---|---|
| Streaming events | WeCom delivery loop (`LOOP-01`), output boundary (`OUTPUT-01`), run state machine | Partial delivery + raw error to lawyer; runs stuck non-terminal | Terminal-event contract; boundary at emission point; cancellation propagation |
| Artifact return | Contract log privacy (`raw_payload_ref`), output boundary | Full-text leak in artifacts; backend noise in artifact metadata | Ref-only in contract events; field allowlist on artifact metadata |
| Session memory (Hindsight) | Privacy discipline, feedback normalization (`FEEDBACK-01`) | Memory poisoning persists across sessions; full-text in memory store; cross-session leakage | Per-session/per-tenant memory isolation; ref-only entries; poison-detection test |
| Multi-provider (Anthropic, Ollama) | Hermes-primary invariant, output boundary, cost | Fallback loops; capability mismatch mid-run; API key in logs; cost explosion | Per-provider policy; capability negotiation; cost ceiling; key-exclusion test |
| MCP Connector Registry | Output boundary, contract neutrality | Malicious tool exfiltrates client data; tool result leaks backend noise to LLM context | Admission review; sandboxed execution; tool-result allowlist |
| Model Provider Gateway | Hermes-primary invariant, routing (`RouteDecision`) | Cascading failure; fallback loop; cost explosion; model selection gaming | Circuit breaker; tried-provider tracking; per-tenant cost ceiling; gateway-policy-controlled selection |
| Multi-Agent Runtime | Run state machine, `ExecutionTrace` relationships, cost | Deadlock; infinite handoff; shared-state corruption; unbounded parallelism | `max_handoffs`/`max_depth`; cycle detection; copy-on-write state; bounded parallelism |
| Skill Registry write | Legal-safety human-review gate, `skill_candidate` invariant | Auto-promotion of legal skills; review bypass; skill injection; version conflict | Human-review gate on every write path; versioned immutable skills; descriptor validation |
| Hybrid routing | Router service (`M2-03`), Hermes-primary, legal safety | High-risk legal routed to cheap model; router hallucination; routing loop; cold-start bias | Legal-risk override; route validation; loop breaker; safe cold-start default |
| Admin Web UI | Admin Console API allowlist, output boundary | XSS via chat content; privilege escalation; CSRF; dashboard data exposure | DOMPurify; API-gated data path; RBAC on every endpoint; CSRF tokens |
| Lawyer Web chat | WeCom loop, privacy, output boundary | Session hijacking; out-of-order messages; file upload malware; offline sync conflict | httpOnly tokens; monotonic sequence; malware scan; conflict detection |
| RBAC | Admin Console API auth, legal-skill promotion gate | Role explosion; default-allow on new endpoints; token leakage after role change | Fixed role set; default-deny with CI scan; short-lived tokens re-validated server-side |
| Multi-tenant | All V2 data (contract logs, feedback, memory, skills, sessions) | Cross-tenant legal data leakage; tenant config poisoning; noisy neighbor; migration errors | Data-layer tenant isolation; per-tenant quotas; migration test; dedicated isolation gate |
