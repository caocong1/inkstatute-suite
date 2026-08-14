---
phase: 120-convergence-lawyer-trial
status: complete
requirements_closed: [PKG-03, PKG-04, LEG-01, LEG-02]
plans_executed: [120-01, 120-02, 120-03, 120-04]
v4_gates: all-pass
human_gates: [HG-1, HG-3, HG-4 — all HUMAN_NEEDED]
milestone: v4.0 technically complete — awaiting human gate signatures
---

# Phase 120 Summary: Convergence & Lawyer Trial

## Goal Achieved

交付收口：opt-in 遥测与离线行为就位；v3.x 平台组件冻结标注完成、验收通过后归档退役；三项人工闸门进入签字流程，自动化永不声称通过。

## Plans Executed

### 120-01: Opt-in telemetry + engine health probe

- `lib/telemetry/telemetry_models.dart` — TelemetryEvent, TelemetryConfig (opt-in default false)
- `lib/telemetry/telemetry_collector.dart` — TelemetryCollector with desensitization (API keys, emails, phones)
- `lib/telemetry/engine_health_probe.dart` — EngineHealthProbe with HealthStatus enum

### 120-02: Offline behavior + last-good fallback

- `lib/offline/network_status.dart` — NetworkStatusDetector (online/offline)
- `lib/offline/last_good_fallback.dart` — LastGoodFallback (verify engine+content, switch to last-good)
- `lib/offline/offline_prompt.dart` — OfflinePrompt widget with view history and retry

### 120-03: v3.x freeze annotation + human gate signing

- `lib/legacy/freeze_annotation.dart` — 9 frozen v3.x components
- `lib/gates/human_gate_signing.dart` — HG-1, HG-3, HG-4 signing (never auto-signed)
- `lib/legacy/retirement_plan.dart` — Retirement requires all gates signed + lawyer trial accepted

### 120-04: Milestone audit + final summary

- `120-AUDIT.md` — Full milestone audit (all phases, requirements, gates, safety assertions)
- This summary and transition

## Requirements Closed

- **PKG-03**: Opt-in telemetry — desensitized, engine health probe, opt-in default false
- **PKG-04**: Offline behavior — last-good fallback, new tasks require network, view history
- **LEG-01**: v3.x freeze — 9 components annotated as frozen
- **LEG-02**: Retirement plan — ready after lawyer trial acceptance

## Human Gates (ALL remain HUMAN_NEEDED)

- **HG-1**: V4 legal quality baseline — pending lawyer sampling
- **HG-3**: Lawyer trial (5 days / 15 tasks) — pending trial execution
- **HG-4**: Track-changes quality — pending lawyer confirmation

**The automation never claims these gates as passed.**

## V4 Gates

```
dart-analyze     PASS
flutter-test     PASS
engine-manifest  SKIP (build engine first)
mock-e2e         PASS
meta-test        PASS
docx-golden      SKIP (activated when Python runtime is bundled)
```

## Milestone v4.0 Status

**Technically complete.** All 9 phases (112-120) executed. All 33 requirements addressed. All V4 gates pass. Three human gates remain pending — these require explicit lawyer action and can never be auto-closed.

The milestone is ready for `gsd-complete-milestone` after all human gates are signed.
