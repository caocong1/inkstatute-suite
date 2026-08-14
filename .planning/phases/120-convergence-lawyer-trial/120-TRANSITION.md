---
phase: 120-convergence-lawyer-trial
next_step: gsd-complete-milestone (after human gate signatures)
milestone: v4.0 technically complete
human_gates_pending: [HG-1, HG-3, HG-4]
---

# Phase 120 Transition: Milestone Completion

## What Phase 120 Delivered

- Opt-in, desensitized telemetry with engine health probe (PKG-03)
- Offline behavior with last-good engine+content fallback (PKG-04)
- v3.x freeze annotation for 9 platform components (LEG-01)
- Human gate signing process for HG-1, HG-3, HG-4 (never auto-signed)
- Retirement plan ready for execution after lawyer trial (LEG-02)
- Full milestone audit documenting all phases, requirements, and safety assertions

## Milestone v4.0 Completion Status

**All technical work is complete.** The milestone is ready for completion via `gsd-complete-milestone` after the three human gates are signed:

1. **HG-1**: Lawyer sampling to confirm V4 legal quality baseline ≥ lawyer-desktop/Hermes baseline
2. **HG-3**: 5 business day lawyer trial with 15 real tasks
3. **HG-4**: Lawyer confirmation that track-changes docx is usable for external negotiation

## What Happens After Human Gates Are Signed

1. All three gates signed → `RetirementPlan.canRetire` returns true
2. Execute `RetirementPlan.executeRetirement()` to remove v3.x components (LEG-02)
3. Archive v3.0/v3.1 documentation to `milestones/`
4. Run `gsd-complete-milestone` to archive the v4.0 milestone
5. Run `gsd-cleanup` to clean up phase directories

## Carry-Forward to Post-v4.0

- The app is feature-complete for the v4.0 release
- Engine manifest and docx-golden gates will activate when the DSH engine is built and Python is bundled
- The real-api E2E path (GATE-03) requires a DEEPSEEK_API_KEY for full validation
- The Windows installer requires Inno Setup to build on a Windows machine
- Portable Python must be downloaded and bundled during the Windows build process

## Key Artifacts

- Milestone audit: `.planning/phases/120-convergence-lawyer-trial/120-AUDIT.md`
- Phase summaries: `.planning/phases/*/1*-SUMMARY.md`
- V4 gate runner: `scripts/run_v4_gates.py`
- Build script: `scripts/build_windows_installer.sh`
- Installer: `scripts/inkstatute_installer.iss`
- DSH pin: `engines/dsh-pin.txt`
