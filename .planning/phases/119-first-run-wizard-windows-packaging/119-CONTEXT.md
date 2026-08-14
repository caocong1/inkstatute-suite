---
phase: 119-first-run-wizard-windows-packaging
created: 2026-08-14
status: planning
requirements: [APP-06, DSH-05, PKG-01, PKG-02]
depends_on: [115, 116, 117, 118]
---

# Phase 119: First-Run Wizard & Windows Packaging — Context

## Goal

"电脑白痴双击即用"的交付形态：首启向导（执业方向 → 密钥 → 模型确认）之后零终端零配置；单 exe 安装包与三层更新器（app/引擎/内容包）落地，引擎层禁自动升级。

## Requirements

- **APP-06**: 首启向导 — 执业方向卡片（设默认预设）→ 密钥（预填或一次性粘贴，存 OS 凭据库）→ 模型确认；之后零终端零配置文件
- **DSH-05**: 凭据与模型 — 密钥存 OS 凭据库、启动时注入；模型/供应商默认（DeepSeek 官方路由）可配；密钥轮换入口（业主模式）；日志与遥测零明文密钥
- **PKG-01**: Windows 单 exe 安装包 — Flutter build + 引擎 zip + 便携 Python + 初始内容包 + 预设；装到 %LOCALAPPDATA%\InkStatute；开始菜单/桌面快捷方式；零命令行
- **PKG-02**: 三层更新器 — app（安装器）/ 引擎（zip 原子替换，禁自动）/ 内容包（唯一自动层）；启动 manifest 检查；签名校验；回滚

## Success Criteria

1. 首启向导三步走通：执业方向卡片 → 密钥 → 模型确认；向导完成后零终端零配置
2. 凭据安全：密钥只进 OS 凭据库，启动时环境注入引擎；仓库/日志/遥测/安装包零明文密钥（grep 断言）
3. 密钥轮换入口：业主模式（设置页隐藏入口 + 快捷键），普通用户不可见
4. 单 exe 安装包：装到 %LOCALAPPDATA%\InkStatute，开始菜单/桌面快捷方式
5. 三层更新器：app/引擎/内容包；引擎禁自动升级；manifest 检查、签名校验、回滚路径
6. 全链路冒烟：干净 Windows 虚拟机安装 → 向导 → 一次真实法律任务 → docx 导出 → 重启状态保留
7. 模型默认：DeepSeek 官方路由配置化；供应商/模型可改但只进业主模式

## Existing Infrastructure

- Phase 112: DSH engine integration, ACP client, process management
- Phase 113: Legal presets (5 domains + legal-core)
- Phase 114: Skill pipeline (dsh target)
- Phase 115: Content auto-update (manifest + sha256 + atomic switch + rollback)
- Phase 116: Chat UI, output boundary, session store, app shell
- Phase 117: Legal guardrails (6 guardrails with double-layer enforcement)
- Phase 118: Word track-changes export (change list schema + Python script + docx exporter)
- V4 gates: dart-analyze, flutter-test, engine-manifest, mock-e2e, meta-test, docx-golden

## What Phase 119 Adds

### First-Run Wizard (APP-06)
- Three-step wizard: practice area → API key → model confirmation
- Practice area cards (商事法/劳动法/家事法/诉讼法 → sets default preset)
- API key input (stored in OS credential store, never in files)
- Model confirmation (DeepSeek default, configurable in owner mode)
- After wizard: zero terminal, zero config files

### Credential Security (DSH-05)
- API key stored in OS credential store (Windows Credential Manager)
- Key injected via environment variable at engine startup
- Zero plaintext keys in repo/logs/telemetry/installer (grep assertion)
- Key rotation entry: owner mode (hidden settings entry + keyboard shortcut)
- Owner mode: Ctrl+Shift+D on settings page

### Windows Packaging (PKG-01)
- Single exe installer (Inno Setup or NSIS)
- Installs to %LOCALAPPDATA%\InkStatute
- Start menu + desktop shortcuts
- Bundles: Flutter build + engine zip + portable Python + initial content pack + presets
- Zero command-line required

### Three-Layer Update (PKG-02)
- App layer: installer self-update (checks for new version, downloads, installs)
- Engine layer: zip atomic replace (DISABLED auto — only with app version release)
- Content pack layer: auto-update (Phase 115, only auto layer)
- Manifest check on startup, signature verification, rollback path

## Plan Structure

- **119-01**: First-run wizard (practice area + API key + model confirmation)
- **119-02**: Credential security + owner mode + key rotation
- **119-03**: Windows packaging (installer script + shortcuts + bundling)
- **119-04**: Three-layer update orchestrator + phase summary
