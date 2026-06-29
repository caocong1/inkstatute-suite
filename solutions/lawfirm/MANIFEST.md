# Lawfirm Solution Pack

Backend-neutral solution pack for the InkStatute lawyer assistant.

This pack exists as a *solution*, not platform core. It loads through
`DefaultSolutionLoader`, validates against `ManifestValidator`, and materializes
to a registered backend (currently `hermes`) via `LawfirmHermesMaterializer`.

## Neutral format mapping

| Neutral field     | Hermes profile equivalent (derived, not stored) |
|-------------------|------------------------------------------------|
| `solution_id`     | profile directory name                         |
| `version`         | profile version metadata                       |
| `persona_ref`     | `SOUL.md` (template)                           |
| `skills[]`        | one `SKILL.md.template` per descriptor         |
| `mcp[]`           | `tools.json`                                   |
| `output_policy`   | output boundary overlay                        |
| `eval[]`          | fixture paths                                  |
| `secret_templates`| names only; values supplied at runtime         |
| `industry_context`| profile metadata block                         |

## Sanitization guarantees

The materializer never bundles:
- Secret values (only `secret_ref` names from `manifest.secret_templates`).
- Customer documents, raw legal payloads, or callback bodies.
- Logs, databases, or media files (binary extensions refused).
- `confidential_artifact` strings.

The bundle's `SANITIZATION_REPORT.md` records `refused_items=[]` for a clean
materialization and aborts with a refusal Issue if any pattern triggers.

## Extending skills

Add a new descriptor to `manifest.skills[]`. The next materialization refreshes
the bundle with an additional `SKILL.md.template`. No Hermes runtime change is
required to declare a new skill; activating it in a live Hermes profile still
requires a Hermes-side onboarding step that is out of scope for this pack.