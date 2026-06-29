# inkstatute-solution-loader

Default-off `SolutionLoader` library implementing
`platform_runtime.protocols.SolutionLoader` (validate / load / materialize_for).

## Boundaries

- Default-OFF behind `INKSTATUTE_SOLUTION_LOADER_ENABLED` (case-insensitive: `1`, `true`, `yes`, `on`).
- Library-only: no server, no channel, no backend-adapter behavior.
- Writes files only inside the caller-provided `output_dir` (path-traversal guard).
- Solution manifests are validated against a strict platform-level rule set; legal-specific
  fields live in `industry_context`, never as top-level keys.

## Bundled solutions

This package is the orchestration layer; concrete solutions live in
`solutions/<solution_id>/`. The reference materialization target is
`solutions/lawfirm/` (see also `solutions/demo_non_legal/`).

## Public surface

```
from inkstatute_solution_loader import (
    DefaultSolutionLoader,
    DefaultSolutionLoaderConfig,
    SolutionLoaderFeatureFlags,
    load_solution_loader_feature_flags,
    MaterializerRegistry,
    MaterializerSideEffects,
    ManifestValidator,
    ManifestValidatorIssue,
)
```

## Operator env

- `INKSTATUTE_SOLUTION_LOADER_ENABLED` — enables the loader; absent ⇒ disabled.
- This package ships NO live bundle promotion. All materialization is opt-in and
  caller-provided output-dir.

## Tests

```bash
PYTHONPATH=packages/solution-loader/src:packages/platform-runtime/src:packages/platform-contract/src:packages/backends/hermes/src \
  python -m unittest packages.solution_loader.tests.test_solution_loader_library -v
```