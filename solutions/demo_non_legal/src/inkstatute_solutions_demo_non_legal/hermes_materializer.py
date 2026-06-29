"""Hermes materializer for the demo_non_legal solution pack.

Reuses the lawfirm sanitize module so refusal patterns live in one place.
"""

from __future__ import annotations

import hashlib
import json as _json
from pathlib import Path
from typing import Any, Mapping

from platform_runtime import (
    BackendSolutionBundle,
    Issue,
    Solution,
    SolutionPackageManifest,
)
from inkstatute_solution_loader import MaterializerSideEffects

# Shared sanitize module: same refusal patterns as lawfirm.
from inkstatute_solutions_lawfirm.sanitize import scan_text


DEMO_NON_LEGAL_SOLUTION_ID = "demo_non_legal"
DEMO_NON_LEGAL_VERSION = "1.0.0"


_PERSONA_PLACEHOLDER = """# Demo Non-Legal Persona (Sanitized Template)

This is a placeholder SOUL.md template produced by
DemoNonLegalHermesMaterializer. It MUST be replaced with a real education-domain
persona authored for the Hermes backend.

Activation: load this template into the Hermes profile directory named
``profiles/{solution_id}/`` and fill in real persona content there.
"""


_SKILL_TEMPLATE = """# Skill: {name}

Description: {description}

Intent: {intent}

Required tools: {required_tools}

Risk level: {risk_level}

This is a neutral skill template produced by DemoNonLegalHermesMaterializer.
"""


class DemoNonLegalHermesMaterializer:
    """Sanitizing Hermes materializer for the demo_non_legal solution pack."""

    def side_effects(self) -> MaterializerSideEffects:
        return MaterializerSideEffects(
            backend_id="hermes",
            declared_output_dir_relative="profiles/<solution_id>",
            side_effect_kinds=("write_dir",),
            notes=(
                "Sanitized Hermes profile bundle. Writes 4 files under "
                "output_dir/profiles/<solution_id>/. Refuses secret/raw-payload/"
                "log/db/media/customer-doc/confidential-artifact content."
            ),
        )

    def materialize(
        self,
        solution: Solution,
        output_dir: Path,
    ) -> tuple[list[Issue], BackendSolutionBundle | None]:
        issues: list[Issue] = []
        issues.extend(self._scan_manifest(solution))
        if issues:
            return issues, None

        bundle_dir = Path(output_dir) / "profiles" / solution.solution_id
        bundle_dir.mkdir(parents=True, exist_ok=True)

        manifest = solution.manifest

        # File 1: SKILL.md.template
        (bundle_dir / "SKILL.md.template").write_text(
            self._render_skill_template(manifest), encoding="utf-8"
        )

        # File 2: SAMPLE_PERSONA.md
        (bundle_dir / "SAMPLE_PERSONA.md").write_text(
            _PERSONA_PLACEHOLDER.format(solution_id=solution.solution_id),
            encoding="utf-8",
        )

        # File 3: tools.json
        tools_payload = {
            "mcp": list(manifest.metadata.get("mcp", [])),
            "output_policy": dict(manifest.metadata.get("output_policy", {})),
            "solution_id": solution.solution_id,
            "version": solution.version,
        }
        (bundle_dir / "tools.json").write_text(
            _json.dumps(tools_payload, indent=2, sort_keys=True), encoding="utf-8"
        )

        # File 4: SANITIZATION_REPORT.md
        bundle_hash = self._hash_bundle(bundle_dir)
        report = (
            "# Sanitization Report\n\n"
            "solution_id: {sid}\n"
            "version: {ver}\n"
            "backend_id: hermes\n"
            "refused_items: []\n"
            "stripped_keys: []\n"
            "redacted_paths: []\n"
            "bundle_hash: {h}\n"
        ).format(sid=solution.solution_id, ver=solution.version, h=bundle_hash)
        (bundle_dir / "SANITIZATION_REPORT.md").write_text(report, encoding="utf-8")

        return [], BackendSolutionBundle(
            backend_id="hermes",
            solution_id=solution.solution_id,
            bundle_ref=str(bundle_dir),
            metadata={
                "materializer": "DemoNonLegalHermesMaterializer",
                "file_count": 4,
                "bundle_hash": bundle_hash,
            },
        )

    @staticmethod
    def _scan_manifest(solution: Solution) -> list[Issue]:
        issues: list[Issue] = []
        m = solution.manifest
        for path, value in (
            ("solution_id", m.solution_id),
            ("version", m.version),
            ("manifest_ref", m.manifest_ref or ""),
        ):
            for code in scan_text(value):
                issues.append(
                    Issue(
                        path=path,
                        code=code,
                        message=f"{path!r} matches refusal pattern: {code}",
                        severity="error",
                    )
                )

        def _walk(prefix: str, value: Any) -> None:
            if isinstance(value, Mapping):
                for k, v in value.items():
                    _walk(f"{prefix}.{k}" if prefix else str(k), v)
            elif isinstance(value, (list, tuple)):
                for i, v in enumerate(value):
                    _walk(f"{prefix}[{i}]", v)
            elif isinstance(value, str):
                for code in scan_text(value):
                    issues.append(
                        Issue(
                            path=prefix,
                            code=code,
                            message=f"string at {prefix!r} matches refusal pattern: {code}",
                            severity="error",
                        )
                    )

        _walk("metadata", m.metadata or {})
        return issues

    @staticmethod
    def _render_skill_template(manifest: SolutionPackageManifest) -> str:
        skills = manifest.metadata.get("skills", []) if manifest.metadata else []
        chunks = []
        for skill in skills:
            chunks.append(
                _SKILL_TEMPLATE.format(
                    name=skill.get("name", ""),
                    description=skill.get("description", ""),
                    intent=skill.get("intent", ""),
                    required_tools=", ".join(skill.get("required_tools", [])),
                    risk_level=skill.get("risk_level", "unknown"),
                )
            )
        if not chunks:
            chunks.append("(no skills declared in manifest)")
        return "\n".join(chunks)

    @staticmethod
    def _hash_bundle(bundle_dir: Path) -> str:
        h = hashlib.sha256()
        for p in sorted(bundle_dir.rglob("*")):
            if p.is_file():
                h.update(p.name.encode("utf-8"))
                h.update(p.read_bytes())
        return h.hexdigest()[:16]