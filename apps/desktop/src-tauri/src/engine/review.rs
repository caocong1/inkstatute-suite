//! Cross-review / adversarial-challenge artifact scanner.
//!
//! Isomorphic to `guardrails.rs::scan`: the model commits to a text
//! convention (enforced by the `[GUARDRAIL:SYNTHESIS]` persona segment in
//! `presets/legal-core/`), this module purely parses the committed final
//! text (no I/O, no tool calls) — the caller enforces what the parse finds.
//! Orchestration (when to call `legal_review_a`/`legal_review_b`/
//! `adversarial_challenge`, how to fold their output into a final answer)
//! lives entirely in the persona; there is no Rust orchestration code for
//! Phase 128, matching `128-CONTEXT.md`'s architectural finding that
//! multi-model review is configuration, not orchestration code.
//!
//! Conventions parsed from the committed final text:
//! 1. Disagreement lines: `[分歧] <issue> ｜ 本意见：<own> ｜ 复核意见：<reviewer> ｜ <resolution>`
//!    (full-width pipe `｜` separator). The final segment marks resolution:
//!    containing "已消解" → resolved; missing or ambiguous → NOT resolved
//!    (conservative direction — silence is treated as disagreement).
//! 2. Fatal challenges: items under a `【致命问题】` section header, one per
//!    line, up to the next `【...】` section header or end of text.
//! 3. Escalations: reuses `guardrails::scan`'s `[HUMAN_REVIEW: …]` extraction,
//!    filtered to marks whose reason mentions "分歧" (disagreement).
//!
//! **Invariant (enforced by `ensure_escalated`, locked in by tests below):**
//! 未消解分歧数 > 0 时，终稿必须带对应的 [HUMAN_REVIEW:] 标记。
//! 若解析出未消解分歧却找不到对应标记，视为模型未遵守人设 —— 由调用方补一条，
//! 绝不因为"模型没标"就当作没有分歧。

use serde::{Deserialize, Serialize};

use super::guardrails;

/// Result of scanning a committed final-draft text for review/challenge
/// structures.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct ReviewScan {
    pub disagreements: Vec<Disagreement>,
    pub unresolved_count: usize,
    pub fatal_challenges: Vec<String>,
    /// Entries from `[HUMAN_REVIEW: 模型间存在未消解分歧 …]` marks — i.e. the
    /// `guardrails::scan` human-review marks whose reason mentions "分歧".
    pub escalations: Vec<String>,
}

/// A single parsed disagreement entry.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Disagreement {
    pub issue: String,
    pub own_position: String,
    pub reviewer_position: String,
    pub resolved: bool,
    pub offset: usize,
}

/// Scan a committed final-draft text for disagreement lines, fatal
/// adversarial-challenge items, and disagreement-related human-review
/// escalations.
pub fn scan_review(text: &str) -> ReviewScan {
    let disagreements = scan_disagreements(text);
    let unresolved_count = disagreements.iter().filter(|d| !d.resolved).count();
    let fatal_challenges = scan_fatal_challenges(text);
    let escalations = scan_escalations(text);

    ReviewScan {
        disagreements,
        unresolved_count,
        fatal_challenges,
        escalations,
    }
}

/// Find all `[分歧] <issue> ｜ 本意见：<own> ｜ 复核意见：<reviewer> ｜ <resolution>`
/// lines. A bare `[分歧]` occurring in ordinary prose (no pipe-separated
/// structure following it) is not recognized — see `parse_disagreement_line`.
fn scan_disagreements(text: &str) -> Vec<Disagreement> {
    let marker = "[分歧]";
    let mut disagreements = Vec::new();
    let mut search_from = 0;

    while let Some(rel) = text[search_from..].find(marker) {
        let marker_start = search_from + rel;
        let after_marker = &text[marker_start + marker.len()..];
        // A disagreement entry is a single line: everything up to the next
        // newline (or end of text).
        let line_end = after_marker.find('\n').unwrap_or(after_marker.len());
        let line = &after_marker[..line_end];

        if let Some(d) = parse_disagreement_line(line, marker_start) {
            disagreements.push(d);
        }
        // Advance past this occurrence regardless of whether it parsed, so
        // an unparseable "[分歧]" is never rescanned as a substring of itself.
        search_from = marker_start + marker.len();
    }

    disagreements
}

/// Parse one candidate disagreement line — the text following a `[分歧]`
/// marker, up to end of line. Returns `None` when the line does not match
/// the required `｜`-separated structure with `本意见：`/`复核意见：` prefixes,
/// so a literal "[分歧]" appearing in ordinary prose is never misrecognized
/// as a structured entry.
fn parse_disagreement_line(line: &str, offset: usize) -> Option<Disagreement> {
    let segments: Vec<&str> = line.split('｜').collect();
    if segments.len() < 3 {
        return None;
    }

    let issue = segments[0].trim();
    if issue.is_empty() {
        return None;
    }

    let own_seg = segments[1].trim();
    let own_position = own_seg
        .strip_prefix("本意见：")
        .or_else(|| own_seg.strip_prefix("本意见:"))?
        .trim();

    let reviewer_seg = segments[2].trim();
    let reviewer_position = reviewer_seg
        .strip_prefix("复核意见：")
        .or_else(|| reviewer_seg.strip_prefix("复核意见:"))?
        .trim();

    // The resolution segment (4th field) may be entirely missing — that is
    // the "末段缺失" case, treated the same as a present-but-ambiguous
    // segment: conservative default is NOT resolved. Segments beyond the
    // 4th (if the resolution text itself happened to contain a `｜`) are
    // rejoined rather than dropped.
    let resolution = if segments.len() >= 4 {
        segments[3..].join("｜")
    } else {
        String::new()
    };
    let resolved = resolution.contains("已消解");

    Some(Disagreement {
        issue: issue.to_string(),
        own_position: own_position.to_string(),
        reviewer_position: reviewer_position.to_string(),
        resolved,
        offset,
    })
}

/// Extract fatal-challenge items from every `【致命问题】` section: one entry
/// per non-blank line (leading `- ` bullet markers stripped), running until
/// the next `【` section header or end of text.
fn scan_fatal_challenges(text: &str) -> Vec<String> {
    let marker = "【致命问题】";
    let mut items = Vec::new();
    let mut search_from = 0;

    while let Some(rel) = text[search_from..].find(marker) {
        let body_start = search_from + rel + marker.len();
        let rest = &text[body_start..];
        let body_end = rest.find('【').unwrap_or(rest.len());
        let body = &rest[..body_end];

        for line in body.lines() {
            let trimmed = line.trim();
            let item = trimmed.strip_prefix('-').map(|s| s.trim()).unwrap_or(trimmed);
            if !item.is_empty() {
                items.push(item.to_string());
            }
        }

        search_from = body_start + body_end;
    }

    items
}

/// Reuse `guardrails::scan`'s `[HUMAN_REVIEW: …]` extraction, filtered to
/// marks whose reason mentions "分歧" (disagreement) — i.e. escalations
/// raised specifically because of unresolved cross-review disagreement,
/// as opposed to the other GRD-14 human-review triggers.
fn scan_escalations(text: &str) -> Vec<String> {
    guardrails::scan(text)
        .human_review
        .into_iter()
        .filter(|mark| mark.reason.contains("分歧"))
        .map(|mark| mark.reason)
        .collect()
}

/// Fallback invariant enforcement: if `scan` found unresolved disagreements
/// but the text carries no matching `[HUMAN_REVIEW: …分歧…]` mark, the model
/// failed to follow the `[GUARDRAIL:SYNTHESIS]` persona instruction. Returns
/// the human-review text the caller (app layer) must append — never `None`
/// when disagreements are unresolved and unmarked, and never treats a
/// model's silence as "no disagreement".
///
/// Re-derives the "already marked" check directly from `text` (rather than
/// trusting `scan.escalations` alone) so a caller cannot accidentally pass a
/// stale `scan` computed from different text and get a wrong answer.
pub fn ensure_escalated(scan: &ReviewScan, text: &str) -> Option<String> {
    if scan.unresolved_count == 0 {
        return None;
    }

    let already_marked = guardrails::scan(text)
        .human_review
        .iter()
        .any(|mark| mark.reason.contains("分歧"));
    if already_marked {
        return None;
    }

    Some(format!(
        "[HUMAN_REVIEW: 模型间存在未消解分歧 —— 共 {} 条未消解，模型未按人设标注，由系统兜底补充]",
        scan.unresolved_count
    ))
}

/// Default adversarial-challenge round cap (`[GUARDRAIL:SYNTHESIS]`:
/// "对抗质询最多两轮").
pub const DEFAULT_MAX_ROUNDS: usize = 2;

/// Tracks adversarial-challenge rounds and decides when to early-stop:
/// no new fatal/attackable findings in a round, or the round cap is reached.
pub struct RoundTracker {
    max_rounds: usize,
    rounds_used: usize,
    stopped_early: bool,
}

impl RoundTracker {
    /// `max_rounds` should be `DEFAULT_MAX_ROUNDS` (2) unless explicitly
    /// overridden.
    pub fn new(max_rounds: usize) -> Self {
        Self {
            max_rounds,
            rounds_used: 0,
            stopped_early: false,
        }
    }

    /// Record one adversarial-challenge round's result. `fatal` is the
    /// number of `【致命问题】` items, `attackable` the number of
    /// `【可被攻击】` items found in that round. Returns whether another
    /// round should be attempted.
    pub fn record(&mut self, fatal: usize, attackable: usize) -> bool {
        self.rounds_used += 1;

        if fatal == 0 && attackable == 0 {
            // Nothing new to challenge — stop regardless of the round cap.
            self.stopped_early = true;
            return false;
        }

        if self.rounds_used >= self.max_rounds {
            return false;
        }

        true
    }

    pub fn rounds_used(&self) -> usize {
        self.rounds_used
    }

    /// True only when the tracker stopped because a round found nothing new
    /// (as opposed to stopping because the round cap was reached while
    /// findings were still coming in).
    pub fn stopped_early(&self) -> bool {
        self.stopped_early
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── Disagreement line parsing ───────────────────────────────────────

    #[test]
    fn disagreement_line_resolved_true_when_final_segment_says_resolved() {
        let text = "[分歧] 对赌条款是否有效｜本意见：有效，依据《公司法》第二十条｜复核意见：与股东仅对赌无效判例冲突｜已消解，现行司法解释明确认可";
        let scan = scan_review(text);
        assert_eq!(scan.disagreements.len(), 1);
        let d = &scan.disagreements[0];
        assert_eq!(d.issue, "对赌条款是否有效");
        assert!(d.own_position.contains("公司法"));
        assert!(d.reviewer_position.contains("判例冲突"));
        assert!(d.resolved, "final segment contains 已消解 → resolved");
        assert_eq!(scan.unresolved_count, 0);
    }

    #[test]
    fn disagreement_line_resolved_false_when_final_segment_says_unresolved() {
        let text = "[分歧] 诉讼时效起算点｜本意见：自知道权利受损之日起算｜复核意见：应自合同约定履行期届满起算｜未消解，双方依据均为现行有效条文";
        let scan = scan_review(text);
        assert_eq!(scan.disagreements.len(), 1);
        assert!(!scan.disagreements[0].resolved);
        assert_eq!(scan.unresolved_count, 1);
    }

    #[test]
    fn disagreement_missing_resolution_segment_defaults_to_unresolved() {
        // Only 3 segments — issue, 本意见, 复核意见 — no trailing resolution
        // field at all. Conservative default: NOT resolved.
        let text = "[分歧] 管辖法院认定｜本意见：应由被告住所地法院管辖｜复核意见：合同约定了仲裁条款，应先审查仲裁协议效力";
        let scan = scan_review(text);
        assert_eq!(scan.disagreements.len(), 1, "entry still recognized despite missing final segment");
        assert!(
            !scan.disagreements[0].resolved,
            "missing resolution segment must default to unresolved (conservative)"
        );
        assert_eq!(scan.unresolved_count, 1);
    }

    #[test]
    fn literal_bracket_text_without_pipe_structure_not_misrecognized() {
        // "[分歧]" appears as an ordinary word in prose, with no pipe-separated
        // structure following it — must not be parsed as a Disagreement.
        let text = "本次庭前会议的核心[分歧]在于证据保全的范围，双方将在正式开庭时进一步陈述意见。";
        let scan = scan_review(text);
        assert!(
            scan.disagreements.is_empty(),
            "malformed [分歧] occurrence in prose must not be recognized"
        );
    }

    #[test]
    fn literal_bracket_text_with_wrong_prefixes_not_misrecognized() {
        // Has pipes, but the required 本意见：/复核意见： prefixes are absent.
        let text = "[分歧] 违约金标准 ｜ 原告主张按合同约定 ｜ 被告主张过高应调整";
        let scan = scan_review(text);
        assert!(
            scan.disagreements.is_empty(),
            "pipe-separated text without 本意见/复核意见 prefixes must not be recognized"
        );
    }

    #[test]
    fn multiple_disagreement_lines_parsed_independently() {
        let text = "\
[分歧] 争点一｜本意见：立场A｜复核意见：立场B｜已消解，现行法明确
[分歧] 争点二｜本意见：立场C｜复核意见：立场D｜未消解，双方均有依据
[分歧] 争点三｜本意见：立场E｜复核意见：立场F";
        let scan = scan_review(text);
        assert_eq!(scan.disagreements.len(), 3);
        assert!(scan.disagreements[0].resolved);
        assert!(!scan.disagreements[1].resolved);
        assert!(!scan.disagreements[2].resolved, "missing 4th segment on line 3");
        assert_eq!(scan.unresolved_count, 2);
    }

    // ── Fatal challenge extraction ──────────────────────────────────────

    #[test]
    fn fatal_challenges_extracts_multiple_items_stopping_at_next_bracket() {
        let text = "\
【致命问题】
- 时效抗辩：起诉已超过三年诉讼时效，且无中断中止事由
- 主体资格：原告未能证明其对涉案债权享有合法受让资格
【可被攻击】
- 证据链存在瑕疵，但不足以推翻结论";
        let scan = scan_review(text);
        assert_eq!(scan.fatal_challenges.len(), 2);
        assert!(scan.fatal_challenges[0].contains("时效抗辩"));
        assert!(scan.fatal_challenges[1].contains("主体资格"));
        // Must not have crossed into the 【可被攻击】 section.
        assert!(!scan.fatal_challenges.iter().any(|i| i.contains("证据链")));
    }

    #[test]
    fn fatal_challenges_empty_when_no_section_present() {
        let scan = scan_review("这是一段没有致命问题小节的普通文本。");
        assert!(scan.fatal_challenges.is_empty());
    }

    #[test]
    fn fatal_challenges_section_runs_to_end_of_text_when_no_next_bracket() {
        let text = "【致命问题】\n- 唯一的致命问题项";
        let scan = scan_review(text);
        assert_eq!(scan.fatal_challenges.len(), 1);
        assert_eq!(scan.fatal_challenges[0], "唯一的致命问题项");
    }

    // ── Escalation extraction ───────────────────────────────────────────

    #[test]
    fn escalations_filter_to_disagreement_related_human_review_marks() {
        let text = "结论一。[HUMAN_REVIEW: 模型间存在未消解分歧 —— 诉讼时效起算点]\n结论二。[HUMAN_REVIEW: 涉及金额超过100万]";
        let scan = scan_review(text);
        assert_eq!(scan.escalations.len(), 1);
        assert!(scan.escalations[0].contains("分歧"));
    }

    // ── ensure_escalated fallback invariant ─────────────────────────────

    #[test]
    fn ensure_escalated_returns_some_when_unresolved_and_unmarked() {
        let text = "[分歧] 争点｜本意见：A｜复核意见：B｜未消解，均有现行依据";
        let scan = scan_review(text);
        assert_eq!(scan.unresolved_count, 1);
        let fallback = ensure_escalated(&scan, text);
        assert!(
            fallback.is_some(),
            "unresolved disagreement with no [HUMAN_REVIEW:] mark must trigger fallback"
        );
        let fallback_text = fallback.unwrap();
        assert!(fallback_text.starts_with("[HUMAN_REVIEW:"));
        assert!(fallback_text.contains("分歧"));
    }

    #[test]
    fn ensure_escalated_returns_none_when_already_marked() {
        let text = "[分歧] 争点｜本意见：A｜复核意见：B｜未消解，均有现行依据\n[HUMAN_REVIEW: 模型间存在未消解分歧 —— 争点]";
        let scan = scan_review(text);
        assert_eq!(scan.unresolved_count, 1);
        assert!(ensure_escalated(&scan, text).is_none());
    }

    #[test]
    fn ensure_escalated_returns_none_when_no_unresolved_disagreements() {
        let text = "[分歧] 争点｜本意见：A｜复核意见：B｜已消解，现行法明确";
        let scan = scan_review(text);
        assert_eq!(scan.unresolved_count, 0);
        assert!(ensure_escalated(&scan, text).is_none());
    }

    // ── RoundTracker early-stop ──────────────────────────────────────────

    #[test]
    fn round_tracker_stops_immediately_on_first_round_with_nothing_new() {
        let mut tracker = RoundTracker::new(DEFAULT_MAX_ROUNDS);
        let should_continue = tracker.record(0, 0);
        assert!(!should_continue, "record(0,0) must return false");
        assert_eq!(tracker.rounds_used(), 1);
        assert!(tracker.stopped_early());
    }

    #[test]
    fn round_tracker_stops_at_cap_after_max_rounds_with_findings() {
        let mut tracker = RoundTracker::new(2);
        assert!(tracker.record(2, 1), "round 1 has findings and cap not reached → continue");
        assert!(!tracker.record(2, 1), "round 2 reaches cap → stop");
        assert_eq!(tracker.rounds_used(), 2);
        assert!(!tracker.stopped_early(), "stopping at the cap is not an early stop");
    }

    #[test]
    fn round_tracker_second_round_with_nothing_new_stops_before_cap() {
        let mut tracker = RoundTracker::new(3);
        assert!(tracker.record(1, 0), "round 1 has a fatal finding → continue");
        let should_continue = tracker.record(0, 0);
        assert!(!should_continue, "round 2 finds nothing new → stop before the round-3 cap");
        assert_eq!(tracker.rounds_used(), 2);
        assert!(tracker.stopped_early());
    }
}
