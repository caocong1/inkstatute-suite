# 墨律 InkStatute

InkStatute（墨律）是面向专业服务场景的全栈 Agent 平台 monorepo。  
第一行业包是中国大陆律师助手「小律」：**通道收发由 InkStatute 自有服务拥有**，Hermes `lawfirm` 是首个可插拔 agent 后端，不是用户入口，也不是平台核心。

本仓库交付的是：平台契约、通道服务、agent adapter、输出边界、契约测试、只读视图与反馈标准化。  
**不重建** Hermes 的 router / skill / MCP / 模型网关核心。

---

## 一句话怎么用

| 你想做的事 | 怎么做 |
|------------|--------|
| 验证代码与契约 | 仓库根目录：`python scripts/run_v2_gates.py` |
| QQ 通道冒烟（无真网） | `python3 scripts/smoke_test.py --dry-run` |
| QQ 真网联调 | 见 [`runbook/SMOKE_TEST_RUNBOOK.md`](runbook/SMOKE_TEST_RUNBOOK.md)（人工门禁 `--live`） |
| 看需求边界 | [`docs/requirements/V2-PRD.md`](docs/requirements/V2-PRD.md) |
| 看规划进度 | `.planning/PROJECT.md` / `ROADMAP.md` / `STATE.md` |

密钥、token、客户材料、运行时 DB **永不提交**。本地用 gitignore 的 `.env`（可参考 [`.env.example`](.env.example)）。

---

## 产品定位

- 中文名：墨律 · 英文名：InkStatute · 仓库：`inkstatute-suite`
- V2 形态：**自有 WeCom/QQ 通道服务 + 后端中立平台契约 + Hermes 首个 agent adapter + 纯律师助手体验**
- 长期方向：可复用行业 Agent 平台（多通道、多后端、多行业）

**核心价值：** 律师通过 InkStatute 自己的通道用助手；平台记录可回放、可测、可换后端的契约事件；Hermes 的 gateway/meta/update/command 噪声不得漏给普通用户。

规格真源：[V2 PRD](docs/requirements/V2-PRD.md)。V1 已退役。

---

## 仓库结构（逻辑）

```text
services/
  wecom-service/          # 企微回调、ACK、发送、卡片、反馈、输出边界
  qqbot-service/          # QQ 薄 webhook 宿主（组合包级 Protocol）
  hermes-contract-layer/  # Hermes agent 适配 / 契约事件
  feedback-service/       # FeedbackEvent 标准化
  conversation-read-view/ # 契约日志只读视图
  admin-console-api/      # 只读运营 API
  admin-web-ui/           # 只读运营看板（非配置页）
  lawyer-web-chat/        # 律师 Web 聊天（扩展面）
packages/
  platform-contract/      # 五契约 schema + 状态机 + 错误码
  platform-runtime/       # 可注入 RunRuntime（feature flag 默认 OFF）
  contract-test-suite/    # schema / 回放 / 可组合性 CI
  channel-core/           # 通道共用逻辑
  channels/wecom|qqbot|…  # ChannelAdapter 实现
  backends/hermes|codex|provider_model
  model-gateway/          # 多 provider 组合后端（扩展）
  …                       # router / skill-registry / rbac / memory 等
solutions/lawfirm/        # 律师行业包（manifest / 物化，非 Hermes 运行时密钥）
apps/platform_api/        # 薄 RunRuntime HTTP 面（默认 OFF）
scripts/                  # run_v2_gates.py、smoke_test.py
runbook/                  # 操作手册（目前以 QQ smoke 为主）
docs/requirements/        # V2 PRD
docs/architecture/        # ADR / 架构
```

---

## 已具备的能力（相对「配置页」）

### 已有

- 平台契约 + CI 门禁（`run_v2_gates.py`）
- WeCom / QQ 通道包与宿主（QQ 宿主 v1.9 已交付；live 验收仍为人工门禁）
- Hermes / Codex / provider_model（含 Ollama OpenAI 兼容 runner）后端适配原型或生产级扩展
- 只读 Admin API + Admin Web UI（会话/任务/反馈/健康/gates）
- 输出边界、反馈标准化、会话只读视图、记忆与多后端扩展（多数 **feature flag 默认 OFF**）

### Operator Config Console (delivered)

The Admin Web UI now exposes server-side rendered (SSR) config pages under `/config/*`:

- `/config/channels` — QQBot and WeCom enablement, dual-knob visibility, and secret-ref credentials
- `/config/providers` — built-in vendor profiles (OpenAI, Anthropic) plus custom OpenAI-compatible endpoints
- `/config/catalog` — main model selection from the built-in catalog with vision-capability badges
- `/config/vision` — image-turn routing mode and optional dedicated vision provider/model

Each config page is rendered with `html.escape`, carries a signed CSRF token bound to the caller identity and route (HMAC-SHA256), and shows a gate-honesty notice. The admin console edits configuration. It does not perform live acceptance. Phase 5 WeCom UAT, Phase 8 lawyer trial, and QQ live acceptance remain carried human gates.

Secrets are stored and edited as refs only (`env:…`, `secret://…`); values are resolved at the process edge, never in the UI or repo.

---

## 配置与密钥（当前约定）

| 场景 | 方式 |
|------|------|
| 本地开发 | 复制 `.env.example` → `.env`，填入本机值（已 gitignore） |
| QQ 宿主生产 | `INKSTATUTE_QQBOT_*_REF` + 双开关；见 [`services/qqbot-service/README.md`](services/qqbot-service/README.md) |
| QQ smoke `--live` | 值型环境变量（非 `*_REF`）；见 [`runbook/SMOKE_TEST_RUNBOOK.md`](runbook/SMOKE_TEST_RUNBOOK.md) |
| provider_model / Ollama | `api_base_url` + `api_key_ref`（如 `OLLAMA_API_KEY`）指向 `https://ollama.com/v1` 等；**不改 Hermes 配置** |
| Hermes agent 模式 | 模型仍由 Hermes 侧配置；本仓库只做 adapter / 契约，不把 Hermes `~/.hermes` 当本项目配置源 |

**重要：** 本仓库的配置面是 InkStatute 自己的 env / 未来配置页。不要把「给本项目配模型」误做成改 Hermes gateway。

---

## 部署与运行（现状实话）

当前交付以 **库 + 可组合宿主 + 门禁** 为主，不是单一「一键安装包」：

1. **CI / 本地门禁**：`python scripts/run_v2_gates.py`
2. **QQ 宿主**：`services/qqbot-service`（stdlib webhook，`POST /qqbot/callback`）；启用前双开关必须显式打开
3. **WeCom 服务**：`services/wecom-service` 边界与策略已具备；完整企微后台对接与日常试运行仍有人工门禁（Phase 5 / Phase 8）
4. **运营看板**：`admin-web-ui`（`admin_web_ui_enabled`，默认 OFF）
5. **端到端「律师每天用」**：依赖通道宿主部署 + agent 后端（默认 Hermes）+ 人工验收；统一运维手册仍在补齐（见下一里程碑配置页与文档）

---

## 开发工作流（GSD）

- 规划状态：`.planning/PROJECT.md`、`REQUIREMENTS.md`、`ROADMAP.md`、`STATE.md`
- 续作：`$gsd-resume-work` 或 `$gsd-progress --next --auto`
- 契约测试与 fixture 优先于通道 / adapter / 输出策略改动

---

## 安全与隐私

- 不提交 secrets、token、运行时 DB、客户文书、原始法律全文
- 契约日志优先 `raw_payload_ref`；法律字段进 `industry_context`
- 高风险法律反馈只记录 `skill_candidate`，不自动改 skill
- 后端/gateway 系统通知不得作为普通用户可见输出

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [V2 PRD](docs/requirements/V2-PRD.md) | 需求与验收真源 |
| [AGENTS.md](AGENTS.md) | Agent 实现约束 |
| [QQ Smoke Runbook](runbook/SMOKE_TEST_RUNBOOK.md) | QQ dry-run / live |
| [qqbot-service README](services/qqbot-service/README.md) | QQ 宿主与 secret ref |
| [wecom-service README](services/wecom-service/README.md) | 企微边界与输出策略 |
| [admin-web-ui README](services/admin-web-ui/README.md) | 只读运营看板 |
| `.planning/` | 里程碑与阶段进度 |

> `docs/operations/`、`docs/api/` 在早期 README 中预留，尚未成册；配置页落地后会补齐操作与 API 说明。
