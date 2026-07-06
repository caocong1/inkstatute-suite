"""Tests enforcing read-only behavior of McpRegistryPort and InMemoryMcpRegistry."""

from __future__ import annotations

import unittest

from inkstatute_mcp_registry.registry import InMemoryMcpRegistry, McpRegistryPort

# Prefixes that indicate a mutating (write) method.
_WRITE_PREFIXES = (
    "add_",
    "create_",
    "update_",
    "delete_",
    "remove_",
    "put_",
    "post_",
    "register_",
    "deactivate_",
    "approve_",
    "set_",
    "save_",
    "insert_",
)


class ReadOnlyEnforcementTests(unittest.TestCase):
    def test_mcp_registry_port_is_read_only(self) -> None:
        """No method on McpRegistryPort starts with a write prefix."""
        mutating = [
            attr
            for attr in dir(McpRegistryPort)
            if not attr.startswith("_")
            and any(attr.startswith(prefix) for prefix in _WRITE_PREFIXES)
        ]
        self.assertEqual(mutating, [], f"Found mutating methods on Port: {mutating}")

    def test_mcp_registry_port_has_exactly_three_read_methods(self) -> None:
        """McpRegistryPort has exactly 3 public methods: list_servers, get_server, search."""
        methods = [m for m in dir(McpRegistryPort) if not m.startswith("_")]
        self.assertEqual(
            sorted(methods),
            ["get_server", "list_servers", "search"],
            f"McpRegistryPort methods changed: {methods}",
        )

    def test_in_memory_registry_no_public_write_methods(self) -> None:
        """InMemoryMcpRegistry public methods (non-underscore) are only read methods."""
        public_methods = {
            m
            for m in dir(InMemoryMcpRegistry)
            if not m.startswith("_")
            and callable(getattr(InMemoryMcpRegistry, m, None))
        }
        # The only public methods should be the 3 read methods
        expected = {"list_servers", "get_server", "search"}
        self.assertEqual(
            public_methods,
            expected,
            f"Unexpected public methods on InMemoryMcpRegistry: {public_methods - expected}",
        )


if __name__ == "__main__":
    unittest.main()
