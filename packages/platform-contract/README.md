# InkStatute Platform Contract

`inkstatute-platform-contract` is the pure definition package for the InkStatute V2 platform contract layer.

It exports JSON Schema files plus Python bindings for the five platform event contracts:

- `AgentTurn`
- `AgentResult`
- `FeedbackEvent`
- `ExecutionTrace`
- `RouteDecision`

The package contains no Hermes imports, no service process, no persistence layer, and no network access. It is intended to be safe for downstream packages to import as a stable contract surface without starting or depending on Hermes runtime behavior.

The contract is industry-neutral. Legal-specific fields must stay in `industry_context` or `metadata` containers rather than becoming top-level required platform fields.
