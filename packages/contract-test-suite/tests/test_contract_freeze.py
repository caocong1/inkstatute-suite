"""Contract freeze baseline hash tests (SAFETY-06).

Detects any modification to the 31 contract surface files (26 schema JSON +
4 Python binding + 1 Protocol) during the V2 human gate period by comparing
SHA-256 hashes against the v1.5 baseline stored in
``fixtures/contract_freeze_baseline.json``.

Two directions are checked:
  1. A file in the baseline has been modified (hash mismatch).
  2. A new schema file has been added without being recorded in the baseline.
"""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BASELINE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "contract_freeze_baseline.json"
SCHEMA_DIR = REPO_ROOT / "packages" / "platform-contract" / "src" / "platform_contract" / "schemas"


class ContractFreezeTests(unittest.TestCase):
    """Assert contract surface files match the v1.5 SHA-256 baseline."""

    def _load_baseline(self) -> dict:
        with open(BASELINE_PATH, encoding="utf-8") as fh:
            return json.load(fh)

    def test_schema_files_match_baseline_hash(self) -> None:
        baseline = self._load_baseline()
        for rel_path, expected_hash in baseline["files"].items():
            with self.subTest(file=rel_path):
                file_path = REPO_ROOT / rel_path
                self.assertTrue(
                    file_path.exists(),
                    f"contract file removed from v1.5 baseline: {rel_path}",
                )
                actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
                self.assertEqual(
                    actual_hash,
                    expected_hash,
                    f"contract file modified from v1.5 baseline: {rel_path}",
                )

    def test_no_new_schema_files_added_without_baseline(self) -> None:
        baseline = self._load_baseline()
        current_files = {
            str(p.relative_to(REPO_ROOT)) for p in SCHEMA_DIR.glob("*.schema.json")
        }
        baseline_files = set(baseline["files"].keys())
        new_files = current_files - baseline_files
        self.assertFalse(
            new_files,
            f"new schema files detected without baseline entry: {sorted(new_files)}",
        )


if __name__ == "__main__":
    unittest.main()
