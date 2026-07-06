"""Tests for the read-only MCP Registry (list_servers, get_server, search)."""

from __future__ import annotations

import unittest

from platform_contract import McpServerDescriptor

from inkstatute_mcp_registry.cursor import decode_cursor, encode_cursor
from inkstatute_mcp_registry.registry import (
    InMemoryMcpRegistry,
    McpServerPage,
    McpServerRecord,
)


def _make_record(
    server_id: str,
    name: str = "test-server",
    transport: str = "stdio",
    capability_refs: list[str] | None = None,
    active: bool = True,
    version: str = "1.0.0",
    admission_status: str = "approved",
) -> McpServerRecord:
    return McpServerRecord(
        server_id=server_id,
        name=name,
        transport=transport,
        capability_refs=capability_refs or [],
        active=active,
        version=version,
        admission_status=admission_status,
    )


class ListServersTests(unittest.TestCase):
    def test_list_servers_returns_active_only(self) -> None:
        """3 active + 1 inactive → list returns 3."""
        registry = InMemoryMcpRegistry([
            _make_record("server-1", active=True),
            _make_record("server-2", active=True),
            _make_record("server-3", active=True),
            _make_record("server-4", active=False),
        ])
        page = registry.list_servers()
        self.assertEqual(len(page.items), 3)
        ids = {d.server_id for d in page.items}
        self.assertEqual(ids, {"server-1", "server-2", "server-3"})

    def test_list_server_pagination(self) -> None:
        """5 servers, limit=2 → 3 pages (2, 2, 1), has_more on first two."""
        registry = InMemoryMcpRegistry([
            _make_record(f"server-{i}") for i in range(1, 6)
        ])
        page1 = registry.list_servers(limit=2)
        self.assertEqual(len(page1.items), 2)
        self.assertTrue(page1.has_more)
        self.assertIsNotNone(page1.next_cursor)

        page2 = registry.list_servers(cursor=page1.next_cursor, limit=2)
        self.assertEqual(len(page2.items), 2)
        self.assertTrue(page2.has_more)
        self.assertIsNotNone(page2.next_cursor)

        page3 = registry.list_servers(cursor=page2.next_cursor, limit=2)
        self.assertEqual(len(page3.items), 1)
        self.assertFalse(page3.has_more)
        self.assertIsNone(page3.next_cursor)

    def test_list_server_cursor_stability(self) -> None:
        """Paginate with limit=2, add a new server, continue from cursor → still correct."""
        registry = InMemoryMcpRegistry([
            _make_record("server-1"),
            _make_record("server-2"),
            _make_record("server-4"),
        ])
        page1 = registry.list_servers(limit=2)
        self.assertEqual(len(page1.items), 2)

        # Add a new server between pages — cursor should still be valid
        registry._records["server-3"] = _make_record("server-3")
        page2 = registry.list_servers(cursor=page1.next_cursor, limit=2)
        # After adding server-3, the sorted list is 1,2,3,4; cursor was after server-2
        # So page2 starts at server-3
        ids = [d.server_id for d in page2.items]
        self.assertEqual(ids, ["server-3", "server-4"])

    def test_list_servers_empty_registry(self) -> None:
        """Empty registry returns empty page with has_more=False."""
        registry = InMemoryMcpRegistry()
        page = registry.list_servers()
        self.assertEqual(len(page.items), 0)
        self.assertFalse(page.has_more)
        self.assertIsNone(page.next_cursor)

    def test_list_servers_no_cursor_returns_first_page(self) -> None:
        """No cursor returns first page sorted by server_id."""
        registry = InMemoryMcpRegistry([
            _make_record("server-c"),
            _make_record("server-a"),
            _make_record("server-b"),
        ])
        page = registry.list_servers()
        ids = [d.server_id for d in page.items]
        self.assertEqual(ids, ["server-a", "server-b", "server-c"])

    def test_list_servers_sorted_by_server_id(self) -> None:
        """Servers are returned sorted by server_id."""
        registry = InMemoryMcpRegistry([
            _make_record("server-z"),
            _make_record("server-a"),
            _make_record("server-m"),
        ])
        page = registry.list_servers()
        ids = [d.server_id for d in page.items]
        self.assertEqual(ids, ["server-a", "server-m", "server-z"])


class GetServerTests(unittest.TestCase):
    def test_get_server_returns_descriptor(self) -> None:
        """get_server returns McpServerDescriptor with correct fields."""
        registry = InMemoryMcpRegistry([
            _make_record(
                "server-1",
                name="Legal Search",
                transport="stdio",
                capability_refs=["law_search"],
            ),
        ])
        desc = registry.get_server("server-1")
        self.assertIsNotNone(desc)
        self.assertIsInstance(desc, McpServerDescriptor)
        self.assertEqual(desc.server_id, "server-1")
        self.assertEqual(desc.name, "Legal Search")
        self.assertEqual(desc.transport, "stdio")
        self.assertEqual(desc.capability_refs, ["law_search"])

    def test_get_server_returns_none_for_unknown(self) -> None:
        """get_server returns None for unknown id."""
        registry = InMemoryMcpRegistry([_make_record("server-1")])
        self.assertIsNone(registry.get_server("unknown"))

    def test_get_server_returns_inactive(self) -> None:
        """get_server returns descriptor for inactive server too."""
        registry = InMemoryMcpRegistry([
            _make_record("server-1", active=False),
        ])
        desc = registry.get_server("server-1")
        self.assertIsNotNone(desc)
        self.assertFalse(desc.metadata["active"])


class SearchTests(unittest.TestCase):
    def test_search_by_name_substring(self) -> None:
        """search('legal') matches servers with 'legal' in name."""
        registry = InMemoryMcpRegistry([
            _make_record("server-1", name="Legal Search"),
            _make_record("server-2", name="Case Database"),
            _make_record("server-3", name="Legal Drafting"),
        ])
        page = registry.search("legal")
        self.assertEqual(len(page.items), 2)
        names = {d.name for d in page.items}
        self.assertEqual(names, {"Legal Search", "Legal Drafting"})

    def test_search_by_capability_ref(self) -> None:
        """search('law_search') matches servers with 'law_search' in capability_refs."""
        registry = InMemoryMcpRegistry([
            _make_record("server-1", capability_refs=["law_search", "case_lookup"]),
            _make_record("server-2", capability_refs=["case_lookup"]),
        ])
        page = registry.search("law_search")
        self.assertEqual(len(page.items), 1)
        self.assertEqual(page.items[0].server_id, "server-1")

    def test_search_pagination(self) -> None:
        """search with limit returns paginated results."""
        registry = InMemoryMcpRegistry([
            _make_record(f"legal-{i}", name=f"Legal Server {i}")
            for i in range(1, 6)
        ])
        page1 = registry.search("legal", limit=2)
        self.assertEqual(len(page1.items), 2)
        self.assertTrue(page1.has_more)

        page2 = registry.search("legal", cursor=page1.next_cursor, limit=2)
        self.assertEqual(len(page2.items), 2)
        self.assertTrue(page2.has_more)

        page3 = registry.search("legal", cursor=page2.next_cursor, limit=2)
        self.assertEqual(len(page3.items), 1)
        self.assertFalse(page3.has_more)

    def test_search_returns_active_only(self) -> None:
        """Inactive servers not in search results."""
        registry = InMemoryMcpRegistry([
            _make_record("server-1", name="Legal Search", active=True),
            _make_record("server-2", name="Legal Drafting", active=False),
        ])
        page = registry.search("legal")
        self.assertEqual(len(page.items), 1)
        self.assertEqual(page.items[0].server_id, "server-1")

    def test_search_case_insensitive(self) -> None:
        """Search is case-insensitive."""
        registry = InMemoryMcpRegistry([
            _make_record("server-1", name="Legal Search"),
        ])
        page = registry.search("LEGAL")
        self.assertEqual(len(page.items), 1)

    def test_search_no_results(self) -> None:
        """Search with no matches returns empty page."""
        registry = InMemoryMcpRegistry([
            _make_record("server-1", name="Legal Search"),
        ])
        page = registry.search("nonexistent")
        self.assertEqual(len(page.items), 0)
        self.assertFalse(page.has_more)


class DescriptorMetadataTests(unittest.TestCase):
    def test_descriptor_metadata_includes_version_and_active(self) -> None:
        """descriptor metadata has version, active, admission_status."""
        registry = InMemoryMcpRegistry([
            _make_record(
                "server-1",
                version="2.1.0",
                active=True,
                admission_status="approved",
            ),
        ])
        desc = registry.get_server("server-1")
        self.assertIsNotNone(desc)
        self.assertEqual(desc.metadata["version"], "2.1.0")
        self.assertTrue(desc.metadata["active"])
        self.assertEqual(desc.metadata["admission_status"], "approved")

    def test_descriptor_metadata_includes_registered_at(self) -> None:
        """descriptor metadata has registered_at."""
        registry = InMemoryMcpRegistry([
            _make_record("server-1"),
        ])
        registry._records["server-1"].registered_at = "2026-07-06T12:00:00Z"
        desc = registry.get_server("server-1")
        self.assertIsNotNone(desc)
        self.assertEqual(desc.metadata["registered_at"], "2026-07-06T12:00:00Z")


class McpServerPageTests(unittest.TestCase):
    def test_page_is_frozen(self) -> None:
        """McpServerPage is a frozen dataclass."""
        page = McpServerPage(items=[], next_cursor=None, has_more=False)
        with self.assertRaises(Exception):
            page.has_more = True  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
