---
phase: 119-first-run-wizard-windows-packaging
next_phase: 120-convergence-lawyer-trial
carry_forward:
  - All v4.0 phases (112-119) complete
  - Human gates HG-1, HG-4, HG-3 remain HUMAN_NEEDED
  - v3.x platform freeze (LEG-01) ready for retirement (LEG-02)
  - Full pipeline ready for lawyer trial
---

# Phase 119 Transition: Packaging → Convergence

## What Phase 119 Delivered

- First-run wizard (3 steps: practice area → API key → model confirmation)
- Credential security (OS credential store, zero plaintext, owner mode)
- Windows packaging (Inno Setup installer, shortcuts, clean uninstall)
- Three-layer update orchestrator (engine auto-update disabled)
- App startup coordination (wizard → engine → chat UI)

## What Phase 120 (Convergence & Lawyer Trial) Needs

Phase 120 is the final phase of milestone v4.0:

1. **Opt-in telemetry (PKG-03)**: Health/crash telemetry, opt-in, desensitized
2. **Offline behavior (PKG-04)**: Last-good engine+content can start, view history
3. **v3.x freeze (LEG-01)**: Mark all v3.x components as frozen/retired
4. **v3.x retirement (LEG-02)**: Archive after lawyer trial acceptance
5. **HG-1 (Legal quality baseline)**: Lawyer confirmation — HUMAN_NEEDED
6. **HG-4 (Track-changes quality)**: Lawyer confirmation — HUMAN_NEEDED (from Phase 118)
7. **HG-3 (Lawyer trial)**: 5 business days / 15 real tasks — HUMAN_NEEDED

## Carry-Forward Notes

- All technical phases (112-119) are complete
- The app is feature-complete for v4.0
- Three human gates remain open and must NOT be auto-closed
- v3.x platform components are frozen but not yet retired
- The full pipeline works: DSH engine → ACP → chat UI → guardrails → Word export
- First-run wizard → zero-terminal zero-config experience is ready
- Windows installer script is ready (needs Inno Setup to build on Windows)
- Three-layer update system is ready (engine never auto-updates)

## Architecture Decisions for Phase 120

- Telemetry is opt-in only, desensitized, reference-first
- Offline mode uses last-good engine+content for viewing history
- v3.x retirement only after lawyer trial acceptance (LEG-02)
- All three human gates (HG-1, HG-3, HG-4) enter signing process
- Automation never claims human gates passed
