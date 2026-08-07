"""Recursive directory walker that discovers all SKILL.md files (read-only).

Walks a repo directory tree recursively and discovers all ``SKILL.md`` files.
Produces raw ``ScannedSkill`` records — classification (orchestration vs leaf)
and metadata enrichment happen in Plan 96-02.

CRITICAL: The scanner NEVER calls any write operation. It reads files only.
All file reads use ``path.read_text(encoding="utf-8")``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .frontmatter_parser import extract_name, parse_frontmatter
from .token_estimator import estimate_tokens

# Directories to skip during traversal.
EXCLUDED_DIRS: set[str] = {".qwen", "node_modules", ".git", "__pycache__", ".claude-plugin"}


@dataclass(frozen=True, slots=True)
class ScannedSkill:
    """A single discovered SKILL.md file with parsed metadata.

    Attributes:
        skill_id: Namespace-prefixed ID (e.g. "commercial-legal:contract-review" or "legal-court-sms").
        name: Skill name from frontmatter or directory name fallback.
        source_repo: "ai-for-china-legal" or "legal-skills" (passed by caller).
        plugin: Plugin name for ai-for-china-legal (e.g. "commercial-legal"), None for legal-skills.
        relative_path: Path relative to repo root.
        absolute_path: Absolute path to the SKILL.md file.
        frontmatter: Parsed frontmatter dict.
        body: Markdown body text.
        raw_text: Full file content.
        token_estimate: Estimated token count.
        warnings: Warnings from frontmatter parsing + scanner.
        depth: Nesting depth (0 = direct child of skills/, 1 = nested under a parent).
    """

    skill_id: str
    name: str
    source_repo: str
    plugin: str | None
    relative_path: str
    absolute_path: str
    frontmatter: dict[str, Any]
    body: str
    raw_text: str
    token_estimate: int
    warnings: list[str] = field(default_factory=list)
    depth: int = 0


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Result of scanning a single repo.

    Attributes:
        repo_name: "ai-for-china-legal" or "legal-skills".
        repo_path: Absolute path to the repo root.
        skills: All discovered skills.
        warnings: Repo-level warnings (e.g. "missing_plugin_json").
    """

    repo_name: str
    repo_path: str
    skills: list[ScannedSkill] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _is_excluded(path: Path) -> bool:
    """Check if *path* contains any excluded directory component."""
    for part in path.parts:
        if part in EXCLUDED_DIRS:
            return True
    return False


def _compute_depth(relative_path: str) -> int:
    """Compute nesting depth from a relative path.

    Returns 0 for ``skills/<name>/SKILL.md`` (direct child),
    1 for ``skills/<parent>/<name>/SKILL.md`` (nested),
    and 0 for paths not containing ``skills/`` (e.g. ``shared/research-gate/SKILL.md``).
    """
    parts = relative_path.replace("\\", "/").split("/")
    try:
        skills_index = parts.index("skills")
    except ValueError:
        return 0
    # Components between "skills/" and "SKILL.md", minus 1
    # parts = [..., "skills", "<name>", "SKILL.md"] → 1 component between → depth 0
    # parts = [..., "skills", "<parent>", "<name>", "SKILL.md"] → 2 components → depth 1
    between = len(parts) - skills_index - 2  # excludes "skills" and "SKILL.md"
    return max(between - 1, 0)


def _determine_plugin(relative_path: str, repo_name: str) -> str | None:
    """Determine the plugin name from the relative path.

    For ai-for-china-legal: returns the first path component if not "shared", else "shared".
    For legal-skills: returns None.
    """
    if repo_name == "legal-skills":
        return None
    parts = relative_path.replace("\\", "/").split("/")
    if not parts:
        return None
    first = parts[0]
    if first == "shared":
        return "shared"
    return first


def _compute_skill_id(name: str, plugin: str | None, repo_name: str) -> str:
    """Compute the namespace-prefixed skill ID.

    - legal-skills: "legal-<name>"
    - shared: "shared:<name>"
    - plugin: "<plugin>:<name>"
    - fallback: <name>
    """
    if repo_name == "legal-skills":
        return f"legal-{name}"
    if plugin == "shared":
        return f"shared:{name}"
    if plugin is not None:
        return f"{plugin}:{name}"
    return name


def scan_repo(repo_path: str | Path, repo_name: str) -> ScanResult:
    """Walk *repo_path* recursively and discover all SKILL.md files.

    This is a READ-ONLY operation. No files are created, modified, or deleted.

    Args:
        repo_path: Absolute or relative path to the repo root.
        repo_name: "ai-for-china-legal" or "legal-skills".

    Returns:
        ScanResult with all discovered skills and any repo-level warnings.
    """
    root = Path(repo_path)
    repo_warnings: list[str] = []
    skills: list[ScannedSkill] = []

    if not root.exists():
        return ScanResult(
            repo_name=repo_name,
            repo_path=str(root),
            skills=[],
            warnings=["repo_path_does_not_exist"],
        )

    # Use rglob to find all SKILL.md files, then filter excluded dirs
    for skill_file in root.rglob("SKILL.md"):
        if _is_excluded(skill_file):
            continue

        # Skip _shared/ directories (reference material, not skills)
        if "_shared" in skill_file.parts:
            continue

        try:
            text = skill_file.read_text(encoding="utf-8")
        except (PermissionError, UnicodeDecodeError) as exc:
            # Graceful degradation: produce a warning record instead of crashing
            relative = str(skill_file.relative_to(root))
            dir_name = skill_file.parent.name
            plugin = _determine_plugin(relative, repo_name)
            skill_id = _compute_skill_id(dir_name, plugin, repo_name)
            skills.append(
                ScannedSkill(
                    skill_id=skill_id,
                    name=dir_name,
                    source_repo=repo_name,
                    plugin=plugin,
                    relative_path=relative,
                    absolute_path=str(skill_file),
                    frontmatter={},
                    body="",
                    raw_text="",
                    token_estimate=0,
                    warnings=[f"read_error: {type(exc).__name__}"],
                    depth=_compute_depth(relative),
                )
            )
            continue

        fm_result = parse_frontmatter(text)
        dir_name = skill_file.parent.name
        name = extract_name(fm_result.frontmatter, fallback=dir_name) or dir_name

        relative = str(skill_file.relative_to(root))
        plugin = _determine_plugin(relative, repo_name)
        skill_id = _compute_skill_id(name, plugin, repo_name)
        depth = _compute_depth(relative)
        token_est = estimate_tokens(text)

        skills.append(
            ScannedSkill(
                skill_id=skill_id,
                name=name,
                source_repo=repo_name,
                plugin=plugin,
                relative_path=relative,
                absolute_path=str(skill_file),
                frontmatter=fm_result.frontmatter,
                body=fm_result.body,
                raw_text=fm_result.raw_text,
                token_estimate=token_est,
                warnings=list(fm_result.warnings),
                depth=depth,
            )
        )

    # Sort by relative_path for deterministic output
    skills.sort(key=lambda s: s.relative_path)

    return ScanResult(
        repo_name=repo_name,
        repo_path=str(root),
        skills=skills,
        warnings=repo_warnings,
    )
