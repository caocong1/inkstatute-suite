"""inkstatute-skill-index: Read-only SKILL.md scanner and indexer.

Re-exports the scanner, frontmatter parser, and token estimator
for discovering and indexing real legal SKILL.md files from
ai-for-china-legal (345 skills) and legal-skills (51 skills).
"""

from .frontmatter_parser import (
    FrontmatterResult,
    extract_description,
    extract_license,
    extract_name,
    extract_version,
    parse_frontmatter,
)
from .scanner import ScanResult, ScannedSkill, scan_repo
from .token_estimator import estimate_tokens, estimate_tokens_for_file, is_cjk

SCANNER_VERSION = "1.0.0"

__all__ = [
    "SCANNER_VERSION",
    "FrontmatterResult",
    "ScanResult",
    "ScannedSkill",
    "estimate_tokens",
    "estimate_tokens_for_file",
    "extract_description",
    "extract_license",
    "extract_name",
    "extract_version",
    "is_cjk",
    "parse_frontmatter",
    "scan_repo",
]
