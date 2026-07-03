# Pitfalls Research

**Domain:** V2 acceptance closure for a legal-tech WeCom service + backend-neutral platform contract + agent-adapter layer (InkStatute V2, milestone v1.5)
**Researched:** 2026-07-03
**Confidence:** HIGH

This research covers common mistakes when **adding V2 acceptance closure** to an existing system that has 4 shipped milestones (v1.1–v1.4), 424+ passing tests, 4 services, and 7 packages. The v1.5 milestone is an audit-and-close task: distinguish "already done but not marked" from "genuinely missing," close code gaps, update traceability, and produce a readiness report leaving only two human gates (Phase 5 live WeCom UAT, Phase 8 five-workday lawyer trial).

---

## Critical Pitfalls

### Pitfall 1: Traceability false positive — marking a requirement "done" because a file/service exists, when production wiring is missing

**What goes wrong:**
The auditor sees that `services/wecom-service/` exists, that `test_output_policy.py` passes, and that the output boundary module is imported somewhere, then marks the Active requirement "Add an assistant output boundary" as validated. But the boundary is only exercised in unit tests with synthetic payloads — the actual WeCom egress path in `WeComSessionRuntime` may bypass it for certain message types, or the production ingress entrypoint may not wire the policy at all. The requirement is marked closed in PROJECT.md, the readiness report claims the output boundary is complete, and the gap is only discovered during Phase 5 live UAT when a Hermes gateway restart notice leaks to a lawyer's WeCom.

**Why it happens:**
This exact pattern already occurred in v1.4. The v1.4 milestone audit initially scored MEM-07 (singleton initialization) and MEM-16 (contract event observability) as "satisfied" because the `Memory` interface, `HindsightMemory` adapter, `MemoryObserver`, and `RetryableMemory` all existed and passed tests. The audit only caught the gap when it checked the **production wiring path**: `ingress_runtime.py` instantiated `WeComSessionRuntime` without a `memory` parameter, and no observer was wired outside tests. The infrastructure was present; the deployment integration was absent. Auditing at the "module exists + tests pass" level produces false positives whenever a requirement implicitly demands production wiring, not just library surfaces.

**How to avoid:**
For each unchecked Active requirement, audit at three levels, not one:
1. **Schema/contract level** — does the event schema, error code, or state machine exist and validate? (Cheapest, most likely already done.)
2. **Library surface level** — does the class/function/adapter exist with tests? (Often done across v1.1–v1.4.)
3. **Production wiring level** — does the actual deployment entrypoint (`ingress_runtime.py`, `dispatch_agent`, WeCom egress path, CI gate job) invoke it with real configuration, not just test doubles? (This is where v1.4 found 2/20 partials.)

Only mark a requirement "validated" when all three levels are confirmed. For the V2 Active requirements specifically:
- "Build InkStatute-owned WeCom service" — verify `receive_callback`, `normalize_turn`, `dispatch_agent`, `send_message`, `feedback_callback`, `output_policy`, `idempotency` are all wired in the **egress path**, not just present as testable functions.
- "Add an assistant output boundary" — verify the boundary sits in the **actual send path** for every outbound message type (text, file, card, status), not just in a unit-tested `OutputPolicy` class. Check that gateway/update/command/meta payloads are blocked or rewritten before reaching `send_message`.
- "Normalize Hermes feedback into FeedbackEvent" — verify the WeCom feedback callback path produces `FeedbackEvent` records with dedupe keys, not just that a normalizer function exists.

**Warning signs:**
- A requirement is marked validated but no integration test exercises the full `WeCom callback → normalize → dispatch → agent → output boundary → send → feedback → FeedbackEvent` chain end-to-end.
- The only tests for a requirement are unit tests with hand-crafted inputs, not fixture-replay tests that flow through the real runtime.
- A service module exists but `ingress_runtime.py` or the deployment entrypoint doesn't import or instantiate it.
- The auditor says "the code is there" but cannot point to the specific line in the production path that invokes it.

**Phase to address:**
v1.5 Phase 1 (audit) — this is the core audit methodology pitfall. The audit plan must mandate three-level verification and explicitly reject "module exists + tests pass" as sufficient evidence for production-wiring requirements.

---

### Pitfall 2: Traceability false negative — leaving a requirement unchecked because it was satisfied by v1.1–v1.4 work under a different name

**What goes wrong:**
The auditor reads the Active requirement "Enforce observability, replay, privacy, and legal safety baselines" and searches for a module literally named "observability" or "replay." Finding nothing by that exact name, they flag it as a genuine gap and the milestone plan adds a phase to build it. But the capability was actually delivered across v1.1–v1.4: `ContractLogStore` provides observability, `contract-test-suite` fixture replay provides replay validation, `raw_payload_ref` and the privacy scanner provide privacy baselines, and `FeedbackLearningPolicy` with human-review-only `skill_candidate` provides legal safety. The requirement is already satisfied but was never marked because the shipped work used different vocabulary than the PRD requirement text.

**Why it happens:**
The V2 Active requirements in PROJECT.md are written at the PRD level (high-level capability statements), while the shipped v1.1–v1.4 code uses implementation-level names (`ContractLogStore`, `MemoryObserver`, `OutputPolicy`, `DeliveryGuard`, `WeComSessionRuntime`). There is no pre-existing traceability matrix mapping PRD requirement text to specific files/classes/tests. The auditor must construct this mapping during the audit, and name-mismatch makes grep-based searches return false negatives. This is especially dangerous for the "softer" requirements: "Enforce observability, replay, privacy, and legal safety baselines" and "Enforce composability and industry-neutral contract behavior in CI" — these are cross-cutting concerns satisfied by multiple modules rather than a single service.

**How to avoid:**
Build a requirement-to-code traceability matrix **before** classifying any requirement as a gap. For each Active requirement:
1. Decompose it into concrete capabilities (e.g., "observability" = contract log writing + memory operation events + runtime audit trail).
2. Search for each capability by **behavior**, not by name: grep for `ContractLog`, `Observer`, `audit`, `replay`, `raw_payload_ref`, `privacy`, `skill_candidate`, `industry_context`, `composability`.
3. Map each found artifact to the requirement with a file path + line reference.
4. Only if no artifact maps to a decomposed capability, classify it as a genuine gap.

For the cross-cutting requirements specifically:
- "Enforce observability, replay, privacy, and legal safety baselines" → check `ContractLogStore`, `ContractLogMemoryObserver`, `MemoryOperationEvent`, `contract-test-suite` replay fixtures, `raw_payload_ref` usage, privacy scanner, `FeedbackLearningPolicy` human-review gate.
- "Enforce composability and industry-neutral contract behavior in CI" → check `.github/workflows/v2-contract-gates.yml`, `scripts/run_v2_gates.py`, non-legal synthetic task fixtures, `industry_context` field isolation tests.

**Warning signs:**
- A requirement is classified as a gap but no one can explain what specific code would need to be written — only that "it's not checked off."
- The auditor searches for the requirement's literal words in the codebase and finds nothing, without trying synonymous capability terms.
- A gap-closure phase is proposed for a capability that already has tests passing in the V2 gate suite.
- The readiness report lists more gaps than the v1.4 audit found integration points (20/20) — if v1.4 closed 10/10 integration points, most V2 Active requirements should already have partial coverage.

**Phase to address:**
v1.5 Phase 1 (audit) — the traceability matrix must be the first deliverable, before any gap classification.

---

### Pitfall 3: Gap closure regressions — modifying shipped v1.1–v1.4 code to close a V2 gap and breaking the 424-test baseline

**What goes wrong:**
The audit identifies a genuine gap (e.g., the WeCom egress path doesn't route through `OutputPolicy` for card messages, only for text). The developer modifies `WeComSessionRuntime` to add the policy check. This change breaks three v1.2 session-continuation tests that assumed all outbound messages pass through unmodified, and one v1.4 memory-observer test that expected `MemoryOperationEvent` to fire before delivery. The V2 gate suite was already fragile (the v1.4 audit found a PYTHONPATH regression that had been hiding 3 broken gates since v1.2), so the regression may not surface immediately if the gate runner's PYTHONPATH is still incomplete for the affected service.

**Why it happens:**
The shipped v1.1–v1.4 code was built with a specific set of assumptions about message flow, session lifecycle, and memory wiring. V2 gap closure changes those assumptions (adding output boundary checks, feedback dedupe, idempotency keys, raw payload redaction). The existing tests encode the old assumptions. Additionally, the V2 gate runner (`scripts/run_v2_gates.py`) had a PYTHONPATH regression from v1.2 through v1.4 that hid 3 broken gates — if that regression was only partially fixed, new regressions in those same gates may still be masked. The developer assumes "424 tests pass" means the baseline is solid, but the baseline may have silent gaps in exactly the services being modified.

**How to avoid:**
1. **Before any gap closure:** Run the full V2 gate suite locally and capture the exact test count and pass/fail baseline. Verify that `scripts/run_v2_gates.py` includes PYTHONPATH entries for all 4 services (`wecom-service`, `hermes-contract-layer`, `conversation-read-view`, `feedback-service`) and all relevant packages. The v1.4 audit fixed a missing-PYTHONPATH regression — confirm that fix is still in place and that no new service was added without its PYTHONPATH entry.
2. **During gap closure:** Add tests for the new behavior **before** modifying shipped code (test-first per AGENTS.md coding rules). Run the full gate suite after each change, not just the affected service's tests.
3. **After gap closure:** Run the complete gate suite again. If the test count drops or any previously-passing test fails, treat it as a regression, not a "test needs updating" — investigate whether the test encoded a valid assumption that the gap closure violated.
4. **For output boundary changes specifically:** The output boundary is the highest-risk modification because it sits in the egress path shared by all message types. Any change to `OutputPolicy` or its wiring must verify that v1.2 session-continuation tests, v1.3 feedback-to-memory tests, and v1.4 memory-observer tests still pass — these all depend on the egress path.

**Warning signs:**
- A gap-closure change modifies `WeComSessionRuntime`, `ingress_runtime.py`, or `OutputPolicy` and the developer only runs the affected service's tests.
- The V2 gate suite test count changes (increases or decreases) without an explicit explanation.
- A test is deleted or marked `skip` during gap closure without a documented reason.
- `scripts/run_v2_gates.py` is modified to add a PYTHONPATH entry — this may indicate the gate was silently broken before, meaning the "424 passing" baseline was inaccurate.
- A gap-closure commit touches files in `packages/platform-contract/` — the contract schemas are the stable coupling point and changes here ripple across all services.

**Phase to address:**
v1.5 Phase 2 (gap closure) — every gap-closure plan must include a pre-change baseline capture, test-first addition, and full gate-suite regression check.

---

### Pitfall 4: PYTHONPATH / gate-runner regression — the "424 passing tests" baseline is silently inaccurate

**What goes wrong:**
The audit relies on `scripts/run_v2_gates.py` reporting "424 tests, all pass" as evidence that the shipped code is healthy. But the gate runner has a history of PYTHONPATH regressions: the v1.4 audit discovered that since v1.2, the runner was missing PYTHONPATH entries for `wecom-service`, `conversation-read-view`, and `feedback-service` gates, which meant 3 gates were silently broken (not running, not failing — just skipped or erroring silently). The audit fixes the PYTHONPATH, the test count jumps, and previously-"passing" gates now fail. The v1.5 audit may inherit a new variant of this regression if v1.4's fix was incomplete or if a new service/package was added without updating the gate runner.

**Why it happens:**
The gate runner is a Python script that manually sets `PYTHONPATH` for each gate. Every time a new service or package is added, the runner must be updated with the new path. This is a manual, error-prone process with no test-the-test mechanism. If a path is missing, the gate either silently skips (if the script catches `ImportError`) or errors in a way that looks like a test failure rather than a configuration failure. The v1.4 audit explicitly called this out as tech debt: "V2 gate runner was missing platform_contract and platform_runtime PYTHONPATH entries for wecom-service, conversation-read-view, and feedback-service gates since v1.2."

**How to avoid:**
1. **First action of the v1.5 audit:** Verify `scripts/run_v2_gates.py` covers all 4 services and 7 packages with correct PYTHONPATH entries. Cross-reference against `services/` and `packages/` directories.
2. **Add a meta-gate:** The gate runner should have a self-check that verifies every expected gate can import its dependencies before running tests. If a gate can't import, it should fail loudly, not silently skip.
3. **Capture the real baseline:** After confirming the gate runner is correct, record the exact test count per gate. This is the true baseline. Any gap closure that changes this number must explain the delta.
4. **Check for new services/packages:** If v1.4 added any service or package that isn't in the gate runner, the "424 tests" number is already stale.

**Warning signs:**
- The gate runner has fewer gate entries than there are services + packages.
- A gate reports "0 tests collected" or "skipped" — this is not "passing," it's "not running."
- The test count hasn't changed across milestones despite code being added — gates may be silently excluded.
- `ImportError` or `ModuleNotFoundError` appears in gate output but is counted as "pass" because the script catches all exceptions.

**Phase to address:**
v1.5 Phase 1 (audit) — gate runner verification must be the very first audit step, before any requirement traceability work, because the gate suite is the evidence source for the entire audit.

---

### Pitfall 5: Overstating readiness — marking the readiness report "ready for V2 acceptance" when only autonomous code closure is complete

**What goes wrong:**
The v1.5 milestone closes all code gaps, updates PROJECT.md traceability, and produces a readiness report. The report says "V2 is ready for acceptance; only Phase 5 and Phase 8 remain." But the report doesn't clearly distinguish between:
- **Autonomous closure complete** (code gaps closed, tests pass, traceability updated) — this is what v1.5 delivers.
- **V2 formally accepted** (Phase 5 live WeCom UAT passed + Phase 8 five-workday lawyer trial passed with metrics) — this requires human execution and legal judgment.

The report's wording implies V2 is "done" or "accepted," when in reality two human gates that have been carried forward since v1.0 (Phase 8) and v1.1 (Phase 5) are still open. A stakeholder reading the report believes V2 is accepted and starts planning M2 work, when no lawyer has ever used the InkStatute WeCom service in production.

**Why it happens:**
Every prior milestone audit (v1.1–v1.4) has explicitly noted "Phase 8 lawyer trial and Phase 5 live WeCom UAT remain parallel human gates, not [milestone] dependencies." This has been said so many times that it risks becoming boilerplate — a checkbox line at the bottom of the report that no one reads seriously. The v1.5 milestone goal itself says "so that only the Phase 5 live WeCom UAT and Phase 8 five-workday lawyer trial human gates remain before V2 is formally accepted," which is correct, but the readiness report must not blur the line between "code is ready for those gates" and "those gates have passed."

**How to avoid:**
The readiness report must use a **two-tier status model**:
1. **Autonomous closure status:** READY / NOT READY — are all code gaps closed, tests passing, traceability updated? This is what v1.5 can claim.
2. **V2 acceptance status:** BLOCKED ON HUMAN GATES — Phase 5 (live WeCom UAT) and Phase 8 (five-workday lawyer trial) are explicitly listed as not-started, with their acceptance criteria quoted verbatim from V2-PRD §10.4. The report must state: "V2 cannot be formally accepted until both human gates pass. This report certifies code readiness, not V2 acceptance."

The report must also list the **specific evidence** that each human gate requires (from V2-PRD §10.4):
- Phase 5: live WeCom end-to-end (send task → InkStatute ACK → Hermes agent → reply/file/card → feedback → FeedbackEvent), using InkStatute WeCom service, not Hermes gateway.
- Phase 8: ≥1 lawyer, 5 workdays, ≥15 real tasks (≥12 with business output), ≥3 task types, long-task success ≥80%, normal-task success ≥85%, feedback collection ≥60%, positive feedback ≥60%, route_mismatch ≤3, no Hermes meta/gateway/update/command leakage to users.

**Warning signs:**
- The readiness report uses the word "accepted" or "complete" without the qualifier "code closure" or "autonomous."
- The report doesn't quote the Phase 5 and Phase 8 acceptance criteria verbatim.
- The report lists human gates as "remaining" but doesn't state they are **not started** and require **human execution** that cannot be substituted by fixtures or tests.
- A stakeholder asks "when does M2 start?" after reading the report — the report should make clear that M2 is blocked on V2 acceptance, which is blocked on human gates.

**Phase to address:**
v1.5 Phase 3 (readiness report) — the report template must enforce the two-tier status model and verbatim human-gate criteria.

---

### Pitfall 6: Understating readiness — leaving requirements unchecked that are already satisfied, inflating the perceived gap and blocking V2 acceptance unnecessarily

**What goes wrong:**
The auditor is conservative and leaves requirements unchecked unless there's a perfect 1:1 match between the requirement text and a shipped artifact. "Build read-only conversation/task/feedback APIs from contract logs" is left unchecked because `conversation-read-view` exists but doesn't expose a REST API — only Python query functions. "Enforce composability and industry-neutral contract behavior in CI" is left unchecked because the CI gate exists but doesn't explicitly run non-legal synthetic tasks. The readiness report then lists 6+ "genuine gaps" when only 2–3 are real, and the milestone plan adds phases to rebuild capabilities that already exist in a slightly different form. This delays V2 acceptance by weeks and risks the regressions described in Pitfall 3.

**Why it happens:**
Conservatism feels safe in a legal-tech context — "better to say it's missing than to claim it's done and be wrong." But false negatives are just as harmful as false positives: they waste milestone time on redundant work, they introduce regression risk by modifying working code, and they erode confidence in the audit process. The auditor may also lack familiarity with the v1.1–v1.4 codebase (which was built across 4 milestones with different phase structures) and default to "not done" when in doubt.

**How to avoid:**
1. Use the traceability matrix from Pitfall 2's prevention strategy. A requirement is "validated" if its decomposed capabilities are each mapped to a shipped artifact with a file path and test reference.
2. For partial satisfaction (infrastructure exists but production wiring missing), use a **"partial"** status, not "gap." The v1.4 audit used this effectively: MEM-07 and MEM-16 were "partial" (infrastructure present, wiring missing), which correctly scoped the gap closure to just the wiring, not a rebuild.
3. For the specific V2 Active requirements, apply this decision rule:
   - "Build read-only conversation/task/feedback APIs from contract logs" → if `conversation-read-view` has Python query functions backed by contract logs and tests, the requirement is **partial** (API surface is library-level, not REST). Gap closure = add minimal REST/API surface if PRD §10.2 requires it, not rebuild the read view.
   - "Enforce composability and industry-neutral contract behavior in CI" → if `v2-contract-gates.yml` runs schema validation and `contract-test-suite` has non-legal fixtures, the requirement is **partial** if non-legal synthetic tasks aren't in CI. Gap closure = add non-legal fixtures to the CI job, not rebuild the test suite.
4. Distinguish "doesn't exist" from "exists but not wired" from "exists and wired but not tested in CI." Each has a different gap-closure cost.

**Warning signs:**
- The audit identifies more than 3–4 genuine gaps despite v1.1–v1.4 shipping 4 milestones with 424+ tests. If the audit finds 8+ gaps, it's likely over-counting.
- A "gap" requires building a new module from scratch when a similar module already exists in a different service.
- The gap-closure plan is larger than the original v1.1 platform foundation (5 phases, 20 plans) — V2 gap closure should be smaller than the original build.
- The auditor says "I can't find it" rather than "I found it here but it's not wired into X."

**Phase to address:**
v1.5 Phase 1 (audit) — the audit must use a three-status model: **validated** (fully satisfied + wired), **partial** (infrastructure exists, wiring/CI/production path missing), **gap** (capability genuinely absent). Only "gap" triggers new build work.

---

### Pitfall 7: Conflating autonomous closure with human gate closure in PROJECT.md traceability

**What goes wrong:**
The v1.5 milestone updates PROJECT.md to move validated requirements from Active to Validated. In doing so, the "Complete the five-workday lawyer trial acceptance criteria" requirement gets moved to Validated with a note like "code readiness verified; trial pending." This makes it look like the lawyer trial is done when it hasn't started. Alternatively, the requirement stays in Active but gets a `[x]` checkmark, which is even worse — the checkbox implies completion. A future reader of PROJECT.md sees 12/12 Active requirements checked and concludes V2 is accepted.

**Why it happens:**
The PROJECT.md Active section uses `[x]` / `[ ]` checkboxes. The v1.5 milestone's instinct is to check off everything that's been audited. But "Complete the five-workday lawyer trial acceptance criteria" is a **human gate requirement** — it cannot be checked by code audit or test passage. The same applies to any requirement whose satisfaction depends on Phase 5 live WeCom UAT evidence. The checkbox format doesn't distinguish "code-ready" from "human-gate-passed."

**How to avoid:**
1. **Never check `[x]` on a human gate requirement based on autonomous work.** The "Complete the five-workday lawyer trial acceptance criteria" requirement must remain `[ ]` until Phase 8 produces real trial evidence with metrics meeting V2-PRD §10.4 thresholds.
2. **Use a separate marker for "code-ready, human-gate-pending."** Either keep the checkbox unchecked with an annotation like `[ ] *(code-ready, human gate pending — see readiness report)*`, or move it to a new "Human Gate Pending" subsection distinct from both Active and Validated.
3. **Apply the same rule to any requirement that depends on live WeCom evidence.** The V2-PRD §10.4 acceptance criteria (long-task success ≥80%, normal-task success ≥85%, feedback collection ≥60%, no Hermes meta leakage to users) can only be verified through live usage, not fixtures. Requirements that implicitly depend on these metrics must not be checked until the trial passes.
4. **The STATE.md "Parallel Human Gate (v1.0)" section already models this correctly** — Phase 08 is marked `HUMAN_NEEDED` and carried forward. The v1.5 milestone must preserve this, not resolve it.

**Warning signs:**
- PROJECT.md shows all Active requirements as `[x]` after v1.5, including the lawyer trial requirement.
- A requirement is moved to Validated with a note containing "pending" or "awaiting" — if it's pending, it's not validated.
- The STATE.md human gate section is removed or marked "resolved" without trial evidence.
- The readiness report and PROJECT.md disagree on whether human gates are open.

**Phase to address:**
v1.5 Phase 2 (traceability update) — the PROJECT.md update plan must explicitly list which requirements are human-gate-dependent and must not be checked.

---

### Pitfall 8: V2-PRD §13 risk items treated as "resolved" because the integration spike is complete, when they are implementation-time risks that only surface during live WeCom

**What goes wrong:**
The PROJECT.md Validated section states "Phase 3 Hermes integration spike is complete: hook ordering is source-confirmed, AgentTurn strategy is documented, identifier/state/privacy/safety rules are defined." The auditor reads this and marks all §13 risks related to hook ordering, message_id stability, and long-task states as resolved. But the integration spike confirmed the risks **at the source level** — it didn't prove they're resolved in a live WeCom deployment. Risks like "message_id stability" (§13.3), "response_filter and template card association" (§13.5), and "WeCom service protocol risks" (§13.17) can only be fully resolved with live evidence from Phase 5 UAT.

**Why it happens:**
The PROJECT.md Validated section uses language like "source-confirmed" and "rules are defined" which is accurate for the spike but容易被误读 as "risk eliminated." The §13 risks are explicitly labeled "V2 实现期必须解决，不阻塞 PRD 定稿但阻塞开发" (must be resolved during implementation, not PRD finalization, but blocks development). Some were resolved during v1.1–v1.4 implementation (hook ordering, identifier rules, privacy rules). Others (message_id stability in live card callbacks, WeCom protocol correctness under real retry/dedup, long-task state signals from real Hermes logs) require live evidence that only Phase 5 can provide.

**How to avoid:**
1. For each §13 risk, classify it as: **source-resolved** (confirmed by code/spike, no live evidence needed), **implementation-resolved** (resolved by shipped code + tests, no live evidence needed), or **live-evidence-pending** (requires Phase 5 or Phase 8 to confirm).
2. Only mark a §13 risk as "resolved" in the readiness report if it's source-resolved or implementation-resolved. Live-evidence-pending risks must be listed as "mitigated in code, pending live confirmation" with the specific Phase 5/8 evidence that would confirm resolution.
3. Specific classification for high-risk items:
   - §13.1 (hook event ordering): implementation-resolved (Phase 3 spike + Phase 4 shadow layer + replay tests).
   - §13.2 (inbound event gaps): implementation-resolved (AgentTurn reverse-inference strategy documented and tested).
   - §13.3 (message_id stability): **live-evidence-pending** — the response_filter generates message_id and writes it to context, but card callback stability must be confirmed in live WeCom.
   - §13.5 (response_filter ↔ template card association): **live-evidence-pending** — one-card-per-reply must be confirmed in live WeCom with real template cards.
   - §13.14 (Hermes gateway as user channel boundary): implementation-resolved in code (output boundary), but **live-evidence-pending** for "no leakage to users" — only Phase 8 can confirm no lawyer ever sees a gateway/update/command notice.
   - §13.17 (WeCom service protocol risks): **live-evidence-pending** — callback verification, AES decryption, access token refresh, media download/upload, retry/dedup all need live WeCom evidence.

**Warning signs:**
- The readiness report says "all §13 risks resolved" without distinguishing source/implementation/live-evidence.
- A §13 risk is marked resolved but no test or fixture exercises it — only a source-code reading or spike document supports the claim.
- The report doesn't list which §13 risks Phase 5 or Phase 8 must confirm.
- "message_id stability" is marked resolved but no live card callback has ever been tested end-to-end through InkStatute WeCom service.

**Phase to address:**
v1.5 Phase 3 (readiness report) — the report must include a §13 risk classification table with source/implementation/live-evidence status per risk.

---

### Pitfall 9: Feedback dedupe and skill_candidate boundary errors — the legal safety trap

**What goes wrong:**
During gap closure for "Normalize Hermes feedback into FeedbackEvent records with dedupe, classification, and human-reviewed skill candidates," the developer implements dedupe using a naive hash of `(message_id, feedback_value)` and wires `skill_candidate` generation to automatically trigger `skillopt-runner`. The dedupe hash fails for button re-clicks that arrive through different network retries with slightly different callback payloads (same logical feedback, different transport metadata), producing duplicate `FeedbackEvent` records that inflate negative-feedback counts and corrupt Phase 8 metrics. Worse, the automatic `skillopt-runner` trigger violates the V2-PRD §13.11 constraint: "V2 只记录 `skill_candidate`，不得自动修改高风险法律 skill" — V2 records skill candidates only, never auto-modifies high-risk legal skills.

**Why it happens:**
Feedback dedupe (§13.6) is harder than it looks: the idempotency key must be stable across WeCom retry, button re-click, and shim multi-write scenarios, but the raw callback payload differs in each case. A naive content hash includes transport metadata that varies, producing false non-matches. The `skill_candidate` boundary is a legal safety rule, not a technical preference — but a developer focused on "closing the gap" may wire the feedback pipeline to the existing `skillopt-runner` auto-optimization flow because it already exists in Hermes, without checking whether V2's constraint explicitly forbids auto-modification.

**How to avoid:**
1. **Dedupe key design:** The idempotency key must be derived from **logical identity**, not raw payload. For WeCom feedback callbacks, the key should be `(target_message_id, button_key, user_id)` — stable across retries. Include a test that simulates: (a) WeCom retrying the same callback 3 times, (b) a user clicking the same button twice, (c) the shim writing twice. All must produce exactly one `FeedbackEvent`.
2. **skill_candidate boundary:** The feedback pipeline must write `skill_candidate` records to a **pending review queue** with no path to automatic skill modification. Add a test that verifies no `skillopt-runner` invocation is triggered by `FeedbackEvent` processing. Add a guard: `FeedbackService` must not import or call `skillopt-runner` or any skill modification function.
3. **Legal safety audit:** The readiness report must explicitly state: "V2 records `skill_candidate` for human review only. No automatic legal skill synthesis or modification is wired. `FeedbackService` does not invoke `skillopt-runner`." This is a legal compliance claim, not just a technical one.

**Warning signs:**
- The dedupe test only checks "same payload twice" — not "same logical feedback via different transport paths."
- `FeedbackService` imports anything from `skillopt-runner` or skill modification modules.
- `skill_candidate` records are written with a `status=auto_applied` or similar field.
- The feedback pipeline has any code path that modifies skill files, skill configs, or routing rules.
- A test claims to verify "no auto-modification" but only checks a flag, not the absence of import/call paths.

**Phase to address:**
v1.5 Phase 2 (gap closure) — feedback-service gap closure must include dedupe multi-path tests and a skill_candidate isolation guard. Phase 3 (readiness report) must include the legal safety compliance statement.

---

### Pitfall 10: CI fixture representativeness — the gate suite passes but doesn't cover the V2-PRD §10.2/§10.3 acceptance scenarios

**What goes wrong:**
The V2 gate suite (`v2-contract-gates.yml` + `run_v2_gates.py`) passes with 424+ tests, and the audit cites this as evidence that "Enforce composability and industry-neutral contract behavior in CI" is satisfied. But the gate suite tests schema validation, happy-path fixture replay, and unit-level behavior — it doesn't include the V2-PRD §10.3 synthetic task set (route error simulation, long-task failure, feedback duplicate click, non-legal tasks) or the §10.2 output boundary fixture (gateway/update/command/meta samples must be blocked or rewritten). The CI gate passes but doesn't actually verify the acceptance criteria. Phase 8 live trial then discovers that route mismatches aren't logged correctly or that non-legal tasks cause schema errors.

**Why it happens:**
The gate suite was built incrementally across v1.1–v1.4, with each milestone adding tests for its own scope. No milestone explicitly added the §10.3 synthetic task set because it was "Phase 8 work" (CI + composability acceptance, step 8 in the V2 development order). The v1.5 audit checks "does CI pass?" (yes) but doesn't check "does CI test what V2-PRD §10.2/§10.3 requires?" (partially). The gap is invisible because the gate suite is large (424+ tests) and passes, creating a false sense of coverage.

**How to avoid:**
1. Map each V2-PRD §10.2 and §10.3 acceptance criterion to a specific CI test or fixture. If no test maps to a criterion, that's a gap.
2. §10.2 required CI coverage:
   - Callback verification/decryption fixtures — verify present.
   - ACK behavior — verify present.
   - Inbound normalization — verify present.
   - Outbound policy (output boundary) — verify present, with gateway/update/command/meta samples.
   - Send envelope construction — verify present.
   - Feedback callback idempotency — verify present (see Pitfall 9).
   - No-secret logging — verify present.
   - Schema validation (5 schemas, fields, enums, required) — verify present.
   - Fixture replay (golden examples) — verify present.
   - Relationship integrity (`message → task → route → response → feedback` chain, breakage ≤5%) — verify present.
   - Contract log coverage ≥95% (AgentTurn + AgentResult co-occurrence) — verify present.
   - Output boundary fixture (backend notices blocked/rewritten) — **likely missing or partial**.
3. §10.3 required synthetic tasks:
   - Simple legal QA (short task) — verify present.
   - Contract review (long task + skill + gate + Artifact) — verify present.
   - Legal retrieval (MCP tool trace) — verify present.
   - Route error simulation (human-tagged `route_mismatch`) — **likely missing**.
   - WeCom feedback (template card → FeedbackEvent) — verify present.
   - Long-task failure (`AsyncTask.status=failed` + read view) — **likely missing**.
   - Non-legal synthetic tasks (财税/工程/教育) — **likely missing or partial**.
4. Gap closure for this requirement = adding the missing fixtures to the CI job, not building new infrastructure.

**Warning signs:**
- The gate suite passes but no test name contains `route_mismatch`, `async_task_failed`, `non_legal`, or `output_boundary`.
- The CI job only runs schema validation and happy-path replay, not synthetic task composition.
- No fixture file exists for "gateway restart notice" or "Hermes update command" output boundary test cases.
- The "non-legal synthetic task" test only checks schema validity, not that legal fields don't leak to top-level required fields.

**Phase to address:**
v1.5 Phase 2 (gap closure) — CI fixture representativeness is likely the largest genuine gap. The gap-closure plan must add missing §10.2/§10.3 fixtures before the readiness report claims CI composability is satisfied.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Marking a requirement "validated" based on module existence + unit tests, without checking production wiring | Faster audit, fewer "partial" statuses to investigate | False positive — gap surfaces during live UAT, erodes trust in audit process | Never for V2 acceptance closure — production wiring is the acceptance criterion |
| Leaving a requirement unchecked because the shipped code uses different vocabulary than the PRD | Conservative, "safe" | False negative — redundant rebuild, regression risk, delayed acceptance | Never — build a traceability matrix first |
| Checking `[x]` on human-gate requirements after code closure | Clean-looking PROJECT.md | Implies V2 is accepted when human gates haven't run | Never — human gate requirements must remain unchecked until human evidence exists |
| Treating the V2 gate suite test count as a stable baseline without verifying the gate runner's PYTHONPATH | Faster — skip gate runner audit | Silent regressions — broken gates counted as passing (happened v1.2–v1.4) | Never — verify gate runner before relying on it |
| Using a naive payload hash for feedback dedupe | Simple to implement | Duplicate FeedbackEvents corrupt Phase 8 metrics, inflate negative feedback | Never — use logical identity key, test multi-path dedupe |
| Wiring skill_candidate to skillopt-runner for "end-to-end" feedback loop | Demonstrates full pipeline | Violates V2-PRD §13.11 legal safety constraint — auto-modifies legal skills | Never in V2 — skill_candidate is human-review-only |
| Citing "424 tests pass" without mapping tests to V2-PRD §10.2/§10.3 criteria | Quick readiness claim | CI passes but doesn't cover acceptance scenarios — gaps surface in Phase 8 | Never — map each criterion to a test before claiming CI coverage |

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| WeCom callback protocol | Assuming the gate suite's synthetic callbacks match real WeCom payload format/encryption | Verify callback verification/decryption fixtures use real WeCom payload structure (XML, AES-encrypted, signed). Live-evidence-pending until Phase 5. |
| WeCom template card feedback | Assuming message_id from response_filter is stable through card callback | §13.3 risk — confirm message_id round-trips through card dispatch → button click → callback. Live-evidence-pending. |
| Hermes hook ordering | Assuming `contract_result_recorder` always runs after `response_filter` | §13.1/§13.13 — source-confirmed in spike, but verify with replay tests that include multiple hooks on `agent:end`. If ordering unstable, merge recorder into response_filter (higher coupling, guaranteed order). |
| Hermes gateway send paths | Assuming `agent:end` is the only outbound path | §13.14 — gateway restart/update/delivery-failure/memory-progress all bypass `agent:end`. Output boundary must sit in InkStatute WeCom egress, not in Hermes hook. |
| Hermes version drift | Assuming the current Hermes version's hooks/adapters/APIs are stable | §13.15 — agent adapter must maintain compatibility matrix + capability probe. Versions lacking agent-invocation/no-channel-IO capability must fail live WeCom acceptance. |
| Hermes profile bundle | Copying the live lawfirm profile directly into a bootstrap bundle | §13.16 — must generate sanitized bundle (no secrets, DBs, logs, customer files, machine paths) + external secrets/env manifest + bootstrap check. |
| feedback.jsonl compatibility | Assuming the existing Hermes feedback.jsonl format matches FeedbackEvent schema | Normalize, don't assume field equivalence. The compatibility path is a migration input, not a schema authority. |
| Long-task state signals | Assuming Hermes logs expose queued/running/waiting_for_user/failed/succeeded cleanly | §13.4 — verify which Hermes log lines map to each async state. If signals are missing, contract layer may need to synthesize states from indirect evidence. |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Contract log write on every event without batching | WeCom 5s ACK timeout under load | Buffer/batch contract log writes; ACK must complete before log write blocks | >10 concurrent lawyer sessions |
| Feedback dedupe via full-table scan per callback | Feedback callback latency spikes | Index dedupe key; use in-memory LRU for recent callbacks | >1000 feedback events |
| Conversation read view built from full contract log scan per query | API response time >2s for history queries | Pre-materialize read view indices; invalidate on new events | >10k contract log entries |
| Memory recall blocking WeCom turn dispatch | Lawyer waits >5s for simple QA response | Keep memory recall fail-open with timeout; pre-turn recall must not block ACK | Hindsight latency >2s or provider quota exhausted |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing raw legal payloads in contract logs for "coverage" | Customer legal documents, work product, and case materials exposed in logs | §13.7/§13.8 — use `raw_payload_ref` only; never store sensitive full text. Coverage ≥95% must not be achieved by writing sensitive content to logs. |
| Committing sanitized profile bundle that still contains machine-absolute paths | Path leakage reveals server structure; bundle fails reproducibility check on new server | §13.16 — bootstrap check must verify no absolute paths; use relative paths + env vars. |
| Logging WeCom access tokens, encoding AES keys, or callback secrets in debug output | Token leakage → WeCom account compromise | Output boundary + no-secret logging test must cover debug/log paths, not just user-facing messages. |
| Allowing Hermes gateway notices to reach lawyer WeCom as "harmless system messages" | Gateway/update/command notices expose Hermes internals to end users; violates V2 user boundary | §13.14 — output boundary must block/rewrite ALL non-agent-end output, not just obvious meta notices. |
| Auto-modifying legal skills based on feedback without human review | Incorrect legal conclusions propagated to all future lawyer tasks | §13.11 — `skill_candidate` is human-review-only. No code path from FeedbackEvent to skill modification. Guard with import/call path test. |
| WeCom callback replay attack via captured encrypted payload | Attacker replays valid callback to trigger agent turns or feedback | Idempotency key must include WeCom MsgId + timestamp window; reject duplicates outside acceptable replay window. |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Lawyer sees Hermes "restarting" or "updating" notice in WeCom | Confusion — "is this my assistant or a system admin message?" | Output boundary converts to InkStatute-owned "服务暂时不可用，请稍后重试" or drops entirely |
| Lawyer receives no ACK within 5s for long task | User re-sends the same task, creating duplicate turns | WeCom service must 5s ACK every callback; long-task result pushed asynchronously with "正在处理中" interim notice |
| Lawyer clicks feedback button twice and sees two "thanks" confirmations | User doubts whether feedback was registered | Dedupe + single confirmation; idempotent UX response |
| Lawyer's feedback "route is wrong" produces no visible acknowledgment | User stops giving feedback; route quality doesn't improve | Record `route_mismatch` + `skill_candidate`, respond with "已记录，感谢反馈" — but never auto-modify the skill |
| Lawyer sees raw skill name or internal route decision in WeCom | Exposes platform internals; feels like a debug tool, not an assistant | Output boundary strips internal identifiers; user sees only lawyer-assistant language |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **WeCom service:** Often missing `idempotency` for retry/duplicate callbacks — verify dedupe key exists and is tested with replay scenarios, not just happy-path single callback.
- [ ] **WeCom service:** Often missing `output_policy` in the actual egress path — verify `send_message` routes through `OutputPolicy` for every message type (text, file, card, status), not just text.
- [ ] **Output boundary:** Often missing gateway/update/command/meta fixture cases — verify test suite includes Hermes restart notice, update prompt, command help, delivery failure, memory/tool progress payloads, not just clean agent replies.
- [ ] **Feedback service:** Often missing multi-path dedupe test — verify test covers WeCom retry, button re-click, and shim multi-write, not just "same payload twice."
- [ ] **Feedback service:** Often missing `skill_candidate` isolation guard — verify no import/call path to `skillopt-runner` or skill modification functions.
- [ ] **Conversation read view:** Often missing REST/API surface — verify requirement is satisfied by query functions if PRD only requires read access, or add minimal API if §10.2 implies external consumability.
- [ ] **CI composability:** Often missing non-legal synthetic tasks — verify CI runs 财税/工程/教育 tasks that return valid `AgentResult` without requiring legal fields.
- [ ] **CI composability:** Often missing route_mismatch and long-task-failure fixtures — verify CI includes non-happy-path synthetic tasks per §10.3.
- [ ] **Contract log coverage:** Often missing the ≥95% AgentTurn+AgentResult co-occurrence check — verify a CI test measures this metric, not just that both schemas validate.
- [ ] **Hermes agent adapter bootstrap:** Often missing sanitized profile bundle reproducibility check — verify bootstrap check runs on a clean environment, not just the dev machine.
- [ ] **Gate runner:** Often missing PYTHONPATH entries for new services — verify `run_v2_gates.py` covers all 4 services + 7 packages, and that "0 tests collected" is treated as failure.
- [ ] **Traceability:** Often missing the PROJECT.md update itself — v1.4 audit found all 20 requirement rows showed "Not started" despite all phases passing. Verify the traceability table is actually updated, not just the audit report.

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| False positive — requirement marked validated but production wiring missing | MEDIUM | Re-audit the specific requirement at production-wiring level; add integration test for the full path; mark as "partial" in PROJECT.md until wiring is confirmed |
| False negative — requirement left unchecked but already satisfied | LOW | Build traceability matrix; map capability to shipped artifact; move to Validated with file references; no code change needed |
| Gap closure regression — shipped test broken by V2 change | MEDIUM | Revert the change; add test-first for new behavior; re-apply change; run full gate suite; investigate whether broken test encoded a valid assumption |
| PYTHONPATH gate runner regression | LOW | Add missing PYTHONPATH entries; re-run all gates; record true baseline; add self-check to gate runner |
| Readiness report overstates acceptance | LOW (report fix) / HIGH (if stakeholder acted on it) | Re-issue report with two-tier status model; explicitly list human gates as not-started; communicate correction to stakeholders |
| Human gate requirement checked in PROJECT.md | LOW | Uncheck the requirement; add annotation "code-ready, human gate pending"; update STATE.md to preserve human gate status |
| §13 risk marked resolved without live evidence | LOW | Re-classify as "mitigated in code, pending live confirmation"; list specific Phase 5/8 evidence needed |
| Feedback dedupe failure corrupting Phase 8 metrics | MEDIUM | Fix dedupe key to logical identity; re-process feedback events; recompute metrics; add multi-path dedupe test |
| skill_candidate auto-modification violation | HIGH | Immediately disable auto-modification path; audit all skill changes made since the violation; revert unauthorized changes; add import/call guard test; document in readiness report as a legal safety incident |
| CI fixture representativeness gap | MEDIUM | Add missing §10.2/§10.3 fixtures to CI job; run gate suite; update readiness report to reflect actual CI coverage |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. False positive (production wiring missing) | v1.5 Phase 1 (audit) | Audit plan mandates three-level verification; each validated requirement has a production-path line reference |
| 2. False negative (different vocabulary) | v1.5 Phase 1 (audit) | Traceability matrix delivered before gap classification; each requirement mapped to file+test |
| 3. Gap closure regression | v1.5 Phase 2 (gap closure) | Pre-change baseline captured; test-first; full gate suite run after each change |
| 4. PYTHONPATH gate runner regression | v1.5 Phase 1 (audit) | Gate runner verified as first audit step; self-check added; true baseline recorded |
| 5. Overstating readiness | v1.5 Phase 3 (readiness report) | Two-tier status model; human gates listed as not-started with verbatim §10.4 criteria |
| 6. Understating readiness | v1.5 Phase 1 (audit) | Three-status model (validated/partial/gap); partial status used for infrastructure-present-wiring-missing |
| 7. Human gate conflation in PROJECT.md | v1.5 Phase 2 (traceability update) | Human-gate requirements explicitly listed as must-not-check; STATE.md human gate section preserved |
| 8. §13 risk misclassification | v1.5 Phase 3 (readiness report) | §13 risk classification table with source/implementation/live-evidence status per risk |
| 9. Feedback dedupe + skill_candidate boundary | v1.5 Phase 2 (gap closure) | Multi-path dedupe test; skill_candidate isolation guard test; legal safety statement in report |
| 10. CI fixture representativeness | v1.5 Phase 2 (gap closure) | §10.2/§10.3 criterion-to-test mapping; missing fixtures added to CI job |

## Sources

- V2-PRD §13 遗留风险与未决问题 (17 risks) — `docs/requirements/V2-PRD.md:688-708`
- V2-PRD §10 验收标准 (acceptance criteria) — `docs/requirements/V2-PRD.md:586-634`
- V2-PRD §12 V2 开发顺序与依赖图 — `docs/requirements/V2-PRD.md:645-686`
- PROJECT.md Active requirements (10 unchecked) — `.planning/PROJECT.md:43-52`
- PROJECT.md Constraints (legal safety, privacy, user-facing output) — `.planning/PROJECT.md:74-84`
- v1.4 Milestone Audit (PYTHONPATH regression, partial requirements, traceability table not updated) — `.planning/milestones/v1.4-MILESTONE-AUDIT.md`
- v1.2 Milestone Audit (Nyquist gaps, tech_debt status, E2E closure) — `.planning/milestones/v1.2-MILESTONE-AUDIT.md`
- MILESTONES.md (shipped v1.1–v1.4 history, deferred items, human gate carry-forward) — `.planning/MILESTONES.md`
- STATE.md (Phase 08 human gate carried forward, deferred items) — `.planning/STATE.md`
- AGENTS.md (legal safety rules, output boundary, skill_candidate constraint, coding rules) — `AGENTS.md`
- V2 gate runner — `scripts/run_v2_gates.py`, `.github/workflows/v2-contract-gates.yml`

---
*Pitfalls research for: V2 acceptance closure (InkStatute v1.5)*
*Researched: 2026-07-03*
