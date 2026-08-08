"""InkStatute Arena Engine — Modes 1+2.

This package implements the arena-engine boundary-layer modules that
enforce safety and persistence invariants at the arena edge:

- ``mock_acp`` — deterministic offline ``BackendAdapter`` for testing
- ``slot_runner`` — asyncio exception-isolated slot execution with retry
- ``artifact_store`` — reference-first structured output persistence (ENGINE-07)
- ``guardrail_boundary`` — post-hoc citation audit + de-AI polish +
  high-risk review enforcement on external ACP agents (SAFE-01..04)
- ``provenance`` — per-claim agent → reviewer → source chain logging (SAFE-07)

These modules are pure functions/classes with no LLM provider dependencies.
The orchestrator never produces content — no ``openai``, ``anthropic``, or
``ollama`` imports are permitted anywhere in this package (ENGINE-05).
Every run uses a fresh context — no ``session/resume`` calls (ENGINE-06).
"""

from __future__ import annotations

from .artifact_store import ArtifactStore, RoundArtifact
from .engine import ArenaEngine
from .guardrail_boundary import GuardrailResult, apply_post_hoc_guardrails
from .mode1 import Mode1Result, run_mode1_parallel
from .mode2 import (
    EventEmitter,
    IterationState,
    Mode2Result,
    _extract_self_score,
    run_mode2_iteration,
)
from .provenance import ProvenanceChain, ProvenanceLogger

__version__ = "0.1.0"

__all__ = [
    "ArenaEngine",
    "ArtifactStore",
    "EventEmitter",
    "GuardrailResult",
    "IterationState",
    "Mode1Result",
    "Mode2Result",
    "ProvenanceChain",
    "ProvenanceLogger",
    "RoundArtifact",
    "__version__",
    "apply_post_hoc_guardrails",
    "run_mode1_parallel",
    "run_mode2_iteration",
]
