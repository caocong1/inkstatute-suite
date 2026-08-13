#!/usr/bin/env python3
"""V4 gate runner: dart analyze + flutter test + engine manifest + mock E2E + meta-test.

Gates:
  1. dart-analyze    -- dart analyze apps/flutter_app/ (zero issues)
  2. flutter-test    -- flutter test (from apps/flutter_app/) (all tests pass)
  3. engine-manifest -- engines/dsh-pin.txt + engines/acp.cordis.yml validation
                       (+ engine-manifest.json if it exists, skip if not)
  4. mock-e2e        -- flutter test packages/acp_client/ (mock ACP E2E smoke)
  5. meta-test       -- every Dart lib/ dir has corresponding test/ coverage (GATE-02)
  6. docx-golden     -- placeholder (skips in Phase 112, active in Phase 118)

Usage:
  python3 scripts/run_v4_gates.py                    # Run all gates
  python3 scripts/run_v4_gates.py --check meta-test  # Run single gate
  python3 scripts/run_v4_gates.py --list             # List gate names

Exit codes:
  0 = all gates passed (or skipped)
  1 = any gate failed
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class GateResult(NamedTuple):
    """Result of a single gate execution."""
    name: str
    passed: bool
    skipped: bool
    message: str
    details: str


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Gate names in execution order
GATE_NAMES = [
    "dart-analyze",
    "flutter-test",
    "engine-manifest",
    "mock-e2e",
    "meta-test",
    "docx-golden",
]

# Gates selectable via --check
CHECK_CHOICES = [
    "dart-analyze",
    "flutter-test",
    "engine-manifest",
    "mock-e2e",
    "meta-test",
]

# Frozen directories (LEG-01) -- never in gate scope
FROZEN_DIRS = [
    "services/gateway",
    "services/wecom-service",
    "services/qqbot-service",
    "services/arena-service",
    "packages/agent-core",
    "packages/arena-engine",
    "packages/acp-client",
    "packages/ui-core",
    "apps/web",
    "apps/desktop",
]

# Required fields in engine-manifest.json
MANIFEST_REQUIRED_FIELDS = [
    "engine_version",
    "dsh_commit",
    "node_version",
    "sha256",
    "built_at",
]


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for --check and --list options."""
    parser = argparse.ArgumentParser(
        description=(
            "V4 gate runner: dart analyze + flutter test + engine manifest "
            "+ mock E2E + meta-test."
        ),
    )
    parser.add_argument(
        "--check",
        choices=CHECK_CHOICES,
        default=None,
        help="Run a single gate (default: run all gates).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List gate names and exit.",
    )
    return parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_binary(name: str) -> str | None:
    """Find a binary on PATH. Returns the path or None."""
    return shutil.which(name)


# ---------------------------------------------------------------------------
# Gate 1: dart-analyze
# ---------------------------------------------------------------------------

def gate_dart_analyze(repo_root: Path) -> GateResult:
    """Gate 1: dart analyze apps/flutter_app/ -- exit 0 required."""
    dart = _find_binary("dart")
    if dart is None:
        return GateResult(
            name="dart-analyze",
            passed=False,
            skipped=False,
            message="dart binary not found on PATH",
            details="Install Flutter SDK and ensure dart is on PATH.",
        )
    flutter_app = repo_root / "apps" / "flutter_app"
    if not flutter_app.exists():
        return GateResult(
            name="dart-analyze",
            passed=False,
            skipped=False,
            message=f"apps/flutter_app not found at {flutter_app}",
            details="",
        )
    completed = subprocess.run(
        [dart, "analyze", "apps/flutter_app"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return GateResult(
            name="dart-analyze",
            passed=True,
            skipped=False,
            message="No issues found",
            details=completed.stdout.strip(),
        )
    return GateResult(
        name="dart-analyze",
        passed=False,
        skipped=False,
        message=f"dart analyze failed (exit {completed.returncode})",
        details=completed.stdout + completed.stderr,
    )


# ---------------------------------------------------------------------------
# Gate 2: flutter-test
# ---------------------------------------------------------------------------

def gate_flutter_test(repo_root: Path) -> GateResult:
    """Gate 2: flutter test (from apps/flutter_app/) -- exit 0 required."""
    flutter = _find_binary("flutter")
    if flutter is None:
        return GateResult(
            name="flutter-test",
            passed=False,
            skipped=False,
            message="flutter binary not found on PATH",
            details="Install Flutter SDK and ensure flutter is on PATH.",
        )
    flutter_app = repo_root / "apps" / "flutter_app"
    if not flutter_app.exists():
        return GateResult(
            name="flutter-test",
            passed=False,
            skipped=False,
            message=f"apps/flutter_app not found at {flutter_app}",
            details="",
        )
    completed = subprocess.run(
        [flutter, "test"],
        cwd=flutter_app,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return GateResult(
            name="flutter-test",
            passed=True,
            skipped=False,
            message="All tests passed",
            details=completed.stdout.strip(),
        )
    return GateResult(
        name="flutter-test",
        passed=False,
        skipped=False,
        message=f"flutter test failed (exit {completed.returncode})",
        details=completed.stdout + completed.stderr,
    )


# ---------------------------------------------------------------------------
# Gate 3: engine-manifest
# ---------------------------------------------------------------------------

def validate_pin_file(pin_file: Path) -> tuple[bool, str]:
    """Validate engines/dsh-pin.txt has dsh_commit and node_version fields.

    Returns (True, message) if valid, (False, error_message) otherwise.
    """
    if not pin_file.exists():
        return False, f"Pin file not found: {pin_file}"
    content = pin_file.read_text()
    has_commit = re.search(r"^dsh_commit=\S+", content, re.MULTILINE) is not None
    has_node = re.search(r"^node_version=\S+", content, re.MULTILINE) is not None
    if not has_commit:
        return False, "dsh-pin.txt missing dsh_commit field"
    if not has_node:
        return False, "dsh-pin.txt missing node_version field"
    return True, "Pin file valid (dsh_commit + node_version present)"


def validate_cordis_config(cordis_file: Path) -> tuple[bool, str]:
    """Validate engines/acp.cordis.yml has approval.policy: ask.

    Returns (True, message) if valid, (False, error_message) otherwise.
    """
    if not cordis_file.exists():
        return False, f"ACP composition config not found: {cordis_file}"
    content = cordis_file.read_text()
    if "policy: ask" not in content:
        return False, "acp.cordis.yml missing 'policy: ask' (approval stack not configured)"
    return True, "ACP composition valid (approval.policy: ask present)"


def validate_manifest_json(manifest_file: Path) -> tuple[bool, str]:
    """Validate engine-manifest.json has all required fields.

    Returns (False, skip_message) if the file doesn't exist (skip, not fail).
    Returns (False, error_message) if the file exists but is invalid.
    Returns (True, success_message) if the file is valid.
    """
    if not manifest_file.exists():
        return False, "engine-manifest.json not found (build engine first)"
    try:
        data = json.loads(manifest_file.read_text())
    except json.JSONDecodeError as exc:
        return False, f"engine-manifest.json is invalid JSON: {exc}"
    missing = []
    empty = []
    for field in MANIFEST_REQUIRED_FIELDS:
        if field not in data:
            missing.append(field)
        elif not data[field]:
            empty.append(field)
    if missing:
        return False, f"engine-manifest.json missing fields: {', '.join(missing)}"
    if empty:
        return False, f"engine-manifest.json has empty fields: {', '.join(empty)}"
    return True, "engine-manifest.json valid (all 5 fields present)"


def gate_engine_manifest(repo_root: Path) -> GateResult:
    """Gate 3: validate engine manifest.

    Checks (all required):
      - engines/dsh-pin.txt exists + has dsh_commit + node_version fields
      - engines/acp.cordis.yml exists + has approval.policy: ask

    Checks (optional -- skip if not found):
      - engines/engine-manifest.json has 5 required fields if it exists
    """
    engines_dir = repo_root / "engines"
    pin_file = engines_dir / "dsh-pin.txt"
    cordis_file = engines_dir / "acp.cordis.yml"
    manifest_file = engines_dir / "engine-manifest.json"

    errors: list[str] = []

    # Validate pin file (required)
    pin_ok, pin_msg = validate_pin_file(pin_file)
    if not pin_ok:
        errors.append(pin_msg)

    # Validate cordis config (required)
    cordis_ok, cordis_msg = validate_cordis_config(cordis_file)
    if not cordis_ok:
        errors.append(cordis_msg)

    # Validate manifest JSON (optional -- skip if not found)
    manifest_ok, manifest_msg = validate_manifest_json(manifest_file)
    manifest_skipped = not manifest_file.exists()

    if errors:
        return GateResult(
            name="engine-manifest",
            passed=False,
            skipped=False,
            message="; ".join(errors),
            details="",
        )

    if manifest_skipped:
        return GateResult(
            name="engine-manifest",
            passed=True,
            skipped=True,
            message=f"Pin + cordis valid; {manifest_msg}",
            details="",
        )

    if not manifest_ok:
        return GateResult(
            name="engine-manifest",
            passed=False,
            skipped=False,
            message=manifest_msg,
            details="",
        )

    return GateResult(
        name="engine-manifest",
        passed=True,
        skipped=False,
        message="Pin + cordis + manifest valid",
        details=manifest_msg,
    )


# ---------------------------------------------------------------------------
# Gate 4: mock-e2e
# ---------------------------------------------------------------------------

def gate_mock_e2e(repo_root: Path) -> GateResult:
    """Gate 4: flutter test packages/acp_client/ -- mock ACP E2E smoke."""
    flutter = _find_binary("flutter")
    if flutter is None:
        return GateResult(
            name="mock-e2e",
            passed=False,
            skipped=False,
            message="flutter binary not found on PATH",
            details="Install Flutter SDK and ensure flutter is on PATH.",
        )
    flutter_app = repo_root / "apps" / "flutter_app"
    acp_client = flutter_app / "packages" / "acp_client"
    if not acp_client.exists():
        return GateResult(
            name="mock-e2e",
            passed=False,
            skipped=False,
            message=f"acp_client package not found at {acp_client}",
            details="",
        )
    completed = subprocess.run(
        [flutter, "test", "packages/acp_client"],
        cwd=flutter_app,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return GateResult(
            name="mock-e2e",
            passed=True,
            skipped=False,
            message="All mock E2E tests passed",
            details=completed.stdout.strip(),
        )
    return GateResult(
        name="mock-e2e",
        passed=False,
        skipped=False,
        message=f"mock E2E tests failed (exit {completed.returncode})",
        details=completed.stdout + completed.stderr,
    )


# ---------------------------------------------------------------------------
# Gate 5: meta-test (GATE-02)
# ---------------------------------------------------------------------------

def find_lib_dirs(flutter_app: Path) -> list[tuple[Path, Path]]:
    """Find all (lib_dir, test_dir) pairs for the meta-test.

    Scans:
      - apps/flutter_app/lib/ (main app)
      - apps/flutter_app/packages/*/lib/ (sub-packages)

    For each directory containing .dart files, maps to the corresponding
    test/ directory. The mapping is:
      <package_root>/lib/<subpath> -> <package_root>/test/<subpath>

    Returns a list of (lib_dir, test_dir) pairs where lib_dir contains
    at least one .dart file.
    """
    pairs: list[tuple[Path, Path]] = []

    # Find all lib roots
    lib_roots: list[Path] = []
    main_lib = flutter_app / "lib"
    if main_lib.is_dir():
        lib_roots.append(main_lib)

    packages_dir = flutter_app / "packages"
    if packages_dir.is_dir():
        for pkg in sorted(packages_dir.iterdir()):
            pkg_lib = pkg / "lib"
            if pkg_lib.is_dir():
                lib_roots.append(pkg_lib)

    # For each lib root, walk and find dirs with .dart files
    for lib_root in lib_roots:
        package_root = lib_root.parent  # flutter_app/ or flutter_app/packages/<pkg>/

        for current_dir, _subdirs, files in os.walk(lib_root):
            current = Path(current_dir)
            # Check if this directory contains .dart files
            dart_files = [f for f in files if f.endswith(".dart")]
            if not dart_files:
                continue

            # Compute relative path from lib root
            rel = current.relative_to(lib_root)

            # Map to test directory
            test_dir = package_root / "test" / rel

            pairs.append((current, test_dir))

    return pairs


def run_meta_test(flutter_app: Path) -> list[str]:
    """Run the meta-test: check every lib/ dir has test coverage.

    Returns a list of uncovered lib dir descriptions (empty list = all covered).
    Each entry describes why a lib/ directory lacks coverage.
    """
    pairs = find_lib_dirs(flutter_app)
    uncovered: list[str] = []

    for lib_dir, test_dir in pairs:
        if not test_dir.is_dir():
            uncovered.append(f"{lib_dir} has no test directory ({test_dir} missing)")
            continue

        # Check for at least one _test.dart file
        test_files = list(test_dir.glob("*_test.dart"))
        if not test_files:
            uncovered.append(f"{lib_dir} has no _test.dart files in {test_dir}")
            continue

        # Check that at least one test file has content (T-112-20 mitigation)
        has_content = any(f.stat().st_size > 0 for f in test_files)
        if not has_content:
            uncovered.append(f"{lib_dir} has only empty _test.dart files in {test_dir}")

    return uncovered


def gate_meta_test(repo_root: Path) -> GateResult:
    """Gate 5: meta-test -- every Dart lib/ directory has test coverage (GATE-02)."""
    flutter_app = repo_root / "apps" / "flutter_app"
    if not flutter_app.exists():
        return GateResult(
            name="meta-test",
            passed=False,
            skipped=False,
            message=f"apps/flutter_app not found at {flutter_app}",
            details="",
        )

    uncovered = run_meta_test(flutter_app)

    if not uncovered:
        return GateResult(
            name="meta-test",
            passed=True,
            skipped=False,
            message="All lib/ directories have test coverage",
            details="",
        )

    return GateResult(
        name="meta-test",
        passed=False,
        skipped=False,
        message=f"{len(uncovered)} lib/ directory(ies) lack test coverage",
        details="\n".join(f"  FAIL: {d}" for d in uncovered),
    )


# ---------------------------------------------------------------------------
# Gate 6: docx-golden (placeholder -- Phase 118)
# ---------------------------------------------------------------------------

def gate_docx_golden(repo_root: Path) -> GateResult:
    """Gate 6: docx golden -- placeholder, skips in Phase 112 (active in Phase 118)."""
    return GateResult(
        name="docx-golden",
        passed=True,
        skipped=True,
        message="SKIP: docx golden not active until Phase 118",
        details="",
    )


# ---------------------------------------------------------------------------
# Gate dispatch
# ---------------------------------------------------------------------------

def run_gate(name: str, repo_root: Path) -> GateResult:
    """Run a single gate by name. Raises ValueError for unknown gates."""
    gates = {
        "dart-analyze": gate_dart_analyze,
        "flutter-test": gate_flutter_test,
        "engine-manifest": gate_engine_manifest,
        "mock-e2e": gate_mock_e2e,
        "meta-test": gate_meta_test,
        "docx-golden": gate_docx_golden,
    }
    if name not in gates:
        raise ValueError(f"Unknown gate: {name}")
    return gates[name](repo_root)


def run_all_gates(repo_root: Path) -> list[GateResult]:
    """Run all gates sequentially in execution order."""
    results: list[GateResult] = []
    for name in GATE_NAMES:
        results.append(run_gate(name, repo_root))
    return results


# ---------------------------------------------------------------------------
# Summary printing
# ---------------------------------------------------------------------------

def print_summary(results: list[GateResult]) -> int:
    """Print summary table and return exit code (0 = all pass, 1 = any fail)."""
    print()
    print("=" * 70)
    print("V4 Gates Summary")
    print("=" * 70)
    print(f"{'Gate':<20} {'Status':<8} {'Message'}")
    print("-" * 70)

    all_passed = True
    for result in results:
        if result.skipped:
            status = "SKIP"
        elif result.passed:
            status = "PASS"
        else:
            status = "FAIL"
            all_passed = False

        print(f"{result.name:<20} {status:<8} {result.message}")
        if result.details and not result.passed:
            for line in result.details.split("\n"):
                print(f"{'':>29} {line}")

    print("-" * 70)
    if all_passed:
        print("All V4 gates passed.")
        return 0
    failed = [r.name for r in results if not r.passed]
    print(f"V4 gates FAILED: {', '.join(failed)}")
    return 1


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Entry point with argparse for --check subcommand."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]

    if args.list:
        for name in GATE_NAMES:
            print(name)
        return 0

    if args.check:
        result = run_gate(args.check, repo_root)
        results = [result]
    else:
        results = run_all_gates(repo_root)

    return print_summary(results)


if __name__ == "__main__":
    raise SystemExit(main())
