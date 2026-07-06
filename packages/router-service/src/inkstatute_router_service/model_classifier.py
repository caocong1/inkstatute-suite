"""ModelClassifierPort — optional model-based confidence scoring for HYBRID routing.

Provides a ``ModelClassifierPort`` Protocol and a ``ModelClassificationResult``
dataclass.  The HYBRID strategy uses this port as the third layer of its
Rule → Skill → Model cascade.  When the port is ``None`` (the default),
the Model layer is skipped and the cascade falls back to confidence 0.0
(safe path / Hermes).

This module defines only the Protocol and data shape — the actual model
call is host-injected, preserving the ``dependencies = []`` invariant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


@dataclass(frozen=True, slots=True)
class ModelClassificationResult:
    """Result of model-based classification for routing.

    ``confidence`` is a float 0.0–1.0 representing the model's confidence
    in the predicted skill.  ``predicted_skill`` is the skill_id the model
    recommends, or ``None`` if the model cannot predict a skill.
    ``metadata`` is an open dict for model-specific diagnostics.
    """

    confidence: float
    predicted_skill: str | None = None
    metadata: dict = field(default_factory=dict)


class ModelClassifierPort(Protocol):
    """Protocol for injectable model-based classifiers.

    Implementations must be stateless and side-effect free.  When no
    classifier is injected (``None``), the HYBRID strategy skips the
    Model layer and falls back to confidence 0.0.
    """

    def classify(self, context: Mapping[str, Any]) -> ModelClassificationResult:
        """Classify *context* and return a confidence score with optional skill prediction."""
        ...


__all__ = [
    "ModelClassifierPort",
    "ModelClassificationResult",
]
