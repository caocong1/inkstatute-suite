:aspect-plan: Real-Provider Validation and Regression Gates

## 1. Phase 31: Real-Provider Validation and Regression Gates

### 1.1. Scope

Validate the full memory stack against a live Hindsight instance, document deployment, and ensure all regression gates pass.

### 1.2. Success Criteria

1. A live Hindsight test proves multi-turn memory, cross-task recall, and preference retention.
2. Automated tests can run in CI without a live provider.
3. The existing V2 gate suite (`scripts/run_v2_gates.py`) passes.
4. Deployment docs include provider setup, required secrets, and resource expectations.

### 1.3. Deliverables

| Deliverable | Location |
|-------------|----------|
| Live provider validation test | `packages/platform-runtime/tests/test_long_term_memory.py` |
| Deployment docs | `docs/deployment/hindsight.md` |
| Milestone completion | `31-VERIFICATION.md`, `STATE.md`, `ROADMAP.md` |

### 1.4. Execution Plan

#### Wave 1: Multi-turn live Hindsight test

- Extend `test_long_term_memory.py` with `HindsightMemoryMultiTurnTest`.
- Scenario:
  1. Retain user preference: "User prefers concise contract summaries."
  2. Retain project fact: "User is handling the Acme contract dispute."
  3. In a new turn, recall with query "What should I remember about summaries?" and verify preference.
  4. In a cross-task query, recall with "Acme" and verify project fact.
  5. Use different turn IDs / bank IDs to prove cross-task recall.

#### Wave 2: Deployment docs

- Create `docs/deployment/hindsight.md`.
- Include Docker run command, required env vars (`HINDSIGHT_BASE_URL`, `HINDSIGHT_API_KEY`), model notes, and resource expectations.
- Include local Ollama setup for dev.

#### Wave 3: Regression gates

- Run `scripts/run_v2_gates.py`.
- Run `pytest packages/platform-runtime/tests/`.
- Run `pytest services/wecom-service/tests/`.

#### Wave 4: Milestone close

- Mark Phase 31 complete.
- Update `STATE.md` and `ROADMAP.md` to mark v1.4 complete.
- Create `31-VERIFICATION.md`.

### 1.5. Verification

- Live Hindsight test passes with local Hindsight + Ollama.
- V2 gates pass.
- Docs are present and accurate.
