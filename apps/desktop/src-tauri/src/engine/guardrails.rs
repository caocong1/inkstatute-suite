//! Guardrail text scanner — derives guardrail events from committed assistant text.
//!
//! Parses three text conventions embedded in model output:
//! 1. Citation level markers: `[verified]` / `[retrieved]` / `[unverified]`
//! 2. Clarification blocks: `[CLARIFY: ... ]` (requires closing `]`)
//! 3. Human review marks: `[HUMAN_REVIEW: reason]`
//!
//! The scanner is pure (no I/O) and used by `mapper.rs` in the
//! `message.completed` branch to emit `citation.recorded`,
//! `elicitation.requested`, and `metadata.human_review` envelopes.

use serde::{Deserialize, Serialize};

/// Result of scanning a committed text for guardrail structures.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct GuardrailScan {
    pub citations: Vec<Citation>,
    pub clarification: Option<ClarificationRequest>,
    pub human_review: Vec<HumanReviewMark>,
}

/// A single citation with its verification level and preceding text.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Citation {
    pub text: String,
    pub level: CitationLevel,
    pub offset: usize,
}

/// Citation verification level.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum CitationLevel {
    Verified,
    Retrieved,
    Unverified,
}

impl CitationLevel {
    fn from_str(s: &str) -> Option<Self> {
        match s {
            "verified" => Some(Self::Verified),
            "retrieved" => Some(Self::Retrieved),
            "unverified" => Some(Self::Unverified),
            _ => None,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Verified => "verified",
            Self::Retrieved => "retrieved",
            Self::Unverified => "unverified",
        }
    }
}

/// A parsed clarification block (`[CLARIFY: ... ]`).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ClarificationRequest {
    pub intro: String,
    pub questions: Vec<ClarificationQuestion>,
}

/// A single question inside a clarification block.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ClarificationQuestion {
    pub id: String,
    pub question: String,
    pub options: Vec<ClarificationOption>,
}

/// A selectable option inside a clarification question.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ClarificationOption {
    pub id: String,
    pub label: String,
    pub value: String,
}

/// A human review mark (`[HUMAN_REVIEW: reason]`).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct HumanReviewMark {
    pub reason: String,
    pub offset: usize,
}

/// Maximum number of characters to capture before a citation marker
/// as the "preceding text" (citation body).
const CITATION_PRECEDING_LIMIT: usize = 200;

/// Scan a committed assistant text for guardrail structures.
///
/// This is the entry point called by `mapper.rs` on `message.completed`.
pub fn scan(text: &str) -> GuardrailScan {
    let citations = scan_citations(text);
    let clarification = scan_clarification(text);
    let human_review = scan_human_review(text);

    GuardrailScan {
        citations,
        clarification,
        human_review,
    }
}

/// Find all `[verified]` / `[retrieved]` / `[unverified]` markers and capture
/// the preceding text (back to the nearest sentence boundary or newline,
/// up to 200 characters).
fn scan_citations(text: &str) -> Vec<Citation> {
    // Regex: \[(verified|retrieved|unverified)\]
    // We use a simple byte-scanner to avoid pulling in the regex crate.
    let mut citations = Vec::new();
    let bytes = text.as_bytes();
    let markers: &[(&[u8], CitationLevel)] = &[
        (b"[verified]", CitationLevel::Verified),
        (b"[retrieved]", CitationLevel::Retrieved),
        (b"[unverified]", CitationLevel::Unverified),
    ];

    let mut i = 0;
    while i < bytes.len() {
        let mut found = false;
        for (marker, level) in markers {
            if bytes[i..].starts_with(marker) {
                let offset = i;
                // Capture preceding text up to 200 chars, back to sentence
                // boundary or newline.
                let preceding = capture_preceding_text(text, offset);
                citations.push(Citation {
                    text: preceding,
                    level: *level,
                    offset,
                });
                i += marker.len();
                found = true;
                break;
            }
        }
        if !found {
            i += 1;
        }
    }

    citations
}

/// Capture the text preceding `offset`, going back up to 200 characters,
/// stopping at the nearest sentence boundary (。！？.!? or newline).
/// The sentence boundary marks the *start* of the citation sentence —
/// text after the boundary (excluding the boundary itself) is the citation body.
/// If the preceding text ends with a sentence boundary (e.g. `。[verified]`),
/// we look past it for the start of the current sentence.
fn capture_preceding_text(text: &str, offset: usize) -> String {
    let start = if offset > CITATION_PRECEDING_LIMIT {
        offset - CITATION_PRECEDING_LIMIT
    } else {
        0
    };

    // We need to work with char boundaries. Find the nearest char boundary
    // at or before `start`.
    let start = text[..start].char_indices().last().map(|(i, _)| i).unwrap_or(0);

    let preceding = &text[start..offset];

    // Strip trailing sentence boundary characters — if the text ends with `。`
    // right before the marker, that `。` is the end of the citation sentence,
    // not the start boundary.
    let boundaries = ['。', '！', '？', '.', '!', '?', '\n'];
    let trimmed_end = preceding.trim_end_matches(|c: char| boundaries.contains(&c));

    // Now find the last sentence boundary in the remaining text —
    // that marks the start of the citation sentence.
    let trim_start = trimmed_end
        .char_indices()
        .rev()
        .find(|(_, c)| boundaries.contains(c))
        .map(|(idx, c)| idx + c.len_utf8())
        .unwrap_or(0);

    trimmed_end[trim_start..].trim().to_string()
}

/// Parse a `[CLARIFY: ... ]` block. The block MUST have a closing `]`.
/// Without a closing bracket, the text is not recognized as a clarification
/// block (prevents false positives from prose containing `[CLARIFY:`).
///
/// Format:
/// ```text
/// [CLARIFY:
/// Q1: <问题>
/// - <选项A>
/// - <选项B>
/// Q2: <问题>
/// ]
/// ```
fn scan_clarification(text: &str) -> Option<ClarificationRequest> {
    // Find the opening `[CLARIFY:`
    let open_marker = "[CLARIFY:";
    let open_pos = text.find(open_marker)?;

    // Find the closing `]` — it must be on its own line or at least after
    // the content. We search for `\n]` or `\n\s*]` pattern.
    let after_open = &text[open_pos + open_marker.len()..];

    // Search for a line that is just `]` (possibly with whitespace).
    // The closing bracket must be preceded by a newline to be a valid block end.
    let mut close_pos = None;
    for (idx, _) in after_open.match_indices('\n') {
        let line_start = idx + 1;
        let rest = &after_open[line_start..];
        let trimmed = rest.trim_start();
        if trimmed.starts_with(']') {
            // Found the closing bracket.
            close_pos = Some(line_start);
            break;
        }
    }

    let close_line_start = close_pos?;

    // The content is between the opening marker and the closing line.
    let content = &after_open[..close_line_start];

    // Parse questions from the content.
    let questions = parse_clarify_questions(content);
    if questions.is_empty() {
        return None;
    }

    Some(ClarificationRequest {
        intro: "请补充以下关键信息".to_string(),
        questions,
    })
}

/// Parse `Q<数字>:` questions and their `- ` options from clarification block content.
fn parse_clarify_questions(content: &str) -> Vec<ClarificationQuestion> {
    let mut questions = Vec::new();
    let mut current_q: Option<ClarificationQuestion> = None;

    for line in content.lines() {
        let trimmed = line.trim();

        // Check for question line: Q<digit>:
        if let Some(rest) = parse_question_line(trimmed) {
            // Save previous question if any.
            if let Some(q) = current_q.take() {
                if q.options.is_empty() {
                    // A question with no options still counts if it has a question text.
                }
                questions.push(q);
            }
            let q_num = questions.len() + 1;
            current_q = Some(ClarificationQuestion {
                id: format!("q{}", q_num),
                question: rest.to_string(),
                options: Vec::new(),
            });
        } else if let Some(opt_text) = parse_option_line(trimmed) {
            if let Some(ref mut q) = current_q {
                let opt_num = q.options.len() + 1;
                q.options.push(ClarificationOption {
                    id: format!("{}-o{}", q.id, opt_num),
                    label: opt_text.to_string(),
                    value: opt_text.to_string(),
                });
            }
        }
        // Other lines are ignored (blank lines, intro text, etc.)
    }

    // Don't forget the last question.
    if let Some(q) = current_q {
        questions.push(q);
    }

    // Filter: questions must have at least a question text.
    questions
}

/// Parse a `Q<digit>: <question>` line. Returns the question text.
fn parse_question_line(line: &str) -> Option<&str> {
    if !line.starts_with('Q') {
        return None;
    }
    // Find the digit(s) after Q.
    let after_q = &line[1..];
    let digit_end = after_q
        .char_indices()
        .take_while(|(_, c)| c.is_ascii_digit())
        .last()
        .map(|(i, c)| i + c.len_utf8())?;
    if digit_end == 0 {
        return None;
    }
    let after_digits = &after_q[digit_end..];
    if !after_digits.starts_with(':') && !after_digits.starts_with('：') {
        return None;
    }
    let question = after_digits[1..].trim();
    if question.is_empty() {
        return None;
    }
    Some(question)
}

/// Parse a `- <option>` line. Returns the option text.
fn parse_option_line(line: &str) -> Option<&str> {
    let trimmed = line.trim_start();
    if !trimmed.starts_with('-') {
        return None;
    }
    let after_dash = trimmed[1..].trim();
    if after_dash.is_empty() {
        return None;
    }
    Some(after_dash)
}

/// Parse `[HUMAN_REVIEW: <reason>]` marks. The bracket MUST close.
fn scan_human_review(text: &str) -> Vec<HumanReviewMark> {
    let marker = "[HUMAN_REVIEW:";
    let mut marks = Vec::new();
    let mut search_from = 0;

    while let Some(start) = text[search_from..].find(marker) {
        let abs_start = search_from + start;
        let after_marker = &text[abs_start + marker.len()..];

        // Find the closing `]`.
        if let Some(close_rel) = after_marker.find(']') {
            let reason = after_marker[..close_rel].trim();
            if !reason.is_empty() {
                marks.push(HumanReviewMark {
                    reason: reason.to_string(),
                    offset: abs_start,
                });
            }
            search_from = abs_start + marker.len() + close_rel + 1;
        } else {
            // No closing bracket — not a valid mark. Advance past this marker.
            search_from = abs_start + marker.len();
        }
    }

    marks
}

/// Check if a tool name is a "research" tool (for GRD-11 research_performed).
/// Matches: web_search, fetch, read, or any tool name containing "search".
pub fn is_research_tool(tool_name: &str) -> bool {
    let name = tool_name.to_lowercase();
    name == "web_search"
        || name == "fetch"
        || name == "read"
        || name == "read_text_file"
        || name.contains("search")
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── Citation tests ──────────────────────────────────────────────────

    #[test]
    fn scan_citation_verified_with_chinese_punctuation() {
        let text = "根据《民法典》第一百四十三条的规定，行为人具有相应的民事行为能力。[verified]";
        let scan = scan(text);
        assert_eq!(scan.citations.len(), 1);
        assert_eq!(scan.citations[0].level, CitationLevel::Verified);
        assert!(
            scan.citations[0].text.contains("民法典"),
            "preceding text should contain citation body"
        );
    }

    #[test]
    fn scan_citation_retrieved_with_newline_boundary() {
        let text = "前文内容。\n根据《劳动合同法》第十条[retrieved]";
        let scan = scan(text);
        assert_eq!(scan.citations.len(), 1);
        assert_eq!(scan.citations[0].level, CitationLevel::Retrieved);
        assert!(
            scan.citations[0].text.contains("劳动合同法"),
            "preceding text should contain the law reference"
        );
        // Should not include text before the sentence boundary.
        assert!(
            !scan.citations[0].text.contains("前文"),
            "should not cross sentence boundary"
        );
    }

    #[test]
    fn scan_citation_unverified() {
        let text = "我记得好像是《刑法》第二百六十四条[unverified]";
        let scan = scan(text);
        assert_eq!(scan.citations.len(), 1);
        assert_eq!(scan.citations[0].level, CitationLevel::Unverified);
    }

    #[test]
    fn scan_multiple_citations() {
        let text = "依据《民法典》第一百四十三条[verified]以及《合同法》第一百零七条[retrieved]，另据旧法[unverified]";
        let scan = scan(text);
        assert_eq!(scan.citations.len(), 3);
        assert_eq!(scan.citations[0].level, CitationLevel::Verified);
        assert_eq!(scan.citations[1].level, CitationLevel::Retrieved);
        assert_eq!(scan.citations[2].level, CitationLevel::Unverified);
    }

    // ── Clarification block tests ───────────────────────────────────────

    #[test]
    fn clarify_complete_block_parses_2q_4opt() {
        let text = "[CLARIFY:\nQ1: 合同类型是什么\n- 买卖合同\n- 租赁合同\nQ2: 争议金额\n- 10万以下\n- 10万以上\n]";
        let scan = scan(text);
        let clar = scan.clarification.expect("should parse clarification");
        assert_eq!(clar.questions.len(), 2, "should have 2 questions");
        assert_eq!(clar.questions[0].options.len(), 2, "Q1 should have 2 options");
        assert_eq!(clar.questions[1].options.len(), 2, "Q2 should have 2 options");
        assert_eq!(clar.questions[0].id, "q1");
        assert_eq!(clar.questions[1].id, "q2");
        assert_eq!(clar.questions[0].question, "合同类型是什么");
        assert_eq!(clar.questions[0].options[0].label, "买卖合同");
        assert_eq!(clar.questions[0].options[1].label, "租赁合同");
    }

    #[test]
    fn clarify_no_close_not_recognized() {
        // No closing ] — must NOT be recognized as a clarification block.
        let text = "正文中出现了 [CLARIFY: 这只是正文中的字样，没有闭合括号\n所以不会被识别为澄清块。";
        let scan = scan(text);
        assert!(
            scan.clarification.is_none(),
            "unclosed [CLARIFY: must not be recognized"
        );
    }

    #[test]
    fn clarify_with_extra_text_before_block() {
        let text = "根据您的问题，我需要补充一些信息。\n[CLARIFY:\nQ1: 案件类型\n- 民事\n- 刑事\n]";
        let scan = scan(text);
        let clar = scan.clarification.expect("should parse");
        assert_eq!(clar.questions.len(), 1);
        assert_eq!(clar.questions[0].options.len(), 2);
    }

    // ── Human review mark tests ─────────────────────────────────────────

    #[test]
    fn human_review_complete_mark_parsed() {
        let text = "本结论涉及合同效力认定。[HUMAN_REVIEW: 合同效力认定需人工复核]";
        let scan = scan(text);
        assert_eq!(scan.human_review.len(), 1);
        assert_eq!(
            scan.human_review[0].reason,
            "合同效力认定需人工复核"
        );
    }

    #[test]
    fn human_review_no_close_not_recognized() {
        // Literal "[HUMAN_REVIEW" without closing ] — must NOT be recognized.
        let text = "正文中提到 [HUMAN_REVIEW 但没有闭合括号，这只是普通文字。";
        let scan = scan(text);
        assert!(
            scan.human_review.is_empty(),
            "unclosed [HUMAN_REVIEW must not be recognized"
        );
    }

    #[test]
    fn human_review_multiple_marks() {
        let text = "结论一[HUMAN_REVIEW: 诉讼时效认定]\n结论二[HUMAN_REVIEW: 合同效力认定]";
        let scan = scan(text);
        assert_eq!(scan.human_review.len(), 2);
        assert_eq!(scan.human_review[0].reason, "诉讼时效认定");
        assert_eq!(scan.human_review[1].reason, "合同效力认定");
    }

    // ── Research tool detection ─────────────────────────────────────────

    #[test]
    fn is_research_tool_matches_search_tools() {
        assert!(is_research_tool("web_search"));
        assert!(is_research_tool("fetch"));
        assert!(is_research_tool("read"));
        assert!(is_research_tool("read_text_file"));
        assert!(is_research_tool("search-skills"));
        assert!(is_research_tool("legal-search"));
    }

    #[test]
    fn is_research_tool_rejects_non_search_tools() {
        assert!(!is_research_tool("bash"));
        assert!(!is_research_tool("pwsh"));
        assert!(!is_research_tool("todo_write"));
        assert!(!is_research_tool("skill"));
    }

    // ── Combined scan ───────────────────────────────────────────────────

    #[test]
    fn scan_all_three_conventions_in_one_text() {
        let text = "根据《民法典》第一百四十三条[verified]\n\n[HUMAN_REVIEW: 合同效力认定]\n\n[CLARIFY:\nQ1: 争议金额\n- 10万以下\n- 10万以上\n]";
        let scan = scan(text);
        assert_eq!(scan.citations.len(), 1);
        assert_eq!(scan.human_review.len(), 1);
        assert!(scan.clarification.is_some());
    }

    #[test]
    fn scan_empty_text_returns_empty() {
        let scan = scan("");
        assert!(scan.citations.is_empty());
        assert!(scan.clarification.is_none());
        assert!(scan.human_review.is_empty());
    }

    #[test]
    fn scan_plain_text_no_markers() {
        let scan = scan("这是一段普通的法律分析文字，没有任何护栏标记。");
        assert!(scan.citations.is_empty());
        assert!(scan.clarification.is_none());
        assert!(scan.human_review.is_empty());
    }
}
