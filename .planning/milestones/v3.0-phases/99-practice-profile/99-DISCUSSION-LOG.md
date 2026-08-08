# Phase 99 Discussion Log — Practice Profile

**Phase:** 99 — Practice Profile
**Mode:** auto
**Created:** 2026-08-11
**Requirements:** PROF-01, PROF-02, PROF-03

---

## Gray Area Analysis

### GA-01: Practice profile data model

**Question:** How to model the practice profile data — structured JSON or prose text?

**Options:**
1. Structured JSON with plugin-specific sections, stored per tenant
2. Prose text (markdown) stored per tenant, parsed at runtime
3. Hybrid: structured JSON with a prose fallback field

**Selected:** Option 1 — Structured JSON with plugin-specific sections

**Rationale:** The original CLAUDE.md files are prose templates, but platform-side multi-tenant storage requires programmatic readability, partial updates, and per-tenant isolation. A structured JSON model with a common header (`identity`, `role`, `integrations`) plus `plugin_configs: dict[str, JsonObject]` accommodates all 13 plugin schemas without hardcoding any single plugin's structure. Each plugin's config is a flexible JsonObject — the cold-start interview writes structured answers, and the injector renders them as context text at execution time.

---

### GA-02: Tenant storage mechanism

**Question:** Where to store practice profiles — database, JSON files, or in-memory?

**Options:**
1. In-memory PracticeProfileStore (Protocol-based, following SessionStore pattern)
2. SQLite database (new dependency)
3. JSON files on disk per tenant

**Selected:** Option 1 — In-memory PracticeProfileStore

**Rationale:** The platform is single-firm scale (≤50 lawyers, AGENTS.md decision 9). All existing tenant-scoped data (sessions, runs, elicitation submissions) uses in-memory storage with Protocol-based interfaces. A `PracticeProfileStore` Protocol with `InMemoryPracticeProfileStore` implementation follows the same pattern. No new runtime dependency is introduced (AGENTS.md coding rule). The Protocol allows future swap to DB/Redis without changing call sites.

---

### GA-03: Package placement

**Question:** Should practice profile logic go in an existing package or a new one?

**Options:**
1. New package `packages/practice-profile`
2. Add to `packages/skill-materializer` (it already handles body injection)
3. Add to `packages/platform-runtime` (it's the runtime composition root)
4. Add to `services/gateway` (it handles tenant-scoped data)

**Selected:** Option 1 — New package `packages/practice-profile`

**Rationale:** Practice profile is a distinct concern from skill indexing, materialization, routing, and platform contracts. It needs its own data model, store, injection logic, and interview orchestration. A new package follows the existing pattern (each concern gets its own package with its own gate). Dependencies: `platform-contract` (elicitation types), `rbac` (Role checks), `skill-index` (querying `practice_profile_dependency`).

---

### GA-04: Context injection mechanism

**Question:** How to inject practice profile into skill context at execution time?

**Options:**
1. PracticeProfileInjector renders profile as context section prepended to skill body
2. Modify body_injector to accept profile data as an extra parameter
3. Inject profile as a separate system message in the agent core

**Selected:** Option 1 — PracticeProfileInjector renders profile as context section prepended to skill body

**Rationale:** The body_injector (Phase 97) handles skill body text injection with budget trimming — it should not be modified (separation of concerns). The PracticeProfileInjector is a separate component that: (a) checks if the skill has `practice_profile_dependency`, (b) fetches the tenant's profile from the store, (c) renders it as a `## 执业配置` context section, (d) prepends it to the skill body. The combined text is then passed to the body_injector for budget trimming. The injector returns metadata (`profile_injected`, `temporary_mode`, `plugin`) for observability.

---

### GA-05: Temporary mode implementation

**Question:** How to implement 临时模式 with [临时模式] tagging?

**Options:**
1. Generate default profile from schema defaults, tag all outputs with [临时模式] prefix in context
2. Return a special "temporary" flag and let the agent core handle tagging
3. Store a temporary profile in the store with a flag

**Selected:** Option 1 — Generate default profile with [临时模式] tag in injected context

**Rationale:** The practice-profile-schema.md already defines temporary mode defaults (平衡型 risk, 律师 role, 中国大陆法律 jurisdiction, etc.). When `PracticeProfileStore.get(tenant_id, plugin)` returns None, the injector generates a `PracticeProfile` from these defaults with `temporary_mode=True`. The injected context section includes `[临时模式 — 配置你的档案以获得定制输出]` as a header tag. For Phase 99, tests assert that: (a) the injector always produces a profile (real or temporary), (b) temporary profiles have `temporary_mode=True`, (c) the `[临时模式]` tag is present in the injected context. User-visible output tagging is enforced by the agent core (Phase 100+), but the contract is established here.

---

### GA-06: Cold-start interview implementation

**Question:** How to implement multi-round 2-4 question cold-start interview?

**Options:**
1. ColdStartInterviewOrchestrator emits elicitation.requested events in sequence, writes answers to store
2. Single large elicitation event with all questions at once
3. Use a separate interview API outside the event system

**Selected:** Option 1 — ColdStartInterviewOrchestrator with sequential elicitation.requested events

**Rationale:** The elicitation contract enforces 2-4 questions per event (`validate_question_count`). The cold-start-interview SKILL.md defines 5 steps, each with multiple questions. Each step maps to one `elicitation.requested` event. The orchestrator: (a) emits the first elicitation event, (b) on answer submission via `POST /v1/runs/{id}/elicitation`, writes answers to the profile store, (c) emits the next event, (d) repeats until complete. This reuses the existing elicitation infrastructure (Phase 88 contract + Phase 91 Gateway handler) without new event types. The interview is plugin-aware — it uses the plugin's interview definition to determine questions.

---

### GA-07: RBAC authorization for practice profiles

**Question:** How to enforce read/write permissions on practice profiles?

**Options:**
1. Write requires ADMIN or OPERATOR; read allowed for all authenticated roles; cross-tenant denied
2. Write requires ADMIN only; read requires LAWYER or above
3. All roles can read and write (self-managed profiles)

**Selected:** Option 1 — Write: ADMIN/OPERATOR; Read: all authenticated; Cross-tenant: denied

**Rationale:** Practice profiles contain firm-level configuration (escalation matrices, liability positions) that should be controlled by admins/operators. All authenticated users within a tenant can read their firm's profile (needed for skill execution context). The Gateway's existing `require_role()` and `check_tenant()` methods enforce this. This aligns with the existing ADM-01 pattern (admin/operator config writes, lawyer/viewer denied mutate).

---

### GA-08: No secrets in practice profiles

**Question:** How to enforce that practice profiles contain no secrets?

**Options:**
1. Validate on write — reject fields matching secret patterns
2. Trust the admin to not put secrets in profiles
3. Encrypt sensitive fields at rest

**Selected:** Option 1 — Validate on write, reject secret patterns

**Rationale:** Practice profiles are business configuration — they should never contain secrets. The `PracticeProfileStore.update()` method validates incoming data against secret-detection patterns (API keys, tokens, passwords, AES keys, private key headers). If any field value matches, the write is rejected with a 400 error. This is a fail-closed approach consistent with AGENTS.md safety rules ("Never commit secrets, tokens, runtime databases, logs").

---

### GA-09: No practice profiles in contract event log

**Question:** How to ensure practice profiles don't enter the contract event log?

**Options:**
1. Runtime-only context; no RunEvent emitted for profile injection; data stays in PracticeProfileStore
2. Emit a redacted RunEvent with only metadata (no profile content)
3. Emit a full RunEvent but scrub profile content before persistence

**Selected:** Option 1 — Runtime-only context, no RunEvent for injection

**Rationale:** Contract events (RunEvent) are the persisted audit trail. Practice profiles are runtime execution context — injected into the skill context but never serialized into events. The `PracticeProfileInjector.inject()` returns a context string passed to the agent, but no `RunEvent` is created. Profile data remains in `PracticeProfileStore` (in-memory). Injector metadata (`profile_injected`, `temporary_mode`, `plugin`) can be included in run metadata (not event payloads) if observability is needed. This follows the reference-first principle — profile content is not persisted in the event stream.

---

### GA-10: API design for practice profile CRUD + interview

**Question:** What's the API for reading/writing practice profiles?

**Options:**
1. Three Gateway endpoints: GET, PUT, POST interview
2. RESTful CRUD: GET/POST/PUT/DELETE on `/v1/practice-profile`
3. Add practice profile fields to the existing sessions/runs API

**Selected:** Option 1 — Three Gateway endpoints

**Rationale:** Following the existing Gateway pattern (`/v1/sessions`, `/v1/runs`, `/v1/skills`), practice profiles get three endpoints:
- `GET /v1/practice-profile` — returns tenant's profile (all plugins or `?plugin=commercial-legal`)
- `PUT /v1/practice-profile` — updates tenant's profile (full or partial via `plugin` parameter)
- `POST /v1/practice-profile/interview` — starts cold-start interview run, returns `run_id` for SSE elicitation consumption

All endpoints use `require_auth()` + `check_tenant()`. Write endpoints use `require_role((Role.ADMIN, Role.OPERATOR))`. The interview endpoint creates a run that emits `elicitation.requested` events consumable via SSE at `/v1/runs/{id}/events`.

---

### GA-11: Coverage of all practice_profile_dependency skills

**Question:** How to cover all ~50 skills with practice_profile_dependency?

**Options:**
1. Query skill-index.json at startup to build a set of skill_ids with practice_profile_dependency=True
2. Hardcode the list of skill_ids that need profile injection
3. Always inject profile for every skill (let the skill ignore it if not needed)

**Selected:** Option 1 — Query skill-index.json at startup

**Rationale:** The skill index (Phase 96) already records `practice_profile_dependency: bool` per skill. The `PracticeProfileInjector` loads the index at initialization and builds a `set[str]` of dependent skill_ids. At injection time, it checks if the target skill_id is in this set — if yes, injects the profile; if no, skips. This ensures all ~50 dependent skills are covered without hardcoding. A test asserts that the set matches the index's `practice_profile_dependency=True` count.

---

## Summary

| # | Gray Area | Selected Option |
|---|-----------|----------------|
| GA-01 | Practice profile data model | Structured JSON with plugin-specific sections |
| GA-02 | Tenant storage mechanism | In-memory PracticeProfileStore (Protocol-based) |
| GA-03 | Package placement | New package `packages/practice-profile` |
| GA-04 | Context injection mechanism | PracticeProfileInjector prepends profile as context section |
| GA-05 | Temporary mode implementation | Generate default profile with [临时模式] tag |
| GA-06 | Cold-start interview | ColdStartInterviewOrchestrator with sequential elicitation events |
| GA-07 | RBAC authorization | Write: ADMIN/OPERATOR; Read: all; Cross-tenant: denied |
| GA-08 | No secrets in profiles | Validate on write, reject secret patterns |
| GA-09 | No profiles in event log | Runtime-only context, no RunEvent for injection |
| GA-10 | API design | Three Gateway endpoints: GET, PUT, POST interview |
| GA-11 | Coverage of dependent skills | Query skill-index.json at startup for skill_id set |

**Total gray areas:** 11
**Auto-selected:** 11/11
