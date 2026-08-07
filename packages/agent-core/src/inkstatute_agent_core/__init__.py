"""InkStatute self-built Python agent core.

This package implements the async streaming turn loop that produces
Phase 88 unified events.  It is the Python replacement for the
``lawyer-desktop`` Rust agent core, with the key fix that tool rounds
also stream — the client never experiences whole-round silence.

Phase 100 (skeleton):
    - ``config.AgentCoreConfig`` — configurable parameters
    - ``event_emitter.EventEmitter`` — monotonic seq + silence threshold + heartbeat

Future phases add the model layer (Phase 100-02), context assembler
and turn loop (Phase 100-03), tools (Phase 101), guardrails (Phase 102),
and dual entry points (Phase 103).
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
