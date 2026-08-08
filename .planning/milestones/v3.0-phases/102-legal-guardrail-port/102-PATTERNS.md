---
phase: 102
slug: legal-guardrail-port
status: complete
created: 2026-08-08
---

# Phase 102 — Pattern Map

## Summary

Phase 102 ports four legal-guardrail components from `lawyer-desktop`'s Rust core into the Python `packages/agent-core`: (1) `prompt_assembler.py` — three-mode Chinese legal prompt assembly with research-gate injection, retrieval tool mapping, citation spec, and skill description/body injection; (2) `tool_leak.py` — DSML/XML tool-call leak detection, full-width character normalization, sanitization, and embedded tool-call parsing; (3) `citations/` — citation extraction via 6 regex patterns and three-state verification (verified/retrieved/unverified); (4) `guardrails.py` — de-AI polish (designed fresh, no Rust source) and guardrail orchestration. Three existing files are modified: `turn_loop.py` (leak retry + citation audit + de-AI polish pipeline), `event_emitter.py` (add `emit_citation_recorded()`), and `config.py` (add `max_leak_retries`).

The codebase has strong existing analogs: `context.py` for the prompt assembler (both are pure-function prompt/context builders with dataclass results), `tools/clarification.py` for the guardrail tool pattern (factory function capturing emitter), `tools/registry.py` for the tool definition pattern, and `event_emitter.py` for the side-channel event emission pattern. The Rust test cases (11 for tool_leak, 10 for router, 10 for citations/extract, 2 for citations/verify) become the Python golden fixture set.

## File Patterns

### prompt_assembler.py (NEW)

**Role:** Pure functions module — system prompt builder (no state, no side effects)
**Data flow:** `AgentMode` enum + `list[SkillMetadata]` + `research_gate_content: str | None` + `active_skill: SkillMetadata | None` + `retrieval_tools: list[str]` → assembled system prompt `str`

**Closest analog:** `packages/agent-core/src/inkstatute_agent_core/context.py` — both are pure-function modules that assemble text (system prompt / context messages) from structured inputs. `context.py` uses module-level helper functions (`_parse_sections`, `_trim_skill_body`, `_estimate_tokens`) and dataclass results (`AgentContextResult`). The prompt assembler should follow the same pattern: module-level constants + pure functions + a top-level `build_system_prompt()` entry point.

**Code excerpt — context.py pure-function pattern (lines 133-174):**
```python
# packages/agent-core/src/inkstatute_agent_core/context.py:133-174

def _parse_sections(skill_text: str) -> tuple[str, list[tuple[str, str]]]:
    """Parse skill body into frontmatter and section list."""
    fm_match = _FRONTMATTER_RE.match(skill_text)
    if fm_match:
        frontmatter = skill_text[: fm_match.end()]
        remaining = skill_text[fm_match.end():]
    else:
        frontmatter = ""
        remaining = skill_text

    h2_positions: list[tuple[int, str]] = []
    for match in _H2_HEADER_RE.finditer(remaining):
        h2_positions.append((match.start(), match.group(1).strip()))

    sections: list[tuple[str, str]] = []
    # ... build sections from h2_positions ...
    return frontmatter, sections
```

**Code excerpt — Rust source to port (router.rs:139-193):**
```rust
// lawyer-desktop/src-tauri/src/skills/router.rs:139-193
pub fn build_system_prompt(
    skills: &[SkillMetadata],
    research_gate_content: Option<&str>,
    active_skill: Option<&SkillMetadata>,
    mode: AgentMode,
    retrieval_tools: &[String],
) -> String {
    let mut prompt = match mode {
        AgentMode::Evidence => build_evidence_system_prompt(),
        AgentMode::Chat => build_qa_system_prompt(),
        AgentMode::Draft => String::from("你是一位专业的中国法律 AI 助手..."),
    };

    let gate = research_gate_content.unwrap_or(RESEARCH_GATE_FALLBACK);
    prompt.push_str(gate);
    prompt.push_str("\n\n");

    prompt.push_str(&build_retrieval_tool_mapping(retrieval_tools));
    prompt.push_str("## 引用书写规范（核验契约）\n...");
    prompt.push_str(&build_skill_descriptions(skills));

    if let Some(skill) = active_skill {
        prompt.push_str(&format!("\n## 当前激活技能: {}\n\n{}\n",
            skill.name, skill.full_content));
    }
    prompt
}
```

**Python port shape:**
```python
# prompt_assembler.py — expected structure
from enum import Enum

class AgentMode(str, Enum):
    CHAT = "chat"
    DRAFT = "draft"
    EVIDENCE = "evidence"

RESEARCH_GATE_FALLBACK = """## research-gate（强制前置）
...
"""

RETRIEVAL_TOOL_MAP: list[tuple[str, str]] = [
    ("legal_search", "聚合检索法律依据..."),
    # ... 10 entries total ...
]

def is_retrieval_tool_name(name: str) -> bool: ...
def is_public_web_tool_text(text: str) -> bool: ...
def is_retrieval_tool(name: str, description: str) -> bool: ...
def build_retrieval_tool_mapping(retrieval_tools: list[str]) -> str: ...
def build_skill_descriptions(skills: list[SkillMetadata]) -> str: ...
def build_system_prompt(
    skills: list[SkillMetadata],
    research_gate_content: str | None,
    active_skill: SkillMetadata | None,
    mode: AgentMode,
    retrieval_tools: list[str],
) -> str: ...
```

**Test pattern:** `tests/test_context.py` uses `unittest.TestCase` with helper functions (`_make_skill_body`, `_make_history`) and assertion-based tests on the assembled result. The prompt assembler tests should follow the same pattern — helper functions to build `SkillMetadata` fixtures, then assert `build_system_prompt(...)` output contains/doesn't contain key substrings. The 10 Rust router.rs tests (lines 507-627) become golden fixtures: e.g. `test_evidence_prompt_mandates_clarify_research_and_review_markers`, `test_qa_prompt_keeps_gate_but_drops_drafting_mandates`, `test_tool_mapping_lists_only_available_tools`, `test_empty_tool_list_degrades_honestly`.

**Rust golden test excerpt (router.rs:511-543):**
```rust
#[test]
fn evidence_prompt_mandates_clarify_research_and_review_markers() {
    let prompt = build_system_prompt(&[], None, None, AgentMode::Evidence, &[]);
    assert!(prompt.contains("Clarify（首轮强制）"));
    assert!(prompt.contains("ask_user"));
    assert!(prompt.contains("Research（法律检索）"));
    assert!(prompt.contains("[待律师复核]"));
    assert!(prompt.contains("research-gate"));
}

#[test]
fn qa_prompt_keeps_gate_but_drops_drafting_mandates() {
    let prompt = build_system_prompt(&[], None, None, AgentMode::Chat, &[]);
    assert!(prompt.contains("research-gate"));
    assert!(prompt.contains("引用书写规范"));
    assert!(prompt.contains("法律问答"));
    assert!(!prompt.contains("文书输出格式（起草时强制）"));
    assert!(!prompt.contains("必须输出一个 JSON 对象"));
    assert!(!prompt.contains("必须调用一次 ask_user"));
}
```

---

### tool_leak.py (NEW)

**Role:** Pure functions module — leak detection, sanitization, and embedded tool-call parsing (no state, no side effects, no dependencies on other new modules)
**Data flow:** `text: str` → `bool` (detection) / `str` (sanitization) / `list[ToolCall]` (parsing)

**Closest analog:** `packages/agent-core/src/inkstatute_agent_core/tools/path_sandbox.py` — both are standalone pure-function modules with no dependencies on other agent-core modules. The module should be entirely self-contained: constants + functions, no classes, no imports from other new modules.

**Code excerpt — Rust source to port (tool_leak.rs:5-47):**
```rust
// lawyer-desktop/src-tauri/src/llm/tool_leak.rs:5-47
const KNOWN_TOOLS: &[&str] = &[
    "search_workspace", "read_chunk", "read_file", "list_files",
    "get_index_status", "read_user_file", "fetch_url", "generate_docx",
    "select_skill", "ask_user",
];

fn normalize_marker_chars(text: &str) -> String {
    text.replace('｜', "|").replace('▁', "_")
}

pub fn contains_tool_leakage(text: &str) -> bool {
    let lower = normalize_marker_chars(text).to_lowercase();
    lower.contains("dsml")
        || lower.contains("tool_calls")
        || lower.contains("tool_call")
        || lower.contains("tool_c")
        || lower.contains("</_calls")
        || lower.contains("_calls>")
        || lower.contains("< name=")
        || lower.contains("<name=")
        || lower.contains("<invoke")
        || lower.contains("invoke>")
        || lower.contains("</invoke")
        || lower.contains("invoke name=")
        || lower.contains("invoke=")
        || lower.contains("parameter name=")
        || lower.contains("parameter name ")
        || lower.contains("function_call")
        || lower.contains("<|")
        || lower.contains("|>")
        || lower.contains("toolalls")
}
```

**Code excerpt — sanitization logic (tool_leak.rs:50-121):**
```rust
// lawyer-desktop/src-tauri/src/llm/tool_leak.rs:50-121
pub fn sanitize_assistant_content(text: &str) -> String {
    let mut s = text.to_string();
    // Phase 1: Block removal — <tool_calls>...</tool_calls> and <invoke>...</invoke>
    while let Some(start) = find_case_insensitive(&s, "<tool_calls") {
        if let Some(end) = find_case_insensitive(&s[start..], "</tool_calls>") {
            s.replace_range(start..start + end + "</tool_calls>".len(), "");
            continue;
        }
        break;
    }
    // ... similar for <invoke>...</invoke> ...
    // Phase 2: Line filtering — skip lines with leak markers, preserve HTML tags
    let mut out = String::new();
    for line in s.lines() {
        let trimmed = line.trim();
        let lower = normalize_marker_chars(trimmed).to_lowercase();
        if lower.contains("dsml") || lower.contains("tool_calls") /* ... */ {
            continue;
        }
        // Only strip <...> lines matching known tool-leak tags, not all HTML
        if trimmed.starts_with('<') && trimmed.ends_with('>') {
            let inner = trimmed[1..trimmed.len()-1].trim().to_lowercase();
            let inner_stripped = inner.strip_prefix('/').unwrap_or(&inner);
            if inner_stripped.starts_with("tool_call")
                || inner_stripped.starts_with("_call")
                || inner_stripped.starts_with("invoke")
                || inner_stripped.starts_with("parameter")
                || inner_stripped.starts_with("name=")
                || inner_stripped.starts_with("function_call")
                || inner_stripped.starts_with("dsml")
            { continue; }
        }
        out.push_str(line);
        out.push('\n');
    }
    collapse_blank_lines(out.trim()).to_string()
}
```

**Code excerpt — embedded tool-call parsing (tool_leak.rs:247-287):**
```rust
// lawyer-desktop/src-tauri/src/llm/tool_leak.rs:247-287
pub fn parse_embedded_tool_calls(content: &str) -> Vec<ToolCall> {
    let content = &normalize_marker_chars(content);
    let mut calls = Vec::new();
    let lower = content.to_lowercase();
    let mut search_from = 0;

    while search_from < content.len() {
        let rel = match lower[search_from..].find("invoke") {
            Some(i) => i,
            None => break,
        };
        let start = search_from + rel;
        let block_end = lower[start..]
            .find("</invoke>")
            .map(|e| start + e + "</invoke>".len())
            .unwrap_or_else(|| {
                lower[start..].find("<invoke")
                    .map(|n| start + n)
                    .unwrap_or(content.len())
            });

        let block = &content[start..block_end.min(content.len())];
        if let Some((name, args)) = parse_invoke_block(block) {
            if KNOWN_TOOLS.contains(&name.as_str()) || name.starts_with("mcp_") {
                calls.push(ToolCall {
                    id: format!("embedded_{}", Uuid::new_v4()),
                    tool_type: "function".into(),
                    function: FunctionCall { name, arguments: args.to_string() },
                });
            }
        }
        search_from = block_end.max(start + 6);
    }
    calls
}
```

**Python port shape:**
```python
# tool_leak.py — expected structure
import re
import uuid

KNOWN_TOOLS: list[str] = [
    "search_workspace", "read_chunk", "read_file", "list_files",
    "get_index_status", "read_user_file", "fetch_url", "generate_docx",
    "select_skill", "ask_user",
]

def normalize_marker_chars(text: str) -> str:
    return text.replace("\uff5c", "|").replace("\u2581", "_")

def contains_tool_leakage(text: str) -> bool: ...
def sanitize_assistant_content(text: str) -> str: ...
def normalize_tool_name(raw: str) -> str: ...
def parse_parameter_value(block: str, param_name: str) -> str | None: ...
def extract_invoke_name(block: str) -> str | None: ...
def parse_invoke_block(block: str) -> tuple[str, dict] | None: ...
def parse_embedded_tool_calls(content: str) -> list[dict]: ...
```

**Test pattern:** The 11 Rust tests (tool_leak.rs:289-392) become Python golden fixtures. Use `unittest.TestCase` with the `REAL_DSML_LEAK` constant replicated verbatim. Key tests:
- `test_detects_dsml_leakage` — `"| | DSML | | tool_calls>"` → True
- `test_detects_fullwidth_dsml_leakage` — `REAL_DSML_LEAK` with U+FF5C → True
- `test_sanitize_strips_real_fullwidth_leak_completely` — `REAL_DSML_LEAK` → `""`
- `test_sanitize_keeps_clean_markdown_tables` — markdown table with `|` separators → unchanged
- `test_parses_mangled_fullwidth_invoke_to_known_tool` — `REAL_DSML_LEAK` → 1 call, name=`search_workspace`
- `test_does_not_treat_parameter_name_as_invoke_name` — `<invoke><parameter name="search_workspace">` → 0 calls
- `test_sanitize_keeps_html_formatting_tags` — `<br>`, `<table>`, `<strong>` → preserved

**Rust golden test excerpt (tool_leak.rs:295-336):**
```rust
const REAL_DSML_LEAK: &str = "<｜｜DSML｜｜tool_c>\n<｜｜DSML｜｜invoke=\"search_\">\n<｜｜DSML｜｜parameter namek\" stringfalse\">13｜｜DSML｜｜parameter>\n<｜｜DSML｜｜ name=\"query\" stringtrue\">保 投标见即付不可</｜｜DSML｜｜parameter>\n</invoke>\n</｜｜DSML｜｜_calls>";

#[test]
fn parses_mangled_fullwidth_invoke_to_known_tool() {
    let calls = parse_embedded_tool_calls(REAL_DSML_LEAK);
    assert_eq!(calls.len(), 1);
    assert_eq!(calls[0].function.name, "search_workspace");
    assert!(calls[0].function.arguments.contains("保 投标见即付不可"));
}
```

---

### citations/extract.py (NEW)

**Role:** Pure functions module — citation extraction via regex (no state, no side effects, no dependencies on other new modules)
**Data flow:** `text: str` → `list[ExtractedCitation]` (deduplicated, first-occurrence order)

**Closest analog:** `packages/agent-core/src/inkstatute_agent_core/context.py` (regex-based parsing) and `tool_leak.py` (new, same pure-function pattern). The Rust source uses `OnceLock<Regex>` for compiled regex caching; Python should use module-level `re.compile()` calls (the standard Python equivalent of `OnceLock`).

**Code excerpt — Rust source to port (extract.rs:10-28, 30-77, 91-162):**
```rust
// lawyer-desktop/src-tauri/src/citations/extract.rs:10-28
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize)]
pub enum CitationKind { Law, Interpretation, Case }

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExtractedCitation {
    pub kind: CitationKind,
    pub source: String,    // 法名 (without 《》)
    pub reference: String, // 第N条 / 法释〔YYYY〕N号 / case number
}

// lawyer-desktop/src-tauri/src/citations/extract.rs:30-37
fn law_article_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(
            r"《([^《》\n]{2,48})》\s*(第[零一二三四五六七八九十百千0-9]+条(?:之[一二三四五六七八九十])?(?:[、和及与]\s*第[零一二三四五六七八九十百千0-9]+条(?:之[一二三四五六七八九十])?)*)",
        ).expect("law article regex")
    })
}

// lawyer-desktop/src-tauri/src/citations/extract.rs:91-162
pub fn extract_citations(text: &str) -> Vec<ExtractedCitation> {
    let mut out: Vec<ExtractedCitation> = Vec::new();
    let mut seen = std::collections::HashSet::new();
    // ... iterate 6 regexes, dedup by (kind, source, reference) ...
    out
}
```

**Python port shape:**
```python
# citations/extract.py — expected structure
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import re

class CitationKind(str, Enum):
    LAW = "law"
    INTERPRETATION = "interpretation"
    CASE = "case"

@dataclass(frozen=True, slots=True)
class ExtractedCitation:
    kind: CitationKind
    source: str
    reference: str

# Module-level compiled regexes (Python equivalent of Rust OnceLock<Regex>)
_LAW_ARTICLE_RE = re.compile(
    r"《([^《》\n]{2,48})》\s*(第[零一二三四五六七八九十百千0-9]+条...)"
)
_ARTICLE_LIST_RE = re.compile(r"第[零一二三四五六七八九十百千0-9]+条(?:之[一二三四五六七八九十])?")
_INTERPRETATION_RE = re.compile(r"(?:《([^《》\n]{2,64})》...)?(法释[〔\[（(]\d{4}[〕\]）)]\d{1,3}号)")
_STATE_COUNCIL_DECREE_RE = re.compile(r"(?:《([^《》\n]{2,64})》...)?(国务院令第\d{1,4}号)")
_CASE_NUMBER_RE = re.compile(r"[（(]\d{4}[）)][一-龥]{1,8}\d{0,4}(?:民初|民终|...)...")
_DB_CASE_ID_RE = re.compile(r"\d{4}-\d{2}-\d-\d{3}-\d{3}")

def _normalize_doc_number(s: str) -> str: ...
def extract_citations(text: str) -> list[ExtractedCitation]: ...
```

**Test pattern:** The 10 Rust tests (extract.rs:164-284) become Python golden fixtures. Use a `kinds()` helper that maps `extract_citations(text)` to `list[tuple[CitationKind, str, str]]` for easy assertion. Key tests:
- `test_extracts_law_article_chinese_and_arabic` — `《中华人民共和国民法典》第五百八十五条` + `《公司法》第20条`
- `test_expands_article_enumerations` — `《民法典》第六百八十六条、第六百八十八条` → 2 items
- `test_extracts_zhi_yi_suffix` — `《刑法》第二百八十七条之一`
- `test_normalizes_interpretation_bracket_variants` — `法释[2016]24号` → `法释〔2016〕24号`
- `test_extracts_case_numbers_fullwidth_and_halfwidth` — `（2024）渝01民初1234号` + `(2023)京民终567号`
- `test_dedupes_repeated_citations` — same citation twice → 1 item
- `test_ignores_plain_text_without_citations` — no `《》` prefix → empty

**Rust golden test excerpt (extract.rs:176-189):**
```rust
fn kinds(text: &str) -> Vec<(CitationKind, String, String)> {
    extract_citations(text).into_iter()
        .map(|c| (c.kind, c.source, c.reference)).collect()
}

#[test]
fn extracts_law_article_chinese_and_arabic() {
    let got = kinds("依据《中华人民共和国民法典》第五百八十五条，以及《公司法》第20条的规定。");
    assert_eq!(got, vec![
        (CitationKind::Law, "中华人民共和国民法典".into(), "第五百八十五条".into()),
        (CitationKind::Law, "公司法".into(), "第20条".into()),
    ]);
}
```

---

### citations/verify.py (NEW)

**Role:** Async verification functions — three-state citation verification against local law library + retrieval evidence
**Data flow:** `list[ExtractedCitation]` + `retrievals: list[tuple[str, str]]` → `list[CitationAuditItem]` (each with status: verified/retrieved/unverified)

**Closest analog:** `packages/agent-core/src/inkstatute_agent_core/tools/executor.py` — both are async dispatching functions that take structured input and produce structured output. The verification module dispatches by `CitationKind` (Law → `verify_law_article`, Interpretation → `verify_interpretation`, Case → `verify_case`), similar to how the executor dispatches by tool name.

**Code excerpt — Rust source to port (verify.rs:39-101, 199-213):**
```rust
// lawyer-desktop/src-tauri/src/citations/verify.rs:39-101
async fn verify_law_article(
    c: &ExtractedCitation,
    retrievals: &[(String, String)],
) -> CitationAuditItem {
    let base = CitationAuditItem {
        kind: c.kind, source: c.source.clone(), reference: c.reference.clone(),
        status: "unverified".into(), tier: None, excerpt: None, url: None, note: None,
    };

    match law_library::lookup_article(&c.source, &c.reference).await {
        Ok(ArticleLookup::Found { entry, heading, text }) => CitationAuditItem {
            status: "verified".into(),
            tier: Some("L1-法规（本地库）".into()),
            excerpt: Some(excerpt(&format!("{} {}", heading, text))),
            url: entry.source_url.clone(),
            ..base
        },
        Ok(ArticleLookup::LawFoundArticleMissing { entry, article_count }) => CitationAuditItem {
            note: Some(format!("《{}》共 {} 条，未找到该条文号", entry.name, article_count)),
            ..base
        },
        Ok(ArticleLookup::LawNotFound { .. }) | Ok(ArticleLookup::BadArticleRef) | Err(_) => {
            if let Some((_, result)) = find_in_retrievals(retrievals, &[&c.source, &c.reference]) {
                CitationAuditItem {
                    status: "retrieved".into(),
                    tier: tier_from_result(result),
                    note: Some("本地库未收录，依据本轮在线检索结果".into()),
                    ..base
                }
            } else {
                CitationAuditItem {
                    note: Some("本地库未收录且本轮未检索到 — 待律师复核".into()),
                    ..base
                }
            }
        }
    }
}

// lawyer-desktop/src-tauri/src/citations/verify.rs:199-213
pub async fn verify_items(
    extracted: Vec<ExtractedCitation>,
    retrievals: &[(String, String)],
) -> Vec<CitationAuditItem> {
    let mut items = Vec::with_capacity(extracted.len());
    for c in &extracted {
        let item = match c.kind {
            CitationKind::Law => verify_law_article(c, retrievals).await,
            CitationKind::Interpretation => verify_interpretation(c, retrievals).await,
            CitationKind::Case => verify_case(c, retrievals),
        };
        items.push(item);
    }
    items
}
```

**Python port shape:**
```python
# citations/verify.py — expected structure
from __future__ import annotations
from dataclasses import dataclass
from .extract import CitationKind, ExtractedCitation

@dataclass(frozen=True, slots=True)
class CitationAuditItem:
    kind: CitationKind
    source: str
    reference: str
    status: str  # "verified" | "retrieved" | "unverified"
    tier: str | None = None
    excerpt: str | None = None
    url: str | None = None
    note: str | None = None

def _excerpt(text: str, max_chars: int = 160) -> str: ...
def _tier_from_result(result: str) -> str | None: ...
def _find_in_retrievals(retrievals, fragments: list[str]) -> tuple[str, str] | None: ...

async def verify_law_article(c: ExtractedCitation, retrievals: list[tuple[str, str]]) -> CitationAuditItem: ...
async def verify_interpretation(c: ExtractedCitation, retrievals: list[tuple[str, str]]) -> CitationAuditItem: ...
def verify_case(c: ExtractedCitation, retrievals: list[tuple[str, str]]) -> CitationAuditItem: ...
async def verify_items(extracted: list[ExtractedCitation], retrievals: list[tuple[str, str]]) -> list[CitationAuditItem]: ...
```

**Note on law_library dependency:** The Rust code calls `law_library::lookup_article()` and `law_library::find_by_doc_number()`. The Python port needs an equivalent interface. For testing, the Rust tests rely on the library being uninitialized (all lookups error → fall back to retrievals). The Python port should accept an optional `LawLibrary` protocol/interface that defaults to `None` (all lookups fail → retrieval path), matching the Rust test behavior.

**Test pattern:** The 2 Rust tests (verify.rs:220-249) become Python golden fixtures. Use `asyncio.run()` or `pytest.mark.asyncio` (the codebase uses `asyncio.run()` in `test_clarification_tool.py`). Key tests:
- `test_case_numbers_verify_against_retrievals_only` — case in retrievals → "retrieved"; case not in retrievals → "unverified" with "待律师复核" note
- `test_law_articles_without_library_fall_back_to_retrievals` — no library → retrieval path; no retrievals → "unverified"

**Rust golden test excerpt (verify.rs:220-233):**
```rust
#[tokio::test]
async fn case_numbers_verify_against_retrievals_only() {
    let text = "参见（2024）渝01民初1234号判决与（2021）粤03民终99号。";
    let retrievals = vec![(
        "mcp__wenshu__search_cases".to_string(),
        "找到案例：（2024）渝01民初1234号 …\n来源层级: L2-入库\n链接: https://...".to_string(),
    )];
    let items = verify_items(extract_citations(text), &retrievals).await;
    assert_eq!(items.len(), 2);
    assert_eq!(items[0].status, "retrieved");
    assert_eq!(items[0].tier.as_deref(), Some("L2-入库"));
    assert_eq!(items[1].status, "unverified");
    assert!(items[1].note.as_deref().unwrap_or("").contains("待律师复核"));
}
```

---

### citations/__init__.py (NEW)

**Role:** Package init + orchestration function — composes extract + verify into `audit()` entry point
**Data flow:** `text: str` + `retrievals: list[tuple[str, str]]` → `CitationAudit` (with items + counts)

**Closest analog:** `packages/agent-core/src/inkstatute_agent_core/tools/builtin_registry.py` — both are package-level orchestration modules that compose sub-modules into a single entry point. `builtin_registry.py` composes individual tool factories into `create_builtin_registry()`; `citations/__init__.py` composes `extract_citations()` + `verify_items()` into `audit()`.

**Code excerpt — Rust source to port (mod.rs:1-55):**
```rust
// lawyer-desktop/src-tauri/src/citations/mod.rs:1-55
pub mod extract;
mod verify;

pub use extract::{extract_citations, CitationKind};

#[derive(Debug, Clone, Serialize)]
pub struct CitationAuditItem {
    pub kind: CitationKind,
    pub source: String,
    pub reference: String,
    pub status: String,
    pub tier: Option<String>,
    pub excerpt: Option<String>,
    pub url: Option<String>,
    pub note: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct CitationAudit {
    pub items: Vec<CitationAuditItem>,
    pub total: usize,
    pub verified: usize,
    pub retrieved: usize,
    pub unverified: usize,
}

pub async fn audit(text: &str, retrievals: &[(String, String)]) -> CitationAudit {
    let extracted = extract_citations(text);
    let items = verify::verify_items(extracted, retrievals).await;
    let count = |status: &str| items.iter().filter(|i| i.status == status).count();
    CitationAudit {
        total: items.len(),
        verified: count("verified"),
        retrieved: count("retrieved"),
        unverified: count("unverified"),
        items,
    }
}
```

**Python port shape:**
```python
# citations/__init__.py — expected structure
from __future__ import annotations
from dataclasses import dataclass, field
from .extract import CitationKind, ExtractedCitation, extract_citations
from .verify import CitationAuditItem, verify_items

@dataclass(frozen=True, slots=True)
class CitationAudit:
    items: list[CitationAuditItem]
    total: int = 0
    verified: int = 0
    retrieved: int = 0
    unverified: int = 0

async def audit(text: str, retrievals: list[tuple[str, str]]) -> CitationAudit:
    extracted = extract_citations(text)
    items = await verify_items(extracted, retrievals)
    return CitationAudit(
        items=items,
        total=len(items),
        verified=sum(1 for i in items if i.status == "verified"),
        retrieved=sum(1 for i in items if i.status == "retrieved"),
        unverified=sum(1 for i in items if i.status == "unverified"),
    )

__all__ = ["audit", "CitationAudit", "CitationAuditItem", "CitationKind",
           "ExtractedCitation", "extract_citations", "verify_items"]
```

**Test pattern:** Integration test that calls `audit()` with a multi-citation text and verifies the counts. Follows the `test_e2e_*` pattern from the existing test suite (e.g. `test_e2e_tool_registry.py`).

---

### guardrails.py (NEW)

**Role:** Guardrail orchestration + de-AI polish implementation (no Rust source — designed fresh)
**Data flow:**
- `de_ai_polish(text: str) -> str` — post-processing function that detects and removes AI-characteristic language patterns
- `enforce_research_gate(prompt: str) -> str` — assertion that research-gate is present in the assembled prompt (code-level enforcement)
- `enforce_ask_user_mandate(prompt: str, mode: AgentMode) -> None` — assertion that Draft/Evidence prompts include ask-user mandate
- `assert_skill_candidate_safety(candidate: dict) -> None` — assertion that `requires_human_review` is always `True`

**Closest analog:** `packages/agent-core/src/inkstatute_agent_core/tools/clarification.py` — both are modules that enforce legal safety rules. The clarification tool terminates the turn when `ask_user` is called; the guardrails module enforces that the prompt assembler's output contains the required guardrails. Both use factory/builder patterns and produce side effects (events / assertions).

**Code excerpt — clarification.py factory pattern (lines 131-182):**
```python
# packages/agent-core/src/inkstatute_agent_core/tools/clarification.py:131-182
def create_clarification_tool(emitter: EventEmitter):
    """Create a clarification (ask_user) tool handler bound to an EventEmitter."""

    async def clarification_handler(arguments: dict) -> ToolResult:
        intro = arguments.get("intro", "")
        raw_questions = arguments.get("questions", [])
        questions = _parse_questions(raw_questions)

        try:
            validate_question_count(questions)
        except ValueError as exc:
            return ToolResult(
                content=f"澄清问题数量不符合要求: {exc}",
                metadata={"terminate_turn": False, "validation_error": True},
            )

        interrupt_id = str(uuid.uuid4())
        emitter.emit_elicitation_requested(
            interrupt_id=interrupt_id,
            intro=intro,
            questions=questions,
        )
        return ToolResult(
            content=f"已向用户提出澄清问题 (interrupt_id={interrupt_id})",
            metadata={"terminate_turn": True, "elicitation_id": interrupt_id},
        )

    return clarification_handler
```

**De-AI polish design (no Rust source — fresh implementation):**
```python
# guardrails.py — expected de-AI polish structure
import re

# AI-characteristic language patterns to detect and clean
_AI_PATTERNS: list[tuple[str, str]] = [
    (r"作为一个AI[助手]?[,，]?\s*", ""),
    (r"作为AI[,，]?\s*", ""),
    (r"根据我的理解[,，]?\s*", ""),
    (r"我无法(?:提供|给出)[^。]*法律建议", ""),
    (r"请注意[,，]?\s*我是(?:一个)?AI", ""),
    (r"以上(?:分析|建议)仅供参考[,，]?\s*不构成法律建议[。.]?", ""),
    # ... more patterns ...
]

def de_ai_polish(text: str) -> str:
    """Remove AI-characteristic language patterns from legal text."""
    result = text
    for pattern, replacement in _AI_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    # Collapse multiple blank lines left by removals
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()

def enforce_research_gate(prompt: str) -> None:
    """Assert that the system prompt contains the research-gate section."""
    if "research-gate" not in prompt:
        raise ValueError("System prompt missing research-gate — legal safety violation")

def enforce_ask_user_mandate(prompt: str, mode: AgentMode) -> None:
    """Assert Draft/Evidence prompts include the ask-user mandate."""
    if mode in (AgentMode.DRAFT, AgentMode.EVIDENCE):
        if "ask_user" not in prompt:
            raise ValueError(f"{mode} prompt missing ask_user mandate")

def assert_skill_candidate_safety(candidate: dict) -> None:
    """Assert that skill_candidate.requires_human_review is always True."""
    if not candidate.get("requires_human_review", False):
        raise ValueError("skill_candidate.requires_human_review must be True — legal safety violation")
```

**Test pattern:** `unittest.TestCase` with assertion-based tests. Key tests:
- `test_de_ai_polish_removes_ai_disclaimers` — "作为一个AI助手，根据我的理解..." → cleaned
- `test_de_ai_polish_preserves_legal_content` — clean legal text → unchanged
- `test_enforce_research_gate_raises_on_missing` — prompt without "research-gate" → `ValueError`
- `test_enforce_ask_user_mandate_raises_for_draft_mode` — Draft prompt without "ask_user" → `ValueError`
- `test_enforce_ask_user_mandate_passes_for_chat_mode` — Chat prompt without "ask_user" → no error
- `test_skill_candidate_safety_rejects_false` — `{"requires_human_review": False}` → `ValueError`
- `test_skill_candidate_safety_accepts_true` — `{"requires_human_review": True}` → no error

---

### turn_loop.py (MODIFIED)

**Role:** Async generator orchestrator — integrate leak detection + retry, citation audit, de-AI polish
**Data flow:** Modified `run_turn()` async generator — adds leak retry loop around LLM streaming, citation audit before `message.completed`, de-AI polish before `message.completed`

**Closest analog:** The existing `turn_loop.py` itself (lines 84-340). The modifications are additive — new logic inserted into the existing flow at specific points.

**Code excerpt — current turn loop final content section (turn_loop.py:318-330):**
```python
# packages/agent-core/src/inkstatute_agent_core/turn_loop.py:318-330
        # 7. No tool calls — final content round
        full_content = "".join(content_parts)
        usage_dict = usage_accumulator.to_dict()

        yield emitter.emit_message_completed(
            full_content,
            metadata={"provider_usage": usage_dict},
        )
        yield emitter.emit_run_state_changed(
            "succeeded",
            metadata={"provider_usage": usage_dict},
        )
        return
```

**Modification points:**

1. **Leak detection + retry (insert before step 7, after streaming completes):**
```python
        # 6b. Leak detection — check if assistant content contains tool-call leakage
        full_content = "".join(content_parts)
        if contains_tool_leakage(full_content):
            if leak_retries < config.max_leak_retries:
                leak_retries += 1
                # Sanitize and retry — do NOT feed leaked text into history
                sanitized = sanitize_assistant_content(full_content)
                # ... retry the same request ...
                continue
            else:
                # Exhausted retries — sanitize and proceed without tools
                full_content = sanitize_assistant_content(full_content)
                # ... fallback: continue with sanitized content ...
```

2. **Citation audit + de-AI polish (insert before `emit_message_completed`):**
```python
        # 7. No tool calls — final content round
        full_content = "".join(content_parts)

        # 7a. Citation audit — extract + verify citations, emit citation.recorded
        retrievals = _collect_retrieval_evidence(current_messages)
        citation_audit = await audit(full_content, retrievals)
        if citation_audit.items:
            yield emitter.emit_citation_recorded(citation_audit.items)

        # 7b. De-AI polish — remove AI-characteristic language
        full_content = de_ai_polish(full_content)

        usage_dict = usage_accumulator.to_dict()
        yield emitter.emit_message_completed(
            full_content,
            metadata={
                "provider_usage": usage_dict,
                "citation_audit": {
                    "total": citation_audit.total,
                    "verified": citation_audit.verified,
                    "retrieved": citation_audit.retrieved,
                    "unverified": citation_audit.unverified,
                },
            },
        )
```

3. **Retrieval evidence collection helper (new internal function):**
```python
def _collect_retrieval_evidence(messages: list[dict]) -> list[tuple[str, str]]:
    """Collect (tool_name, result_text) pairs from retrieval tool results in history."""
    evidence = []
    for msg in messages:
        if msg.get("role") == "tool" and msg.get("content"):
            # Need to track which tool produced this result
            # ... implementation ...
    return evidence
```

**Test pattern:** Follow the existing `test_e2e_turn_orchestration.py` pattern — use a fixture provider that yields controlled deltas, then assert the emitted events include `citation.recorded` and that the final `message.completed` content has been de-AI polished. The leak retry tests should use a fixture provider that first yields leaked content, then clean content on retry.

---

### event_emitter.py (MODIFIED)

**Role:** Event emitter — add `emit_citation_recorded()` convenience method
**Data flow:** `list[CitationAuditItem]` → `RunEvent` with `event_type="citation.recorded"` and `CitationRecordedPayload`

**Closest analog:** The existing `emit_artifact_created()` and `emit_elicitation_requested()` methods (event_emitter.py:358-416) — both are convenience methods that build a payload, call `_emit()`, and append to the side-channel buffer.

**Code excerpt — existing side-channel emit pattern (event_emitter.py:358-416):**
```python
# packages/agent-core/src/inkstatute_agent_core/event_emitter.py:358-416
    def emit_artifact_created(
        self,
        artifact: Artifact,
        metadata: JsonObject | None = None,
    ) -> RunEvent:
        """Emit an ``artifact.created`` event."""
        payload = ArtifactCreatedPayload(
            artifact=artifact,
            metadata=metadata or {},
        )
        event = self._emit(RunEventType.ARTIFACT_CREATED_V3, payload, metadata=metadata)
        self._side_channel_events.append(event)
        return event

    def emit_elicitation_requested(
        self,
        interrupt_id: str,
        intro: str,
        questions: list[ElicitationQuestion],
        resume_state_ref: str | None = None,
        expires_at: str | None = None,
        metadata: JsonObject | None = None,
    ) -> RunEvent:
        """Emit an ``elicitation.requested`` event."""
        payload = ElicitationRequestedPayload(
            interrupt_id=interrupt_id,
            intro=intro,
            questions=questions,
            resume_state_ref=resume_state_ref,
            expires_at=expires_at,
            metadata=metadata or {},
        )
        event = self._emit(RunEventType.ELICITATION_REQUESTED, payload, metadata=metadata)
        self._side_channel_events.append(event)
        return event
```

**Existing platform-contract types (unified_events.py:132-141):**
```python
# packages/platform-contract/src/platform_contract/unified_events.py:132-141
@dataclass(frozen=True, slots=True)
class CitationRecord:
    source: str
    status: str

@dataclass(frozen=True, slots=True)
class CitationRecordedPayload:
    citations: list[CitationRecord] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)
```

**New method to add:**
```python
    def emit_citation_recorded(
        self,
        citations: list[CitationAuditItem],
        metadata: JsonObject | None = None,
    ) -> RunEvent:
        """Emit a ``citation.recorded`` event.

        Args:
            citations: List of ``CitationAuditItem`` objects from the citation audit.
            metadata: Optional metadata dict.

        Returns:
            A ``RunEvent`` with ``event_type="citation.recorded"`` and a
            serialized ``CitationRecordedPayload``.
        """
        records = [
            CitationRecord(source=item.source or item.reference, status=item.status)
            for item in citations
        ]
        payload = CitationRecordedPayload(
            citations=records,
            metadata=metadata or {},
        )
        event = self._emit(RunEventType.CITATION_RECORDED, payload, metadata=metadata)
        self._side_channel_events.append(event)
        return event
```

**Test pattern:** Follow the existing `test_event_emitter.py` pattern — use `FakeClock` and `FakeMonotonicClock` for deterministic testing, assert `event.event_type == "citation.recorded"`, assert `event.seq` is monotonic, assert the payload contains the correct `CitationRecord` objects.

---

### config.py (MODIFIED)

**Role:** Configuration dataclass — add `max_leak_retries` field
**Data flow:** No change to data flow — just a new field with a default value

**Closest analog:** The existing `AgentCoreConfig` dataclass itself (config.py:28-72).

**Code excerpt — current config (config.py:28-72):**
```python
# packages/agent-core/src/inkstatute_agent_core/config.py:28-72
@dataclass(frozen=True, slots=True)
class AgentCoreConfig:
    """Configuration for the agent core turn loop."""
    max_turns: int = 10
    silence_threshold_seconds: float = 5.0
    response_max_tokens: int = 8192
    temperature: float = 0.3
    context_budget_tokens: int = 32768
    chars_per_token: int = 4
    heartbeat_metadata_key: str = "heartbeat"
    metadata: JsonObject = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_turns < 1:
            raise ValueError(f"max_turns must be >= 1, got {self.max_turns}")
        if self.silence_threshold_seconds <= 0:
            raise ValueError(
                f"silence_threshold_seconds must be > 0, "
                f"got {self.silence_threshold_seconds}"
            )
```

**Modification — add `max_leak_retries` field:**
```python
@dataclass(frozen=True, slots=True)
class AgentCoreConfig:
    """Configuration for the agent core turn loop."""
    max_turns: int = 10
    silence_threshold_seconds: float = 5.0
    response_max_tokens: int = 8192
    temperature: float = 0.3
    context_budget_tokens: int = 32768
    chars_per_token: int = 4
    heartbeat_metadata_key: str = "heartbeat"
    max_leak_retries: int = 3  # NEW — matches Rust MAX_LEAK_RETRIES (chat.rs:36)
    metadata: JsonObject = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_turns < 1:
            raise ValueError(f"max_turns must be >= 1, got {self.max_turns}")
        if self.silence_threshold_seconds <= 0:
            raise ValueError(...)
        if self.max_leak_retries < 0:  # NEW validation
            raise ValueError(f"max_leak_retries must be >= 0, got {self.max_leak_retries}")
```

**Test pattern:** Follow the existing `test_config.py` pattern — test default value (3), test custom value, test validation (negative value raises `ValueError`).

---

## Test Patterns

### General structure

All tests in `packages/agent-core/tests/` use **`unittest.TestCase`** (not pytest). The codebase does not use `pytest.mark.parametrize` — instead, multiple test methods per class or multiple assertions per test method.

**File naming:** `test_<module_name>.py` for unit tests, `test_e2e_<feature>.py` for integration tests.

**Async tests:** Use `asyncio.run()` to execute async handlers in synchronous test methods (see `test_clarification_tool.py:35-36`):
```python
def _run_handler(handler, arguments: dict) -> ToolResult:
    return asyncio.run(handler(arguments))
```

### Helper / fixture pattern

Tests define helper functions at the module level for building test fixtures (see `test_context.py:24-60`):
```python
def _make_skill_body(skill_id: str = "test-skill", *, description: str = "...", sections=None) -> dict:
    """Build a skill body dict with frontmatter + description + sections."""
    parts = ["---", "skill_id: " + skill_id, "name: Test Skill", "---", "", description, ""]
    if sections:
        for header, body in sections:
            parts.append(f"## {header}")
            parts.append(body)
            parts.append("")
    return {"skill_id": skill_id, "body": "\n".join(parts)}

def _make_history(n_turns: int, *, content_size: int = 50) -> list[dict]:
    """Build a conversation history with n_turns pairs of (user, assistant)."""
    history = []
    for i in range(n_turns):
        history.append({"role": "user", "content": f"User question {i} " + "x" * content_size})
        history.append({"role": "assistant", "content": f"Assistant answer {i} " + "y" * content_size})
    return history
```

### Deterministic clock pattern

For event emitter tests, use injectable fake clocks (see `test_event_emitter.py:18-42`):
```python
class FakeClock:
    """Returns incrementing ISO timestamps for deterministic testing."""
    def __init__(self, start: str = "2026-01-01T00:00:00+00:00"):
        self._tick = 0
    def __call__(self) -> str:
        result = f"2026-01-01T00:00:{self._tick:02d}+00:00"
        self._tick += 1
        return result

class FakeMonotonicClock:
    """Returns controlled monotonic values for silence threshold testing."""
    def __init__(self, start: float = 0.0):
        self._current = start
    def __call__(self) -> float:
        return self._current
    def advance(self, seconds: float) -> None:
        self._current += seconds
```

### Golden fixture pattern (Phase 102 specific)

The Rust test cases become Python golden fixtures. Each Rust test function maps to one Python test method. The `REAL_DSML_LEAK` constant must be replicated verbatim (including full-width U+FF5C `｜` and U+2581 `▁` characters). The test assertions should be exact string/value comparisons, not substring checks, wherever the Rust test uses `assert_eq!`.

### E2E test pattern

Integration tests (e.g. `test_e2e_turn_orchestration.py`) use a `FixtureProvider` that yields controlled `ContentDelta`, `ToolCallDelta`, `FinishDelta` objects to simulate LLM streaming. The turn loop is run via `asyncio.run()` collecting all yielded events into a list, then assertions are made on the event sequence.

---

## Rust Source Patterns

### Pattern 1: OnceLock<Regex> → module-level re.compile()

The Rust code uses `OnceLock<Regex>` for lazy-compiled regex caching (extract.rs:30-77). The Python equivalent is module-level `re.compile()` calls — Python compiles regexes at import time and caches them automatically.

```rust
// Rust pattern
fn law_article_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"...").expect("regex"))
}
```
```python
# Python equivalent
_LAW_ARTICLE_RE = re.compile(r"...")
```

### Pattern 2: String concatenation → f-string / str.join()

The Rust `build_system_prompt()` uses `prompt.push_str()` for incremental string building (router.rs:170-192). The Python port should use f-strings and `str.join()` for readability, but the output must be byte-identical to the Rust output for golden fixture comparison.

```rust
// Rust pattern
let mut prompt = String::new();
prompt.push_str(gate);
prompt.push_str("\n\n");
prompt.push_str(&build_retrieval_tool_mapping(retrieval_tools));
```
```python
# Python equivalent
parts = [base_prompt, gate, "\n\n", build_retrieval_tool_mapping(retrieval_tools), ...]
prompt = "".join(parts)
```

### Pattern 3: Option<&str> → str | None

Rust `Option<&str>` maps to Python `str | None`. The `unwrap_or()` pattern maps to `or` or explicit `if ... is not None` checks.

```rust
// Rust pattern
let gate = research_gate_content.unwrap_or(RESEARCH_GATE_FALLBACK);
```
```python
# Python equivalent
gate = research_gate_content if research_gate_content is not None else RESEARCH_GATE_FALLBACK
```

### Pattern 4: Vec<ToolCall> with UUID → list[dict] with uuid4

Rust generates UUIDs for embedded tool calls via `Uuid::new_v4()` (tool_leak.rs:273). Python uses `uuid.uuid4()`.

```rust
// Rust pattern
calls.push(ToolCall {
    id: format!("embedded_{}", Uuid::new_v4()),
    tool_type: "function".into(),
    function: FunctionCall { name, arguments: args.to_string() },
});
```
```python
# Python equivalent
calls.append({
    "id": f"embedded_{uuid.uuid4()}",
    "type": "function",
    "function": {"name": name, "arguments": json.dumps(args)},
})
```

### Pattern 5: Annotation-style audit (never blocks output)

The citation audit is explicitly annotation-style — it never blocks output (mod.rs:3: "Annotation-style — never blocks output"). The Python port must preserve this: `audit()` returns a `CitationAudit` with status labels, but never raises an exception or prevents the response from being emitted. Unverified citations get `[待律师复核]` notes, but the text is still delivered.

### Pattern 6: Honest degradation

When no retrieval tools are available, the Rust code emits honest degradation text (router.rs:104-111): "当前未接入任何法律检索工具...禁止声称「已检索」「经检索形成」". The Python port must preserve this exact behavior — the prompt must not pretend tools exist when they don't.

### Pattern 7: Full-width character normalization

The DSML leak detection normalizes full-width characters before all detection and parsing (tool_leak.rs:18-23): U+FF5C `｜` → `|`, U+2581 `▁` → `_`. This normalization must be applied at the start of `contains_tool_leakage()`, `sanitize_assistant_content()`, and `parse_embedded_tool_calls()`. The Python port must use the exact same Unicode code points.

### Pattern 8: Skill candidate safety invariant

The `skill_candidate.requires_human_review` safety invariant has no Rust implementation — it is a platform-level rule. The Python port must enforce it with a test assertion that verifies `requires_human_review` is always `True` for any skill candidate. This is a code-level guardrail, not a prompt-level instruction.
