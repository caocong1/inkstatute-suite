# Phase 128 Deferred Items

## Found during 128-01, out of scope for this plan

- **`engine::supervisor` test helper leaks `INKSTATUTE_TEST_API_KEY` across the test binary.**
  `apps/desktop/src-tauri/src/engine/supervisor.rs:337` (`spawn_supervisor` test helper) calls
  `env::set_var("INKSTATUTE_TEST_API_KEY", "sk-test-no-real")` and never calls `env::remove_var`.
  Since all unit tests in this crate's lib share one test binary process, once any supervisor
  spawn test runs, every provider looks "configured" for the rest of that `cargo test` invocation
  (`load_key` checks this var first, unconditionally, in debug builds). Not fixed here — out of
  scope for 128-01 (different file, pre-existing, not in this plan's `files_modified`). Worked
  around in `credentials.rs`'s new tests by extracting the branch-selection and env-pair-assembly
  logic into pure functions tested with synthetic input instead of the real credential store (see
  `classify_review_capability` / `provider_env_pairs`), rather than depending on this var's
  absence. A future cleanup of `supervisor.rs`'s test helper (add the matching `remove_var`, or a
  `Drop` guard) would let *any* test in the crate safely assert "provider X is unconfigured" via
  the real store again.

- **12 pre-existing `cargo clippy --lib -- -D warnings` findings**, all in files untouched by this
  plan (`engine/supervisor.rs`, `engine/tailer.rs`, `engine/updater.rs`) — `std::io::Error::other`
  suggestions, a `while-let-loop` simplification, an `Iterator::last` on a `DoubleEndedIterator`.
  Confirmed via `git stash` that the count is identical with and without this plan's changes.
  clippy is not part of `scripts/gates/v5/run-gates.mjs`, so these do not block anything today.

- **Phase 127 has no `SUMMARY.md` files** in `.planning/phases/127-packaging-three-layer-updates/`
  despite STATE.md/PROJECT.md recording it as complete. Not investigated or fixed — unrelated to
  128-01's file scope.
