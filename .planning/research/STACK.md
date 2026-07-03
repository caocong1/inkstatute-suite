# Stack Research

**Domain:** M2 Multi-Backend & Platform Extensions — Codex adapter, direct provider_model adapter, Router Service, Skill Registry read, conversation-read-view completion, Admin Console API, QQBot channel
**Researched:** 2026-07-03
**Confidence:** HIGH

## Context

The v1.6 M2 milestone extends the platform beyond Hermes-only. Seven new features prove contract portability (Codex + provider_model backends, QQBot channel), normalize platform services (Router Service, Skill Registry, Admin Console API), and complete read views (conversation-read-view). This research covers ONLY the stack additions/changes needed for these M2 features.

**Critical architectural constraint discovered:** Every existing package and service in the repo declares `dependencies = []` in `pyproject.toml`. No package uses FastAPI, aiohttp, uvicorn, SQLAlchemy, or any third-party runtime library. Services are pure-Python handler functions returning `(status_code, body)` tuples (see `services/conversation-read-view/src/conversation_read_view/api.py:handle_get`). Channel/backend adapters wrap "sanitized primitives" with `network_io: False` (see `packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py`). The AGENTS rule is explicit: *"Do not introduce a new service, database, queue, or runtime dependency unless the V2 PRD or the active GSD plan requires it."* M2 features must follow this same pattern — dependency-free packages with optional runtime dependencies documented but not required.

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python stdlib `subprocess` + `json` | 3.11+ (CI floor) | Codex adapter: invoke `codex exec` as subprocess, parse JSONL/JSON output | Mirrors the existing Hermes adapter's `HermesOneShotRunner` Protocol and `oneshot_command: tuple[str, ...]` config pattern (`packages/backends/hermes/src/inkstatute_backends_hermes/config.py:23`). `codex exec --json` emits JSONL events; `--output-schema` returns JSON Schema-validated final output. No Python SDK needed — the adapter wraps subprocess I/O and maps to `AgentResult`/`ExecutionTrace` contract events. Keeps `dependencies = []`. |
| `openai` Python SDK | 2.44.0 (Jun 2026) | Direct provider_model adapter: `AsyncOpenAI` client for OpenAI-compatible LLM endpoints | The official OpenAI Python library, async-first via `httpx`, Python 3.9+. Supports any OpenAI-compatible endpoint via `base_url` (including `ollama.com/v1` which Hermes already uses). `client.chat.completions.create(stream=True)` and `client.responses.create(stream=True)` provide SSE streaming that maps to `RunEvent` contract events. This is the minimal dependency for a direct-LLM mode without a full agent runtime. Add as optional dependency: `[project.optional-dependencies] provider_model = ["openai>=2.0"]`. |
| `anthropic` Python SDK | 0.116.0 (Jul 2026) | Direct provider_model adapter: `AsyncAnthropic` client for Anthropic Claude endpoints | Optional second provider proving multi-provider contract portability. Async-first via `httpx`, Python 3.9+. `client.messages.create()` and `client.messages.stream()` map to the same `AgentResult`/`ExecutionTrace` contract. Add as optional dependency: `[project.optional-dependencies] anthropic = ["anthropic>=0.100"]`. Only needed if the prototype targets Anthropic; OpenAI-compatible alone suffices for the M2 contract-portability proof. |
| `qq-botpy` (botpy) | 1.2.1 (Mar 2024) | QQBot channel: official Tencent QQ Bot Python SDK for WebSocket gateway, message receive/send | The official Tencent `tencent-connect/botpy` SDK, asyncio-based `botpy.Client`, Python 3.8+. Provides `on_at_message_create` / `on_message_create` event handlers and `message.reply()` / `api.post_c2c_messages()` send. Auth via AppID + AppSecret. Dependencies: `aiohttp>=3.7.4,<4`, `PyYAML`, `APScheduler`. The ChannelAdapter package itself stays `dependencies = []` (wraps sanitized primitives like WeCom); `qq-botpy` is an optional runtime dependency for live deployment: `[project.optional-dependencies] runtime = ["qq-botpy>=1.2"]`. |
| Pure-Python handler functions | — | Router Service, Admin Console API, conversation-read-view: `handle(path, query, ...) -> (status_code, body)` | The existing `services/conversation-read-view/src/conversation_read_view/api.py` proves this pattern: no HTTP framework, pure routing via string prefix matching, `urllib.parse.parse_qs` for query strings, returns `(int, dict)` tuples. Router Service and Admin Console API follow the same pattern. HTTP serving is deferred to the deployment layer, not the package. Keeps `dependencies = []`. |
| `itertools.islice` + dict comprehensions (stdlib) | 3.11+ | conversation-read-view pagination and filtering | The existing `ContractLogReadModel` (`services/conversation-read-view/src/conversation_read_view/read_model.py`) builds in-memory dict indexes from JSONL contract logs. Pagination is `list(items)[offset:offset+limit]` or `itertools.islice`. Filtering is dict comprehensions over the existing `_conversations`/`_tasks`/`_trace_to_task_id` dicts. No SQL, no ORM, no pagination library needed. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `codex` CLI (npm/standalone binary) | latest (2026) | Codex adapter runtime: the `codex exec` subcommand for non-interactive agent runs | Installed on the host machine, NOT a Python dependency. The adapter invokes it via `subprocess` just like Hermes `oneshot_command`. Key flags: `--json` (JSONL event stream), `--output-schema <schema.json>` (JSON Schema draft 2020-12 validated final output), `-o <file>` (write final message), `--sandbox read-only` (safest for prototype), `--skip-git-repo-check`, `--ephemeral` (no session persistence). Multi-turn: `codex exec resume --last "follow-up prompt"`. |
| `contract_test_suite.event_stream_replay` | internal (existing) | Skill Registry read + conversation-read-view + Admin Console API: load and replay JSONL contract logs | Already built (`packages/contract-test-suite/src/contract_test_suite/event_stream_replay.py`). `load_event_stream(Path)` returns validated event records. Skill Registry reads `ExecutionTrace.active_skill_name` from these logs; conversation-read-view already uses it; Admin Console API reuses the same loader for operational views. No new dependency. |
| `run_v2_gates.py --json-summary` | internal (existing) | Admin Console API: health/gate status read-only views | Already built (`scripts/run_v2_gates.py`). Emits JSON summary of 9 V2 gates. Admin Console API invokes it via `subprocess` and exposes the results as read-only `/health` and `/gates` endpoints. No new dependency. |
| `platform_contract.events.RouteDecision` | internal (existing) | Router Service: normalized routing decision contract event | Already defined (`packages/platform-contract/src/platform_contract/events.py:207`). The Router Service produces `RouteDecision` dataclass instances with `primary_skill`, `confidence`, `mode`, `gates_before`, `gates_after`, `matched_rule`, `reason`. No new contract schema needed. |
| `wecom_service.active_task_router` | internal (existing) | Router Service: precedent for pure-Python regex-based routing | Already built (`services/wecom-service/src/wecom_service/active_task_router.py`). Uses `re.compile` patterns, `StrEnum` route classification, dataclass decisions. The Router Service extracts and generalizes this pattern into a standalone service. No new library. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `packages/backends/codex/` (new) | Codex adapter package mirroring `packages/backends/hermes/` structure | `src/inkstatute_backends_codex/` with `adapter.py` (CodexBackendAdapter implementing BackendAdapter Protocol), `config.py` (CodexBackendConfig with `exec_command: tuple[str, ...] = ("codex", "exec", "--json", "--sandbox", "read-only")`), `manifest.py` (build_codex_manifest with `AgentBackendMode.CODEX`), `runs_api.py` (optional). `pyproject.toml` with `dependencies = []`. Test fixtures with `codex exec --json` JSONL samples. |
| `packages/backends/provider_model/` (new) | Direct provider_model adapter package | `src/inkstatute_backends_provider_model/` with `adapter.py` (ProviderModelBackendAdapter implementing BackendAdapter Protocol), `config.py` (ProviderModelConfig with `provider`, `model`, `api_base_url`, `api_key_secret_ref`), `manifest.py` (build_provider_model_manifest with `AgentBackendMode.PROVIDER_MODEL`). `pyproject.toml` with `dependencies = []` and `[project.optional-dependencies] openai = ["openai>=2.0"]`. The adapter imports `openai` lazily inside `submit_run()` so the package imports without the dependency installed. |
| `services/router-service/` (new) | Independent Router Service as pure-Python library | `src/router_service/` with `router.py` (pure function `route(turn, context) -> RouteDecision`), `api.py` (`handle_post(path, body) -> (status_code, dict)` for HTTP-style routing requests), `config.py`. `pyproject.toml` with `dependencies = []`. Extracts routing logic from `platform-runtime` and `wecom-service/active_task_router.py`. NO FastAPI — follows `conversation-read-view/api.py` pattern. |
| `packages/skill-registry/` (new) | Read-only Skill Registry package | `src/skill_registry/` with `reader.py` (parses `solutions/*/manifest.json` `skills` arrays + contract log `ExecutionTrace.active_skill_name`), `api.py` (`handle_get(path, query) -> (status_code, dict)` for `/skills`, `/skills/{name}`). `pyproject.toml` with `dependencies = []`. Uses stdlib `json` for manifest parsing and `contract_test_suite.event_stream_replay` for log-derived skill usage. |
| `services/admin-console-api/` (new) | Read-only Admin Console API as pure-Python library | `src/admin_console_api/` with `api.py` (`handle_get(path, query) -> (status_code, dict)` for `/sessions`, `/tasks`, `/feedback`, `/gates`, `/health`), `views.py` (aggregates from `ContractLogReadModel` + `run_v2_gates.py` subprocess + `contract_test_suite` checkers). `pyproject.toml` with `dependencies = []`. NO FastAPI. |
| `packages/channels/qqbot/` (new) | QQBot ChannelAdapter package mirroring `packages/channels/wecom/` | `src/inkstatute_channels_qqbot/` with `adapter.py` (QQBotChannelAdapter implementing ChannelAdapter Protocol), `config.py` (QQBotChannelConfig with `app_id_secret_ref`, `app_secret_ref`, `token_secret_ref`), `normalization.py` (parse QQ Bot callback envelopes, normalize to `AgentTurn`/`FeedbackEvent`). `pyproject.toml` with `dependencies = []` and `[project.optional-dependencies] runtime = ["qq-botpy>=1.2"]`. Adapter wraps sanitized primitives with `network_io: False`, exactly like WeCom. |

## Installation

```bash
# === M2 Core: No new required dependencies ===
# Router Service, Skill Registry, conversation-read-view, Admin Console API
# all use Python 3.11+ stdlib only. No installation required.

python3 -c "import json, re, subprocess, pathlib, itertools, urllib.parse, dataclasses; print('stdlib OK')"

# === Codex adapter: install Codex CLI on host (not a Python package) ===
# Requires Node.js 22+ or download standalone binary
npm install -g @openai/codex   # or: brew install codex
codex --version                # verify installation
# The adapter invokes `codex exec` via subprocess — no Python dependency.

# === Direct provider_model adapter: optional Python dependencies ===
# Only needed when running the provider_model prototype against live LLM endpoints
pip install "openai>=2.0"           # OpenAI-compatible providers (OpenAI, ollama, Azure, etc.)
pip install "anthropic>=0.100"      # Optional: Anthropic Claude direct

# === QQBot channel: optional Python dependency for live deployment ===
pip install "qq-botpy>=1.2"         # Tencent QQ Bot SDK (asyncio, aiohttp, WebSocket gateway)

# === Verify optional dependencies ===
python3 -c "import openai; print(f'openai {openai.__version__}')"
python3 -c "import anthropic; print(f'anthropic {anthropic.__version__}')"
python3 -c "import botpy; print(f'botpy (qq-botpy) loaded')"
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `codex exec` subprocess + stdlib JSON parsing | OpenAI Agents SDK (`openai-agents` v0.17.7) as Python library for Codex integration | Only if Codex exposes a stable Python SDK API for programmatic agent runs that is simpler than subprocess. As of Jul 2026, `codex exec --json` is the documented non-interactive surface; the Agents SDK is a separate multi-agent framework, not a Codex CLI wrapper. Subprocess mirrors the Hermes `oneshot_command` pattern exactly, proving contract portability without a new Python dependency. |
| `codex exec --output-schema` for structured output | `codex exec --json` JSONL parsing only | Use `--json` when you need full event-stream telemetry (token usage, intermediate items, tool calls). Use `--output-schema` when you only need the final structured result mapped to `AgentResult`. For the M2 prototype, `--output-schema` with a schema matching `AgentResult` shape is cleaner; `--json` is useful for `ExecutionTrace` event mapping. Both can be combined. |
| `openai` SDK v2.44.0 for provider_model | `litellm` v1.90.2 (unified 100+ provider gateway) | Only if the prototype must prove compatibility with many non-OpenAI providers simultaneously. LiteLLM is a heavy dependency (proxy server, caching, extra-proxy extras) that violates the dependency-free stance. The `openai` SDK alone covers OpenAI-compatible endpoints (including ollama which Hermes already uses via `base_url`). Adding `anthropic` SDK proves multi-provider. LiteLLM is overkill for a contract-portability prototype. |
| `anthropic` SDK v0.116.0 as optional second provider | `openai` SDK alone with Anthropic via proxy | Only if you don't need to prove direct Anthropic API compatibility. The `openai` SDK can call Anthropic via a LiteLLM proxy or OpenAI's Anthropic-compatible endpoint, but that adds infrastructure. Direct `anthropic` SDK is cleaner for proving the BackendAdapter contract works with a non-OpenAI provider. |
| Pure-Python handler functions (`handle_get -> (status_code, body)`) for Router Service | FastAPI v0.139.0 as HTTP framework | Only if the Router Service must be a standalone deployed HTTP service with auto-generated OpenAPI docs. The existing services (`conversation-read-view`, `feedback-service`, `wecom-service`) are ALL pure-Python handler functions with `dependencies = []`. Adding FastAPI would introduce the first non-stdlib runtime dependency (Pydantic, Starlette, uvicorn) and break the architectural pattern. HTTP serving is a deployment concern, not a package concern. |
| Pure-Python handler functions for Admin Console API | FastAPI with auto-generated Swagger UI | Only if operators need interactive API documentation. The Admin Console API is read-only views over contract logs and gate results — the same data shape as `conversation-read-view`. FastAPI's Swagger UI is nice but adds 3+ dependencies. A simple JSON API with stdlib handlers is sufficient for M2; a FastAPI wrapper can be added at deployment time without changing the package. |
| `itertools.islice` + dict comprehensions for pagination | SQLAlchemy + database for conversation-read-view | Only if the contract log volume exceeds in-memory dict capacity. The existing `ContractLogReadModel` loads JSONL into in-memory dicts. For M2 volumes (lawyer trial scale: 15-50 tasks), this is trivially fast. A database would violate "no new authoritative conversation database" (PRD §1.2) and add a runtime dependency. |
| `qq-botpy` v1.2.1 (official Tencent SDK) for QQBot | Custom WebSocket client using stdlib `websockets` or `aiohttp` directly | Only if `qq-botpy` proves incompatible with Python 3.11 or has breaking bugs. `qq-botpy` is the official SDK from `tencent-connect/botpy`, maintained by Tencent, asyncio-based, MIT licensed. It handles auth (AppID + AppSecret), WebSocket gateway reconnection, and message normalization. Building a custom client would duplicate this work and is not M2 scope. The SDK's `aiohttp` dependency is acceptable as an optional runtime dependency. |
| `qq-botpy` as optional dependency (`[project.optional-dependencies]`) | `qq-botpy` as required dependency in `packages/channels/qqbot/pyproject.toml` | Only if the channel adapter package cannot function without the SDK at import time. The WeCom adapter pattern proves that ChannelAdapter packages can be `dependencies = []` with `network_io: False` — they wrap sanitized primitives. The `botpy` import is deferred to runtime/deployment. This keeps CI and contract tests dependency-free. |
| Parse `manifest.json` + contract logs for Skill Registry | Query a Hermes skill registry API or CLI | Only if Hermes exposes a skill registry API. Source inspection confirms Hermes has NO skill registry API — skill metadata lives in `solutions/*/manifest.json` `skills` arrays (name, description, intent, required_tools, risk_level) and in `ExecutionTrace.active_skill_name` in contract logs. PRD §3.2: "V2 不建独立 Skill Registry，只通过 Hermes router 日志和 skill index 读取 skill 元数据." Stdlib `json` parsing is the correct approach. |

## What NOT to Use

| Technology | Why NOT | Used Instead |
|------------|---------|-------------|
| FastAPI v0.139.0 | Introduces Pydantic v2, Starlette, uvicorn as required dependencies. Every existing service uses `dependencies = []` and pure-function handlers. FastAPI would break the architectural pattern and the AGENTS dependency rule. | Pure-Python `handle_get/handle_post -> (status_code, body)` functions, exactly like `services/conversation-read-view/src/conversation_read_view/api.py` |
| aiohttp (as a service framework) | No existing service uses aiohttp as an HTTP server. `wecom-service` has `dependencies = []`. aiohttp is only acceptable as a transitive dependency of `qq-botpy` for the QQBot channel runtime. | stdlib `urllib.parse` for query parsing; HTTP serving deferred to deployment |
| SQLAlchemy / any ORM | PRD §1.2: "不建独立 Conversation API + 数据库." Contract logs are JSONL files, not relational data. The existing `ContractLogReadModel` uses in-memory dicts. | `contract_test_suite.event_stream_replay.load_event_stream()` + dict indexes |
| LiteLLM v1.90.2 | Heavy dependency (proxy server, caching, 100+ provider adapters). Overkill for a provider_model prototype that needs to prove contract portability, not provider coverage. The `openai` SDK with `base_url` covers OpenAI-compatible providers. | `openai` SDK v2.44.0 (optional) + `anthropic` SDK v0.116.0 (optional) |
| OpenAI Agents SDK (`openai-agents` v0.17.7) | It's a multi-agent workflow framework, not a Codex CLI integration. The Codex adapter needs to invoke `codex exec` as a subprocess, not build agent graphs. Using the Agents SDK would add an unnecessary abstraction layer and dependency. | `codex exec` subprocess + stdlib JSON/JSONL parsing |
| Pydantic v2 | No existing package uses Pydantic. All dataclasses are stdlib `@dataclass(frozen=True, slots=True)`. Adding Pydantic for request/response validation in Router Service or Admin Console API would break the dependency-free pattern. | stdlib `dataclasses` + manual dict validation (existing pattern in `platform_contract.agent_adapter.validate_agent_backend_manifest`) |
| uvicorn | No existing service runs uvicorn. Services are libraries, not ASGI apps. | Pure-function handlers; deployment-layer HTTP serving is out of M2 package scope |
| Flask | Sync-only, not async-compatible with the Python 3.11 async core. No existing service uses it. | Pure-function async handlers |
| Starlette | ASGI toolkit that would be used with FastAPI. Same dependency concerns. | Pure-function handlers |
| any pagination library (e.g., `fastapi-pagination`) | The existing read model is in-memory dicts. Pagination is `list(items)[offset:offset+limit]`. A library adds complexity for a 3-line operation. | `itertools.islice` or list slicing |
| qq-bot (old `qq-bot` v0.8.5) | Deprecated predecessor of `qq-botpy`. The official docs say "原机器人的老版本 qq-bot 仍然可以使用，但新接口的支持上会逐渐暂停." | `qq-botpy` v1.2.1 (`pip install qq-botpy`, `import botpy`) |

## Stack Patterns by Variant

### M2-01: Codex Adapter (`packages/backends/codex/`)

**Pattern:** Subprocess one-shot, mirroring Hermes adapter exactly.

```
RunRequest → CodexBackendAdapter.submit_run()
  → subprocess: codex exec --json --sandbox read-only --skip-git-repo-check \
      --output-schema <agent_result_schema.json> -o <output.json> "<prompt>"
  → parse JSONL events from stdout (thread.started, turn.completed, item.*)
  → parse final JSON from -o file (schema-validated AgentResult shape)
  → map to AgentResult + ExecutionTrace contract events
  → return RunHandle
```

**Key integration points:**
- `AgentBackendMode.CODEX` already exists in `platform_contract.agent_adapter` (line 14)
- `AdapterCapabilitySet`: `invocation_mode="sync"`, `no_channel_io=True`, `run_invocation_modes=["oneshot"]`, `stream_event_support=False` (same reduced capabilities as Hermes one-shot)
- `HermesOneShotRunner` Protocol pattern (`packages/backends/hermes/src/inkstatute_backends_hermes/adapter.py:27`) → `CodexOneShotRunner` Protocol with identical `invoke(req) -> CodexOneShotResult` shape
- Config: `CodexBackendConfig(oneshot_command=("codex", "exec", "--json", "--sandbox", "read-only", "--skip-git-repo-check"))` — mirrors `HermesBackendConfig.oneshot_command`

**No new Python dependencies.** `dependencies = []`.

### M2-02: Direct provider_model Adapter (`packages/backends/provider_model/`)

**Pattern:** Async LLM client call, no agent runtime.

```
RunRequest → ProviderModelBackendAdapter.submit_run()
  → lazy import: from openai import AsyncOpenAI
  → client = AsyncOpenAI(api_key=..., base_url=config.api_base_url)
  → response = await client.chat.completions.create(
      model=config.model, messages=[{"role": "user", "content": req.turn.content}],
      stream=False
    )
  → map response.choices[0].message.content to AgentResult.content
  → map response.usage to ExecutionTrace metadata
  → return RunHandle
```

**Key integration points:**
- `AgentBackendMode.PROVIDER_MODEL` already exists (line 15)
- `AdapterCapabilitySet`: `invocation_mode="sync"`, `no_channel_io=True`, `session_memory_support=False`, `trace_support=True`
- Lazy import pattern: `openai` imported inside `submit_run()` so package imports without it
- `pyproject.toml`: `dependencies = []`, `[project.optional-dependencies] openai = ["openai>=2.0"]`

**Optional dependency:** `openai>=2.0` (only when running live).

### M2-03: Router Service (`services/router-service/`)

**Pattern:** Pure-Python routing library, extracted from platform-runtime + wecom-service.

```
AgentTurn → router_service.route(turn, context) -> RouteDecision
  → regex/classifier matching (mirrors wecom_service.active_task_router._classify_intent)
  → produce RouteDecision dataclass (platform_contract.events.RouteDecision)
  → return contract event-ready decision
```

**Key integration points:**
- `RouteDecision` contract event already defined (`platform_contract.events.RouteDecision`, line 207)
- `route_decision.schema.json` already exists in `packages/platform-contract/src/platform_contract/schemas/`
- Precedent: `services/wecom-service/src/wecom_service/active_task_router.py` — pure regex routing with `StrEnum` routes, `dataclass` decisions, `re.compile` patterns
- `api.py`: `handle_post(path, body) -> (status_code, dict)` — same pattern as `conversation-read-view/api.py:handle_get`
- NO FastAPI, NO aiohttp. `dependencies = []`.

### M2-04: Skill Registry Read (`packages/skill-registry/`)

**Pattern:** Parse existing manifest JSON + contract log execution traces.

```
sources:
  1. solutions/*/manifest.json → skills[] (name, description, intent, required_tools, risk_level)
  2. contract logs → ExecutionTrace.active_skill_name per turn
  → merge into SkillRegistry (dict[skill_name, SkillMetadata])
  → expose via handle_get("/skills", query) and handle_get("/skills/{name}", query)
```

**Key integration points:**
- `solutions/lawfirm/manifest.json` already has `skills` array with 4 skills (line 12-41)
- `contract_test_suite.event_stream_replay.load_event_stream()` for log-derived skill usage
- `ExecutionTrace.active_skill_name` field in contract events
- stdlib `json` for manifest parsing — no Hermes API exists (PRD §3.2 confirms)
- `api.py`: `handle_get(path, query) -> (status_code, dict)` — same pattern as conversation-read-view
- `dependencies = []`.

### M2-05: conversation-read-view Completion (`services/conversation-read-view/`)

**Pattern:** Extend existing `ContractLogReadModel` with pagination/filtering.

```
Existing: handle_get("/conversations/{id}", query) → single conversation
          handle_get("/tasks/{id}", query) → single task
          handle_get("/feedback", query) → pending feedback list

M2 adds: handle_get("/conversations", query) → paginated list with ?limit&offset&user_id&status
         handle_get("/tasks", query) → paginated list with ?limit&offset&status&trace_id
         handle_get("/traces/{trace_id}", query) → trace query
         handle_get("/feedback", query) → extend beyond pending-only filter
```

**Key integration points:**
- `ContractLogReadModel` (`read_model.py:28`) already has `_conversations`, `_tasks`, `_trace_to_task_id` dicts
- Add `list_conversations(limit, offset, filters) -> dict` and `list_tasks(limit, offset, filters) -> dict` methods
- Pagination: `list(self._conversations.values())[offset:offset+limit]`
- Filtering: dict comprehension `{k: v for k, v in items if filter_fn(v)}`
- `api.py:handle_get` extended with new route prefixes
- `dependencies = []`. No new library.

### M2-06: Admin Console API (`services/admin-console-api/`)

**Pattern:** Read-only operational views, pure-function handlers.

```
handle_get("/sessions", query) → paginated session list from ContractLogReadModel
handle_get("/tasks", query) → paginated task list
handle_get("/feedback", query) → feedback queue summary
handle_get("/gates", query) → V2 gate status (subprocess: run_v2_gates.py --json-summary)
handle_get("/health", query) → component health aggregation
```

**Key integration points:**
- Reuses `ContractLogReadModel` from `conversation-read-view` (import as library)
- Reuses `run_v2_gates.py --json-summary` via `subprocess` (existing gate runner)
- Reuses `contract_test_suite` checkers (`boundary_checks`, `privacy_scan`, `coverage_report`)
- `api.py`: `handle_get(path, query, ...) -> (status_code, dict)` — identical pattern to conversation-read-view
- NO FastAPI. `dependencies = []`.

### M2-07: QQBot Channel (`packages/channels/qqbot/`)

**Pattern:** ChannelAdapter wrapping sanitized QQ Bot primitives, mirroring WeCom adapter.

```
RawInbound → QQBotChannelAdapter.verify_and_ack(raw) → AckResponse
RawInbound → QQBotChannelAdapter.normalize_inbound(raw) → InboundNormalized
  → parse QQ Bot callback envelope (at_message_create / message_create events)
  → normalize to AgentTurn or FeedbackEvent
ChannelDelivery → QQBotChannelAdapter.deliver(delivery) → DeliveryResult
  → build QQ Bot send envelope (text / rich_media / ark)
  → network_io: False (sanitized primitive, like WeCom)
```

**Key integration points:**
- `ChannelAdapter` Protocol (`platform_runtime.protocols.ChannelAdapter`, line 208) — same 5 methods as WeCom
- `ChannelCapabilitySet`: `supports_text=True`, `supports_files=True` (rich_media), `supports_cards=False` (QQ Bot has no template cards), `supports_streaming=False`, `ack_deadline_ms=5000`
- Config: `QQBotChannelConfig(app_id_secret_ref=..., app_secret_ref=..., token_secret_ref=...)` — mirrors `WeComChannelConfig` secret-ref pattern
- `botpy.Client` event handlers (`on_at_message_create`, `on_message_create`) map to `RawInbound` at the service boundary
- `botpy.api.post_c2c_messages()` / `message.reply()` map to `ChannelDelivery` at the service boundary
- `pyproject.toml`: `dependencies = []`, `[project.optional-dependencies] runtime = ["qq-botpy>=1.2"]`
- `botpy` imported lazily at runtime, NOT at package import time

**Optional dependency:** `qq-botpy>=1.2` (only for live deployment).

## Version Compatibility

| Component | Version | Python | Verified Date | Notes |
|-----------|---------|--------|---------------|-------|
| `openai` SDK | 2.44.0 | >=3.9 (tested on 3.13) | 2026-07-03 | PyPI latest. AsyncOpenAI uses httpx. Supports `base_url` for OpenAI-compatible endpoints. |
| `anthropic` SDK | 0.116.0 | >=3.9 | 2026-07-03 | PyPI latest (released 2026-07-02). AsyncAnthropic uses httpx. |
| `qq-botpy` (botpy) | 1.2.1 | >=3.8 | 2026-07-03 | PyPI latest. Last release Mar 2024. Dependencies: aiohttp>=3.7.4,<4, PyYAML, APScheduler. GitHub: tencent-connect/botpy (837 stars). |
| `codex` CLI | latest 2026 | Node.js 22+ | 2026-07-03 | `codex exec --json` stable. `--output-schema` uses JSON Schema draft 2020-12. `codex exec resume --last` for multi-turn. Not a Python package — subprocess invocation. |
| FastAPI (NOT recommended) | 0.139.0 | >=3.10 | 2026-07-03 | Listed for reference only. Do NOT add to any M2 package. |
| LiteLLM (NOT recommended) | 1.90.2 | >=3.10,<3.14 | 2026-07-03 | Listed for reference only. Do NOT add to any M2 package. |
| Python (CI floor) | 3.11 | — | — | `tomllib` stdlib since 3.11. All M2 packages target >=3.11. |
| `openai-agents` (NOT recommended) | 0.17.7 | >=3.10 | 2026-07-03 | Listed for reference only. Not a Codex CLI integration; it's a multi-agent framework. |

## Sources

- [Codex CLI Command Reference — `codex exec`](https://developers.openai.com/codex/cli/reference)
- [Codex Non-Interactive Mode — `--json`, `--output-schema`, `resume`](https://developers.openai.com/codex/noninteractive)
- [Codex CLI Features — resuming conversations, scripting](https://developers.openai.com/codex/cli/features)
- [Codex exec Structured Output Pipelines — `--output-schema`, `--json`, `resume`](https://codex.danielvaughan.com/2026/06/11/codex-exec-structured-output-pipelines-output-schema-json-resume-ci-automation/)
- [OpenAI Python SDK — PyPI v2.44.0](https://pypi.org/project/openai/)
- [OpenAI Python SDK — streaming helpers, AsyncOpenAI](https://github.com/openai/openai-python/blob/main/helpers.md)
- [OpenAI Streaming API Responses — SSE, Responses API](https://developers.openai.com/api/docs/guides/streaming-responses)
- [Anthropic Python SDK — PyPI v0.116.0](https://pypi.org/project/anthropic/)
- [Anthropic Python SDK — GitHub, async clients](https://github.com/anthropics/anthropic-sdk-python)
- [OpenAI Agents SDK — PyPI v0.17.7](https://pypi.org/project/openai-agents/) (considered, not recommended)
- [LiteLLM — PyPI v1.90.2](https://pypi.org/project/litellm/) (considered, not recommended)
- [QQ Bot Python SDK — official docs](https://bot.q.qq.com/wiki/develop/pythonsdk/)
- [tencent-connect/botpy — GitHub](https://github.com/tencent-connect/botpy)
- [qq-botpy — PyPI v1.2.1](https://pypi.org/project/qq-botpy/)
- [botpy setup.py — dependencies: aiohttp, PyYAML, APScheduler](https://github.com/tencent-connect/botpy/blob/master/setup.py)
- [FastAPI — PyPI v0.139.0](https://pypi.org/project/fastapi/) (considered, not recommended)
- Existing codebase: `packages/backends/hermes/src/inkstatute_backends_hermes/adapter.py` (Hermes adapter pattern)
- Existing codebase: `packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py` (WeCom channel pattern)
- Existing codebase: `services/conversation-read-view/src/conversation_read_view/api.py` (pure-function handler pattern)
- Existing codebase: `services/wecom-service/src/wecom_service/active_task_router.py` (pure-Python routing precedent)
- Existing codebase: `packages/platform-contract/src/platform_contract/agent_adapter.py` (AgentBackendMode enum)
- Existing codebase: `packages/platform-contract/src/platform_contract/events.py` (RouteDecision dataclass)
- Existing codebase: `solutions/lawfirm/manifest.json` (skill metadata source)
- PRD §3.2: "V2 不建独立 Skill Registry，只通过 Hermes router 日志和 skill index 读取 skill 元数据"
- PRD §11: M2 milestone scope
