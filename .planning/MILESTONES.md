# Project Milestones: 墨律 InkStatute

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

**What's next:** Next milestone — TBD via `/gsd-new-milestone`

---
