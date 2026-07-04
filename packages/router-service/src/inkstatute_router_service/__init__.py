"""inkstatute-router-service: standalone router library.

Re-exports the RouterPort Protocol, RouterService class, RouterStrategy enum,
and the classify_intent classifier function.
"""

from .classifier import classify_intent
from .port import RouterPort
from .service import RouterService
from .strategies import RouterStrategy

__all__ = [
    "RouterPort",
    "RouterService",
    "RouterStrategy",
    "classify_intent",
]
