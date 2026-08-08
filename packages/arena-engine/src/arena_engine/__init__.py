"""InkStatute Arena Engine — Modes 1-4 + arena safety primitives.

This package implements the arena-engine boundary-layer modules that
enforce safety and persistence invariants at the arena edge:

- ``mock_acp`` — deterministic offline ``BackendAdapter`` for testing
- ``slot_runner`` — asyncio exception-isolated slot execution with retry
- ``artifact_store`` — reference-first structured output persistence (ENGINE-07)
- ``guardrail_boundary`` — post-hoc citation audit + de-AI polish +
  high-risk review enforcement on external ACP agents (SAFE-01..04)
- ``provenance`` — per-claim agent → reviewer → source chain logging (SAFE-07)
- ``review`` — structured review output (ReviewFinding, ConfidenceLevel,
  SeverityLevel) for Modes 3+4 cross-review phases
- ``families`` — cross-family review enforcement (SAFE-06) with explicit
  degradation when only same-family agents are available
- ``mode3`` — Arena Review (self-score + cross-review + independent synthesis)
- ``mode4`` — Adversarial (arena review + adversarial challenge + multi-round
  synthesis with early stopping)

These modules are pure functions/classes with no LLM provider dependencies.
The orchestrator never produces content — no ``openai``, ``anthropic``, or
``ollama`` imports are permitted anywhere in this package (ENGINE-05).
Every run uses a fresh context — no ``session/resume`` calls (ENGINE-06).
"""

from __future__ import annotations

from .artifact_store import ArtifactStore, RoundArtifact
from .engine import ArenaEngine
from .families import (
    CrossFamilyPairingResult,
    DEFAULT_FAMILY_MAP,
    _pair_cross_family,
    get_backend_family,
)
from .guardrail_boundary import GuardrailResult, apply_post_hoc_guardrails
from .mode1 import Mode1Result, run_mode1_parallel
from .mode2 import (
    EventEmitter,
    IterationState,
    Mode2Result,
    _extract_self_score,
    run_mode2_iteration,
)
from .mode3 import Mode3Result, run_mode3_arena_review
from .mode4 import Mode4Result, SynthesisRound, run_mode4_adversarial
from .provenance import ProvenanceChain, ProvenanceLogger
from .review import ConfidenceLevel, ReviewFinding, SeverityLevel

__version__ = "0.1.0"

__all__ = [
    "ArenaEngine",
    "ArtifactStore",
    "ConfidenceLevel",
    "CrossFamilyPairingResult",
    "DEFAULT_FAMILY_MAP",
    "EventEmitter",
    "GuardrailResult",
    "IterationState",
    "Mode1Result",
    "Mode2Result",
    "Mode3Result",
    "Mode4Result",
    "ProvenanceChain",
    "ProvenanceLogger",
    "ReviewFinding",
    "RoundArtifact",
    "SeverityLevel",
    "SynthesisRound",
    "__version__",
    "apply_post_hoc_guardrails",
    "get_backend_family",
    "run_mode1_parallel",
    "run_mode2_iteration",
    "run_mode3_arena_review",
    "run_mode4_adversarial",
]
