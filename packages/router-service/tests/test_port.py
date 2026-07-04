"""Tests for the RouterPort Protocol."""

from __future__ import annotations

import unittest
from typing import Protocol

from inkstatute_router_service import RouterPort, RouterService


class TestRouterPort(unittest.TestCase):
    """Verify RouterPort is a Protocol and RouterService satisfies it."""

    def test_router_port_is_protocol(self) -> None:
        """RouterPort must be a typing.Protocol."""
        self.assertTrue(
            hasattr(RouterPort, "_is_protocol")
            or (isinstance(RouterPort, type) and Protocol in RouterPort.__mro__),
            "RouterPort must be a typing.Protocol",
        )

    def test_router_service_satisfies_router_port_protocol(self) -> None:
        """RouterService must have a callable decide method (structural subtyping)."""
        self.assertTrue(hasattr(RouterService, "decide"), "RouterService must have decide")
        self.assertTrue(callable(getattr(RouterService, "decide")), "decide must be callable")

    def test_router_port_has_decide_method(self) -> None:
        """RouterPort Protocol must declare decide."""
        self.assertIn("decide", dir(RouterPort))


if __name__ == "__main__":
    unittest.main()
