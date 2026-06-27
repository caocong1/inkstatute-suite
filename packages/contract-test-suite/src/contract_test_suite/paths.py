"""Repository-local paths used by the contract test suite."""

from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PACKAGE_ROOT.parents[1]
PLATFORM_CONTRACT_ROOT = REPO_ROOT / "packages" / "platform-contract"
PLATFORM_SCHEMA_ROOT = PLATFORM_CONTRACT_ROOT / "src" / "platform_contract" / "schemas"
PLATFORM_FIXTURE_ROOT = PLATFORM_CONTRACT_ROOT / "fixtures"
LOCAL_FIXTURE_ROOT = PACKAGE_ROOT / "fixtures"
