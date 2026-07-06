"""inkstatute-router-service: standalone router library.

Re-exports the RouterPort Protocol, RouterService class, RouterStrategy enum,
the classify_intent classifier function, and the tool-resolution join helpers.
"""

from .classifier import classify_intent
from .port import RouterPort
from .service import RouterService
from .strategies import RouterStrategy
from .tool_resolver import ToolResolutionMap, resolve_all_tool_refs, resolve_tool_refs

__all__ = [
    "RouterPort",
    "RouterService",
    "RouterStrategy",
    "ToolResolutionMap",
    "classify_intent",
    "resolve_all_tool_refs",
    "resolve_tool_refs",
]
