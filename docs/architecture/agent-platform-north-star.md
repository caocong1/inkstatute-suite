# InkStatute Agent Platform North Star Architecture

> Status: promoted architecture authority for milestone v1.1, Phase 09-13.
> Phase 09 promotes this document from `.planning/drafts/agent-platform-north-star.md`
> into `docs/architecture/` so implementation can reference a stable
> architecture document. `docs/requirements/V2-PRD.md` remains the source for
> non-regression of the existing lawyer-bot behavior; it is not a replacement for
> this North Star architecture.

This is the target architecture for the reusable InkStatute agent platform. It is
backend-neutral, channel-neutral, and industry-neutral. The lawyer assistant is
the first solution, Hermes is the first backend, and WeCom is the first channel.
None of those define platform core.

## Primer

The platform is defined by four stable interface contracts:

- `ChannelAdapter`: how a communication channel plugs in and turns raw inbound
  channel events into neutral messages, then delivers neutral outbound messages.
- `BackendAdapter`: how an agent backend plugs in and runs agent work for a
  solution.
- `SolutionLoader`: how a product or industry solution package is validated,
  loaded, and materialized for a selected backend.
- `RunRuntime`: the embeddable conductor that wires channels, solutions,
  backends, storage, output policy, secrets, and feature flags together.

The practical rule is simple: platform code depends on neutral contracts. WeCom,
Hermes, and the lawyer solution are implementations or examples that plug into
those contracts.

## Why This Refactor Exists

The current lawyer assistant already works through a Hermes `lawfirm` profile:
persona, skills, MCP tools, hooks, model configuration, and channel integrations
are all present in that runtime. That proves product value, but it also means the
channel, backend, solution, and runtime boundaries currently live inside Hermes
conventions.

Milestone v1.1 extracts InkStatute-owned platform boundaries beside the running
lawyer bot. The refactor is a strangler-fig path:

- keep the existing lawyer bot running;
- define InkStatute-owned contracts around the platform seams;
- add new runtime lanes behind default-off flags;
- prove parity with fixtures and human gates before live promotion.

This milestone does not rebuild Hermes core, session storage, router, skill
registry, MCP registry, or model gateway. Hermes lawfirm remains the first
backend and first solution materialization target.

## Tech Stack

| Layer | Choice | Rationale |
| --- | --- | --- |
| Cross-language contracts | JSON Schema plus Python bindings first | Existing V2 contract work already uses this pattern, and JSON Schema keeps Python core and TypeScript clients aligned. |
| Platform core | Python 3.11+ async | The first backend and solution are Python/Hermes-shaped, orchestration is I/O-bound, and Python has the richest agent integration surface. |
| Client SDK and embeddable chat UI | TypeScript | Web, Tauri, Electron, Flutter webview, and other clients can share one generated SDK and one chat component. |
| Local embedded runtime | Deferred Python sidecar or thin wrapper | The runtime is designed to be embeddable through dependency injection, but no local runtime is implemented in this milestone. |

Rust or Go are deferred until a local embedded runtime becomes an active
requirement. TypeScript belongs at the client edge for this milestone, not in the
core orchestration runtime.

## Layered Architecture

```text
Clients
  Web SPA, Tauri, Electron, Flutter
  Platform API: HTTP control plus SSE/WebSocket streaming

Channel layer
  ChannelAdapter: WeCom, QQBot, Web API, webhook, SSE
  Data: ChannelMessage, ChannelDelivery

Platform runtime
  RunRuntime: lifecycle, session, output boundary, audit, feature flags
  Calls BackendAdapter through Protocol signatures only

Backend layer
  BackendAdapter: Hermes first, Codex/provider_model/self-built later
  Executes agent logic with a loaded SolutionBinding

Solution layer
  SolutionLoader: lawyer first, non-legal packs later
  Neutral manifest plus backend-specific materialization
```

The platform keeps these invariants:

- Channel and runtime are separable. A desktop or server host can construct a
  runtime with zero channel adapters.
- Backends are swappable. A new backend implements `BackendAdapter`; channels,
  runtime, and solutions do not change.
- Solutions are backend-portable. The solution manifest is neutral, while each
  backend materializes it into a backend-native bundle.
- Runtime is embeddable. `RunRuntime` depends on injected ports, not on a server,
  channel protocol, database, or backend implementation.

## Contract 1: ChannelAdapter

`ChannelAdapter` owns channel-specific verification, acknowledgements,
normalization, delivery, and health reporting. A channel adapter must not import
or call a backend adapter directly.

```python
from typing import Protocol

class ChannelAdapter(Protocol):
    def channel_id(self) -> str: ...
    def capabilities(self) -> "ChannelCapabilitySet": ...
    async def verify_and_ack(self, raw: "RawInbound") -> "AckResponse": ...
    async def normalize_inbound(self, raw: "RawInbound") -> "InboundNormalized": ...
    async def deliver(self, delivery: "ChannelDelivery") -> "DeliveryResult": ...
    async def health(self) -> "ComponentHealth": ...
```

WeCom is the first channel, but it does not define the platform boundary. The
ordinary-user WeCom boundary is owned by InkStatute, not by Hermes gateway.

## Contract 2: BackendAdapter

`BackendAdapter` owns backend-specific invocation and state retrieval. It accepts
neutral run requests and solution bindings, then returns neutral contract events,
artifacts, and run state.

```python
from typing import AsyncIterator, Protocol

class BackendAdapter(Protocol):
    def backend_id(self) -> str: ...
    def capabilities(self) -> "AdapterCapabilitySet": ...
    async def bootstrap_check(self) -> "BootstrapStatus": ...
    async def submit_run(self, req: "RunRequest") -> "RunHandle": ...
    async def get_run(self, run_id: str) -> "Run": ...
    async def stream_events(self, run_id: str) -> AsyncIterator["RunEvent"]: ...
    async def cancel_run(self, run_id: str) -> "Run": ...
    async def submit_approval(self, run_id: str, approval: "Approval") -> "Run": ...
    async def collect_artifacts(self, run_id: str) -> list["ArtifactRecord"]: ...
```

Hermes is the first backend. It stays behind this adapter contract and must not
become the channel boundary or platform core. Future `codex` and
`provider_model` modes must fit the same contract.

`AdapterCapabilitySet` is extended additively. Existing manifests remain valid,
while new capability fields express run invocation modes, stream support, cancel
support, approval support, live update support, parallel task support, and
session memory support.

`Approval` is for tool or run approval only. High-risk legal conclusions and
skill candidates remain human-reviewed.

## Contract 3: SolutionLoader

`SolutionLoader` owns solution validation, loading, and backend-specific
materialization.

```python
from typing import Protocol

class SolutionLoader(Protocol):
    def validate(self, manifest: "SolutionPackageManifest") -> list["Issue"]: ...
    def load(self, manifest: "SolutionPackageManifest") -> "Solution": ...
    def materialize_for(
        self,
        solution: "Solution",
        backend_id: str,
    ) -> "BackendSolutionBundle": ...
```

A neutral solution contains persona references, neutral skill descriptors, MCP
server references and secret templates, output policy overlays, evaluation
fixtures, default adapter config, and industry context defaults. It does not
encode Hermes runtime internals as platform requirements.

The lawyer pack is currently Hermes-shaped content. The contract is neutral now;
the first materialization target is the Hermes profile so current lawyer
behavior can keep working while portability is proven.

## Contract 4: RunRuntime

`RunRuntime` is the embeddable runtime surface. It is constructed with injected
ports and exposes run lifecycle operations.

```python
from typing import AsyncIterator, Protocol

class RunRuntime(Protocol):
    async def create_run(self, req: "RunRequest") -> "Run": ...
    async def poll(self, run_id: str) -> "Run": ...
    async def stream(self, run_id: str) -> AsyncIterator["RunEvent"]: ...
    async def cancel(self, run_id: str) -> "Run": ...
    async def approve(self, run_id: str, approval: "Approval") -> "Run": ...
```

The runtime is a library surface, not a server by definition. FastAPI, aiohttp,
Tauri sidecars, Electron child processes, and test harnesses are hosts that may
construct it.

Every user-visible event or delta must pass through the assistant output
boundary before leaving the runtime or channel layer. Backend-originated meta,
gateway, update, command, debug, and operator notices must not reach ordinary
lawyer users.

## Additive Data Contracts

The existing `packages/platform-contract` package remains the cross-language
contract source. Phase 09 extends it additively with neutral schemas and Python
bindings for:

- `ChannelMessage`
- `ChannelDelivery`
- `Run`
- `RunEvent`
- `RunStep`
- `ToolCall`
- `Approval`
- `ArtifactRecord`
- `Session`
- `Tenant`
- `Workspace`
- `SolutionPackageManifest`
- neutral skill and MCP descriptors
- `BotInstance`
- `ChannelBinding`

Rules:

- `Run.status` uses existing `AsyncTaskState` values.
- `ArtifactRecord` is a top-level artifact reference and does not replace nested
  `AgentResult.artifacts`.
- Secrets are represented by `secret_ref` or secret template names only.
- Legal-specific fields live in `industry_context` or solution-specific
  metadata, never as platform-level required fields.
- Relationship replay proves `ChannelMessage -> AgentTurn -> Run ->
  RunEvent/RunStep -> AgentResult/ArtifactRecord -> ChannelDelivery ->
  FeedbackEvent`.

## Hermes Mapping

| North Star seam | First implementation | Milestone behavior |
| --- | --- | --- |
| `ChannelAdapter` | InkStatute-owned WeCom wrapper | Wrapped behind a default-off channel lane; Hermes gateway is not the ordinary-user channel. |
| `BackendAdapter` | Hermes lawfirm | One-shot remains default until `/v1/runs` parity is proven. |
| `SolutionLoader` | Neutral lawyer manifest materialized to Hermes profile | The live profile is referenced through sanitized, reproducible materialization. |
| `RunRuntime` | New embeddable runtime | Default-off until fake-backend tests, parity checks, and human gates pass. |

Hermes `/v1/runs` is not assumed equivalent to the proven one-shot lawfirm path.
It remains behind a parity gate. The default Hermes lane stays one-shot until
fixture evidence proves equivalent routing, skills, gates, MCP behavior, output
boundary handling, and artifacts.

## Human Gates And Safety Boundaries

Phase 09-13 work is autonomous for code, tests, fixtures, and documentation. The
following remain human gates outside the autonomous path:

- promoting any new runtime, channel, or backend lane to live default-on;
- Phase 08 five-workday lawyer trial acceptance;
- high-risk legal feedback and legal conclusion skill changes.

Repository artifacts must contain only code, schemas, sanitized fixtures,
sanitized summaries, ADRs, and secret-name templates. Runtime secrets, callback
bodies, raw user messages, media, generated confidential documents, transcripts,
runtime databases, logs, and customer legal payloads must not be committed.

## Deferred Scope

This milestone does not build:

- a self-built InkStatute agent runtime;
- production Codex, Claude Code, OpenCode, or direct provider-model adapters;
- desktop local embedded runtime;
- native mobile UI;
- full security platform such as RBAC, WORM audit, key rotation, or tenant
  isolation;
- automatic legal skill synthesis.

The four contracts are designed so these can be added later without
re-architecting the platform.

## Verification Policy

Phase 09 establishes static contracts and documentation only. `packages/platform-runtime`
must remain signature-only in this plan: Protocols, type aliases, and pure data
shapes are allowed; orchestration, network behavior, storage behavior, WeCom
behavior, Hermes behavior, and solution materialization behavior are deferred to
later phases.

Boundary scans may allow names such as Hermes, WeCom, lawfirm, codex, and
provider_model only as explicit examples, enum values, package names, or
allowlisted concrete implementations. Neutral platform core must continue to
reject private runtime paths, raw payloads, secret values, logs, customer
materials, and legal-only top-level coupling.
