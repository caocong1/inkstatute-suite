/**
 * GATE-13: update-rollback — bad packages must not move the current pointer.
 *
 * Runs the Rust integration tests in update_rollback_test.rs (all #[ignore]d
 * because they need network access to npm). The tests verify:
 *   A) Bad integrity → assemble fails, current unchanged, bad dir cleaned
 *   B) Bad smoke → smoke fails, current unchanged, v1 still intact
 *   C) Success path → current moves, previous version retained
 *   D) Rollback → current switches to previous version
 */
import { execSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const REPO_ROOT = resolve(import.meta.dirname, "..", "..", "..");
const CARGO_TOML = resolve(REPO_ROOT, "apps/desktop/src-tauri/Cargo.toml");
const TEST_FILE = resolve(REPO_ROOT, "apps/desktop/src-tauri/tests/update_rollback_test.rs");
const UPDATER_PATH = resolve(REPO_ROOT, "apps/desktop/src-tauri/src/engine/updater.rs");

const checks = [];
const fails = [];

function check(name, fn) {
  try {
    fn();
    checks.push(name);
    console.log(`[PASS] ${name}`);
  } catch (e) {
    fails.push({ name, error: e.message });
    console.error(`[FAIL] ${name}`);
    console.error(`       ${e.message}`);
  }
}

// Pre-flight: the test file must exist.
check("GATE-13.0: update_rollback_test.rs exists", () => {
  if (!existsSync(TEST_FILE)) {
    throw new Error(`Test file not found: ${TEST_FILE}`);
  }
});

// Pre-flight: the invariant comment must be in updater.rs.
check("GATE-13.1: invariant comment in updater.rs", () => {
  const text = readFileSync(UPDATER_PATH, "utf8");
  if (!text.includes("Invariant") || !text.includes("current") || !text.includes("smoke")) {
    throw new Error("updater.rs must document the current-pointer invariant");
  }
});

// Static check: write_current only appears after smoke success in updater.rs.
check("GATE-13.2: write_current only after smoke in updater.rs", () => {
  const text = readFileSync(UPDATER_PATH, "utf8");
  const lines = text.split("\n");
  const writeCurrentLines = [];
  const smokeOkLines = [];
  lines.forEach((line, i) => {
    if (line.includes("write_current")) writeCurrentLines.push(i + 1);
    if (line.includes("smoke.ok")) smokeOkLines.push(i + 1);
  });
  if (writeCurrentLines.length === 0) {
    throw new Error("No write_current calls found in updater.rs");
  }
  // Each write_current call in the apply() and rollback() methods must be
  // preceded by a smoke.ok check within ~30 lines.
  for (const wcLine of writeCurrentLines) {
    const hasSmokeBefore = smokeOkLines.some(
      (sl) => sl < wcLine && wcLine - sl < 40
    );
    if (!hasSmokeBefore) {
      throw new Error(
        `write_current at line ${wcLine} has no smoke.ok check within 40 lines before it`
      );
    }
  }
});

// Run the integration tests (network-required, so they're #[ignore]d).
check("GATE-13.3: cargo test update_rollback (integration)", () => {
  try {
    execSync(
      `cargo test --manifest-path "${CARGO_TOML}" --test update_rollback_test -- --ignored --test-threads=1`,
      { stdio: "pipe", cwd: REPO_ROOT, timeout: 300000 }
    );
  } catch (e) {
    const stderr = e.stderr ? e.stderr.toString() : e.message;
    // Extract just the test result line for a cleaner error.
    const resultLine = stderr.split("\n").find((l) => l.includes("test result"));
    throw new Error(resultLine || stderr.slice(0, 500));
  }
});

// Summary
console.log();
if (fails.length > 0) {
  console.error(`update-rollback: ${checks.length} passed, ${fails.length} failed`);
  process.exit(1);
} else {
  console.log(`update-rollback: ${checks.length} passed, 0 failed`);
}
