# InkStatute Agent Platform — North Star Architecture

> Status: target architecture (北极星). This is the long-term design the platform converges toward. It is intentionally backend-, channel-, and industry-neutral. The lawyer assistant is the first *solution*, Hermes is the first *backend*, WeCom is the first *channel*.
>
> Authority note: this document supersedes the V2 PRD's platform-shape assumptions for the new "Platform Foundation" milestone. V2 PRD remains the source of truth only for the existing lawyer-bot behavior that must not regress. The new milestone is a deliberate refactor, not an additive patch on V2's `services/` layout.
>
> Decisions in this document were made by the agent under explicit user delegation (2026-06-29) after the user asked for a complete refactor toward a reusable agent platform.

---

## 0. Plain-language primer (read this first)

Some terms in this doc are precise but simple. In one breath:

- **Interface / Contract**: an agreed list of operations (with inputs and outputs) that a component promises to provide, **without saying how it does them**. Like the spec of a wall power socket: any device with the right plug works, regardless of the appliance inside.
- **Python `Protocol`**: Python's way to *write down* such a contract as a class that lists method names and their input/output types but contains no real code. Any class that happens to have those methods automatically "satisfies" the Protocol. This is the mechanism that makes backends and channels **swappable** — we code against the Protocol, not against Hermes specifically.
- **JSON Schema**: a language-neutral file that describes the *shape of data* (which fields exist, types, required-ness). It is how Python, TypeScript, Rust, etc. all agree on the same data without sharing code.
- **The 4 interfaces** (the heart of the platform). Think of an assembly line:
  1. **ChannelAdapter** — "how a chat tool plugs in" (receive a user message, send a reply). e.g. WeCom, QQBot, a Web API.
  2. **BackendAdapter** — "how an agent brain plugs in" (start a run, stream results, cancel, approve). e.g. Hermes today; Codex/Claude Code/OpenCode/self-built later.
  3. **SolutionLoader** — "how a product/industry pack plugs in" (load a persona + skills + tools). e.g. the lawyer pack; an IT-ops pack later.
  4. **RunRuntime** — "the conductor" that wires a channel → a backend → running a solution, and can be embedded as a plain library inside a server, a desktop app, etc.

If you remember only one sentence: **the platform is four plugs (channel, backend, solution, runtime) defined by neutral contracts; everything specific (WeCom, Hermes, lawyer) is just the first thing plugged into each.**

---

## 1. Why a refactor (and what we keep)

The current lawyer assistant is, in fact, a **Hermes profile** at `~/.hermes/profiles/lawfirm/` (persona `SOUL.md`, ~96 legal skills, 2 MCP servers, 4 hooks, glm-5.2 model, WeCom+QQBot channels). Hermes itself already has plugin channels, provider adapters, and "profiles" that behave like solution packages. So the platform shape the user wants partly *exists inside Hermes* — but it is owned by Hermes, shaped by Hermes conventions (SKILL.md, hooks, gateway), and not reusable as an InkStatute-owned product.

The refactor goal is to make **InkStatute own the platform seams** so that:
- channels, backends, and solutions are all swappable through InkStatute contracts;
- the lawyer pack can later run on a non-Hermes backend (including a self-built agent);
- the same core can ship an IT-ops bot, etc., without rewriting agent plumbing;
- clients (Web/desktop/mobile) are all just consumers of one platform API.

**We keep** (do not rebuild this milestone): Hermes core (router/skills/MCP/model loop), the working lawyer WeCom bot, and the V2 contract definitions that already proved useful. The refactor is a *strangler-fig*: build the new core beside the running bot, reach parity behind flags, then retire the old path.

---

## 2. Tech stack decision (final)

| Layer | Language | Rationale |
|-------|----------|-----------|
| **Cross-language contracts** | **JSON Schema** (+ generated Python & TS types) | Already the neutral format; lets Python core and TS clients agree without shared code. |
| **Platform core**: RunRuntime, ChannelAdapters, BackendAdapters, SolutionLoader, platform API server | **Python 3.11+ (async)** | Fastest to build; richest agent/MCP/LLM ecosystem; the first backend (Hermes) and the lawyer solution are Python/Hermes-flavored, so the Hermes adapter is most natural; reuses proven V2 contract patterns. Orchestration is I/O-bound, so raw-speed languages buy little here. |
| **Client SDK + embeddable chat UI component** | **TypeScript** | Every client (Web SPA, Tauri webview, Electron, Flutter webview) is web/TS. One SDK + one chat component serves all of them. Generated from the OpenAPI/JSON Schema. |
| **Desktop shells** (future) | Tauri (Rust) or Electron (TS) hosting the TS component | Out of scope this milestone; the contract just must not block it. |
| **Mobile** (future) | Flutter thin client | Out of scope this milestone. |
| **Local embedded runtime** (north-star) | Python sidecar first; thin Rust/Go wrapper only if needed | Deferred. Embeddability is preserved by keeping RunRuntime an injectable library, not by rewriting in Rust now. |

**Why not a TypeScript core?** It would unify with clients and with Claude Code/OpenCode, but it would rewrite the proven Python contract/test work and mismatch the first backend (Hermes) and the lawyer solution, slowing "enter dev ASAP." TS earns its place at the client edge, not the orchestration core.

**Why not Rust/Go core?** Justified only if the *local embedded runtime* were a this-milestone requirement. It is explicitly deferred ("default remote + reserve embeddable"). Rust/Go would slow delivery and add little to an I/O-bound orchestrator whose latency is dominated by the LLM backends.

**Embeddability is a design rule, not a language choice:** RunRuntime is a dependency-injected Python library with a thin transport shell. A server, a Tauri sidecar, or an Electron child process are all just hosts of that same library.

---

## 3. Layered architecture (target)

```
 Clients      Web SPA · Tauri · Electron · Flutter        (all consume one Platform API)
   │          Platform API  =  HTTP (control) + SSE/WebSocket (streaming)   — transport-agnostic
   ▼
 Channel layer    ChannelAdapter:  WeCom · QQBot · WebAPI · Webhook · SSE …
   │              protocol  ⇄  ChannelMessage / ChannelDelivery     (never calls a backend directly)
   ▼
 Platform runtime    RunRuntime:  run lifecycle · session · output boundary · audit · feature flags
   │                 speaks the BackendAdapter Protocol             (embeddable library, not a server)
   ▼
 Backend layer    BackendAdapter:  Hermes(first) · Codex · ClaudeCode · OpenCode · self-built(north-star)
   │              executes agent logic with a Solution loaded
   ▼
 Solution layer   Solution:  lawyer(first) · it-ops · …            backend-portable: persona+skills+MCP+policy+config
```

**Cross-cutting:** `packages/platform-contract` (the data contracts); identity (`Tenant`/`Workspace`/`BotInstance`); storage & audit (contract logs / read views / runtime audit); privacy & assistant-output-boundary.

**Four invariants that make the decoupling real:**
- **N1 — channel/runtime separable**: a desktop app can embed RunRuntime with **zero** channels (it talks to the runtime API directly).
- **N2 — backend swappable**: a new backend = one BackendAdapter implementation; runtime/channels/solutions untouched.
- **N3 — solution backend-portable**: a solution is described neutrally and **materialized per backend**; Hermes profile is just one materialization target.
- **N4 — runtime embeddable**: RunRuntime depends only on injected ports; servers/sidecars are thin hosts.

---

## 4. The four interface contracts

Defined at **Python `Protocol` signatures + JSON Schema draft** depth, because the autonomous build implements directly against them. Names are stable; signatures may be refined during Phase 09/10 as long as the invariants hold.

### 4.1 ChannelAdapter (通道)

```python
from typing import Protocol, AsyncIterator

class ChannelAdapter(Protocol):
    def channel_id(self) -> str: ...
    def capabilities(self) -> "ChannelCapabilitySet": ...
    # inbound
    async def verify_and_ack(self, raw: "RawInbound") -> "AckResponse": ...
    async def normalize_inbound(self, raw: "RawInbound") -> "InboundNormalized": ...
        # InboundNormalized = ChannelMessage (+ optional AgentTurn | FeedbackEvent)
    # outbound
    async def deliver(self, delivery: "ChannelDelivery") -> "DeliveryResult": ...
    async def health(self) -> "ComponentHealth": ...
```

- `ChannelCapabilitySet`: `supports_text/files/cards/images/voice`, `supports_streaming`, `ack_deadline_ms`, `idempotency_strategy`.
- **Rule (N1)**: a ChannelAdapter **must not import or call any BackendAdapter**. It submits inbound to RunRuntime and receives `ChannelDelivery` to send. This is enforced by a boundary scan.
- WeCom is owned by InkStatute (the existing live-bridge primitives are wrapped behind this Protocol). Hermes gateway is never the ordinary-user channel.

### 4.2 BackendAdapter (后端 / agent — the most important)

```python
class BackendAdapter(Protocol):
    def backend_id(self) -> str: ...
    def capabilities(self) -> "AdapterCapabilitySet": ...        # extends the EXISTING dataclass
    async def bootstrap_check(self) -> "BootstrapStatus": ...
    async def submit_run(self, req: "RunRequest") -> "RunHandle": ...
    async def get_run(self, run_id: str) -> "Run": ...           # Run.status uses AsyncTaskState
    async def stream_events(self, run_id: str) -> AsyncIterator["RunEvent"]: ...
    async def cancel_run(self, run_id: str) -> "Run": ...
    async def submit_approval(self, run_id: str, approval: "Approval") -> "Run": ...
    async def collect_artifacts(self, run_id: str) -> list["ArtifactRecord"]: ...
```

- `RunRequest` carries: `AgentTurn`, a **`SolutionBinding`** (which solution + config), `session_id`/`tenant_id`/`workspace_id`/`bot_instance_id`, and `OutputConstraints`.
- **Rule (N2/N3)**: the adapter receives a *neutral* solution reference and is responsible for **materializing** it into backend-native form. Hermes adapter → resolve/sync a Hermes profile; a future self-built adapter → load into its own engine. The runtime never sees backend-native solution details.
- **Capabilities** *extend* the existing `AdapterCapabilitySet` (`packages/platform-contract/src/platform_contract/agent_adapter.py`): add `run_invocation_modes`, `stream_event_support`, `cancel_support`, `approval_support`, `live_update_support`, `parallel_task_support`, `session_memory_support`. Existing fields stay valid; `validate_agent_backend_manifest()` stays backward-compatible.
- **Safety invariant**: `Approval` is for tool/run approval only. It must never auto-approve a high-risk legal conclusion; `skill_candidate.requires_human_review` stays true.

### 4.3 SolutionLoader + neutral solution format (后端可移植)

```python
class SolutionLoader(Protocol):
    def validate(self, manifest: "SolutionPackageManifest") -> list["Issue"]: ...
    def load(self, manifest: "SolutionPackageManifest") -> "Solution": ...
    def materialize_for(self, solution: "Solution", backend_id: str) -> "BackendSolutionBundle": ...
        # no external side effects beyond a declared output dir
```

A **neutral solution** = manifest + resources, none of it Hermes-runtime-shaped at the contract level:
- `persona_ref` → system prompt / SOUL text
- `skills[]` → **neutral skill descriptors**: `name`, `description`, `intent/routing_hints`, `required_tools/mcp`, `risk_level` — *what* the skill is, not Hermes SKILL.md runtime
- `mcp[]` → MCP server refs + config templates (secret names only)
- `output_policy` overlay (assistant-output-boundary rules for this product)
- `eval` / contract fixtures
- `default_adapter_config` (e.g., model hints) and `secret_templates` (names only)
- `industry_context` defaults (where legal-specific data lives)

**Portability mechanism = "describe neutrally, materialize per backend."** Honest scope note: the lawyer pack's ~96 skills are currently Hermes `SKILL.md` files. The *contract* is neutral now; the *content* migrates over time. The first materialization target is the Hermes profile, so the lawyer bot keeps working unchanged while the neutral wrapper is proven.

### 4.4 RunRuntime (可嵌入运行时)

```python
class RunRuntime:
    def __init__(self,
                 backend: BackendAdapter,
                 solution_loader: SolutionLoader,
                 channels: list[ChannelAdapter] = (),     # may be empty (embedded mode)
                 storage: "ContractLogStore" = ...,
                 output_boundary: "OutputBoundary" = ...,
                 secret_resolver: "SecretResolver" = ...,
                 feature_flags: "FeatureFlags" = ...): ...
    async def create_run(self, req: "RunRequest") -> "Run": ...
    async def poll(self, run_id: str) -> "Run": ...
    async def stream(self, run_id: str) -> AsyncIterator["RunEvent"]: ...   # already through output_boundary
    async def cancel(self, run_id: str) -> "Run": ...
    async def approve(self, run_id: str, approval: "Approval") -> "Run": ...
```

- **Rule (N4)**: depends only on injected ports (backend, loader, channels, storage, boundary, secrets, flags). No hard dependency on a network server or any specific channel.
- **Output boundary wraps every event/delta path** before it leaves the runtime, so streamed tool/approval/gateway/meta events can never reach ordinary users.
- A FastAPI/aiohttp server, a Tauri sidecar, and an Electron child process are all just thin hosts that construct a `RunRuntime` and expose `create_run/poll/stream/cancel/approve`.

---

## 5. Data contracts (`packages/platform-contract`, additive)

Keep: `AgentTurn`, `AgentResult`, `FeedbackEvent`, `ExecutionTrace`, `RouteDecision`, `AgentBackendManifest`, `AdapterCapabilitySet`.

Add (JSON Schema + Python bindings; TS generated):
`ChannelMessage`, `ChannelDelivery`, `Run`, `RunEvent`, `RunStep`, `ToolCall`, `Approval`, `ArtifactRecord`, `Session`, `Tenant`, `Workspace`, `SolutionPackageManifest` (+ neutral skill/mcp descriptors), `BotInstance`, `ChannelBinding`.

Rules: `Run.status` = existing `AsyncTaskState`; `ArtifactRecord` is a top-level ref distinct from nested `AgentResult.artifacts`; `ChannelBinding`/secrets are `secret_ref` only; legal-only fields live in `industry_context`; relationship replay must prove `ChannelMessage → AgentTurn → Run → RunEvent/RunStep → AgentResult/ArtifactRecord → ChannelDelivery → FeedbackEvent`.

---

## 6. Client embedding architecture (default remote, reserve embeddable)

- **Now**: all clients are thin and speak the Platform API (HTTP + SSE/WebSocket). Build **one embeddable Web chat component** (renders `RunEvent` streaming, citations, file cards) + **one TS client SDK**. Tauri/Electron load the component directly; Flutter loads it via `webview_flutter` first, native later.
- **Reserved (not built now)**: because of N4, a desktop app can later embed the Python RunRuntime as a **Tauri sidecar** / **Electron child process** for offline / local-file / intranet / "documents never leave the device" cases — **without changing the API**. Mobile stays a thin client.
- **This milestone only guarantees**: the API is transport-agnostic, channels are separable from runtime, and the runtime is injectable. No local runtime is implemented.

---

## 7. How Hermes maps onto the north star (proof it hosts today's reality)

| North-star seam | Hermes reality | This-milestone behavior |
|-----------------|----------------|-------------------------|
| ChannelAdapter | InkStatute owns WeCom via the live bridge; Hermes gateway not used for ordinary users | Wrap existing WeCom primitives behind `ChannelAdapter`; no live change by default |
| BackendAdapter | `/v1/runs`+`/events`+`/approval`+`/stop` exist (`~/.hermes/.../api_server.py:4340-4377`), plus subprocess one-shot (proven) | Default one-shot; `/v1/runs` allowed only after a **lawfirm-equivalence parity spike** |
| SolutionLoader | `~/.hermes/profiles/lawfirm/` is a de-facto solution package | Neutral manifest references the profile; Hermes adapter materializes to a profile |
| RunRuntime | live bridge currently inlines orchestration | Extract into an embeddable `RunRuntime`; default-OFF behind flags |

**Unproven and treated as a spike, not a fact:** whether Hermes `/v1/runs` executes the lawfirm profile (router/skills/gates/MCP/output) identically to the one-shot path. Until proven, one-shot stays default.

---

## 8. North-star scope explicitly deferred (not this milestone)

- Self-built agent runtime (LLM loop + tool execution owned by InkStatute) — future BackendAdapter implementation.
- Productized Codex / Claude Code / OpenCode / direct provider-model backends.
- Desktop local embedded runtime; native mobile UI.
- Full security platform (encryption, multi-tenant isolation, RBAC, WORM, key rotation).
- Automatic legal-skill synthesis.

These are reachable *without re-architecture* because the four contracts above are designed to host them.

---

*North Star authored 2026-06-29 under user delegation. Companion execution plan: `agent-platformization-plan-v5.md`.*
