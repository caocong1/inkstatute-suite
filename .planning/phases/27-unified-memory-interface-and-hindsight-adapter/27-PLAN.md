:aspect-plan: Unified Memory Interface and Hindsight Adapter

## 1. Phase 27: Unified Memory Interface and Hindsight Adapter

### 1.1. Scope

Define a backend-agnostic `Memory` interface (async, retain/recall/reflect) and implement a Hindsight adapter. Keep the existing native SQLite path as a deprecated optional implementation so V2 gates remain green.

### 1.2. Success Criteria

1. `Memory` interface exposes `aretain`, `arecall`, and `areflect` with clear inputs/outputs.
2. `HindsightMemory` implements `Memory` using `hindsight-client` against a configurable base URL.
3. `FakeMemory` implements `Memory` in-memory for contract tests without a live provider.
4. Existing V2 contract tests and gates still pass.
5. SQLite memory store is no longer the default runtime path; it is explicitly opt-in.

### 1.3. Deliverables

| Deliverable | Location |
|-------------|----------|
| `Memory` interface | `packages/platform-runtime/src/platform_runtime/long_term_memory.py` |
| `HindsightMemory` adapter | `packages/platform-runtime/src/platform_runtime/hindsight_memory.py` |
| `FakeMemory` test double | `packages/platform-runtime/src/platform_runtime/fake_memory.py` |
| Adapter capability manifest | `HindsightMemoryStoreCapabilityManifest` in `memory_adapters.py` |
| Contract tests | `packages/platform-runtime/tests/test_long_term_memory.py` |
| Integration tests (optional) | `packages/platform-runtime/tests/test_hindsight_memory.py` |

### 1.4. Execution Plan

#### Wave 1: Interface design

- Define `Memory` Protocol with `aretain`, `arecall`, `areflect`.
- Define dataclasses: `MemoryRetainInput`, `MemoryRecallInput`, `MemoryReflectInput`, `MemoryRecallResult`, `MemoryReflectResult`.
- Add privacy-safe metadata validation (no raw payloads, no secrets).
- Export from `platform_runtime.__init__`.

#### Wave 2: Hindsight adapter

- Implement `HindsightMemory` using `hindsight_client.Hindsight`.
- Map tenant/workspace/user to Hindsight `bank_id`.
- Use environment variables for base URL and API key: `HINDSIGHT_BASE_URL`, `HINDSIGHT_API_KEY`, `HINDSIGHT_LLM_MODEL`, `HINDSIGHT_EMBEDDING_MODEL`.
- Implement `capability_manifest()` returning a Hindsight-specific manifest.

#### Wave 3: Fake memory and contract tests

- Implement `FakeMemory` in-memory with deterministic `aretain`/`arecall`/`areflect`.
- Write contract tests that exercise both `FakeMemory` and, when env vars present, `HindsightMemory`.
- Ensure `HindsightMemory` tests are skipped when live provider is unavailable.

#### Wave 4: Deprecate SQLite default path

- Update `DefaultRunRuntime` to not auto-create `SQLiteMemoryStore`.
- Remove SQLite default from `__init__` if needed; keep imports for opt-in use.
- Add deprecation note in `sqlite_memory.py`.
- Update any tests that implicitly depend on SQLite default.

### 1.5. Verification

- Run `python -m pytest packages/platform-runtime/tests/test_long_term_memory.py` — passes.
- Run `scripts/run_v2_gates.py` — passes.
- Optional: run `python -m pytest packages/platform-runtime/tests/test_hindsight_memory.py` with local Hindsight — passes.
