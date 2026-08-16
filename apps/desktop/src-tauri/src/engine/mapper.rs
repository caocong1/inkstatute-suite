//! DSH session event → `RunEventEnvelope` mapper.
//!
//! Translates the 19+ DSH `SessionEventKind` values into the 15 unified
//! `event_type` strings consumed by `packages/ui-core/src/event-reducer.ts`.
//! The reducer is immutable (never modified in Phase 124); the mapper is the
//! only place where DSH-specific event shapes become UI-neutral envelopes.
//!
//! Stateful: tracks the current run ID, a monotonic output sequence counter,
//! tool-call accumulation (so the first `tool-call-delta` for a given index
//! emits `tool_call.started`), and the pending session title (attached as
//! metadata to the next emitted envelope).

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use super::acp::PermissionRequest;
use super::events::{AssistantChunk, SessionEvent, SessionEventKind, SessionHeader};
use super::guardrails;

/// The 15 unified event types recognized by the reducer.
pub const EVENT_SESSION_STARTED: &str = "session.started";
pub const EVENT_MESSAGE_DELTA: &str = "message.delta";
pub const EVENT_MESSAGE_COMPLETED: &str = "message.completed";
pub const EVENT_THOUGHT_DELTA: &str = "thought.delta";
pub const EVENT_TOOL_CALL_STARTED: &str = "tool_call.started";
pub const EVENT_TOOL_CALL_DELTA: &str = "tool_call.delta";
pub const EVENT_TOOL_CALL_COMPLETED: &str = "tool_call.completed";
pub const EVENT_PLAN_UPDATED: &str = "plan.updated";
pub const EVENT_PHASE_CHANGED: &str = "phase.changed";
pub const EVENT_ELICITATION_REQUESTED: &str = "elicitation.requested";
pub const EVENT_PERMISSION_REQUESTED: &str = "permission.requested";
pub const EVENT_ARTIFACT_CREATED: &str = "artifact.created";
pub const EVENT_CITATION_RECORDED: &str = "citation.recorded";
pub const EVENT_RUN_STATE_CHANGED: &str = "run.state_changed";
pub const EVENT_ERROR: &str = "error";

/// The unified envelope shape, serializable to JSON for the Tauri event channel.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RunEventEnvelope {
    pub event_id: String,
    pub run_id: String,
    pub event_type: String,
    pub occurred_at: String,
    pub seq: u64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub payload: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<Value>,
}

/// Stateful mapper from DSH session events to unified envelopes.
pub struct EventMapper {
    run_id: String,
    out_seq: u64,
    /// Tool-call IDs seen so far (by block index) — the first delta for a new
    /// index emits `tool_call.started`.
    seen_tool_calls: std::collections::HashMap<u32, String>,
    /// Pending session title, attached as metadata to the next envelope.
    pending_title: Option<String>,
    /// Current turn number (for plan.updated step labels).
    current_turn: u64,
    /// Current step number within the turn.
    current_step: u64,
    /// Whether any research-type tool was called in this run (GRD-11).
    research_performed: bool,
}

impl EventMapper {
    pub fn new(run_id: String) -> Self {
        Self {
            run_id,
            out_seq: 0,
            seen_tool_calls: std::collections::HashMap::new(),
            pending_title: None,
            current_turn: 0,
            current_step: 0,
            research_performed: false,
        }
    }

    fn next_seq(&mut self) -> u64 {
        let s = self.out_seq;
        self.out_seq += 1;
        s
    }

    fn envelope(
        &mut self,
        event_type: &str,
        occurred_at: String,
        payload: Option<Value>,
        metadata: Option<Value>,
    ) -> RunEventEnvelope {
        let seq = self.next_seq();
        // Attach pending title as metadata if present.
        let pending = self.pending_title.take();
        let metadata = match (pending, metadata) {
            (Some(title), Some(mut m)) => {
                if let Some(obj) = m.as_object_mut() {
                    obj.insert("session_title".to_string(), Value::String(title));
                }
                Some(m)
            }
            (Some(title), None) => Some(json!({ "session_title": title })),
            (None, m) => m,
        };

        RunEventEnvelope {
            event_id: format!("{}-{}", self.run_id, seq),
            run_id: self.run_id.clone(),
            event_type: event_type.to_string(),
            occurred_at,
            seq,
            payload,
            metadata,
        }
    }

    /// Map a `SessionHeader` → `session.started` envelope.
    pub fn map_header(&mut self, h: &SessionHeader) -> Vec<RunEventEnvelope> {
        let payload = json!({
            "backend_id": h.id,
            "session_id": h.id,
            "metadata": {
                "cwd": h.cwd,
                "agent_preset": h.agent_preset,
            }
        });
        let occurred_at = iso_time(h.created_at);
        vec![self.envelope(
            EVENT_SESSION_STARTED,
            occurred_at,
            Some(payload),
            None,
        )]
    }

    /// Map a DSH `SessionEvent` → zero or more unified envelopes.
    pub fn map(&mut self, ev: &SessionEvent) -> Vec<RunEventEnvelope> {
        let occurred_at = iso_time(ev.time);
        match &ev.kind {
            SessionEventKind::TurnStart => {
                self.current_turn = ev
                    .raw
                    .get("data")
                    .and_then(|d| d.get("turn"))
                    .and_then(|t| t.as_u64())
                    .unwrap_or(self.current_turn + 1);
                let metadata = json!({ "research_performed": self.research_performed });
                vec![self.envelope(
                    EVENT_RUN_STATE_CHANGED,
                    occurred_at,
                    Some(json!({ "status": "running" })),
                    Some(metadata),
                )]
            }

            SessionEventKind::TurnEnd => {
                let reason = ev.raw.get("data").and_then(|d| d.get("reason"));
                let kind = reason.and_then(|r| r.get("kind")).and_then(|k| k.as_str());
                match kind {
                    Some("error") | Some("failed") => {
                        let error_msg = reason
                            .and_then(|r| r.get("error"))
                            .and_then(|e| e.get("message"))
                            .and_then(|m| m.as_str())
                            .unwrap_or("引擎运行出错");
                        // Strip technical prefixes like "Error:" — the UI must
                        // show a clean Chinese message.
                        let clean = clean_error_message(error_msg);
                        let payload = json!({
                            "error": {
                                "category": "engine",
                                "message": clean,
                            }
                        });
                        vec![self.envelope(EVENT_ERROR, occurred_at, Some(payload), None)]
                    }
                    _ => {
                        let metadata = json!({ "research_performed": self.research_performed });
                        vec![self.envelope(
                            EVENT_RUN_STATE_CHANGED,
                            occurred_at,
                            Some(json!({ "status": "completed" })),
                            Some(metadata),
                        )]
                    }
                }
            }

            SessionEventKind::StepStart => {
                self.current_step = ev
                    .raw
                    .get("data")
                    .and_then(|d| d.get("step"))
                    .and_then(|s| s.as_u64())
                    .unwrap_or(self.current_step + 1);
                let step_label = format!("步骤 {}.{}", self.current_turn, self.current_step);
                let payload = json!({
                    "plan": [{
                        "title": step_label,
                        "status": "run",
                    }]
                });
                vec![self.envelope(
                    EVENT_PLAN_UPDATED,
                    occurred_at,
                    Some(payload),
                    None,
                )]
            }

            SessionEventKind::StepEnd => {
                let step_label = format!("步骤 {}.{}", self.current_turn, self.current_step);
                let payload = json!({
                    "plan": [{
                        "title": step_label,
                        "status": "done",
                    }]
                });
                vec![self.envelope(
                    EVENT_PLAN_UPDATED,
                    occurred_at,
                    Some(payload),
                    None,
                )]
            }

            SessionEventKind::AssistantChunk => {
                self.map_assistant_chunk(ev, &occurred_at)
            }

            SessionEventKind::AssistantMessage => {
                // Concatenate all text blocks from the message content.
                let content = ev
                    .raw
                    .get("data")
                    .and_then(|d| d.get("message"))
                    .and_then(|m| m.get("content"))
                    .and_then(|c| c.as_array())
                    .map(|blocks| {
                        let mut buf = String::new();
                        for block in blocks {
                            if block.get("type").and_then(|t| t.as_str()) == Some("text") {
                                if let Some(text) = block.get("text").and_then(|t| t.as_str()) {
                                    buf.push_str(text);
                                }
                            }
                        }
                        buf
                    })
                    .unwrap_or_default();
                let message_id = ev
                    .raw
                    .get("data")
                    .and_then(|d| d.get("message"))
                    .and_then(|m| m.get("id"))
                    .and_then(|i| i.as_str())
                    .unwrap_or("")
                    .to_string();

                // A tool-only commit carries no text; emitting completed for it
                // renders a bare avatar row with an empty bubble in the thread.
                if content.trim().is_empty() {
                    return Vec::new();
                }

                // Scan the committed text for guardrail structures (GRD-12/13/14).
                let scan = guardrails::scan(&content);

                let mut out = Vec::new();

                // Build metadata for the message.completed envelope.
                let metadata = if !scan.human_review.is_empty() {
                    let reasons: Vec<&str> =
                        scan.human_review.iter().map(|m| m.reason.as_str()).collect();
                    Some(json!({ "human_review": reasons }))
                } else {
                    None
                };

                let payload = json!({
                    "content": content,
                    "message_id": message_id,
                });
                out.push(self.envelope(
                    EVENT_MESSAGE_COMPLETED,
                    occurred_at.clone(),
                    Some(payload),
                    metadata,
                ));

                // Emit citation.recorded for each citation found.
                for citation in &scan.citations {
                    let cite_payload = json!({
                        "citations": [{
                            "source": citation.text,
                            "status": citation.level.as_str(),
                        }]
                    });
                    out.push(self.envelope(
                        EVENT_CITATION_RECORDED,
                        occurred_at.clone(),
                        Some(cite_payload),
                        None,
                    ));
                }

                // Emit elicitation.requested if a clarification block was found.
                if let Some(clar) = &scan.clarification {
                    let questions: Vec<Value> = clar
                        .questions
                        .iter()
                        .map(|q| {
                            let options: Vec<Value> = q
                                .options
                                .iter()
                                .map(|opt| {
                                    json!({
                                        "label": opt.label,
                                        "value": opt.value,
                                    })
                                })
                                .collect();
                            json!({
                                "id": q.id,
                                "question": q.question,
                                "options": options,
                            })
                        })
                        .collect();
                    let elicitation_payload = json!({
                        "interrupt_id": format!("clarify-{}", message_id),
                        "intro": clar.intro,
                        "questions": questions,
                    });
                    out.push(self.envelope(
                        EVENT_ELICITATION_REQUESTED,
                        occurred_at.clone(),
                        Some(elicitation_payload),
                        None,
                    ));
                }

                out
            }

            SessionEventKind::ToolCall => {
                let tool_call_id = ev
                    .raw
                    .get("data")
                    .and_then(|d| d.get("toolCallId"))
                    .and_then(|t| t.as_str())
                    .unwrap_or("")
                    .to_string();
                let tool_name = ev
                    .raw
                    .get("data")
                    .and_then(|d| d.get("name"))
                    .and_then(|n| n.as_str())
                    .unwrap_or("")
                    .to_string();
                // Track research-type tool calls for GRD-11 research_performed.
                if guardrails::is_research_tool(&tool_name) {
                    self.research_performed = true;
                }
                self.seen_tool_calls
                    .insert(0, tool_call_id.clone()); // track by index 0 fallback
                let payload = json!({
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                });
                vec![self.envelope(
                    EVENT_TOOL_CALL_STARTED,
                    occurred_at,
                    Some(payload),
                    None,
                )]
            }

            SessionEventKind::ToolResult => {
                let tool_call_id = ev
                    .raw
                    .get("data")
                    .and_then(|d| d.get("toolCallId"))
                    .and_then(|t| t.as_str())
                    .unwrap_or("")
                    .to_string();
                let is_error = ev
                    .raw
                    .get("data")
                    .and_then(|d| d.get("isError"))
                    .and_then(|e| e.as_bool())
                    .unwrap_or(false);
                let status = if is_error { "error" } else { "done" };
                let payload = json!({
                    "tool_call_id": tool_call_id,
                    "status": status,
                });
                vec![self.envelope(
                    EVENT_TOOL_CALL_COMPLETED,
                    occurred_at,
                    Some(payload),
                    None,
                )]
            }

            SessionEventKind::SessionTitle => {
                // No standalone event — stash the title for the next envelope.
                let title = ev
                    .raw
                    .get("data")
                    .and_then(|d| d.get("title"))
                    .and_then(|t| t.as_str())
                    .unwrap_or("")
                    .to_string();
                if !title.is_empty() {
                    self.pending_title = Some(title);
                }
                Vec::new()
            }

            SessionEventKind::RequestHeader
            | SessionEventKind::RequestContext
            | SessionEventKind::AgentInboxSpliced
            | SessionEventKind::SessionCreated
            | SessionEventKind::SessionDisposed
            | SessionEventKind::SessionFlush
            | SessionEventKind::SessionEndSeed
            | SessionEventKind::ToolCodeDispatch
            | SessionEventKind::ToolCodeDispatchStart
            | SessionEventKind::UserMessage
            | SessionEventKind::Other(_) => {
                // Drop noise / unsupported kinds. UserMessage is handled
                // separately (the UI renders user messages from its own input,
                // not from the observation plane).
                Vec::new()
            }
        }
    }

    fn map_assistant_chunk(&mut self, ev: &SessionEvent, occurred_at: &str) -> Vec<RunEventEnvelope> {
        let chunk = match ev.assistant_chunk() {
            Some(c) => c,
            None => return Vec::new(),
        };
        match chunk {
            AssistantChunk::TextDelta { text, .. } => {
                let payload = json!({ "delta": text });
                vec![self.envelope(
                    EVENT_MESSAGE_DELTA,
                    occurred_at.to_string(),
                    Some(payload),
                    None,
                )]
            }
            AssistantChunk::ReasoningDelta { text, .. } => {
                let payload = json!({ "delta": text });
                vec![self.envelope(
                    EVENT_THOUGHT_DELTA,
                    occurred_at.to_string(),
                    Some(payload),
                    None,
                )]
            }
            AssistantChunk::ToolCallDelta {
                index,
                id,
                name,
                arguments_delta,
            } => {
                let mut out = Vec::new();
                // First delta for this index → emit tool_call.started.
                if !self.seen_tool_calls.contains_key(&index) {
                    self.seen_tool_calls.insert(index, id.clone());
                    let tool_name = name.clone().unwrap_or_default();
                    // Track research-type tool calls for GRD-11 research_performed.
                    if guardrails::is_research_tool(&tool_name) {
                        self.research_performed = true;
                    }
                    let payload = json!({
                        "tool_call_id": id,
                        "tool_name": tool_name,
                    });
                    out.push(self.envelope(
                        EVENT_TOOL_CALL_STARTED,
                        occurred_at.to_string(),
                        Some(payload),
                        None,
                    ));
                }
                // Then emit the delta.
                let payload = json!({
                    "tool_call_id": id,
                    "content": arguments_delta,
                });
                out.push(self.envelope(
                    EVENT_TOOL_CALL_DELTA,
                    occurred_at.to_string(),
                    Some(payload),
                    None,
                ));
                out
            }
            AssistantChunk::Usage { usage } => {
                // Map usage into run.state_changed metadata.
                let prompt_tokens = usage
                    .get("prompt_tokens")
                    .and_then(|t| t.as_u64())
                    .unwrap_or(0);
                let completion_tokens = usage
                    .get("completion_tokens")
                    .and_then(|t| t.as_u64())
                    .unwrap_or(0);
                let total_tokens = usage
                    .get("total_tokens")
                    .and_then(|t| t.as_u64())
                    .unwrap_or(prompt_tokens + completion_tokens);
                let payload = json!({ "status": "running" });
                let metadata = json!({
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                    }
                });
                vec![self.envelope(
                    EVENT_RUN_STATE_CHANGED,
                    occurred_at.to_string(),
                    Some(payload),
                    Some(metadata),
                )]
            }
            AssistantChunk::BlockStart { .. }
            | AssistantChunk::BlockEnd { .. }
            | AssistantChunk::Finish { .. }
            | AssistantChunk::Unknown(_) => {
                // Block boundaries and finish reasons are metadata, not UI events.
                Vec::new()
            }
        }
    }

    /// Map an ACP permission request → `permission.requested` envelope.
    pub fn map_permission(&mut self, req: &PermissionRequest) -> RunEventEnvelope {
        let occurred_at = iso_time_now();
        let tool_call_id = req.tool_call_id.clone().unwrap_or_default();
        let description = req
            .tool_name
            .clone()
            .unwrap_or_else(|| "引擎请求执行操作".to_string());
        let kind = req
            .options
            .iter()
            .find_map(|o| o.kind.clone())
            .unwrap_or_default();
        let payload = json!({
            "permission_id": req.request_id.to_string(),
            "tool_call_id": tool_call_id,
            "description": description,
            "kind": kind,
        });
        self.envelope(
            EVENT_PERMISSION_REQUESTED,
            occurred_at,
            Some(payload),
            None,
        )
    }
}

/// Convert a DSH millisecond timestamp to an ISO 8601 string.
fn iso_time(ms: i64) -> String {
    let secs = ms / 1000;
    let millis = ms % 1000;
    // Build a UTC datetime string without chrono.
    let dt = format_unix_time(secs);
    format!("{dt}.{millis:03}Z")
}

/// Format a Unix timestamp (seconds) as `YYYY-MM-DDTHH:MM:SS` in UTC.
fn format_unix_time(secs: i64) -> String {
    // Algorithm: civil_from_days (Howard Hinnant).
    let days = secs.div_euclid(86400);
    let rem = secs.rem_euclid(86400);
    let hour = rem / 3600;
    let minute = (rem % 3600) / 60;
    let second = rem % 60;

    let (y, m, d) = civil_from_days(days);
    format!("{y:04}-{m:02}-{d:02}T{hour:02}:{minute:02}:{second:02}")
}

fn civil_from_days(z: i64) -> (i64, u32, u32) {
    let z = z + 719468;
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = (doy - (153 * mp + 2) / 5 + 1) as u32;
    let m = if mp < 10 { mp + 3 } else { mp - 9 } as u32;
    (if m <= 2 { y + 1 } else { y }, m, d)
}

fn iso_time_now() -> String {
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default();
    iso_time(now.as_millis() as i64)
}

/// Strip technical prefixes like "Error:", "AUTH:", etc. from an error message
/// and return a clean user-facing string. If the message is already clean
/// (Chinese), return it as-is. If it's purely technical/English, return a
/// generic Chinese message.
fn clean_error_message(msg: &str) -> String {
    let trimmed = msg.trim();
    // If the message contains CJK characters, it's likely already user-facing.
    let has_cjk = trimmed.chars().any(|c| {
        ('\u{4E00}'..='\u{9FFF}').contains(&c) || ('\u{3400}'..='\u{4DBF}').contains(&c)
    });
    if has_cjk {
        return trimmed.to_string();
    }
    // Strip common technical prefixes.
    let cleaned = trimmed
        .trim_start_matches("Error:")
        .trim_start_matches("error:")
        .trim()
        .to_string();
    if cleaned.is_empty() || !cleaned.chars().any(|c| c.is_alphabetic()) {
        return "引擎运行出错，请稍后重试".to_string();
    }
    // If still purely English/technical, return a generic Chinese message.
    if !cleaned.chars().any(|c| ('\u{4E00}'..='\u{9FFF}').contains(&c)) {
        return "引擎运行出错，请稍后重试".to_string();
    }
    cleaned
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::events::parse_line;

    fn fixture_lines(name: &str) -> Vec<String> {
        let manifest = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let text = std::fs::read_to_string(manifest.join("tests/fixtures").join(name))
            .unwrap_or_else(|_| panic!("read fixture {name}"));
        text.lines().map(|l| l.to_string()).collect()
    }

    fn map_fixture(name: &str) -> Vec<RunEventEnvelope> {
        let lines = fixture_lines(name);
        let mut mapper = EventMapper::new("run-test".to_string());
        let mut out = Vec::new();
        for line in &lines {
            match parse_line(line).unwrap() {
                super::super::events::ParsedLine::Header(h) => {
                    out.extend(mapper.map_header(&h));
                }
                super::super::events::ParsedLine::Event(ev) => {
                    out.extend(mapper.map(&ev));
                }
                _ => {}
            }
        }
        out
    }

    #[test]
    fn success_fixture_produces_message_and_completed() {
        let envelopes = map_fixture("session-success.jsonl");
        let has_delta = envelopes
            .iter()
            .any(|e| e.event_type == EVENT_MESSAGE_DELTA);
        let has_completed = envelopes
            .iter()
            .any(|e| e.event_type == EVENT_MESSAGE_COMPLETED);
        assert!(has_delta, "should have message.delta events");
        assert!(has_completed, "should have message.completed event");
        // The completed message content should be nonempty.
        let completed = envelopes
            .iter()
            .find(|e| e.event_type == EVENT_MESSAGE_COMPLETED)
            .unwrap();
        let content = completed
            .payload
            .as_ref()
            .and_then(|p| p.get("content"))
            .and_then(|c| c.as_str())
            .unwrap_or("");
        assert!(!content.is_empty(), "completed message content nonempty");
    }

    #[test]
    fn success_fixture_produces_thought_delta() {
        let envelopes = map_fixture("session-success.jsonl");
        let has_thought = envelopes.iter().any(|e| e.event_type == EVENT_THOUGHT_DELTA);
        assert!(has_thought, "should have thought.delta events");
    }

    #[test]
    fn success_fixture_produces_tool_call_lifecycle() {
        let envelopes = map_fixture("session-success.jsonl");
        let has_started = envelopes
            .iter()
            .any(|e| e.event_type == EVENT_TOOL_CALL_STARTED);
        let has_completed = envelopes
            .iter()
            .any(|e| e.event_type == EVENT_TOOL_CALL_COMPLETED);
        assert!(has_started, "should have tool_call.started");
        assert!(has_completed, "should have tool_call.completed");
    }

    #[test]
    fn success_fixture_run_completes() {
        let envelopes = map_fixture("session-success.jsonl");
        let last_state = envelopes
            .iter()
            .filter(|e| e.event_type == EVENT_RUN_STATE_CHANGED)
            .last();
        let status = last_state
            .and_then(|e| e.payload.as_ref())
            .and_then(|p| p.get("status"))
            .and_then(|s| s.as_str());
        assert_eq!(status, Some("completed"), "last run.state_changed should be completed");
    }

    #[test]
    fn success_fixture_no_error() {
        let envelopes = map_fixture("session-success.jsonl");
        let has_error = envelopes.iter().any(|e| e.event_type == EVENT_ERROR);
        assert!(!has_error, "success fixture should not produce error events");
    }

    #[test]
    fn failure_fixture_produces_error() {
        let envelopes = map_fixture("session-sample.jsonl");
        let error_ev = envelopes.iter().find(|e| e.event_type == EVENT_ERROR);
        assert!(error_ev.is_some(), "failure fixture should produce an error event");
        let msg = error_ev
            .unwrap()
            .payload
            .as_ref()
            .and_then(|p| p.get("error"))
            .and_then(|e| e.get("message"))
            .and_then(|m| m.as_str())
            .unwrap_or("");
        // Error message must be Chinese and must not contain "Error:".
        assert!(!msg.contains("Error:"), "error message must not contain 'Error:'");
        let has_cjk = msg.chars().any(|c| ('\u{4E00}'..='\u{9FFF}').contains(&c));
        assert!(has_cjk, "error message must be Chinese: {msg}");
    }

    #[test]
    fn failure_fixture_run_status_error() {
        let envelopes = map_fixture("session-sample.jsonl");
        let has_error = envelopes.iter().any(|e| e.event_type == EVENT_ERROR);
        assert!(has_error);
    }

    #[test]
    fn session_started_from_header() {
        let lines = fixture_lines("session-success.jsonl");
        let first = lines.first().unwrap();
        let h = match parse_line(first).unwrap() {
            super::super::events::ParsedLine::Header(h) => h,
            _ => panic!("first line should be header"),
        };
        let mut mapper = EventMapper::new("run-1".to_string());
        let envs = mapper.map_header(&h);
        assert_eq!(envs.len(), 1);
        assert_eq!(envs[0].event_type, EVENT_SESSION_STARTED);
        assert_eq!(envs[0].run_id, "run-1");
    }

    #[test]
    fn session_title_attached_as_metadata() {
        let envelopes = map_fixture("session-success.jsonl");
        // The title event (seq 7) should cause the next envelope to carry
        // session_title in metadata.
        let has_title_meta = envelopes.iter().any(|e| {
            e.metadata
                .as_ref()
                .and_then(|m| m.get("session_title"))
                .is_some()
        });
        assert!(has_title_meta, "session title should appear in metadata");
    }

    #[test]
    fn usage_mapped_to_run_state_changed_metadata() {
        let envelopes = map_fixture("session-success.jsonl");
        let usage_env = envelopes.iter().find(|e| {
            e.event_type == EVENT_RUN_STATE_CHANGED
                && e.metadata
                    .as_ref()
                    .and_then(|m| m.get("usage"))
                    .is_some()
        });
        assert!(usage_env.is_some(), "usage chunk should map to run.state_changed with usage metadata");
        let usage = usage_env
            .unwrap()
            .metadata
            .as_ref()
            .unwrap()
            .get("usage")
            .unwrap();
        let prompt = usage.get("prompt_tokens").and_then(|t| t.as_u64()).unwrap_or(0);
        assert!(prompt > 0, "prompt_tokens should be > 0");
    }

    #[test]
    fn exactly_15_event_types() {
        // Verify the mapper only produces the 15 recognized event types.
        let all_types = [
            EVENT_SESSION_STARTED,
            EVENT_MESSAGE_DELTA,
            EVENT_MESSAGE_COMPLETED,
            EVENT_THOUGHT_DELTA,
            EVENT_TOOL_CALL_STARTED,
            EVENT_TOOL_CALL_DELTA,
            EVENT_TOOL_CALL_COMPLETED,
            EVENT_PLAN_UPDATED,
            EVENT_PHASE_CHANGED,
            EVENT_ELICITATION_REQUESTED,
            EVENT_PERMISSION_REQUESTED,
            EVENT_ARTIFACT_CREATED,
            EVENT_CITATION_RECORDED,
            EVENT_RUN_STATE_CHANGED,
            EVENT_ERROR,
        ];
        for env in map_fixture("session-success.jsonl") {
            assert!(
                all_types.contains(&env.event_type.as_str()),
                "unknown event_type: {}",
                env.event_type
            );
        }
        for env in map_fixture("session-sample.jsonl") {
            assert!(
                all_types.contains(&env.event_type.as_str()),
                "unknown event_type: {}",
                env.event_type
            );
        }
    }

    #[test]
    fn seq_is_monotonic() {
        let envelopes = map_fixture("session-success.jsonl");
        let mut prev = 0u64;
        for e in &envelopes {
            assert!(e.seq >= prev, "seq must be monotonic: {} < {}", e.seq, prev);
            prev = e.seq;
        }
    }

    // ── Guardrail-derived event tests (GRD-11/12/13/14) ─────────────────

    /// Helper: build a synthetic AssistantMessage event with given text.
    fn make_assistant_message(text: &str) -> SessionEvent {
        let raw = json!({
            "type": "assistant_message",
            "time": 1000i64,
            "data": {
                "message": {
                    "id": "msg-test",
                    "content": [{ "type": "text", "text": text }]
                }
            }
        });
        SessionEvent {
            seq: 0,
            time: 1000,
            kind: SessionEventKind::AssistantMessage,
            raw,
        }
    }

    /// Helper: build a synthetic ToolCall event.
    fn make_tool_call(name: &str) -> SessionEvent {
        let raw = json!({
            "type": "tool_call",
            "time": 500i64,
            "data": { "toolCallId": "tc-1", "name": name }
        });
        SessionEvent {
            seq: 0,
            time: 500,
            kind: SessionEventKind::ToolCall,
            raw,
        }
    }

    /// Helper: build a synthetic TurnEnd (completed) event.
    fn make_turn_end() -> SessionEvent {
        let raw = json!({
            "type": "turn_end",
            "time": 2000i64,
            "data": { "reason": { "kind": "completed" } }
        });
        SessionEvent {
            seq: 0,
            time: 2000,
            kind: SessionEventKind::TurnEnd,
            raw,
        }
    }

    #[test]
    fn message_completed_with_citation_emits_citation_recorded() {
        let mut mapper = EventMapper::new("run-grd".to_string());
        let ev = make_assistant_message("根据《民法典》第一百四十三条[verified]");
        let envs = mapper.map(&ev);
        let has_cite = envs.iter().any(|e| e.event_type == EVENT_CITATION_RECORDED);
        assert!(has_cite, "should emit citation.recorded for [verified]");
        let cite_env = envs.iter().find(|e| e.event_type == EVENT_CITATION_RECORDED).unwrap();
        let status = cite_env.payload.as_ref()
            .and_then(|p| p.get("citations"))
            .and_then(|c| c.as_array())
            .and_then(|arr| arr.first())
            .and_then(|c| c.get("status"))
            .and_then(|s| s.as_str());
        assert_eq!(status, Some("verified"));
    }

    #[test]
    fn message_completed_with_clarify_emits_elicitation_requested() {
        let text = "[CLARIFY:\nQ1: 合同类型\n- 买卖\n- 租赁\n]";
        let mut mapper = EventMapper::new("run-grd".to_string());
        let ev = make_assistant_message(text);
        let envs = mapper.map(&ev);
        let has_elicitation = envs.iter().any(|e| e.event_type == EVENT_ELICITATION_REQUESTED);
        assert!(has_elicitation, "should emit elicitation.requested for [CLARIFY:]");
    }

    #[test]
    fn message_completed_with_human_review_adds_metadata() {
        let text = "结论[HUMAN_REVIEW: 合同效力认定]";
        let mut mapper = EventMapper::new("run-grd".to_string());
        let ev = make_assistant_message(text);
        let envs = mapper.map(&ev);
        let completed = envs.iter().find(|e| e.event_type == EVENT_MESSAGE_COMPLETED).unwrap();
        let hr = completed.metadata.as_ref()
            .and_then(|m| m.get("human_review"))
            .and_then(|h| h.as_array());
        assert!(hr.is_some(), "metadata should contain human_review");
        assert_eq!(hr.unwrap().len(), 1);
    }

    #[test]
    fn message_completed_without_human_review_has_no_human_review_metadata() {
        let text = "普通结论，无人审标记。";
        let mut mapper = EventMapper::new("run-grd".to_string());
        let ev = make_assistant_message(text);
        let envs = mapper.map(&ev);
        let completed = envs.iter().find(|e| e.event_type == EVENT_MESSAGE_COMPLETED).unwrap();
        let hr = completed.metadata.as_ref()
            .and_then(|m| m.get("human_review"));
        assert!(hr.is_none(), "no human_review metadata when no marks");
    }

    #[test]
    fn research_performed_true_when_search_tool_called() {
        let mut mapper = EventMapper::new("run-grd".to_string());
        // TurnStart first
        let ts = SessionEvent {
            seq: 0,
            time: 0,
            kind: SessionEventKind::TurnStart,
            raw: json!({ "data": { "turn": 1 } }),
        };
        mapper.map(&ts);
        // Tool call with research tool
        mapper.map(&make_tool_call("web_search"));
        // TurnEnd
        let envs = mapper.map(&make_turn_end());
        let state_env = envs.iter().find(|e| e.event_type == EVENT_RUN_STATE_CHANGED).unwrap();
        let rp = state_env.metadata.as_ref()
            .and_then(|m| m.get("research_performed"))
            .and_then(|r| r.as_bool());
        assert_eq!(rp, Some(true), "research_performed should be true after web_search");
    }

    #[test]
    fn research_performed_false_when_no_search_tool() {
        let mut mapper = EventMapper::new("run-grd".to_string());
        let ts = SessionEvent {
            seq: 0,
            time: 0,
            kind: SessionEventKind::TurnStart,
            raw: json!({ "data": { "turn": 1 } }),
        };
        mapper.map(&ts);
        // Non-research tool
        mapper.map(&make_tool_call("bash"));
        let envs = mapper.map(&make_turn_end());
        let state_env = envs.iter().find(|e| e.event_type == EVENT_RUN_STATE_CHANGED).unwrap();
        let rp = state_env.metadata.as_ref()
            .and_then(|m| m.get("research_performed"))
            .and_then(|r| r.as_bool());
        assert_eq!(rp, Some(false), "research_performed should be false without search tools");
    }
}
