:aspect-plan: Memory Semantics: Focus vs Retention

## 1. Phase 28: Memory Semantics: Focus vs Retention

### 1.1. Scope

Define durable vs transient memory classification, add retention and recall policies, and implement them on top of the `Memory` interface without changing the Hindsight API surface.

### 1.2. Success Criteria

1. A `MemoryContentClassifier` labels content as durable or transient and assigns a category.
2. A `MemoryRetentionPolicy` controls what categories are retained and how facts are extracted.
3. A `MemoryFocusPolicy` controls recall relevance thresholds and max results.
4. `aretain` returns a `MemoryRetentionDecision` showing what was retained/discarded.
5. `arecall` returns a `MemoryFocusResult` with selected and filtered memories.
6. Existing V2 gates remain green.

### 1.3. Deliverables

| Deliverable | Location |
|-------------|----------|
| Memory policies and classifier | `packages/platform-runtime/src/platform_runtime/memory_policy.py` |
| Updated `Memory` interface | `packages/platform-runtime/src/platform_runtime/long_term_memory.py` |
| Updated `FakeMemory` | `packages/platform-runtime/src/platform_runtime/fake_memory.py` |
| Updated `HindsightMemory` | `packages/platform-runtime/src/platform_runtime/hindsight_memory.py` |
| Policy contract tests | `packages/platform-runtime/tests/test_memory_policy.py` |

### 1.4. Execution Plan

#### Wave 1: Classifier and policy types

- Add `MemoryCategory` enum: `user_preference`, `project_fact`, `lesson_learned`, `task_detail`, `transient`.
- Add `MemoryContentClassifier` with rule-based heuristics:
  - `user_preference`: contains "prefer", "like", "dislike", "always", "never".
  - `project_fact`: contains "project", "case", "client", "contract".
  - `lesson_learned`: contains "should", "must not", "lesson", "learned".
  - `task_detail`: contains specific one-off actions.
  - `transient`: everything else or explicitly marked.
- Add `MemoryRetentionPolicy` with `allowed_categories` and `extract_facts` flag.
- Add `MemoryFocusPolicy` with `max_results`, `minimum_relevance_score`, `required_categories`.
- Add `MemoryRetentionDecision` and `MemoryFocusResult` dataclasses.

#### Wave 2: Update Memory interface

- Add optional `retention_policy` to `MemoryRetainInput`.
- Add optional `focus_policy` to `MemoryRecallInput`.
- Update return types to `MemoryRetentionDecision` and `MemoryFocusResult`.
- Keep backward compatibility: if no policy, default to retain all and recall top-N.

#### Wave 3: Update adapters

- `FakeMemory` applies classifier and filters before storing.
- `HindsightMemory` passes category hints as metadata; for local test it uses `FakeMemory` classifier to filter results.
- Add `MemoryPolicyError` for invalid policy.

#### Wave 4: Tests and gates

- Write contract tests for classifier, retention policy, and recall focus.
- Run `scripts/run_v2_gates.py`.

### 1.5. Verification

- `pytest packages/platform-runtime/tests/test_memory_policy.py` passes.
- `pytest packages/platform-runtime/tests/test_long_term_memory.py` passes.
- `scripts/run_v2_gates.py` passes.
