---
phase: 120-convergence-lawyer-trial
created: 2026-08-14
status: planning
requirements: [PKG-03, PKG-04, LEG-01, LEG-02]
depends_on: [119]
human_gates: [HG-1, HG-3, HG-4]
---

# Phase 120: Convergence & Lawyer Trial — Context

## Goal

交付收口：opt-in 遥测与离线行为就位；v3.x 平台组件冻结标注完成、验收通过后归档退役；三项人工闸门（HG-1 法律质量、HG-4 修订稿质量、HG-3 律师试运行）进入签字流程，自动化永不声称通过。

## Requirements

- **PKG-03**: 健康/崩溃遥测 — opt-in、脱敏上传；引擎健康探针（initialize 握手）内嵌；业主远程日志路径
- **PKG-04**: 离线行为 — last-good 引擎+内容可启动、可看历史；新任务需联网并明确提示
- **LEG-01**: v3.x 平台冻结 — 标注 frozen，不进 V4 交付物与门禁，不新开工
- **LEG-02**: 收敛 — 律师试运行验收后移除退役目录；v3.0/v3.1 文档归档到 milestones/

## Success Criteria

1. 遥测：opt-in、脱敏（无密钥/无客户全文/无原始 payload）；引擎健康探针；业主远程日志路径
2. 离线行为：断网可启动、可看历史、新任务明确提示"需联网"
3. LEG-01 冻结标注：v3.x 组件在 README + MILESTONES 标 frozen；v4 门禁不覆盖冻结代码
4. LEG-02 收敛：律师试运行验收通过后移除退役目录；v3.0/v3.1 文档归档
5. **HG-3**: 五工作日 / 15 真实任务律师试运行记录签字
6. **HG-1**: V4 基线法律质量经律师抽样确认不低于 lawyer-desktop/Hermes 基线
7. **HG-4**: 随 Phase 118 验收一并签字
8. v4 门禁全绿
9. Milestone audit 与归档完成

## Human Gates (NEVER auto-close)

- **HG-1**: V4 基线法律质量 — 律师抽样确认
- **HG-3**: 律师试运行 — 五工作日 / 15 真实任务
- **HG-4**: 修订稿质量 — 律师确认可用于对外谈判 (from Phase 118)

## Plan Structure

- **120-01**: Opt-in telemetry + engine health probe (PKG-03)
- **120-02**: Offline behavior + last-good fallback (PKG-04)
- **120-03**: v3.x freeze annotation + LEG-01/LEG-02 + human gate signing process
- **120-04**: Milestone audit + final summary
