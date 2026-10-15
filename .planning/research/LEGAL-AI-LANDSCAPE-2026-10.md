# 法律 AI 外部调研（2026-06 至 2026-10）

**调研日期**：2026-10-15。**方法**：三路并行 WebSearch / WebFetch 调研（产品与监管、开源生态、2026 法规更新），每条结论标注置信度：**H** 官方原文或已抓取文章；**M** 可靠二手来源或单一来源；**L** 自媒体 / 应用商店；**未核实** 无法确认。
**用途**：为 `ai-for-china-legal` 语料与本仓产品决策提供外部参照；不改变 AGENTS.md 的既定架构决策（含 APP-04 放弃）。
**已据此落地**：语料仓 v1.2（研究闸门「已核验」定义、法发〔2026〕10号第19条提交前核验、`REVIEW_STATUS`）；本仓 `presets/` 物化更新。未落地项见第 4 节。

## 1. 产品与监管动态

### 1.1 直接影响产品的两条发现

1. **最高法法发〔2026〕10号《关于依法审理涉人工智能纠纷案件的意见》（2026-09-07）第 19 条**：AI 辅助形成的诉讼文书、案例检索报告提交法庭前须核实法律、司法解释、案例的真实性与准确性，并对 AI 辅助使用情况作出说明；伪造证据按民诉法第 114 条处理（[南都](https://c.m.163.com/news/a/L6850DH305129QAF.html)、[君合 2026-09-18](https://junhe.com/legal-updates/3146)，H）。→ 已写入语料研究闸门与诉讼类技能；产品侧建议：诉讼类导出前按引用逐条核验状态门禁 + 自动生成《AI 辅助使用情况说明》。
2. **引擎模型别名风险**：DeepSeek 2026-09-10 发布 V4.1-Flash，官方模型名改为 `deepseek-flash`，`deepseek-v4-flash` 仅「临时」路由；2026-07-24 `deepseek-chat` / `deepseek-reasoner` 已完全下线；`deepseek-v4-pro` 的后续服务状态官方两页说法不一致（[changelog](https://api-docs.deepseek.com/updates)、[news 260910](https://api-docs.deepseek.com/news/news260910)，H）。本仓 `engines/acp.cordis.yml` L52 / L53 / L177 受影响，`glm-4-plus` / `glm-4-flash`（L34 / L38）条目过时。未改动，须走冒烟闸。

### 1.2 中国法律 AI 产品（2026）

| 产品 | 2026 信号 | 对本项目的参照 | 置信 |
|---|---|---|---|
| 北大法宝 法宝灵境 / 律爱多（2026-09-20） | agent + skills + tools 工作台，可本地部署；合同审查输出「原文定位 / 依据 / 理由 / 待确认事项」；**MCP 2.0** 含 `pkulaw-citation-validator`、`pkulaw-case-number-recognition`、`pkulaw-law-recognition`，CLI 调用不耗 LLM token（[mcp.pkulaw.com](https://mcp.pkulaw.com/)） | 唯一发现的中国法引用校验型工具；可作研究闸门的 DSH 工具 | H |
| 智合 AI 3.0（WAIC 2026-07-18） | 三层：法律智能本体 / **Skill 中心**（指令 + 参考文件 + 脚本隔离执行 + 跨会话记忆）/ 数字法务 bot；「幻觉防火墙」拦截未核验案例与法条；6 模型以 DeepSeek V4 Pro 优先 | 市场已收敛到「skills + 引用防火墙 + 律师终局判断」 | H/M |
| 华宇元典 × Kimi（2026-06-26） | 元典数据内置 Kimi Web / Kimi Work / Kimi Code 插件；REST + MCP 开放平台 | 本仓 `yuandian` 连接器已定位为兜底 | M |
| 法大大 睿契 Richee.ai（2026-05-12） | 桌面 agent，10+ agent、100+ skills、长期记忆、「文件留本机」；腾讯 WorkBuddy 首批应用 | 与本仓「本地桌面 + 云模型」形态相同；「本地≠离线」提示同样适用 | M |
| 典典 AI 律助 1.0（2026-09-16） | 20 专项 agent + 分诊 agent；**985 条 skill**（清单 + SOP + 法条依据 + 模板）；风险分级双轨，律师确认关键判断；时间戳审计；引用对照国家法律数据库；每条结论自评论证强度 | 与本仓分域预设 + 人审标记思路一致 | M |
| 秘塔 MetaLaw / 得理法搜 | 检索强，无审查 / 起草 / 尽调 | — | M/L |
| 通义法睿、法行宝、AlphaGPT、MeCheck、小包公、法狗狗、无讼 | **未找到 2026 官方发布** | — | 未核实 |
| DeepSeek Harness 社区桌面版（2026-08-14） | 官方 MIT 仓库的 Electron 壳，Win x64 / Apple Silicon | 纯 DSH 壳已免费开源，不构成差异化；差异化在法律护栏、分域技能与人审链路 | H |
| AI Workdeck（2026-06-10，AGPLv3） | 「律师的 VS Code」：Electron + Spring + Vue，WPS WebOffice 编辑 DOCX，MCP | 参照其 DOCX 编辑接入方式 | M |

未发现任何中国产品提供 Word / WPS 原生修订（Track Changes）输出（未核实缺口）。

### 1.3 全球设计参照

- **Harvey**（2026-09-23）Word 内自定义 agent：修改以修订痕迹进入，用户逐条预览 / 应用 / 附批注 / 丢弃；agent 可中途停下向用户提问（[harvey.ai](https://www.harvey.ai/blog/run-custom-harvey-agents-in-microsoft-word)，H）——与本仓澄清卡同构。
- **Microsoft** Legal Agent for Word（Frontier 预览，2026-10-07 更新）：条款对照 playbook 出修订稿（[MC1388706](https://mc.merill.net/message/MC1388706)，H）。
- **Anthropic**：Cowork legal plugin（2026-02，开源，`/review-contract` 红黄绿）；Claude for Word（2026-04-10，原生修订）；2026-05-12 发布 20+ MCP 连接器与 12 个执业领域插件，**每个插件以 setup interview 学习 playbook、升级链、风险校准与行文风格**（[LawNext](https://www.lawnext.com/2026/05/anthropic-goes-all-in-on-legal-releasing-more-than-20-connectors-and-12-practice-area-plugins-for-claude.html)，H/M）——与语料仓 cold-start-interview 同构。
- **OpenAI** Astra for Law（2026-09-17）：GPT-6 + 法律检索索引 + 指令；Vals Legal Research Bench 200 题通过率 54% vs 仅网页搜索 38.7%（自报）——**权威索引接地比换模型更有效**（[SiliconANGLE](https://siliconangle.com/2026/09/17/openai-launches-astra-for-law-a-gpt-6-configuration-for-legal-research/)，H）。
- **Vals Legal Research Bench**（2026-10-12）：榜首 55.29%；DeepSeek V4 Pro 0813 40.87%（第 28）；V4.1 Flash 41.35%；最佳中国模型 GLM 5.3 49.04%。美国法；**无可比的中国法 agent 基准**（[vals.ai](https://www.vals.ai/benchmarks/legal_research)，H）。
- 市场说明：Harvey / Microsoft / Anthropic / OpenAI 2026 年均已出 Word 原生修订；APP-04 放弃决定不变，仅记录。

### 1.4 监管与执业规范

| 文件 | 要点 | 置信 |
|---|---|---|
| 法发〔2026〕10号（2026-09-07） | 见 1.1 | H |
| 上海律协《律师企业法律顾问服务 AI 应用操作指引（2026）（试行）》（2026-07-07，一年试行） | 1.3.3 AI 内容须人工复核验证；1.3.2 使用前脱敏，未经授权或安全评估不向公共 AI 平台上传商业秘密 / 个人隐私；示例提示词「不得编造法律依据、监管口径或案例」，不确定点标 **「【需律师核查】」**（[东方律师网](https://www.lawyers.org.cn/info/10aadc765e124cb4ac999d47cda0b0a8)） | H |
| 宁夏律协指引（2026-03-22） | 鼓励私有化部署；公有云须风险评估与脱敏；「严禁直接采信」；AI 使用过错责任不可转移 | H |
| 《粤港澳大湾区法律服务 AI 应用倡议》（2026-08-29，12 家机构） | 核实 AI 内容；**必须征得当事人同意**；防敏感数据泄露 | M |
| 全国律协 / 司法部 | 仅见 2026-09 问卷调研；**无全国性指引** | M |
| 《人工智能法》 | 全国人大 2026 预备审议；国务院 2026 计划要求综合立法；截至 2026-08 无草案提交；9–10 月状态未核实 | M |
| 《人工智能生成合成内容标识办法》（2025-09-01 施行） | 文本显式标识、导出文件保留标识、元数据隐式标识、不得删除标识；是否适用于律所交付物无官方口径 | H 文本 / L 适用 |
| CAC 备案 / 登记；清朗行动（2026-04 起） | 截至 2026-08-31：1,112 项备案、731 款登记；经 API 调用已备案模型的应用在属地网信办登记；清朗已处置 1.4 万+ AI 产品 | H |
| 数据合规 | 《个人信息出境认证办法》2026-01-01 施行；网络安全法修正增 AI 条款 2026-01-01 施行；无针对律所向模型 API 传客户材料的 2026 专门指引 | H/M |
| 域外 | 爱尔兰高院 HC142（2026-09-01）：人工控制下独立核验，**用另一 AI 核验不算**；日本法务省指引 2026-08-21；ABA 512 | H/M |

### 1.5 质量与风险证据

- **北京通州案**（2025-12 入人民法院案例库）：律师引用两个 AI 虚构「参考案例」，案号真实但内容无关；裁判要旨：未经甄别核实的虚假案例应承担法律后果，情节较重可参照民诉法第 114 条第 1 款（[中新网 2026-01-15](https://www.chinanews.com.cn/fz/2026/01-15/10552373.shtml)，H）。
- **宜昌西陵案**（2026-07-21 报道）：真实 URL 配虚构要旨、不存在案号配伪造文书网链接、真实案号属无关帮信罪判决、**改写两高司法解释文本**、虚构通知条款；律师当庭训诫，「助理用了 AI」抗辩被驳（[极目](https://www.ctdsb.net/c1747_202607/2806924.html)，H）。
- 提供者责任：李小亮诉百度（南京中院 2026-03 维持诽谤认定，驳回「AI 幻觉」抗辩）；杭州互联网法院「AI 幻觉」案按过错责任，提供者尽合理措施与提示则免责（H）。
- 引用核查器效果（Princeton，arXiv 2606.21155，2026）：4,499 条引用、5 类错误；最佳 F1 68.8%；最佳 agent 可靠发现不存在案例与案名不符，**但难以核验 pincite**；新模型不必然更好（H）。
- 中国法幻觉率仅有个人小样本基准（23 题 × 5 旧模型，33–54% 引用幻觉，多为虚构条文序号，L）。
- DeepSeek API：V4 1M 上下文默认；峰时定价 UTC 01–04、06–10 工作日（北京 09–12、14–18）为谷时两倍（[pricing](https://api-docs.deepseek.com/quick_start/pricing)，H）。

### 1.6 agent 工程实践（2026）

| 来源 | 实践 | 适用 |
|---|---|---|
| Anthropic《Harness design for long-running apps》（2026-03-24） | 生成者与评估者分离；agent 自评「可靠地偏正面」；硬通过阈值；文件交接 | Phase 128 复核人设 |
| Anthropic《Demystifying evals》（2026-01-09） | 代码 / 模型 / 人工评分混合；LLM 裁判对专家校准并允许「Unknown」；pass^k；从真实失败中取 20–50 个简单任务起步 | v5 门禁、HG-1 证据 |
| Anthropic《Effective harnesses for long-running agents》（2025-11-26） | JSON 特性清单，每项初始为失败，agent 只能改状态字段；进度文件 | 尽调清单（语料 playbook 已采用底稿 schema） |
| Anthropic《Managed Agents》（2026-04-08） | 会话 = 外置追加式事件日志；新 harness 从日志恢复；harness 不见凭据 | 与本仓 JSONL 观测面、回灌、环境注入密钥一致 |
| Claude context-engineering cookbook（2026-03-20） | 压缩（默认 150K 触发）会丢细节：高层事实 3/3 保留，附录冷门数值 0/3；压缩前把精确值写入笔记 | 长文起草、回灌 |
| Agent Skills 规范（agentskills.io） | 启动仅加载 name + description；SKILL.md < 500 行；参考文件一层深 | 与 ≤8,000 字符目录预算一致 |
| LLM-as-judge 预印本（2026，M） | LexRubric 裁判与 3 名专家一致率 79.4%、κ 0.589；原始一致率高估 33–41 点；9 模型跨族集成在 COLIEE 2026 法条蕴含 96.3% | 裁判校准；集成仅用于是非判断 |
| 多模型「盲审」 | 无同行评议研究或律协指引；HC142 明示 AI 核 AI 不算核验 | 交叉复核只作筛查，标「AI 交叉审阅（非核验）」 |

## 2. 开源生态与组件（2026-10-15）

来源：GitHub / npm / PyPI / crates.io / Hugging Face API 当日查询；「最近活动」= 最近 push 或发布；厂商自报数据已注明。调研代理同时读了本仓、语料仓与本地 `deepseek-harness` 仓以判断相关性。

### 2.1 中国法律 LLM：均已停更（H）

DISC-LawLLM（Apache-2.0，2025-05 仅改 README）、ChatLaw（AGPL-3.0，2025-01）、LaWGPT / Lawyer-LLaMA / InternLM-Law（2024 停更）、LexiLaw（MIT，2026-03 仅改 README）、夫子·明察 / HanFei（停更）、智海-录问（2026-04 新技术报告，模型仍为 2023 年 Baichuan-7B）、Unilaw-R1 / PoliLegalLM（2026 论文，未见权重）；通义 / 智谱 / DeepSeek / Qwen 无法律专用开源权重。**结论：不采用、不微调；精力投入检索接地与评测。**

### 2.2 评测与基准

| 项目 | 许可 | 最近活动 | 内容 | 用途 |
|---|---|---|---|---|
| [LexRubric](https://github.com/foggpoy/LexRubric) | MIT | 2026-08-29 | EMNLP 2026：649 个中文开放式任务、12,337 条专家 pass/fail 标准、14 场景 | 咨询类回答的 rubric 模板 |
| [PLawBench](https://github.com/SKYLENAGE-AI/PLawBench) | 仓库无许可（论文 CC BY 4.0） | 2026-02-09 | 850 题、约 12.5k rubric；含 250 案例分析、18 咨询、12 起诉状 / 答辩状起草 | 最接近的公开中文起草评测 |
| [LegalCiteTrust](https://github.com/lyxx3rd/LegalCiteTrust) | Apache-2.0 | 2026-07-12 | 72 份中文长篇研究报告的引用：是否存在、是否忠实、是否支持命题 | **引用审计的现成回归集** |
| [LegalAgentBench](https://github.com/CSHaitao/LegalAgentBench) | 无 | 2026-04-10 | 300 个中文 agent 任务、17 语料、37 工具、中间步骤计分 | DSH + skills 端到端 |
| [LexGenius](https://github.com/QwenQKing/LexGenius) | 无 | 2026-09-03 | ACL 2026：7 维 11 任务 20 能力 | 选型能力图 |
| LawBench / LexEval | Apache-2.0 / MIT | 2023 / 2024 | 考试式静态题库 | 冒烟 |
| LawFlow / MSLR-Bench / JuDGE / CaseGen | 无 / Apache-2.0 / MIT / 无 | 2025–2026 | 多阶段民事诉讼推理、判决与案件文书生成 | 诉讼推理参照 |
| [CAIL2025](https://github.com/china-ai-law-challenge/CAIL2025) | 无 | 2025-10-22 | 法考客观 / 主观、agent 庭审、agent 调解、法律数值计算、量刑；**无合同审查赛道**；CAIL 2026 未见公告 | 数值任务可用于赔偿 / 利息技能 |
| [Harvey LAB](https://github.com/harveyai/harvey-labs) | MIT | 2026-10-08（1,450★） | 1,200+ 任务、24 领域、75k 条全通过标准；含首轮 / 后轮 redline、约 17.5k 个 .docx 样本、并购尽调扩展（2026-07-17）；美国法 | **redline / DD / memo 评测的最佳开放格式**（`task.json`） |
| [ContractScrub](https://arxiv.org/abs/2608.20204) | 论文 CC BY-NC-SA | 2026-08-20 | 合同终稿校对：误用定义术语、错误交叉引用、措辞不一致；数据集未公开 | 终稿校对 rubric 的错误清单 |

**结论：GitHub / Hugging Face / arXiv 上没有公开的中国法合同修订或尽调基准（M-H）。**

### 2.3 中国法律数据连接器（2026 实测状态）

| 源 | 状态 | 说明 |
|---|---|---|
| flk.npc.gov.cn | ✅ JSON 接口无 key 无验证码 | 旧 `/api/` 已下线；`/law-search/search/list`、`flfgDetails?bbbs=`、`download/pc`、`enumData` 可用；语料仓 `law-database` 连接器已迁移 |
| [lawtext/laws](https://github.com/lawtext/laws) | ✅ 每日自动更新 | 2,000+ 国家法律 Markdown / docx；地方法规卷 2026-04-19 停更；无许可声明 → 只作变化信号 |
| [law-crawler-unified](https://github.com/Li2zon3/law-crawler-unified) | MIT，2026-04-18 | flk + 外交部条约库 + 国务院规章库 | 
| 北大法宝 MCP + [`@pkulaw/mcp-cli`](https://www.npmjs.com/package/@pkulaw/mcp-cli) 0.3.2 | 付费；CLI MIT，2026-09-22 | 法规 / 案例语义与关键词检索、条文定位、法规与案号识别、**引用校验** `pku_citation_validator`；Bearer token；CLI 不耗 LLM token |
| 元典开放平台 + [官方 DSH 插件](https://github.com/yuandian-ailaw/yuandian_dsh_plugin) | 付费；插件 MIT，2026-10-02 | 统一 MCP 端点 `open.chineselaw.com/mcp`（法规、案例、企业 26 接口、证券）；OAuth 或 API key；**插件要求 DSH ≥0.1.2-rc.1 <0.2.0** |
| [企查查法律数据 MCP](https://agent.qcc.com/legal) + [DSH OAuth 插件](https://github.com/duhu2000/qcc-mcp-legal-oauth) | 付费；插件 MIT，2026-08-19 | 10 个工具含 `get_legal_citation_verify` / `get_judicial_citation_verify`；企业数据另一 MCP；插件要求 `dsh-mcp-client ^0.1.0-rc.6` |
| 得理开放平台 | 付费（页面 © 2024） | 判决、法规、评注、专利、商标预付费 API；MCP 仅见于搜索摘要，页面未证实 |
| 法信 | — | 无公开 API / MCP；服务协议禁止系统提取 |
| 人民法院案例库 | ✅ 本人登录后可用 | 约 5.2k 案例；社区 MCP server 被 Glama 标为无响应 |
| 裁判文书网 | 仅本人浏览器会话 | [cncases/cases](https://github.com/cncases/cases)（MPL-2.0，1,134★）本地检索 85M 文书第三方 dump——来源与个人信息（PIPL）风险 |
| gsxt.gov.cn | ❌ 2026-08 境外自动请求 24 次中 21 次 403 | 改用企查查 / 元典企业数据；语料仓 `connectors/gsxt` 仍为占位 |
| 信用中国 | ❌ 验证码 / 限速 | 社区监测工具预留打码服务与代理设置 |
| fgk.chinatax.gov.cn | ✅ 普通 HTTP 带重试 | 与 LWC-2026-0004 实测一致 |

### 2.4 技能仓库与 SKILL.md 规范

| 仓库 | 许可 | 最近活动 | 内容 | 相关性 |
|---|---|---|---|---|
| [anthropics/claude-for-legal](https://github.com/anthropics/claude-for-legal) | Apache-2.0 | 2026-07-23（9,677★） | 12 个执业领域插件 + CoCounsel 插件，151 个 SKILL.md | 语料仓上游；其 `corporate-legal`（tabular review、DD issue extraction、closing checklist、written consents、entity compliance）、`product-legal`、`legal-clinic` 无本地对应 |
| [knowledge-work-plugins/legal](https://github.com/anthropics/knowledge-work-plugins) | Apache-2.0 | 2026-09-21 | 合同审查、NDA 分诊、合规检查等 9 个技能 | 薄基线 |
| [cat-xierluo/legal-skills](https://github.com/cat-xierluo/legal-skills) | **逐 skill：约 42 MIT / 19 CC BY-NC 4.0** | 2026-10-14（732★，2,211 commits） | 66 个 SKILL.md，46 个带 Python；非商业：contract-copilot、judgment-analysis、legal-case-analysis、legal-text-format 等；MIT：legal-ocr、yuandian-law-search、verification-gate、de-ai-polish、md2word、dsh-plugin-dev | 即 AGENTS.md 所指 `legal-skills`；DEFER-01 可按 skill 逐个评估 |
| claude-for-legal-HoriZon / workbuddy-cn-legal-skills / claude-for-legal-cn | Apache-2.0 | 2026-06-10 / 05-14 / 10-14 | 面向中国执业的上游改编（HoriZon 9 插件 69 技能，内置元典） | 对比参照 |
| [lawve-ai/awesome-legal-skills](https://github.com/lawve-ai/awesome-legal-skills) | NOASSERTION | 2026-10-02（865★） | 无中文条目 | 分发缺口 |
| gongwen-gbt9704-skill / gongwen-skill | MIT | 2026-09 / 10 | GB/T 9704 公文版式；后者可写原生修订与批注 | 中文字体与版式参照 |
| element-lawsuit-templates | 无许可 | 2026-05-26 | 最高法要素式诉状模板 58 案由、104 空白 + 104 示例 | 仅参照 |

**SKILL.md 规范（[agentskills.io](https://agentskills.io/specification)，Apache-2.0，26k★）2026 年未变**：`name` ≤64 字符、小写字母 / 数字 / 连字符、无双连字符、须与目录名一致；`description` ≤1,024 字符；可选 `license` / `compatibility`（≤500）/ `metadata` / `allowed-tools`。2026 提交仅澄清（name 允许数字 2026-05-16；metadata 措辞 2026-08-03；新增 `evals/evals.json` 评测指南，有 / 无技能对照运行）。Claude Code 另加 `when_to_use` 等字段并在 1,536 字符截断描述；claude.ai 与 Skills API 拒绝规范外字段；DSH `skill-filesystem` 支持 `disable-model-invocation` / `user-invocable`。

### 2.5 Word / DOCX 工程

| 工具 | 许可 | 最近活动 | 能力 | 相关性 |
|---|---|---|---|---|
| [OfficeCLI](https://github.com/iOfficeAI/OfficeCLI) | Apache-2.0 | v1.0.157，2026-10-12（32k★） | 内置 .NET 单二进制；插入 / 删除 / 格式 / 移动修订、按作者接受拒绝、修订式查找替换、批注 | Windows 单文件最佳；本仓笔记记其截图功能失效 |
| [docx-redline-js](https://github.com/AnsonLai/docx-redline-js) | MIT | 0.9.0，2026-10-11 | 纯 JS 真实 `w:ins` / `w:del`、格式修订、批注、接受 / 拒绝；**「拒绝全部修订」不能恢复源稿时拒绝输出** | LWC-2026-0002 的可逆性测试现成实现 |
| [Docxodus](https://github.com/JSv4/Docxodus) / [Python-Redlines](https://github.com/JSv4/Python-Redlines) | MIT | 2026-10-12 / 1.0.0 | .NET / WebAssembly：两稿比较生成原生修订、渲染、编辑 | 两稿比对 |
| [jubarte-redlines](https://github.com/jandira-tech/jubarte-redlines) | **AGPL-3.0** | 2026-10-15 | Rust 引擎，比较 / 接受拒绝 / DOCX→PDF/PNG | Rust 适合 Tauri 但 AGPL 阻碍闭源分发 |
| [adeu](https://github.com/dealfluence/adeu) / [safe-docx](https://github.com/UseJunior/safe-docx) | MIT / Apache-2.0 | 2026-10 | MCP server：把 agent 文本编辑落为原生修订 | agent 侧修订层 |
| [vespper-docx-conformance](https://github.com/ANKOHR/vespper-docx-conformance) | 无 | 2026-08-24 | 8 个有效 + 5 个故意损坏的修订样本，含原稿 / 接受视图与 Word 渲染对照 | docx 门禁样本模式 |
| python-docx 1.2.0 / docx (JS) 9.11.0 | MIT | 2025-06 / 2026-10-13 | 前者有批注无修订；后者支持修订与批注 | DSH 内置 Word 技能用 python-docx，并声明不得伪造修订 |
| pandoc + [TomBener/pandoc-templates](https://github.com/TomBener/pandoc-templates)、[docx-pipeline](https://github.com/redamancy231-create/docx-pipeline) | GPL-2.0 / MIT / MIT | 2026-10-14 | 读修订（接受 / 拒绝）；中文 reference.docx 模板（后者 4 套预设） | 外部调用 |

APP-04 已放弃；这些工具服务于语料仓修订工作流，或日后重开 APP-04 时的选型。

### 2.6 扫描件 OCR（中文）

OmniDocBench v1.6（维护方自报，中英通用页面含模糊扫描）：PaddleOCR-VL-1.6 96.34、MinerU2.5-Pro 95.75、GLM-OCR 95.22、dots.ocr 90.77、DeepSeek-OCR 2 90.25、HunyuanOCR 89.95、Qwen3-VL-235B 89.78。**无任何工具公布中国法院文书的识别准确率。**

| 工具 | 许可 | 最近活动 | 说明 | 离线 Windows 适配 |
|---|---|---|---|---|
| [PaddleOCR 3.7](https://github.com/PaddlePaddle/PaddleOCR) | Apache-2.0 | 2026-06-11 | PP-OCRv6（34.5M 参数，识别 +5.1%、CPU 5.2×）；PaddleOCR-VL-1.6（0.9B）；DOCX 导出 | 最准；Python 运行时重 |
| [RapidOCR 3.10](https://github.com/RapidAI/RapidOCR) | Apache-2.0 | 2026-10-08 | ONNX Runtime；3.9 起默认 PP-OCRv6 | CPU 基线 |
| [oar-ocr](https://github.com/GreatV/oar-ocr)（Rust crate） | Apache-2.0 | 0.10.0，2026-10-03 | PP-OCRv6 预设、印章文字模式、PaddleOCR-VL-1.5；模型可编译进二进制 | **最适合 Tauri**（无 Python） |
| [MinerU 4](https://github.com/opendatalab/MinerU) | Apache-2.0 附条件（月活 >1 亿或月收入 >2,000 万美元需授权；在线服务须署名） | 4.0.12，2026-10-11 | PDF / OFD / Office → Markdown / JSON；默认 CPU（ONNX + llama.cpp） | Python sidecar |
| GLM-OCR / dots.ocr / DeepSeek-OCR-2 | Apache+MIT / MIT / Apache-2.0 | 2026 | 0.9B–3B 文档视觉模型 | GLM-OCR 为宽松小模型 |
| HunyuanOCR-1.5 | 腾讯社区许可 | 2026-09-24 | 1B | 需许可审查 |
| Marker / Surya / Chandra | 代码 Apache-2.0，权重 modified OpenRAIL-M（融资 / 收入 <500 万美元免费） | 2026 | PDF→Markdown | **权重许可是商业陷阱** |
| [OmniDocBench](https://github.com/opendatalab/OmniDocBench) v1.7 | Apache-2.0 | 2026-09-11 | 解析评测框架 | 用自有案卷集评分 |

### 2.7 引擎与 ACP 生态

| 项目 | 许可 | 最近活动 | 说明 | 相关性 |
|---|---|---|---|---|
| [deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) | MIT（插件 MIT / BSD-3） | v0.2.1-alpha.3，2026-10-14（249,709★，2026-08-13 创建）；npm `@deepseek-ai/dsh` latest 与 next 均 0.2.0-rc.2（2026-09-29） | **本仓钉 0.1.0-rc.6（2026-08-13）**；`session/list` / `resume` / `close` 自 2026-08-22（`dsh-v0.1.2-alpha.1`）加入，现为稳定 ACP v1 方法；`session/resume` 恢复会话「不重放旧更新」 | 触及决策 #3 与 FUTURE-08 |
| `@deepseek-ai/dsh-acp` / `dsh-acp-app` | BSD-3 / MIT | 0.2.0-rc.2 | ACP 服务端；`dsh-acp-demo` 停在 0.1.1-rc.2，由 `dsh-acp-app` 取代；ACP SDK 1.4.0；`session/new` 接受 HTTP MCP 服务器；仍无 `session/load` | 本仓 lock 仍为 SDK 0.25.1 |
| npm `deepseek-harness` | MIT | 0.0.1，2026-08-19 | **仅占名的占位包** | 勿依赖 |
| [ACP 规范](https://github.com/agentclientprotocol/agent-client-protocol) / TS SDK 1.8.0 / [Rust crate](https://crates.io/crates/agent-client-protocol) 3.3.0 | Apache-2.0 | 2026-10 | 稳定 v1 含 `session/list`、`resume`、`close`、`delete`、`set_config_option`；SDK 1.0.0 于 2026-06-24 | Rust crate 可替代 `src-tauri` 手写 JSON-RPC（新依赖需计划批准） |
| [ACP registry](https://github.com/agentclientprotocol/registry) | Apache-2.0 | 2026-10-14 | 列有 qwen-code、qoder、kimi、glm-acp-agent、codebuddy-code、minimax-code；**DSH 未列入** | 国产 agent 已采用 ACP |
| [Jockey](https://github.com/recailai/jockey) / [Perch](https://github.com/chenweigao/perch) / [Martty](https://github.com/openma-ai/Martty) | MIT | 2026-10 | Jockey：Tauri + Rust + SolidJS 的 ACP 客户端；Perch：驱动 DSH，有审批卡与会话恢复；Martty：Rust 终端 DSH 客户端 | 同栈 / 同引擎参照 |
| AionUi / DeepChat | Apache-2.0 | 2026-10 | 桌面 ACP 客户端，技能与 MCP 管理，中文本地化 | UX 参照 |
| Zed / JetBrains / 100+ 客户端（含 Lark ACP、WeChat ACP） | — | — | ACP 起于 Zed（2025-08），JetBrains 共同开发 | 生态健康 |

### 2.8 与本地仓库的不一致

- `engines/dsh-pin.txt` 钉 `0.1.0-rc.6` + 已冻结的 `dsh-acp-demo`；`engine-lock.json` 的 ACP SDK 为 0.25.1，上游 0.1.2-rc.1 起为 1.4.0。
- `AGENTS.md` 对 `legal-skills` 的描述（51 个、CC-BY-NC）已过时——现为 66 个、逐 skill 许可（2026-10-15 已改）。
- 语料仓 `connectors/gsxt/connector.json` 声明的 `https://www.gsxt.gov.cn/api` 不存在（CONNECTORS.md 已称占位）。

## 3. 2026 年中国法规更新与陈旧引用清单

核验标记：**OFF** 官方页面核实（gov.cn、npc、court.gov.cn、部委、省级政府、税务法规库、新华社 / 人民日报刊发文本）；**SEC** 二手来源；**UNV** 未核实（否定性结论归此类）。最高法司法解释栏目核到 2026-09-21，约 2026-10-12 后的文件可能未收入。完整 A–G 域表已按域写入语料仓各 `_shared/*-citations.md` 的「2026 年更新」节；本节保留立法日历、跨域要点与陈旧引用清单。

**立法日历**：常委会第 17 次（2025-09-12）仲裁法 → 第 18 次（2025-10-28）网络安全法修正、海商法 → 第 19 次（2025-12-27）对外贸易法、民用航空法、渔业法 → 全国人大四次会议（2026-03-12）生态环境法典、民族团结进步促进法、国家发展规划法 → 第 22 次（04-30）监狱法、社会救助法，企业国有资产法修订草案一审 → 第 23 次（06-26）商标法、注册会计师法修改，招标投标法修订草案一审 → 第 24 次（08-28）医疗保障法、律师法修改、国防动员法。

### 3.1 对语料与已交付案例影响最大的文件

| 域 | 文件 | 施行 | 要点 | 核验 |
|---|---|---|---|---|
| 劳动 | 法释〔2025〕12 号 劳动争议解释（二） | 2025-09-01 | 第 1–2 条转包挂靠用工主体；第 3 条混同用工共同担责；第 10 条「连续订立二次」四种情形；第 13–15 条竞业限制；第 16 条领取养老金属不能继续履行；第 19 条不缴社保约定无效。废止解释（一）第 32 条第 1 款 | OFF（河南高院转载） |
| 劳动 | 《超龄劳动者基本权益保障暂行规定》人社部等令第 56 号 | 2026-07-01 | 书面「用工协议」、不低于最低工资、单位缴工伤保险、争议走仲裁、弹性延迟退休期间适用劳动合同法 | OFF |
| 劳动 | 法释〔2026〕14 号 服务期批复；案由规定第三次修正法〔2025〕227 号；北京 2026 年度社保基数 7,270–36,348；北京 2025 仲裁十大典型案例 | 2026-07-30 / 2026-01-01 / 2026-07 / 参考 | 学历教育服务期不得仅以第 22、25 条否定；一级案由含「新就业形态用工纠纷」；引入 AI 替代岗位≠客观情况重大变化 | OFF / SEC |
| 公司交易 | 国务院令第 784 号 认缴期限；国资发产权规〔2025〕17 号 操作规则；国市监注发〔2026〕5 号 登记文书规范 2026 年版；鼓励外商投资产业目录 2025 年版；国务院令第 837 号 对外投资规定 | 2027-06-30 截止 / 2025-02-18 / 2026-05-01 / 2026-02-01 / 2026-07-01 | 存量公司认缴调整截止；32 号令配套；股东变更不再要求股权转让协议；境外投资核准备案与安全审查 | OFF（837 号为 SEC） |
| 公司交易 | 《仲裁法》2025 修订；《反不正当竞争法》2025 修订；《商标法》2026 修订 | 2026-03-01 / 2025-10-15 / 2027-01-01 | 撤销裁决 3 个月、仲裁地、特别仲裁；第 8 条第 2 款受贿方、第 24 条罚则；商标法施行前仍引 2019 版 | OFF（仲裁法条号 SEC） |
| 税务信用 | 《信用修复管理办法》发改委令 2025 年第 36 号；《全国税务行政处罚裁量基准（2026 年版）》公告 2026 年第 20 号；《行政复议法实施条例》2026 修订国务院令第 836 号；法释〔2026〕3 号 起诉期限；增值税法及实施条例 | 2026-04-01 / 2026-11-01 / 2026-07-01 / 2026-05-01 / 2026-01-01 | 公示期三类；偷逃税四阶次；复议条例 66→77 条；直接起诉 6 个月、复议后 15 日、最长 20 年 / 5 年；增值税暂行条例废止 | OFF |
| 税务信用 | 54 号令现行状态 | — | 官方法规库仍「全文有效」；第 18 条 6 个月与 36 号令「严重」类 1 年如何协调 UNV；2026 年版惩戒清单文号本次未能独立复核（2026-09-13 会话曾抓取 PDF） | OFF / UNV |
| 数据 AI | 《网络安全法》2025 修正；《个人信息出境认证办法》令第 20 号；小型处理者简化措施令第 25 号；网络数据安全风险评估办法令第 24 号 | 2026-01-01 / 2026-01-01 / 2026-09-01 / 2026-08-20 | 条号后移（21→23、37→39、59→61 等）；认证门槛 10 万–100 万人、证书 3 年；<10 万人处理者出境豁免与 5 年审计；重要数据处理者每年评估 | OFF（条号对应 SEC） |
| 建工 | 法释〔2026〕12 号 建工解释（二） | 2026-06-30（新受理一审） | 第 1 条非必须招标不因未招标无效；第 2 条先谈后招无效；第 3–4 条借用资质；第 6–7 条实际施工人只能向承包人主张、经代位权向发包人；第 13 条审计期限 1 年；第 17–21 条优先受偿权；第 23 条冲突以新为准 | OFF |
| 诉讼 | 法释〔2026〕19 号 刑民交叉；法发〔2026〕10 号 涉 AI 纠纷意见；法释〔2025〕15 号 协议管辖；律师法修改；法〔2026〕119 号 指导案例清理 | 2026-09-22 / 2026-09-07 / 2025-12-31 / 2026-09-01 / 2026-08-15 | 「同一事实」、预决效力、中止与受理；AI 诉状核实披露；非五地协议管辖须实际联系；律师法重新编号；指导案例 123、136、139、204 号不再参照 | OFF（15 号内容 SEC） |
| 刑事合规 | 法释〔2026〕6 号 贪污贿赂解释（二）；生态环境法典；对外贸易法 2025；反外国制裁法实施规定国务院令第 803 号；金融机构客户尽调办法 | 2026-05-01 / 2026-08-15 / 2026-03-01 / 2025-03-23 / 2026-01-01 | 单位行贿数额；非国家工作人员犯罪参照国家工作人员标准；环保法等 10 部废止；名称为「规定」非「实施条例」 | OFF（6 号全文 SEC） |

### 3.2 陈旧引用清单（2025 年语料常见旧锚点 → 替换）

| # | 旧锚点 | 变化 | 替换为 |
|---|---|---|---|
| 1 | 劳动争议解释（一）第 32 条第 1 款（已享受养老保险待遇者按劳务关系） | 2025-09-01 废止 | 法释〔2025〕12 号第 16 条（第 21 条为 SEC）；人社部令第 56 号第 2、6、15、19 条 |
| 2 | 以劳动合同法第 22、25 条否定事业单位学历教育服务期 | 2026-07-30 批复 | 法释〔2026〕14 号 |
| 3 | 案由规定（2020 修正）劳动争议一级案由 | 2026-01-01 修正 | 法〔2025〕227 号 |
| 4 | 仲裁法（2017 修正）第 58 条撤销事由、第 59 条 6 个月 | 2026-03-01 全面修订 | 新法第 71、72 条（3 个月）；第 81 条仲裁地；第 82 条特别仲裁 |
| 5 | 网络安全法（2017）第 21、37、41、59 条；第 64 条第 1 款、第 66 条罚则 | 2026-01-01 重新编号 | 第 23、39、43、61 条；第 71 条（转致）；新增第 20、63、73 条 |
| 6 | 增值税暂行条例及实施细则 | 2026-01-01 废止 | 增值税法及实施条例（国务院令第 826 号） |
| 7 | 增值税一般纳税人登记管理办法（税务总局令第 43 号） | 2026-01-01 废止 | 税务总局令第 62 号 |
| 8 | 税收违法违纪行为处分规定（监察部等令第 26 号） | 2026-01-01 取代 | 税务总局令第 60 号 |
| 9 | 发改委令 2023 年第 58 号 信用信息修复办法（试行） | 2026-04-01 废止 | 发改委令 2025 年第 36 号第 7–14、25 条 |
| 10 | 纳税信用管理办法（试行）2014 年第 40 号及 2019 年第 37 号、2021 年第 31 号 | 2025-07-01 废止 | 税务总局公告 2025 年第 12 号第 24 条及附件 |
| 11 | 失信惩戒措施基础清单 2022 年版（发改财金规〔2022〕1917 号） | 已取代 | 2025 年版（发改财金规〔2025〕297 号）；2026 年版文号本次未能独立核实 |
| 12 | 行政复议法实施条例（2007）条号 | 2026-07-01 修订，66→77 条 | 国务院令第 836 号，逐条重新对应 |
| 13 | 行诉法解释（法释〔2018〕1 号）起诉期限条款 | 2026-05-01 专项解释 | 法释〔2026〕3 号第 2–7 条 |
| 14 | 治安管理处罚法（2012 修正）条号 | 2026-01-01 修订 | 2025 修订版（144 条） |
| 15 | 建工解释（一）第 43 条第 2 款 实际施工人直接起诉发包人 | 2026-06-30 后新受理案件 | 法释〔2026〕12 号第 6–7、23 条；农民工工资另依保障农民工工资支付条例 |
| 16 | 贪污贿赂解释（法释〔2016〕9 号）第 11 条 二倍、五倍 | 2026-05-01 | 法释〔2026〕6 号第 8 条（取代系依第 24 条推断，需核） |
| 17 | 经济纠纷涉经济犯罪规定（法释〔1998〕7 号）；九民纪要第 128–130 条 | 2026-09-22 | 法释〔2026〕19 号（第 24 条冲突规则，未点名废止，逐条核对） |
| 18 | 指导案例 123、136、139、204 号 | 2026-08-15 不再参照 | 法〔2026〕119 号；生态环境法典 |
| 19 | 反不正当竞争法（2019 修正）第 7、12、19 条 | 2025-10-15 修订 | 第 8 条（新增受贿方）、第 13 条、第 24 条 |
| 20 | 环境保护法（2014）等 10 部法律 | 2026-08-15 废止 | 生态环境法典（主席令第 70 号） |
| 21 | 律师法（2017 修正）第 31、41 条等 | 2026-09-01 重新编号 | 第 34、44 条；新增第 3、7、46、62 条 |
| 22 | 对外贸易法（2022 修正）条号 | 2026-03-01 修订 | 2025 修订版（11 章 83 条） |
| 23 | 鼓励外商投资产业目录（2022 年版） | 2026-02-01 废止 | 2025 年版 |
| 24 | 「反外国制裁法实施条例」 | 名称引错 | 《实施〈反外国制裁法〉的规定》（国务院令第 803 号） |
| 25 | 北京最低工资 2,420 元；社保基数 7,162–35,811 | 2025-09-01、2026-07 换版 | 2,540 元；7,270–36,348 元 |

**未变（否定性结论，UNV）**：劳务派遣暂行规定仍为人社部令第 22 号（网传「2026 版」无官方出处）；北京人口与计划生育条例仍为 2021 修正；负面清单 2024 年版；经营者集中申报标准国务院令第 773 号；民诉法、民诉法解释第 247 条、合同编通则解释、担保制度解释 2026 年无修改；建筑法 2019 修正；行政处罚法 2021 后未改；人工智能法未提请审议；刑法修正案（十三）未见。

### 3.3 语料缺口处置（2026-10-15）

| 调研指出的缺口 | 处置 |
|---|---|
| `data-compliance/_shared/data-protection-citations.md` 仍引《网络安全法》（2017）第 21、37 条 | 新增「七之二、2026 年更新与条号变更」节，标注条号后移与认证办法、令第 24 / 25 号 |
| `construction-legal/_shared/construction-law-citations.md` 实际施工人可以发包人为被告 | 行内加法释〔2026〕12 号第 6–7、23 条限制；新增「六之二、2026 年更新」节 |
| `litigation-legal/_shared/civil-procedure-citations.md` 仲裁法版本说明仍为 1994 / 1995 | 改为 2025 修订（2026-03-01，撤销 3 个月）；新增「三之二、2026 年更新」节（法释〔2026〕19 号、法发〔2026〕10 号、法释〔2025〕15 号、案由修正、律师法、指导案例清理） |
| `regulatory-legal/_shared/administrative-law-citations.md` 起诉期限仍「待验证」 | B.3 / B.4 行内指向法释〔2026〕3 号与国务院令第 836 号；新增「I. 2026 年行政程序与税务裁量更新」节；H.3 补 36 号令条文、2026 年版清单文号 caveat、两部规章协调 UNV |
| `criminal-compliance/_shared/criminal-law-citations.md` 职务侵占等缺数额锚点 | C3 行内加法释〔2026〕6 号第 8 条；新增「H. 2026 年更新」节 |
| `employment-legal/_shared/labor-law-citations.md` 缺令第 56 号、法释〔2026〕14 号、案由修正 | G 节条号按官方全文重排（第 1–2、3、10、13–16、19 条）并加配套；新增「I. 超龄劳动者与退休年龄」节；案例类登记北京 2025 典型案例 |
| `presets/` 为物化副本 | 先改语料仓，再 `node scripts/materialize-corpus-skills.mjs` 重新物化（本次已执行） |

## 4. 对本仓与语料仓的影响（按影响排序）

| # | 建议 | 依据 | 状态 |
|---|---|---|---|
| 1 | 「已核验」= 法条逐字一致且现行有效 / 案例案号可解析且法院、案由、要旨与命题一致；其余只能是 retrieved / unverified | 通州、宜昌案；Princeton 核查器研究；HC142 | ✅ 语料 v1.2 研究闸门；产品侧 CITATION_AUDIT 护栏文案可同步细化 |
| 2 | 诉讼类导出门禁 + 自动生成《AI 辅助使用情况说明》；任一引用未核验不得标可提交 | 法发〔2026〕10号第 19 条；通州案要旨 | ✅ 语料；⏳ 产品（Phase 128 之后的导出面） |
| 3 | `deepseek-v4-flash` → `deepseek-flash`，走 `acp.cordis.yml` + 冒烟闸；增加「实际服务模型 == 钉住模型」门禁 | DeepSeek 2026-07-24 下线旧模型；官方两页冲突 | ⏳ 需真实 key，已记 STATE.md |
| 4 | 把北大法宝 MCP（`pku_citation_validator` 等，官方 CLI `@pkulaw/mcp-cli`）或企查查法律数据 MCP（`get_legal_citation_verify` / `get_judicial_citation_verify`）经 `session/new` 注入为研究闸门工具，token 入凭据库并列入 GRD-06 外传提示；用 LegalCiteTrust（Apache-2.0）做引用审计回归集 | 仅有的中国法引用校验服务；Astra 显示权威索引接地提升 15 点 | ⏳ 产品决策（语料 authoritative-sources 已登记） |
| 5 | GRD-06 按事项确认并记录「委托人已同意 / 已脱敏」，显示模型提供方所在地；含客户材料的事项默认境内提供方 | 大湾区倡议要求当事人同意；上海指引禁止未授权上传；境外提供方触发 PIPL 出境规则 | ⏳ 产品 |
| 6 | 去 AI 腔润色只改文风，不得删除 AI 使用说明、人审标记、导出文件标识 | 标识办法第 4 / 10 条 + 清朗执法；法发〔2026〕10号披露要求 | ✅ 语料交付 QA；⏳ 产品 DE_AI_POLISH 护栏文案 |
| 7 | 建 20–50 题中国法评测集（取自真实失败：假案号、改写司法解释、虚构条文序号、已废止法规），律师写 rubric，all-pass + pass^k，κ 校准裁判 | 无中国法 agent 基准；DeepSeek V4 Pro 落后榜首约 14 点；可作 HG-1 证据 | ⏳ 案例库复盘已列为下一步 |
| 8 | 交叉复核作为独立怀疑型评估者，输出标「AI 交叉审阅（非核验）」，不与引用审计状态混淆 | Anthropic harness 设计；HC142 | ⏳ Phase 128 人设文案 |
| 9 | 事实与引用 JSON 台账 + 只许改状态的尽调清单，回灌与压缩时回喂 | cookbook 压缩实验 0/3；长任务 harness 经验 | ✅ 语料 playbook 底稿 schema；⏳ 产品回灌面 |
| 10 | 导出文本中 `[HUMAN_REVIEW:]` 呈现为「【需律师核查】」；预设加入「不得编造法律依据、监管口径或案例」 | 上海律协 2026 指引惯例 | ✅ 语料交付 QA（可选惯例）；⏳ 产品 |
| 11 | 向业主以外的人分发 exe 前评估 CAC 登记义务 | 经 API 调用已备案模型的应用登记 731 款；清朗执法活跃；2023 暂行办法第 2 条对非公众服务的豁免未在本次重新核对 | ⏳ 发布前法律意见 |
| 12 | 批量任务（尽调扫描、复核轮次）避开北京工作日 09–12、14–18 | DeepSeek 峰谷定价两倍差 | ⏳ 操作建议 |
| 13 | DSH 钉版升级到 ≥0.1.2-rc.1 的精确版本（现 0.2.0-rc.2），`dsh-acp-demo` 换 `dsh-acp-app`，在 RTM-07 实测 `session/list` / `session/resume`；若可用，回灌路径可缩减或移除 | 2.7；FUTURE-08 触发条件已满足；触及决策 #3 | ⏳ **业主决定**；走 dsh-pin → gen-engine-lock → 冒烟闸 |
| 14 | 全部技能加 `evals/evals.json`（有 / 无技能对照），pass/fail 标准参照 LexRubric / PLawBench | agentskills 评测指南；HG-1 需逐技能证据 | ⏳ |
| 15 | 以 Harvey LAB `task.json` 格式建中国法 redline / DD 任务集 | 无中国基准 | ⏳（与第 7 条合并执行） |
| 16 | 移植上游 `corporate-legal`（tabular review、DD issue extraction、closing checklist、written consents、entity compliance）到中国实务 | 上游最大缺口；`equity-transaction-dd` 已覆盖部分 | ⏳ |
| 17 | DEFER-01 按 skill 逐个许可评估：约 42 个 MIT 可署名参照，19 个 CC BY-NC 排除 | legal-skills 实测 | ⏳ 业主决定 |
| 18 | App 内 OCR 用 oar-ocr（Rust，PP-OCRv6，印章模式），复杂版面可选 MinerU 4 sidecar；用自有扫描案卷（案号、金额、日期）抽样评分 | 2.6；厂商无法院文书准确率 | ⏳ 产品（新依赖需计划批准） |
| 19 | 语料仓 `connectors/gsxt` 占位改用企查查 / 元典企业数据 | GSXT 403；信用中国验证码 | ⏳；语料已登记替代源 |
| 20 | 修订类工作流（语料侧，或日后重开 APP-04）以 docx-redline-js 的「拒绝全部恢复源稿」为门禁，配合 OfficeCLI；避开 AGPL 的 jubarte 与专有条款的 Anthropic docx 脚本 | 2.5 | ✅ 语料 document-delivery-qa 第 6 节已登记 |
| 21 | `src-tauri` 控制面参考 Rust `agent-client-protocol` crate 与 Jockey / Perch / Martty | 2.7 | ⏳ 新依赖需 phase 计划批准 |

**未找到 / 未核实**：通义法睿、法行宝、AlphaGPT、MeCheck、小包公、法狗狗、无讼的 2026 官方发布；中国产品的 Word / WPS 原生修订；Vals 2026 报告或 Stanford 2026 幻觉更新；全国律协 / 司法部全国指引；2026 年 9–10 月《人工智能法》草案；DeepSeek 2026 隐私政策变更；标识办法对律所交付物的官方口径。
