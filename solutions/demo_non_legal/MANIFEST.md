# Demo Non-Legal Solution Pack

Backend-neutral demo solution pack for an education-domain assistant.

This pack exists to **prove the contracts are industry-neutral**. It uses the
same `DefaultSolutionLoader`, the same validator, the same materializer-
registry contract, and the same sanitize module as `solutions/lawfirm/`.
Only the manifest JSON, the industry_context key, and a small materializer
class change.

## What this proves

A non-lawyer pack runs through the platform contracts unchanged:
- `DefaultSolutionLoader.validate(manifest)` returns zero Issues.
- A registered `DemoNonLegalHermesMaterializer.materialize(solution, output_dir)`
  produces a sanitized 4-file bundle.
- The same `MaterializerRegistry` holds both `lawfirm` and `demo_non_legal`
  materializers side by side.
- The same `DefaultSolutionLoader` instance handles both solutions in
  sequence without any per-solution reconfiguration.

## Neutral format mapping

The structure mirrors `solutions/lawfirm/manifest.json` exactly, except:
- `solution_id` is `demo_non_legal`.
- `industry_context` key is `education_domain` (NOT `legal_domain`).
- `output_policy.allow_legal_conclusions` is `false`.
- `mcp[]` lists education-domain tools with secret_ref names only.

## Adding new non-legal packs

Future packs (IT-ops, finance, customer-support, ...) follow the same
template. Each new pack is a single `solutions/<id>/` directory with:
- `manifest.json` (neutral fields only).
- `src/inkstatute_solutions_<id>/hermes_materializer.py` (MaterializerFn shape).
- `tests/test_<id>_solution.py`.

No platform-core change is needed.