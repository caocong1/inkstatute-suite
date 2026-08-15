//! Phase 124 / Plan 124-03: event mapper integration tests + GATE-12 fixture dump.
//!
//! `dump_envelopes_from_fixture` feeds `tests/fixtures/session-success.jsonl`
//! through `EventMapper` and writes the resulting envelopes to
//! `tests/fixtures/expected-envelopes.json`. This file is then consumed by
//! `scripts/gates/v5/event-mapping.mjs` which reduces the envelopes through
//! `packages/ui-core/src/event-reducer.ts` and asserts the `RenderState` is
//! correct.
//!
//! `#[ignore]` — run with `cargo test -- --ignored dump_envelopes_from_fixture`
//! to regenerate the fixture. The committed `expected-envelopes.json` is the
//! gate input.

use std::fs;
use std::path::PathBuf;

use inkstatute_desktop_lib::engine::events::{parse_line, ParsedLine};
use inkstatute_desktop_lib::engine::mapper::{EventMapper, RunEventEnvelope};

fn manifest_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

#[ignore = "regenerates expected-envelopes.json fixture"]
#[tokio::test]
async fn dump_envelopes_from_fixture() {
    let fixture_path = manifest_dir().join("tests/fixtures/session-success.jsonl");
    let output_path = manifest_dir().join("tests/fixtures/expected-envelopes.json");

    let text = fs::read_to_string(&fixture_path).expect("read session-success.jsonl");
    let mut mapper = EventMapper::new("run-gate-12".to_string());
    let mut envelopes: Vec<RunEventEnvelope> = Vec::new();

    for line in text.lines() {
        match parse_line(line).expect("parse line") {
            ParsedLine::Header(h) => envelopes.extend(mapper.map_header(&h)),
            ParsedLine::Event(ev) => envelopes.extend(mapper.map(&ev)),
            ParsedLine::Ignored => {}
        }
    }

    let json = serde_json::to_string_pretty(&envelopes).expect("serialize envelopes");
    fs::write(&output_path, json).expect("write expected-envelopes.json");
    println!(
        "Wrote {} envelopes to {}",
        envelopes.len(),
        output_path.display()
    );
}

#[tokio::test]
async fn expected_envelopes_fixture_exists() {
    let path = manifest_dir().join("tests/fixtures/expected-envelopes.json");
    assert!(
        path.is_file(),
        "expected-envelopes.json must exist — run `cargo test -- --ignored dump_envelopes_from_fixture` to regenerate"
    );
    let text = fs::read_to_string(&path).expect("read expected-envelopes.json");
    let envelopes: Vec<RunEventEnvelope> =
        serde_json::from_str(&text).expect("parse expected-envelopes.json");
    assert!(
        !envelopes.is_empty(),
        "expected-envelopes.json must contain at least one envelope"
    );
    // Verify all event types are within the 15-type vocabulary.
    let valid_types = [
        "session.started",
        "message.delta",
        "message.completed",
        "thought.delta",
        "tool_call.started",
        "tool_call.delta",
        "tool_call.completed",
        "plan.updated",
        "phase.changed",
        "elicitation.requested",
        "permission.requested",
        "artifact.created",
        "citation.recorded",
        "run.state_changed",
        "error",
    ];
    for env in &envelopes {
        assert!(
            valid_types.contains(&env.event_type.as_str()),
            "invalid event_type in fixture: {}",
            env.event_type
        );
    }
}
