"""InkStatute Arena Engine — Modes 1+2.

This package implements the arena-engine boundary-layer modules that
enforce safety and persistence invariants at the arena edge:

- ``mock_acp`` — deterministic offline ``BackendAdapter`` for testing
- ``slot_runner`` — asyncio exception-isolated slot execution with retry

These modules are pure functions/classes with no LLM provider dependencies.
The orchestrator never produces content — no ``openai``, ``anthropic``, or
``ollama`` imports are permitted anywhere in this package (ENGINE-05).
Every run uses a fresh context — no ``session/resume`` calls (ENGINE-06).
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = [
    "__version__",
]
