# Platform Contract Fixtures

These fixtures are synthetic, non-sensitive examples for checking the Phase 1
platform contract package. They demonstrate event relationships only; they are
not production logs, legal documents, customer records, or Hermes runtime data.

Each fixture is a top-level object with:

- `fixture_id`: stable identifier for the example.
- `description`: short explanation of the scenario.
- `events`: related `agent_turn`, `route_decision`, `execution_trace`,
  `agent_result`, and `feedback_event` objects.

Relationship checks focus on:

- every event sharing the same `turn_id`;
- `conversation_id` matching between `AgentTurn` and `FeedbackEvent`;
- `result_id` and `feedback_target` connecting `AgentResult` and
  `FeedbackEvent`;
- `ExecutionTrace.artifacts_written` referencing `AgentResult.artifacts`.

Legal-specific sample details must stay inside extension containers such as
`industry_context` or `metadata`. Raw legal payloads and sensitive personal data
must be represented only by references, such as `raw_payload_ref` or artifact
URIs.
