"""Hermes materializer for the lawfirm solution pack.

Produces a sanitized Hermes profile bundle under
``output_dir/profiles/<solution_id>/`` with exactly four files. Any pre-flight
sanitization refusal aborts the bundle before any file is written.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from platform_runtime import (
    BackendSolutionBundle,
    Issue,
    Solution,
    SolutionPackageManifest,
)
from inkstatute_solution_loader import MaterializerSideEffects

from .sanitize import scan_text


LAWFIRM_SOLUTION_ID = "lawfirm"
LAWFIRM_VERSION = "1.0.0"
LAWFIRM_PERSONA_REF = "personas/lawfirm_persona.md"


_PERSONA_PLACEHOLDER = """# Lawfirm Persona (Sanitized Template)

This is a placeholder SOUL.md template produced by LawfirmHermesMaterializer.
It MUST be replaced with a real persona authored for the Hermes backend.

Real persona authoring is a Hermes-side onboarding step that lives outside
this pack. The pack ships only the neutral template; it never contains
customer-specific guidance, case materials, or confidential artifacts.

Activation: load this template into the Hermes profile directory named
``profiles/{solution_id}/`` and fill in real persona content there.
"""


_SKILL_TEMPLATE = """# Skill: {name}

Description: {description}

Intent: {intent}

Required tools: {required_tools}

Risk level: {risk_level}

This is a neutral skill template produced by LawfirmHermesMaterializer.
"""


_TOOLS_JSON_TEMPLATE = """{{
  "mcp": {mcp_json},
  "output_policy": {output_policy_json}
}}
"""


class LawfirmHermesMaterializer:
    """Sanitizing Hermes materializer for the lawfirm solution pack."""

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
        # Pre-flight scan: refuse any string fields that trip the sanitize rules.
        issues: list[Issue] = []
        issues.extend(self._scan_manifest(solution))
        if issues:
            return issues, None

        bundle_dir = Path(output_dir) / "profiles" / solution.solution_id
        bundle_dir.mkdir(parents=True, exist_ok=True)

        manifest = solution.manifest
        metadata = manifest.metadata or {}

        # File 1: SKILL.md.template (one file, listing all skills).
        skills_text = self._render_skill_template(manifest)
        (bundle_dir / "SKILL.md.template").write_text(skills_text, encoding="utf-8")

        # File 2: SAMPLE_PERSONA.md
        persona_text = _PERSONA_PLACEHOLDER.format(solution_id=solution.solution_id)
        (bundle_dir / "SAMPLE_PERSONA.md").write_text(persona_text, encoding="utf-8")

        # File 3: tools.json
        import json as _json

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

        bundle_ref = str(bundle_dir)
        return [], BackendSolutionBundle(
            backend_id="hermes",
            solution_id=solution.solution_id,
            bundle_ref=bundle_ref,
            metadata={
                "materializer": "LawfirmHermesMaterializer",
                "file_count": 4,
                "bundle_hash": bundle_hash,
            },
        )

    # ---- internals -----------------------------------------------------

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

        # Recursively scan metadata for refuse-pattern strings.
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
        # `skills` lives in metadata per the lawfirm manifest.json shape.
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