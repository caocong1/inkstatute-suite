//! DSH session log event model.
//!
//! Maps 1:1 to the NDJSON lines written by the engine's persistence plugin to
//! `<sessionsRoot>/<cwd-dir>/<sessionId>/session.jsonl`. The first line is a
//! `SessionHeader` (no `seq`); every subsequent line is a `SessionEvent` with a
//! monotonically increasing `seq`.
//!
//! Unknown `type` values are parsed into [`SessionEventKind::Other`] rather than
//! rejected — DSH is a pre-release and new event kinds must never crash the
//! tailer (see Phase 124 CONTEXT risk #3 and the binding decision that the
//! observation plane reads files, not a plugin we maintain).

use serde::Deserialize;
use serde_json::Value;

/// First line of `session.jsonl` — has no `seq` field.
#[derive(Debug, Clone, Deserialize)]
pub struct SessionHeader {
    pub id: String,
    pub version: u32,
    #[serde(rename = "createdAt")]
    pub created_at: i64,
    #[serde(default)]
    pub cwd: Option<String>,
    #[serde(default, rename = "delegationDepth")]
    pub delegation_depth: u32,
    #[serde(default, rename = "agentPreset")]
    pub agent_preset: Option<String>,
}

/// Every line after the header.
#[derive(Debug, Clone)]
pub struct SessionEvent {
    pub seq: u64,
    pub time: i64,
    pub kind: SessionEventKind,
    /// Original JSON kept verbatim — the mapper pulls fields on demand.
    pub raw: Value,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SessionEventKind {
    TurnStart,
    TurnEnd,
    StepStart,
    StepEnd,
    UserMessage,
    AssistantMessage,
    AssistantChunk,
    ToolCall,
    ToolResult,
    ToolCodeDispatch,
    ToolCodeDispatchStart,
    SessionTitle,
    SessionCreated,
    SessionDisposed,
    SessionFlush,
    SessionEndSeed,
    RequestHeader,
    RequestContext,
    AgentInboxSpliced,
    Other(String),
}

impl SessionEventKind {
    /// Classify a raw `type` string from a log line.
    pub fn from_type_str(t: &str) -> Self {
        match t {
            "turn/start" => Self::TurnStart,
            "turn/end" => Self::TurnEnd,
            "step/start" => Self::StepStart,
            "step/end" => Self::StepEnd,
            "user/message" => Self::UserMessage,
            "assistant/message" => Self::AssistantMessage,
            "assistant/chunk" => Self::AssistantChunk,
            "tool/call" => Self::ToolCall,
            "tool/result" => Self::ToolResult,
            "tool/code-dispatch" => Self::ToolCodeDispatch,
            "tool/code-dispatch-start" => Self::ToolCodeDispatchStart,
            "session/title" => Self::SessionTitle,
            "session/created" => Self::SessionCreated,
            "session/disposed" => Self::SessionDisposed,
            "session/flush" => Self::SessionFlush,
            "session/end-seed" => Self::SessionEndSeed,
            "request/header" => Self::RequestHeader,
            "request/context" => Self::RequestContext,
            "agent/inbox/spliced" => Self::AgentInboxSpliced,
            other => Self::Other(other.to_string()),
        }
    }
}

/// The `data.chunk` union carried by `assistant/chunk` events
/// (source: `packages/llm/llm/src/types.ts:291`).
#[derive(Debug, Clone)]
pub enum AssistantChunk {
    BlockStart {
        index: u32,
        block_type: String,
    },
    TextDelta {
        index: u32,
        text: String,
    },
    ReasoningDelta {
        index: u32,
        text: String,
    },
    ToolCallDelta {
        index: u32,
        id: String,
        name: Option<String>,
        arguments_delta: String,
    },
    BlockEnd {
        index: u32,
        block: Value,
    },
    Usage {
        usage: Value,
    },
    Finish {
        reason: Value,
    },
    Unknown(Value),
}

impl AssistantChunk {
    /// Parse the `data.chunk` object of an `assistant/chunk` event.
    pub fn from_value(chunk: &Value) -> Self {
        let chunk_type = chunk.get("type").and_then(|v| v.as_str()).unwrap_or("");
        let index = chunk.get("index").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
        match chunk_type {
            "block-start" => AssistantChunk::BlockStart {
                index,
                block_type: chunk
                    .get("blockType")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string(),
            },
            "text-delta" => AssistantChunk::TextDelta {
                index,
                text: chunk
                    .get("text")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string(),
            },
            "reasoning-delta" => AssistantChunk::ReasoningDelta {
                index,
                text: chunk
                    .get("text")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string(),
            },
            "tool-call-delta" => AssistantChunk::ToolCallDelta {
                index,
                id: chunk
                    .get("id")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string(),
                name: chunk
                    .get("name")
                    .and_then(|v| v.as_str())
                    .map(|s| s.to_string()),
                arguments_delta: chunk
                    .get("argumentsDelta")
                    .and_then(|v| v.as_str())
                    .or_else(|| chunk.get("arguments_delta").and_then(|v| v.as_str()))
                    .unwrap_or("")
                    .to_string(),
            },
            "block-end" => AssistantChunk::BlockEnd {
                index,
                block: chunk.get("block").cloned().unwrap_or(Value::Null),
            },
            "usage" => AssistantChunk::Usage {
                usage: chunk.get("usage").cloned().unwrap_or(Value::Null),
            },
            "finish" => AssistantChunk::Finish {
                reason: chunk.get("reason").cloned().unwrap_or(Value::Null),
            },
            _ => AssistantChunk::Unknown(chunk.clone()),
        }
    }
}

/// What [`parse_line`] produced from a single NDJSON line.
#[derive(Debug, Clone)]
pub enum ParsedLine {
    Header(SessionHeader),
    Event(SessionEvent),
    /// A line that is valid JSON but is neither a recognizable header nor an
    /// event with a `seq` field. The tailer drops these silently.
    Ignored,
}

#[derive(Debug, thiserror::Error)]
pub enum EventParseError {
    #[error("line is not valid JSON: {0}")]
    InvalidJson(String),
    #[error("header line missing required field: {0}")]
    BadHeader(String),
    #[error("event line missing required field: {0}")]
    BadEvent(String),
}

/// Parse one NDJSON line from `session.jsonl`.
///
/// - The first line of a file has `type: "session"` (no `seq`) → [`ParsedLine::Header`].
/// - Any line with a numeric `seq` and a `type` → [`ParsedLine::Event`].
/// - Anything else (non-JSON, JSON without `seq`/`type`) → [`ParsedLine::Ignored`]
///   for events, or an error only when a line claims to be a header but is
///   malformed. Non-JSON lines are [`ParsedLine::Ignored`] so the tailer can
///   keep going without aborting.
pub fn parse_line(line: &str) -> Result<ParsedLine, EventParseError> {
    let trimmed = line.trim();
    if trimmed.is_empty() {
        return Ok(ParsedLine::Ignored);
    }
    let value: Value = match serde_json::from_str(trimmed) {
        Ok(v) => v,
        Err(_) => return Ok(ParsedLine::Ignored),
    };

    let type_str = value.get("type").and_then(|v| v.as_str()).unwrap_or("");

    if type_str == "session" {
        let header: SessionHeader = serde_json::from_value(value.clone()).map_err(|e| {
            EventParseError::BadHeader(format!("session header deserialize failed: {e}"))
        })?;
        return Ok(ParsedLine::Header(header));
    }

    let seq = match value.get("seq").and_then(|v| v.as_u64()) {
        Some(s) => s,
        None => return Ok(ParsedLine::Ignored),
    };
    let time = value
        .get("time")
        .and_then(|v| v.as_i64())
        .unwrap_or(0);
    let kind = SessionEventKind::from_type_str(type_str);

    Ok(ParsedLine::Event(SessionEvent {
        seq,
        time,
        kind,
        raw: value,
    }))
}

impl SessionEvent {
    /// If this is an `assistant/chunk` event, return its parsed chunk.
    pub fn assistant_chunk(&self) -> Option<AssistantChunk> {
        if !matches!(self.kind, SessionEventKind::AssistantChunk) {
            return None;
        }
        let chunk = self.raw.get("data")?.get("chunk")?;
        Some(AssistantChunk::from_value(chunk))
    }

    /// `true` only when this is a `user/message` event whose
    /// `data.source.kind == "user"`.
    ///
    /// DSH splices runtime context snapshots and skill listings into the inbox
    /// as `user/message` events (seq 5/6 in the measured sample). Rendering
    /// those would dump a system reminder into the conversation. The
    /// `data.source.kind == "user"` discriminator is the only reliable filter
    /// — system-injected messages either omit `source` or carry a different
    /// `kind`.
    pub fn is_real_user_message(&self) -> bool {
        if !matches!(self.kind, SessionEventKind::UserMessage) {
            return false;
        }
        self.raw
            .get("data")
            .and_then(|d| d.get("source"))
            .and_then(|s| s.get("kind"))
            .and_then(|k| k.as_str())
            == Some("user")
    }

    /// Concatenate `data.content[].text` for a real user message.
    pub fn text_of_user_message(&self) -> Option<String> {
        if !matches!(self.kind, SessionEventKind::UserMessage) {
            return None;
        }
        let content = self
            .raw
            .get("data")
            .and_then(|d| d.get("content"))
            .and_then(|c| c.as_array())?;
        let mut buf = String::new();
        for item in content {
            if item.get("type").and_then(|t| t.as_str()) == Some("text") {
                if let Some(text) = item.get("text").and_then(|t| t.as_str()) {
                    buf.push_str(text);
                }
            }
        }
        Some(buf)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture_path() -> std::path::PathBuf {
        let manifest = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        manifest.join("tests/fixtures/session-sample.jsonl")
    }

    fn read_fixture_lines() -> Vec<String> {
        let text = std::fs::read_to_string(fixture_path()).expect("read session-sample.jsonl");
        text.lines().map(|l| l.to_string()).collect()
    }

    #[test]
    fn sample_parses_fully() {
        let lines = read_fixture_lines();
        assert!(lines.len() >= 14, "sample must have at least 14 lines");
        let mut header_count = 0;
        let mut event_count = 0;
        let mut ignored_count = 0;
        for line in &lines {
            match parse_line(line).expect("parse line") {
                ParsedLine::Header(_) => header_count += 1,
                ParsedLine::Event(_) => event_count += 1,
                ParsedLine::Ignored => ignored_count += 1,
            }
        }
        assert_eq!(header_count, 1, "exactly one header line");
        assert!(
            event_count >= 13,
            "expected at least 13 events, got {event_count}"
        );
        // No line in the measured sample should be ignored.
        assert_eq!(ignored_count, 0, "no ignored lines in sample");
    }

    #[test]
    fn exactly_one_real_user_message() {
        let lines = read_fixture_lines();
        let mut real = 0;
        let mut user_message_kinds = 0;
        for line in &lines {
            if let ParsedLine::Event(ev) = parse_line(line).expect("parse line") {
                if matches!(ev.kind, SessionEventKind::UserMessage) {
                    user_message_kinds += 1;
                    if ev.is_real_user_message() {
                        real += 1;
                        // The real user message is seq 4 in the sample.
                        assert_eq!(ev.seq, 4, "real user message should be seq 4");
                    }
                }
            }
        }
        assert!(
            user_message_kinds >= 3,
            "sample must contain the 3 user/message lines (seq 4/5/6)"
        );
        assert_eq!(real, 1, "exactly one real user message");
    }

    #[test]
    fn seq_5_and_6_are_not_real_user_messages() {
        let lines = read_fixture_lines();
        for line in &lines {
            if let ParsedLine::Event(ev) = parse_line(line).expect("parse line") {
                if ev.seq == 5 || ev.seq == 6 {
                    assert!(
                        matches!(ev.kind, SessionEventKind::UserMessage),
                        "seq {} should be user/message",
                        ev.seq
                    );
                    assert!(
                        !ev.is_real_user_message(),
                        "seq {} is system-injected and must not be a real user message",
                        ev.seq
                    );
                }
            }
        }
    }

    #[test]
    fn unknown_type_goes_to_other() {
        let line = r#"{"type":"some/future/event","seq":99,"time":1,"data":{}}"#;
        let ev = match parse_line(line).unwrap() {
            ParsedLine::Event(ev) => ev,
            other => panic!("expected event, got {other:?}"),
        };
        assert_eq!(ev.kind, SessionEventKind::Other("some/future/event".to_string()));
        assert_eq!(ev.seq, 99);
    }

    #[test]
    fn non_json_line_is_ignored() {
        let line = "this is not json at all";
        assert!(matches!(parse_line(line).unwrap(), ParsedLine::Ignored));
    }

    #[test]
    fn empty_line_is_ignored() {
        assert!(matches!(parse_line("   ").unwrap(), ParsedLine::Ignored));
    }

    #[test]
    fn header_parses_fields() {
        let line = r#"{"type":"session","version":0,"id":"abc","createdAt":1786767750643,"cwd":"/abs/ws","delegationDepth":0}"#;
        let h = match parse_line(line).unwrap() {
            ParsedLine::Header(h) => h,
            other => panic!("expected header, got {other:?}"),
        };
        assert_eq!(h.id, "abc");
        assert_eq!(h.version, 0);
        assert_eq!(h.created_at, 1786767750643);
        assert_eq!(h.cwd.as_deref(), Some("/abs/ws"));
        assert_eq!(h.delegation_depth, 0);
        assert!(h.agent_preset.is_none());
    }

    #[test]
    fn assistant_chunk_seven_types() {
        let cases: &[(&str, &str)] = &[
            ("block-start", r#"{"type":"block-start","index":0,"blockType":"text"}"#),
            ("text-delta", r#"{"type":"text-delta","index":0,"text":"hi"}"#),
            (
                "reasoning-delta",
                r#"{"type":"reasoning-delta","index":0,"text":"thinking"}"#,
            ),
            (
                "tool-call-delta",
                r#"{"type":"tool-call-delta","index":1,"id":"tc1","name":"read","argumentsDelta":"{\"a\""}"#,
            ),
            (
                "block-end",
                r#"{"type":"block-end","index":0,"block":{"type":"text","text":"hi"}}"#,
            ),
            ("usage", r#"{"type":"usage","usage":{"prompt_tokens":10}}"#),
            ("finish", r#"{"type":"finish","reason":{"kind":"stop"}}"#),
        ];
        for (label, chunk_json) in cases {
            let chunk: Value = serde_json::from_str(chunk_json).unwrap();
            let parsed = AssistantChunk::from_value(&chunk);
            // Just confirm it parses into the expected variant by debug format.
            let dbg = format!("{parsed:?}");
            match *label {
                "block-start" => assert!(dbg.contains("BlockStart"), "{label}: {dbg}"),
                "text-delta" => assert!(dbg.contains("TextDelta"), "{label}: {dbg}"),
                "reasoning-delta" => assert!(dbg.contains("ReasoningDelta"), "{label}: {dbg}"),
                "tool-call-delta" => assert!(dbg.contains("ToolCallDelta"), "{label}: {dbg}"),
                "block-end" => assert!(dbg.contains("BlockEnd"), "{label}: {dbg}"),
                "usage" => assert!(dbg.contains("Usage"), "{label}: {dbg}"),
                "finish" => assert!(dbg.contains("Finish"), "{label}: {dbg}"),
                _ => unreachable!(),
            }
        }
        // Unknown chunk type.
        let unknown: Value = serde_json::from_str(r#"{"type":"future-chunk"}"#).unwrap();
        assert!(matches!(
            AssistantChunk::from_value(&unknown),
            AssistantChunk::Unknown(_)
        ));
    }

    #[test]
    fn assistant_chunk_extraction_from_event() {
        let line = r#"{"type":"assistant/chunk","seq":10,"time":1,"data":{"turn":1,"step":1,"chunk":{"type":"text-delta","index":0,"text":"hello"}}}"#;
        let ev = match parse_line(line).unwrap() {
            ParsedLine::Event(ev) => ev,
            other => panic!("expected event, got {other:?}"),
        };
        let chunk = ev.assistant_chunk().expect("chunk");
        match chunk {
            AssistantChunk::TextDelta { index, text } => {
                assert_eq!(index, 0);
                assert_eq!(text, "hello");
            }
            other => panic!("expected TextDelta, got {other:?}"),
        }
    }

    #[test]
    fn text_of_user_message_concatenates() {
        let line = r#"{"type":"user/message","seq":4,"time":1,"data":{"content":[{"type":"text","text":"hello "},{"type":"text","text":"world"}],"role":"user","id":"m1","source":{"kind":"user"}}}"#;
        let ev = match parse_line(line).unwrap() {
            ParsedLine::Event(ev) => ev,
            other => panic!("expected event, got {other:?}"),
        };
        assert!(ev.is_real_user_message());
        assert_eq!(ev.text_of_user_message().as_deref(), Some("hello world"));
    }

    #[test]
    fn user_message_without_source_is_not_real() {
        let line = r#"{"type":"user/message","seq":5,"time":1,"data":{"content":[{"type":"text","text":"ctx"}],"role":"user","id":"m2"}}"#;
        let ev = match parse_line(line).unwrap() {
            ParsedLine::Event(ev) => ev,
            other => panic!("expected event, got {other:?}"),
        };
        assert!(!ev.is_real_user_message());
    }
}
