---
phase: 102
slug: legal-guardrail-port
status: complete
created: 2026-08-08
---

# Phase 102 Research — Legal Guardrail Port

## Executive Summary

Phase 102 ports the most valuable legal product knowledge from `lawyer-desktop`'s Rust core into the Python `packages/agent-core`. The port covers four components: (1) `skills/router.rs` (627 lines) — Chinese legal prompt assembly with three-mode base prompts, research-gate injection, retrieval tool mapping, citation writing spec, and skill description/body injection; (2) `llm/tool_leak.rs` (392 lines) — tool call leak detection and parsing with DSML/XML variant recognition, full-width character normalization, and leak retry logic; (3) citation audit (`citations/` module, 589 lines total) — citation extraction via regex, three-state verification (verified/retrieved/unverified) against local law library and retrieval evidence; (4) four legal guardrails enforced at code level — research-gate, ask-user-enforcement, citation audit, and de-AI polish.

The Python target (`packages/agent-core`) is well-prepared: Phase 100 built the async streaming turn loop, context assembler, event emitter, and model layer (550 tests); Phase 101 added the tool layer (clarification, file_read, regulation_search, document_generate, MCP client). The event vocabulary already includes `citation.recorded` with `CitationRecordedPayload` and `CitationRecord` dataclasses (defined in Phase 88). The EventEmitter does NOT yet have an `emit_citation_recorded()` convenience method — this must be added. The turn loop has a `tool_executor` seam and side-channel event buffer that citation audit can use to emit `citation.recorded` events. The de-AI polish guardrail has no Rust implementation — it is a concept referenced in skill `declared_gates` metadata (`de-ai-polish`) and the PRD, but has no existing code in `lawyer-desktop`; it must be designed fresh in Python.

The highest risk is prompt logic distortion (HG-1, not auto-closable). The mitigation is a golden fixture comparison set: Rust-side test cases from `tool_leak.rs` (11 tests), `router.rs` (10 tests), `citations/extract.rs` (10 tests), and `citations/verify.rs` (2 tests) become the Python-side comparison set. Each must pass with equivalent behavior. The `skill_candidate.requires_human_review` safety invariant has no Rust implementation either — it is a platform-level safety rule that must be enforced in the Python core with test assertions.

## Source Analysis

### 1. router.rs — Chinese Legal Prompt Assembly

**File**: `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/src/skills/router.rs` (627 lines)

#### Three Modes

The `build_system_prompt()` function (line 139) takes an `AgentMode` enum (Chat / Draft / Evidence) and selects a different base prompt for each:

**Draft mode** (lines 149-164): Inline string — "你是一位专业的中国法律 AI 助手，面向中国大陆执业律师". Includes:
- 重要声明 (output is draft for lawyer review, not legal advice)
- ## 工作原则 (4 principles: cite precise article numbers, mark uncertain as [待律师复核], state conflicts, no Baidu Baike/Zhihu as legal source)
- ## 文书输出格式（起草时强制）(5 rules: JSON output structure with `assistant_notes` + `document`, separation of notes vs document, API tool calls only, mandatory first-turn `ask_user` with 2-4 questions, complete `document.sections`)

**Chat (Q&A) mode** — `build_qa_system_prompt()` (lines 195-213): "你是一位专业的中国法律 AI 助手...进行**自由法律问答 / 法律研究 / 风险分析**". Key rules:
- No formal document output, no JSON document structure
- Search before answering for specific statutes/cases
- `fetch_url` for user-provided URLs
- Pure definitional/process questions can be answered directly
- No forced `ask_user` — don't stop answering for missing info
- Markdown output, conclusion-first

**Evidence mode** — `build_evidence_system_prompt()` (lines 215-236): "你是一位专业的中国法律 AI 助手，正在基于用户授权的本地案卷目录进行**证据驱动**分析与写作". Key rules:
- 禁止臆测 — all facts from workspace tool retrieval
- 禁止 bulk directory dump — must use `search_workspace` → `read_chunk`/`read_file`
- Key conclusions must cite `relative_path` and/or `chunk_id`
- Five-stage workflow: Plan → Clarify (首轮强制 ask_user) → Evidence → Research (法律检索) → Write
- Output: Markdown 诉讼方案 (not JSON), starts with `# 文书标题`

#### Research-Gate Injection (lines 167-171)

After the mode-specific base prompt, the research-gate is injected in ALL modes (including Evidence — "evidence reports cite statutes too"):

```rust
let gate = research_gate_content.unwrap_or(RESEARCH_GATE_FALLBACK);
prompt.push_str(gate);
prompt.push_str("\n\n");
```

The `RESEARCH_GATE_FALLBACK` constant (lines 5-14) is used when no `research-gate` skill content is loaded from the skill corpus:

```rust
const RESEARCH_GATE_FALLBACK: &str = r#"## research-gate（强制前置）

在生成任何法律文书、出具法律意见或引用具体法条之前，你必须：

1. 先通过可用工具检索相关法律法规、司法解释或权威案例
2. 确认检索结果与用户需求匹配后，再起草文书内容
3. 每条法条引用必须标注精确条文号与来源层级
4. 无法检索到权威来源时，标注 [待律师复核] 并说明检索局限
5. 禁止仅依据训练数据中的法条记忆直接作答
"#;
```

When the skill corpus is available, `research_gate_content` is loaded from `shared/research-gate/SKILL.md` via `loader::load_research_gate(&root)` (chat.rs line 468-469). The loaded content replaces the fallback.

#### Retrieval Tool Mapping (lines 34-137)

**`is_retrieval_tool_name(name)`** (lines 36-49): Returns true for known retrieval tool names:
- Direct matches: `legal_search`, `search_law`, `get_law_article`, `fetch_url`, `search_workspace`
- MCP tools (`mcp__` prefix): checks if name contains fragments `["law", "legal", "fagui", "statute", "wenshu", "case", "judgment"]` OR matches public web tool text

**`is_public_web_tool_text(text)`** (lines 51-58): Checks for fragments `["web", "search", "fetch", "url", "browser", "crawl", "网页", "搜索", "抓取", "链接"]`

**`is_retrieval_tool(name, description)`** (lines 60-63): Combines name check + description check for MCP tools.

**`RETRIEVAL_TOOL_MAP`** (lines 67-99): Static array of 10 `(tool_name, mapped_research_step)` pairs:
- `legal_search` → "聚合检索法律依据（一次并发查本地法规库与在线官方源，检索首选）"
- `fetch_url` → "读取用户本轮明确提供的网页链接"
- `search_law` → "本地法规库全文检索（定位法条，离线可用）"
- `get_law_article` → "本地法规库精确取条文原文"
- `mcp__law-database__search_laws` → "在线检索法律法规"
- `mcp__law-database__get_law_detail` → "在线获取法规全文"
- `mcp__law-database__search_cases_by_law` → "按法条检索关联指导/公报案例"
- `mcp__wenshu__search_cases` → "检索裁判案例"
- `mcp__wenshu__get_case_detail` → "按案号获取案例详情"
- `search_workspace` → "检索本地案卷材料"

**`build_retrieval_tool_mapping(retrieval_tools)`** (lines 103-137): Builds the prompt section `## 检索工具映射`. Key behavior:
- If `retrieval_tools` is empty → emits honest degradation text: "当前未接入任何法律检索工具...禁止声称「已检索」「经检索形成」；所有法条与案例引用必须标注 [待律师复核]"
- If non-empty → emits "本应用没有 WebSearch/WebFetch。research-gate 中的检索步骤按以下映射执行：" followed by:
  1. Lines from `RETRIEVAL_TOOL_MAP` where the tool is actually available (only promises available tools)
  2. Unknown retrieval tools (not in the map) get a generic description
  3. Closing warning: "以上清单之外的检索工具不存在，禁止假装调用或声称已检索"

#### Citation Writing Spec (lines 175-181)

Injected after the retrieval tool mapping in ALL modes:

```rust
prompt.push_str(
    "## 引用书写规范（核验契约）\n\
    1. 法条统一写 `《法名》第N条`（如《中华人民共和国民法典》第五百八十五条）\n\
    2. 司法解释附文号 `法释〔YYYY〕N号`；行政法规可附 `国务院令第N号`\n\
    3. 案例附完整案号（如 `（2024）渝01民初1234号`）或入库案例编号（如 `2024-10-2-358-001`）\n\
    4. 未经工具检索核验的引用一律标注 [待律师复核]\n\n",
);
```

#### Skill Description List & Active Skill Body Injection (lines 16-32, 183-190)

**`build_skill_descriptions(skills)`** (lines 16-32): Builds `## 可用法律技能` section listing all skills as `- **{name}** ({plugin_name}): {description}`, skipping `research-gate` (it's injected separately).

**Active skill body injection** (lines 185-190): If an `active_skill` is provided, injects:
```
## 当前激活技能: {skill.name}

{skill.full_content}
```

#### Tool Definitions (lines 238-501)

Three groups of tool definitions:
1. `build_workspace_tool_definitions()` (lines 238-308): `search_workspace`, `read_chunk`, `read_file`, `list_files`, `get_index_status`
2. `build_law_tool_definitions()` (lines 312-361): `legal_search`, `search_law`, `get_law_article`
3. `build_builtin_tool_definitions(mode, include_workspace)` (lines 363-501): `read_user_file`, `fetch_url`, `generate_docx`, `select_skill`, `ask_user` — plus law tools and optionally workspace tools. **Chat mode excludes `generate_docx`** (line 490-492).

#### `route_skill()` (lines 503-505)

Simple lookup: `skills.iter().find(|s| s.name == skill_name)`.

### 2. tool_leak.rs — Tool Call Leak Detection

**File**: `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/src/llm/tool_leak.rs` (392 lines)

#### KNOWN_TOOLS Constant (lines 5-16)

```rust
const KNOWN_TOOLS: &[&str] = &[
    "search_workspace", "read_chunk", "read_file", "list_files",
    "get_index_status", "read_user_file", "fetch_url", "generate_docx",
    "select_skill", "ask_user",
];
```

#### Full-Width Character Normalization (lines 18-23)

```rust
fn normalize_marker_chars(text: &str) -> String {
    text.replace('｜', "|").replace('▁', "_")
}
```

Maps DeepSeek DSML full-width characters: U+FF5C `｜` → `|`, U+2581 `▁` → `_`. This is applied before all detection and parsing.

#### `contains_tool_leakage(text)` (lines 26-47)

Returns true if the text contains leaked tool-call markup. Checks (on normalized + lowercased text):
- `dsml`, `tool_calls`, `tool_call`, `tool_c`, `</_calls`, `_calls>`
- `< name=`, `<name=`, `<invoke`, `invoke>`, `</invoke`, `invoke name=`, `invoke=`
- `parameter name=`, `parameter name `
- `function_call`, `<|`, `|>`, `toolalls`

#### `sanitize_assistant_content(text)` (lines 50-121)

Strips tool markup from assistant text for display/persistence. Three-phase approach:

1. **Block removal** (lines 53-72): While-loop removes `<tool_calls>...</tool_calls>` blocks and `<invoke>...</invoke>` blocks (case-insensitive). Also handles nested `<invoke` within invoke blocks.

2. **Line filtering** (lines 74-118): Iterates lines, skips lines that contain leak markers (same set as `contains_tool_leakage`). Also strips `<...>` lines where the inner content starts with known tool-leak tags (`tool_call`, `_call`, `invoke`, `parameter`, `name=`, `function_call`, `dsml`). **Preserves HTML formatting tags** (`<br>`, `<table>`, `<strong>`, `<p>`, etc.) — only strips tool-leak tags, not all HTML.

3. **Collapse blank lines** (lines 120-121): `collapse_blank_lines()` just trims.

#### `normalize_tool_name(raw)` (lines 131-164)

Fuzzy-matches leaked tool names to known tools:
1. Exact match against `KNOWN_TOOLS`
2. Substring heuristics: `search`+`work`/`space`/`pace` → `search_workspace`, `read`+`chunk` → `read_chunk`, `read`+`file` → `read_file`, `list`+`file` → `list_files`, `index`+`status` → `get_index_status`
3. Fallback: `KNOWN_TOOLS.contains(n) || known.contains(n)` bidirectional substring match

#### `parse_parameter_value(block, param_name)` (lines 166-188)

Extracts parameter values from `<parameter name="key">value</parameter>` blocks. Handles both `"` and `'` quotes. Value is text between `>` and `<` (or newline/`|` if no closing tag).

#### `extract_invoke_name(block)` (lines 201-213)

Extracts tool name from invoke header only (not from `<parameter name="...">` fields inside). Handles `invoke name="x"` and mangled `invoke="x"` variants.

#### `parse_invoke_block(block)` (lines 215-244)

Parses a complete `<invoke name="...">...</invoke>` block into `(tool_name, args_json)`. Extracts parameters: `query`, `k`, `chunk_id`, `relative_path`, `max_chars`, `pattern`, `path`, `url`, `skill_name`, `reason`. Numeric params (`k`, `max_chars`) are parsed as integers.

#### `parse_embedded_tool_calls(content)` (lines 247-287)

Main entry point for parsing leaked tool calls. Scans for `invoke` occurrences (case-insensitive), extracts blocks bounded by `</invoke>` or next `<invoke`, parses each block. Only accepts tools in `KNOWN_TOOLS` or starting with `mcp_`. Returns `Vec<ToolCall>` with UUID-generated IDs (`embedded_{uuid}`).

#### Leak Retry Logic (in chat.rs, not tool_leak.rs)

The leak retry logic is in `commands/chat.rs` (lines 36, 760, 934-957, 1064-1083, 1106-1111):
- `MAX_LEAK_RETRIES: usize = 3` (line 36)
- When `contains_tool_leakage()` detects leakage in assistant content:
  - If `leak_retries < MAX_LEAK_RETRIES`: increment counter, log warning, retry the same request (do NOT feed leaked text into history)
  - If exhausted: set `leak_fallback = true`, retry without tools (line 1106-1111)
- After all retries, `sanitize_assistant_content()` is called on the final response (line 1233)
- Historical messages with leakage are also sanitized before being fed back (line 1648)

### 3. Citation Audit

**Files**:
- `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/src/citations/mod.rs` (55 lines)
- `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/src/citations/extract.rs` (284 lines)
- `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/src/citations/verify.rs` (250 lines)
- `/home/sorawatcher/workspace/lawyer-desktop/src-tauri/src/law_library/mod.rs` (568 lines — local law library, the verification anchor)

#### Data Structures (mod.rs lines 12-38)

```rust
pub struct CitationAuditItem {
    pub kind: CitationKind,        // Law | Interpretation | Case
    pub source: String,            // 法名 (without 《》) or empty for bare case numbers
    pub reference: String,         // 第N条 / 法释〔YYYY〕N号 / case number
    pub status: String,            // "verified" | "retrieved" | "unverified"
    pub tier: Option<String>,      // 来源层级 (e.g. "L1-法规（本地库）")
    pub excerpt: Option<String>,   // 160-char excerpt of verified text
    pub url: Option<String>,       // source URL
    pub note: Option<String>,      // human-readable note (e.g. "待律师复核")
}

pub struct CitationAudit {
    pub items: Vec<CitationAuditItem>,
    pub total: usize,
    pub verified: usize,
    pub retrieved: usize,
    pub unverified: usize,
}
```

#### `audit(text, retrievals)` (mod.rs lines 43-55)

Entry point. `retrievals` are `(tool_name, result_text)` pairs from this turn's retrieval tools. Never fails — errors degrade to unverified. Flow:
1. `extract_citations(text)` → `Vec<ExtractedCitation>`
2. `verify::verify_items(extracted, retrievals)` → `Vec<CitationAuditItem>`
3. Count statuses → `CitationAudit`

#### Citation Extraction (extract.rs lines 1-162)

Five regex patterns extract citations from text:

1. **`law_article_re()`** (lines 30-38): `《([^《》\n]{2,48})》\s*(第[零一二三四五六七八九十百千0-9]+条...)` — extracts `《法名》第N条` with Chinese/Arabic numerals, 之 suffix, and enumeration (、和及与)

2. **`article_list_re()`** (lines 40-46): `第[零一二三四五六七八九十百千0-9]+条(?:之[一二三四五六七八九十])?` — extracts individual article references from within a law citation (expands enumerations like 第六百八十六条、第六百八十八条)

3. **`interpretation_re()`** (lines 48-54): `(?:《([^《》\n]{2,64})》...)?(法释[〔\[（(]\d{4}[〕\]）)]\d{1,3}号)` — extracts judicial interpretation doc numbers

4. **`state_council_decree_re()`** (lines 56-62): `(?:《([^《》\n]{2,64})》...)?(国务院令第\d{1,4}号)` — extracts State Council decrees

5. **`case_number_re()`** (lines 64-72): Full case numbers like `（2024）渝01民初1234号` — matches fullwidth/halfwidth brackets, court codes, case types (民初/民终/民申/刑初/行初/执异/知民终/破申/赔/仲/清申 etc.)

6. **`db_case_id_re()`** (lines 74-77): `\d{4}-\d{2}-\d-\d{3}-\d{3}` — 入库案例编号 like `2024-10-2-358-001`

**`normalize_doc_number(s)`** (lines 80-88): Normalizes bracket variants so `法释[2020]28号` == `法释〔2020〕28号` for dedup.

**`extract_citations(text)`** (lines 91-162): Runs all regexes, deduplicates by `(kind, source, reference)`, preserves first-occurrence order.

#### Three-State Verification (verify.rs lines 1-213)

**`verify_items(extracted, retrievals)`** (lines 199-213): Dispatches by `CitationKind`:
- `Law` → `verify_law_article()` (async)
- `Interpretation` → `verify_interpretation()` (async)
- `Case` → `verify_case()` (sync)

**`verify_law_article()`** (lines 39-101):
1. Try `law_library::lookup_article(source, reference)` — local law library exact match
2. If `ArticleLookup::Found` → status="verified", tier="L1-法规（本地库）", excerpt=160 chars, url from entry. If status != "现行有效", add warning note.
3. If `LawFoundArticleMissing` → note about wrong article number, stays unverified
4. If not in local library → check retrieval evidence: `find_in_retrievals(retrievals, [source, reference])`. If found → status="retrieved", tier from result. If not → status="unverified", note="待律师复核"

**`verify_interpretation()`** (lines 103-158):
1. Try `law_library::find_by_doc_number(reference)` — match by 文号
2. If found → verified. If not, try `lookup_article(source, "第一条")` — match by adjacent 《name》
3. Fall back to retrieval evidence
4. Fall back to unverified

**`verify_case()`** (lines 160-197):
1. Weak verification: case number must appear in this turn's retrieval output
2. Also try halfwidth-bracket form (convert （ to ( )
3. If found in retrievals → status="retrieved", tier from result
4. If not → status="unverified", note="本轮检索结果中未出现该案号 — 待律师复核"

**Helper functions**:
- `excerpt(text)` (lines 9-16): 160-char excerpt with ellipsis
- `tier_from_result(result)` (lines 18-25): Extracts `来源层级:` line from retrieval result
- `find_in_retrievals(retrievals, fragments)` (lines 28-37): Finds retrieval result containing ALL fragments

#### Citation Audit Integration in chat.rs (lines 762-1244)

- `turn_retrievals: Vec<(String, String)>` accumulates `(tool_name, result_text)` from retrieval tools across all tool rounds (line 763)
- After final response: `crate::citations::audit(&full_response, &turn_retrievals).await` (line 1241)
- Audit result emitted as trace event `"citation_audit"` (line 1242)
- Audit result stored in message metadata as `citation_audit` field (lines 1247-1250)

### 4. Four Legal Guardrails

#### Guardrail 1: Research-Gate (未检索不得给法律结论)

**Where implemented**: 
- **Prompt-level**: `router.rs` lines 5-14 (fallback), 167-171 (injection). The research-gate text is injected into every system prompt in every mode.
- **Skill-level**: `shared/research-gate/SKILL.md` in `ai-for-china-legal` — the full research-gate skill content is loaded and injected when available (chat.rs lines 468-473).
- **Tool-mapping enforcement**: `build_retrieval_tool_mapping()` (router.rs lines 103-137) — only promises actually-available tools, explicitly states "禁止假装调用或声称已检索" when tools are missing.
- **Citation spec enforcement**: "未经工具检索核验的引用一律标注 [待律师复核]" (router.rs line 180).

**How it enforces**: The system prompt explicitly instructs the LLM to search before concluding, and the citation audit (guardrail 3) post-hoc verifies whether citations were actually retrieved. The guardrail is prompt-level (instructs the model) + audit-level (verifies compliance after the fact). There is no code-level **block** that prevents the model from outputting legal conclusions without research — the enforcement is through prompt instructions + citation audit labeling.

**Python port implication**: The research-gate must be injected into the system prompt assembled by the Python prompt assembler. The citation audit must run after the final response and label unverified citations. Code-level enforcement means the prompt assembler MUST inject the research-gate — there is no code path that assembles a legal prompt without it.

#### Guardrail 2: Ask-User-Enforcement (关键事实缺失时阻断起草)

**Where implemented**:
- **Prompt-level**: Draft mode prompt (router.rs lines 162-163): "本会话首次正式起草前，必须调用一次 ask_user 提出 2-4 个必要问题". Evidence mode prompt (router.rs line 225): "Clarify（首轮强制）...必须调用一次 ask_user".
- **Tool-level**: The `ask_user` tool definition (router.rs lines 439-485) with 2-4 question validation.
- **Turn-level**: `finish_ask_user_turn()` in chat.rs (lines 1326-1390) — when the LLM calls `ask_user`, the turn is terminated, `waiting_for_user` status is emitted, and the conversation pauses.
- **Python existing**: The clarification tool (`packages/agent-core/src/inkstatute_agent_core/tools/clarification.py`) already implements `ask_user` with `terminate_turn` metadata and `elicitation.requested` event emission.

**How it enforces**: The prompt instructs the LLM to call `ask_user` before drafting. The tool handler terminates the turn. The LLM cannot produce a draft without first calling `ask_user` (unless the user has already provided all key facts, in which case the prompt allows skipping). This is prompt-level instruction + tool-level turn termination.

**Python port implication**: The prompt assembler must include the ask-user enforcement text in Draft and Evidence modes. The existing clarification tool already handles turn termination. Code-level enforcement means the prompt MUST include the ask-user mandate in Draft/Evidence modes — no code path should assemble a Draft/Evidence prompt without it.

#### Guardrail 3: Citation Audit

**Where implemented**: `citations/` module (589 lines total) — see Section 3 above.

**How it enforces**: Post-hoc annotation. The audit never blocks output (mod.rs line 3: "Annotation-style — never blocks output"). It extracts all citations, verifies each against local law library + retrieval evidence, and labels as verified/retrieved/unverified. Unverified citations get `[待律师复核]` notes. The audit result is attached to the message metadata.

**Python port implication**: Must port the extraction regexes and three-state verification logic. Must emit `citation.recorded` event (the event type already exists in the platform contract). The audit runs after the final response, before `message.completed`.

#### Guardrail 4: De-AI Polish

**Where implemented**: **No Rust implementation exists.** The de-AI polish guardrail is:
- Referenced in the PRD (V3-PRD.md line 209, 424, 475) as one of four guardrails
- Referenced in skill `declared_gates` metadata: `metadata_extractor.py` line 60 — pattern `"de-ai-polish"` with aliases `["de-ai-polish", "去AI化", "de-AI"]`
- Referenced in ROADMAP Phase 98 success criteria (line 266): `gate_after = legal-de-ai-polish`
- **No code in `lawyer-desktop`** implements de-AI polish — grep for `de.?AI|polish|去AI|AI腔|AI味` in `lawyer-desktop/src-tauri/src/` found zero matches in Rust source code.

**What it should do**: Remove AI-sounding language patterns from legal text output. This is a post-processing step that detects and removes/phrases characteristic AI language patterns (e.g., "作为一个AI", "根据我的理解", overly formal/robotic phrasing, excessive hedging) from generated legal documents.

**Python port implication**: Must be designed fresh. The implementation should be a post-processing function that:
1. Detects AI-characteristic language patterns in the final response
2. Removes or rewrites them
3. Has tests verifying that AI-sounding text is cleaned
4. Is enforced at code level (called after citation audit, before `message.completed`)

### 5. Rust Test Cases (Golden Fixture Source)

These are the exact test cases that must be replicated as Python-side golden fixtures.

#### tool_leak.rs Tests (11 tests, lines 289-391)

| # | Test Name | What It Verifies |
|---|-----------|-----------------|
| 1 | `detects_dsml_leakage` | `\| \| DSML \| \| tool_calls>` → true; `<invoke name="search_workspace">` → true |
| 2 | `detects_fullwidth_dsml_leakage` | Real DSML leak with U+FF5C `｜` → true; `<｜tool▁calls▁begin｜>` → true |
| 3 | `sanitize_strips_real_fullwidth_leak_completely` | `REAL_DSML_LEAK` constant → sanitizes to empty string |
| 4 | `sanitize_keeps_clean_markdown_tables` | Markdown table with `\|` separators → unchanged |
| 5 | `sanitize_strips_inline_leak_lines_but_keeps_prose` | Mixed text → strips DSML lines, keeps "以下是分析：" and "结论：可以起诉。" |
| 6 | `parses_mangled_fullwidth_invoke_to_known_tool` | `REAL_DSML_LEAK` → parses to 1 call, tool_name="search_workspace", args contain "保 投标见即付不可" |
| 7 | `parses_invoke_block` | Standard `<invoke name="search_workspace">` with query/k params → 1 call, correct name and args |
| 8 | `does_not_treat_parameter_name_as_invoke_name` | `<invoke><parameter name="search_workspace">` → 0 calls (parameter name is not invoke name) |
| 9 | `detects_and_strips_bare_parameter_tool_fragment` | Bare `parameter name lawName...invoke>` → detected + sanitized to empty |
| 10 | `detects_and_strips_shortened_tool_c_fragment` | `tool_c>< name="law_name"...` → detected + sanitized to empty |
| 11 | `sanitize_keeps_html_formatting_tags` | `<br>`, `<table>`, `<strong>` → preserved |
| 12 | `sanitize_keeps_short_html_like_tags_under_120` | `<p>` → preserved |

**`REAL_DSML_LEAK` constant** (line 295): Verbatim leaked content from a real failed conversation (deepseek-v4-pro, 2026-06-10):
```
<｜｜DSML｜｜tool_c>\n<｜｜DSML｜｜invoke="search_">\n<｜｜DSML｜｜parameter namek" stringfalse">13｜｜DSML｜｜parameter>\n<｜｜DSML｜｜ name="query" stringtrue">保 投标见即付不可</｜｜DSML｜｜parameter>\n</invoke>\n</｜｜DSML｜｜_calls>
```

#### router.rs Tests (10 tests, lines 507-626)

| # | Test Name | What It Verifies |
|---|-----------|-----------------|
| 1 | `evidence_prompt_mandates_clarify_research_and_review_markers` | Evidence prompt contains "Clarify（首轮强制）", "ask_user", "Research（法律检索）", "[待律师复核]", "research-gate" |
| 2 | `draft_prompt_mandates_first_turn_clarification_and_gate` | Draft prompt contains "必须调用一次 ask_user", "research-gate", "引用书写规范" |
| 3 | `qa_prompt_keeps_gate_but_drops_drafting_mandates` | Chat prompt has "research-gate", "引用书写规范", "法律问答"; does NOT have "文书输出格式（起草时强制）", "必须输出一个 JSON 对象", "必须调用一次 ask_user" |
| 4 | `tool_mapping_lists_only_available_tools` | With tools ["search_law", "mcp__law-database__search_laws"] → mapping contains both, does NOT contain "mcp__wenshu__search_cases", contains "清单之外的检索工具不存在" |
| 5 | `empty_tool_list_degrades_honestly` | Empty tool list → mapping contains "未接入任何法律检索工具", "[待律师复核]" |
| 6 | `qa_mode_excludes_generate_docx_but_other_modes_keep_it` | Chat mode: no generate_docx; Draft mode: has generate_docx; Evidence mode: has generate_docx |
| 7 | `chat_mode_keeps_fetch_url_but_excludes_docx` | Chat mode tools include fetch_url, exclude generate_docx |
| 8 | `public_web_tools_are_retrieval_tools` | `fetch_url` with Chinese desc → true; `mcp__browser__fetch` with English desc → true; `mcp__web-search__search` → true; `mcp__settings__update_config` → false |
| 9 | `retrieval_tool_name_detection` | legal_search, search_law, get_law_article, fetch_url, search_workspace, mcp__law-database__search_laws, mcp__wenshu__get_case_detail → true; generate_docx, ask_user, mcp__gsxt__query_company → false |

#### citations/extract.rs Tests (10 tests, lines 164-284)

| # | Test Name | What It Verifies |
|---|-----------|-----------------|
| 1 | `extracts_law_article_chinese_and_arabic` | `《中华人民共和国民法典》第五百八十五条` + `《公司法》第20条` → 2 Law citations |
| 2 | `expands_article_enumerations` | `《民法典》第六百八十六条、第六百八十八条` → 2 citations |
| 3 | `extracts_zhi_yi_suffix` | `《刑法》第二百八十七条之一` → reference="第二百八十七条之一" |
| 4 | `extracts_interpretation_with_adjacent_name` | `《...担保制度的解释》（法释〔2020〕28号）` → Interpretation with ref="法释〔2020〕28号" |
| 5 | `normalizes_interpretation_bracket_variants` | `法释[2016]24号` → normalized to `法释〔2016〕24号` |
| 6 | `extracts_state_council_decree` | `《融资担保公司监督管理条例》（国务院令第683号）` → Interpretation with source and reference |
| 7 | `extracts_case_numbers_fullwidth_and_halfwidth` | `（2024）渝01民初1234号` and `(2023)京民终567号` → 2 Case citations, both normalized to fullwidth |
| 8 | `extracts_specialized_case_types` | `（2022）最高法知民终82号` and `（2021）粤03执异77号` → 2 citations |
| 9 | `extracts_db_case_ids` | `2024-10-2-358-001` → 1 Case citation |
| 10 | `dedupes_repeated_citations` | `《民法典》第五百八十五条` repeated → 1 citation |
| 11 | `ignores_plain_text_without_citations` | Text without citations → empty; `第十条` without 《》 → empty |
| 12 | `handles_inner_book_titles_in_law_name` | `《最高人民法院关于适用〈中华人民共和国民法典〉有关担保制度的解释》第二十一条` → Law with source containing "担保制度的解释" |

#### citations/verify.rs Tests (2 tests, lines 215-250)

| # | Test Name | What It Verifies |
|---|-----------|-----------------|
| 1 | `case_numbers_verify_against_retrievals_only` | Case in retrieval → "retrieved" with tier; case not in retrieval → "unverified" with "待律师复核" note |
| 2 | `law_articles_without_library_fall_back_to_retrievals` | Law article in retrieval → "retrieved"; law article not in retrieval → "unverified" |

**Total: 35 Rust test cases** become the Python golden fixture comparison set.

## Target Analysis

### 6. Python Agent-Core Structure

**Package**: `/home/sorawatcher/workspace/inkstatute-suite/packages/agent-core/`
**Layout**: `src/inkstatute_agent_core/`

```
src/inkstatute_agent_core/
├── __init__.py          # Package docstring, __version__
├── config.py            # AgentCoreConfig (frozen dataclass)
├── context.py           # AgentContextAssembler (580 lines — history trim + skill body injection)
├── event_emitter.py     # EventEmitter (419 lines — monotonic seq, heartbeat, side-channel)
├── fixtures.py          # Test fixtures
├── messages.py          # Message helpers
├── model/               # Model layer (provider.py, openai_runner.py, anthropic_runner.py, ollama_runner.py, etc.)
├── turn_loop.py         # run_turn() async generator (391 lines)
└── tools/               # Tool layer
    ├── __init__.py       # Exports all tools
    ├── builtin_registry.py  # create_builtin_registry() factory
    ├── clarification.py     # ask_user tool (elicitation.requested + terminate_turn)
    ├── document_generate.py # generate_review_docx tool (Word track-changes)
    ├── executor.py          # create_dispatching_executor()
    ├── file_read.py         # read_file tool (PathSandbox)
    ├── mcp_client.py        # MCP client (JSON-RPC stdio)
    ├── path_sandbox.py      # PathSandbox (traversal protection)
    ├── regulation_search.py # search_laws tool (MCP or fixture)
    └── registry.py          # ToolRegistry
```

#### Turn Loop (turn_loop.py)

`run_turn()` (line 84) is an async generator yielding `RunEvent` objects. Key structure:
1. **Round loop** (line 121): `for _round in range(config.max_turns)`
2. **Phase emit** (line 123): `emit_phase_changed(phase, previous_phase)`
3. **LLM streaming** (lines 150-163): `async for delta in provider.chat_stream(request)` — handles ContentDelta, ReasoningDelta, ToolCallDelta, UsageDelta, FinishDelta
4. **Tool call execution** (lines 181-316): If tool_call_deltas accumulated:
   - Build assistant message with tool calls
   - For each tool call: emit `tool_call.started`, heartbeat, execute via `tool_executor`, drain side-channel events, emit `tool_call.completed`
   - Check `terminate_turn` metadata (for ask_user)
   - Append tool results to messages, continue to next round
5. **Final content** (lines 318-330): If no tool calls — emit `message.completed` + `run.state_changed(succeeded)`
6. **Turn limit** (lines 332-339): If max_turns reached — emit `error` + `run.state_changed(failed)`

**Tool executor seam**: `tool_executor: ToolExecutor | None` where `ToolExecutor = Callable[[str, str, dict], Awaitable[ToolResult]]`. The `create_dispatching_executor(registry)` function wraps a `ToolRegistry` into this interface.

**Where new code fits**:
- **Prompt assembler**: New module `prompt_assembler.py` (or `prompt.py`) — replaces the current simple system prompt with the full `build_system_prompt()` logic. The turn loop's `messages` parameter currently receives pre-built messages; the prompt assembler would build the system message.
- **Tool leak detector**: New module `tool_leak.py` — `contains_tool_leakage()`, `sanitize_assistant_content()`, `parse_embedded_tool_calls()`, `normalize_marker_chars()`, `normalize_tool_name()`. Called in the turn loop after streaming content, before `message.completed`.
- **Citation auditor**: New module `citation_audit.py` (or `citations/` sub-package) — `extract_citations()`, `verify_items()`, `audit()`. Called after final response, before `message.completed`. Emits `citation.recorded` via side-channel.
- **Guardrails**: New module `guardrails.py` — orchestrates the four guardrails. Research-gate and ask-user-enforcement are prompt-level (enforced by prompt assembler). Citation audit is post-hoc. De-AI polish is post-processing.
- **Leak retry**: Integrated into turn loop — after streaming, if `contains_tool_leakage(content)`, retry up to `MAX_LEAK_RETRIES` (3).

#### Context Assembler (context.py)

`AgentContextAssembler` (580 lines) handles:
- CJK-aware token estimation
- Skill body parsing into sections by `##` headers
- Priority-based section trimming (Protected → High → Medium → Low)
- History trimming (max_history_turns, budget fraction)
- Total token budget enforcement

This is where skill body injection happens. The prompt assembler should use the context assembler's skill body injection capability for the `active_skill` body injection part of `build_system_prompt()`.

### 7. Event Vocabulary

**`citation.recorded` event**: **Already defined** in the platform contract:
- `RunEventType.CITATION_RECORDED = "citation.recorded"` (enums.py line 123)
- `CitationRecordedPayload` (unified_events.py lines 138-141): `citations: list[CitationRecord]`, `metadata: JsonObject`
- `CitationRecord` (unified_events.py lines 132-135): `source: str`, `status: str`
- Registered in `_PAYLOAD_REGISTRY` (unified_events.py line 175)

**EventEmitter**: Does NOT yet have `emit_citation_recorded()` method. Current methods:
- `emit_message_delta`, `emit_message_completed`, `emit_thought_delta`
- `emit_tool_call_started`, `emit_tool_call_delta`, `emit_tool_call_completed`
- `emit_phase_changed`, `emit_run_state_changed`, `emit_error`
- `emit_artifact_created` (side-channel), `emit_elicitation_requested` (side-channel)

**Action needed**: Add `emit_citation_recorded(citations: list[CitationRecord], metadata)` method to EventEmitter. It should use the side-channel buffer (like `emit_artifact_created`) so the turn loop can drain it.

**`CitationRecord` limitation**: The current `CitationRecord` dataclass has only `source` and `status` fields. The Rust `CitationAuditItem` has 7 fields (`kind`, `source`, `reference`, `status`, `tier`, `excerpt`, `url`, `note`). The Python port should either:
- Extend `CitationRecord` with additional fields, OR
- Put additional fields in the event `metadata`, OR
- Keep `CitationRecord` minimal and put full audit details in metadata

This is an implementation decision for the planner.

### 8. Test Infrastructure

**Framework**: pytest (Python 3.11+, pyproject.toml with setuptools)
**Test location**: `packages/agent-core/tests/`
**Current test count**: 550 tests across 30 test files

**Test patterns**:
- **Unit tests**: `test_config.py`, `test_event_emitter.py`, `test_context.py`, `test_tool_registry.py`
- **Tool tests**: `test_clarification_tool.py`, `test_file_read_tool.py`, `test_regulation_search_tool.py`, `test_document_generate_tool.py`, `test_mcp_client.py`, `test_path_sandbox.py`, `test_builtin_registry.py`
- **E2E tests**: `test_e2e_turn_orchestration.py`, `test_e2e_context_budget.py`, `test_e2e_error_recovery.py`, `test_e2e_model_layer.py`, `test_e2e_multi_tool.py`, `test_e2e_tool_error_recovery.py`, `test_e2e_mcp_tools.py`, `test_e2e_trackchanges.py`
- **Security tests**: `test_security_verification.py` (no subprocess, no exec/eval, PathSandbox traversal rejection)
- **Success criteria mapping**: `test_phase101_success_criteria.py` (maps SCs to verifying tests)
- **Fixtures**: `tests/fixtures/` directory, `FixtureProvider` + `Fake*Transport` for no-external-LLM testing
- **Silence threshold**: `test_silence_threshold.py` (ScriptedClock + RecordingEmitter)

**How to add new tests**: Create `test_{module_name}.py` in `tests/`. Use `pytest` fixtures. For LLM-dependent tests, use `FixtureProvider` with scripted responses. For event tests, use `RecordingEmitter` or direct `EventEmitter` with injected clocks.

**Gate coverage**: Every new `src/` directory must be covered by a gate. The `gate-coverage` meta-test enforces this. New modules in `agent-core/src/inkstatute_agent_core/` must have corresponding test files.

## Validation Architecture

### Approach

The port is validated through three layers:

1. **Golden fixture comparison**: Each Rust test case (35 total) is replicated as a Python test with the same input and expected output. The Rust source code is the source of truth — the Python implementation must produce equivalent results. This is mandated by AGENTS.md: "When porting logic from `lawyer-desktop` (Rust), use the Rust-side test cases as the Python-side golden fixture set. Do not port by reading and re-writing from memory."

2. **Guardrail enforcement tests**: For each of the four guardrails, tests must verify that the guardrail cannot be bypassed:
   - Research-gate: prompt assembler always includes research-gate text; no code path produces a legal prompt without it
   - Ask-user-enforcement: Draft/Evidence prompts always include ask-user mandate; clarification tool terminates turn
   - Citation audit: audit runs after every final response; unverified citations are labeled
   - De-AI polish: post-processing runs after citation audit; AI-characteristic patterns are removed

3. **Safety invariant tests**: `skill_candidate.requires_human_review` is always true; no code path auto-synthesizes or auto-modifies legal conclusion skills.

### Test Strategy

| Test Type | What | Count (est.) |
|-----------|------|-------------|
| Tool leak detection | 12 Rust tests replicated + edge cases | ~15 |
| Tool leak sanitization | 12 Rust tests replicated + edge cases | ~15 |
| Tool leak parsing | 6 Rust tests replicated | ~8 |
| Prompt assembly | 10 Rust tests replicated + mode coverage | ~15 |
| Retrieval tool mapping | 5 Rust tests replicated | ~8 |
| Citation extraction | 12 Rust tests replicated | ~15 |
| Citation verification | 2 Rust tests replicated + library mock | ~10 |
| Citation event emission | citation.recorded event structure | ~5 |
| Guardrail enforcement | 4 guardrails × bypass attempts | ~12 |
| De-AI polish | Pattern detection + removal | ~8 |
| Safety invariants | skill_candidate, requires_human_review | ~5 |
| Golden fixture replay | Same input → same output comparison | ~10 |
| **Total estimated** | | **~126 new tests** |

### Key Risks

1. **Rust→Python prompt logic distortion** (HG-1): The Chinese legal prompt text is large and mode-dependent. Any character difference changes the LLM's behavior. Mitigation: golden fixture comparison with exact string matching; lawyer sampling (HG-1 not auto-closable).

2. **Regex port gaps**: The citation extraction regexes use Rust's `regex` crate syntax. Python's `re` module has slightly different behavior for Unicode character classes (`[一-龥]` in case_number_re). Must verify each regex produces identical matches on the same input.

3. **Full-width character normalization**: The `｜` (U+FF5C) and `▁` (U+2581) characters must be handled correctly in Python strings. Python string replacement is straightforward but must be tested with the exact `REAL_DSML_LEAK` fixture.

4. **Guardrail bypass**: The guardrails are primarily prompt-level (instructions to the LLM) + post-hoc audit. A model could still output legal conclusions without research. The "code-level enforcement" means the prompt assembler MUST inject the guardrail text — there is no code path that skips it. Tests must verify this by checking that the assembled prompt always contains the required sections.

5. **De-AI polish has no reference implementation**: Unlike the other three guardrails, de-AI polish has no Rust code to port. The patterns for "AI-sounding language" must be designed from scratch. Risk: over-aggressive polishing could alter legal meaning. Mitigation: conservative pattern set, tests with known AI-sounding and known clean legal text.

6. **`skill_candidate` safety**: The `requires_human_review = True` invariant has no Rust implementation. It is a platform-level safety rule. Must be enforced in the Python core with test assertions that verify no code path sets it to False or auto-synthesizes skills.

7. **CitationRecord payload simplification**: The existing `CitationRecord` dataclass has only `source` and `status`. The full audit has 7+ fields. Decision needed on whether to extend the dataclass or use metadata. This affects the event schema (Phase 88 contract).

## Implementation Approach

### Recommended Module Structure

```
src/inkstatute_agent_core/
├── prompt_assembler.py       # NEW — build_system_prompt(), build_qa/draft/evidence prompts,
│                             #   research-gate injection, retrieval tool mapping, citation spec,
│                             #   skill description list, active skill body injection
├── tool_leak.py              # NEW — contains_tool_leakage(), sanitize_assistant_content(),
│                             #   parse_embedded_tool_calls(), normalize_marker_chars(),
│                             #   normalize_tool_name(), KNOWN_TOOLS
├── citations/                # NEW sub-package
│   ├── __init__.py           #   audit(), CitationAuditItem, CitationAudit
│   ├── extract.py            #   extract_citations(), CitationKind, ExtractedCitation, 6 regexes
│   └── verify.py             #   verify_items(), verify_law_article/interpretation/case()
├── guardrails.py             # NEW — de-AI polish implementation, guardrail orchestration
├── turn_loop.py              # MODIFIED — integrate leak detection + retry, citation audit,
│                             #   de-AI polish, citation.recorded emission
├── event_emitter.py          # MODIFIED — add emit_citation_recorded() method
├── context.py                # UNCHANGED (skill body injection already exists)
├── config.py                 # MODIFIED — add max_leak_retries field (default 3)
└── tools/                    # UNCHANGED (existing tools)
```

### Dependency Analysis

```
prompt_assembler.py
  ├── depends on: AgentMode enum (from router-service or new local enum)
  ├── depends on: SkillMetadata type (from skill-index or local protocol)
  ├── depends on: context.py (for skill body injection / token budget)
  └── no dependency on tool_leak or citations

tool_leak.py
  ├── no dependencies on other new modules
  └── standalone (pure functions)

citations/extract.py
  ├── no dependencies on other new modules
  └── standalone (pure regex functions)

citations/verify.py
  ├── depends on: citations/extract.py (ExtractedCitation, CitationKind)
  └── depends on: law_library (local regulation library — may need a Python equivalent
      or a mock/fixture for testing)

citations/__init__.py
  ├── depends on: citations/extract.py + citations/verify.py
  └── produces: audit() function + CitationAudit dataclass

guardrails.py
  ├── depends on: prompt_assembler.py (research-gate, ask-user-enforcement)
  ├── depends on: citations/ (citation audit)
  └── implements: de-AI polish (standalone)

turn_loop.py (modified)
  ├── depends on: tool_leak.py (leak detection + retry)
  ├── depends on: citations/ (post-response audit)
  ├── depends on: guardrails.py (de-AI polish)
  └── depends on: event_emitter.py (emit_citation_recorded)
```

**Parallelization opportunities**:
- `tool_leak.py` and `citations/extract.py` are fully independent — can be developed in parallel
- `prompt_assembler.py` is independent of tool_leak and citations — can be developed in parallel
- `citations/verify.py` depends on `citations/extract.py` — sequential
- `guardrails.py` depends on all others — last
- Turn loop integration depends on all — last

### Estimated Plan Count

**Recommended: 5 plans**

| Plan | Content | Est. Tests |
|------|---------|-----------|
| 102-01 | `tool_leak.py` — port all detection/sanitization/parsing + 12 Rust golden fixtures | ~38 |
| 102-02 | `prompt_assembler.py` — three-mode prompts, research-gate, retrieval tool mapping, citation spec, skill injection + 10 Rust golden fixtures | ~23 |
| 102-03 | `citations/` — extraction (6 regexes) + three-state verification + `emit_citation_recorded()` + 14 Rust golden fixtures | ~30 |
| 102-04 | `guardrails.py` — de-AI polish + four-guardrail enforcement tests + `skill_candidate.requires_human_review` safety tests | ~25 |
| 102-05 | Turn loop integration — leak retry, citation audit pipeline, de-AI polish pipeline, golden fixture replay, success criteria mapping, phase completion | ~10 |

**Total: ~126 new tests, 5 plans**

This matches the ROADMAP estimate of "4-5" plans and the pattern from Phases 100 (4 plans) and 101 (4 plans).
