"""Tests for router tool-resolution join (skill required_tool_refs → MCP capability_refs)."""

from __future__ import annotations

import unittest

from platform_contract import McpServerDescriptor, NeutralSkillDescriptor

from inkstatute_router_service import (
    ToolResolutionMap,
    resolve_all_tool_refs,
    resolve_tool_refs,
)


class _FakeMcpRegistry:
    """Fake MCP registry for testing — implements the search interface."""

    def __init__(self, servers: list[McpServerDescriptor]) -> None:
        self._servers = servers

    def search(
        self,
        query: str,
        cursor: str | None = None,
        limit: int = 50,
    ) -> _FakePage:
        needle = query.lower()
        matched = [
            s
            for s in self._servers
            if needle in s.server_id.lower()
            or needle in s.name.lower()
            or any(needle in cap.lower() for cap in s.capability_refs)
        ]
        return _FakePage(matched)


class _FakePage:
    """Fake pagination page."""

    def __init__(self, items: list[McpServerDescriptor]) -> None:
        self.items = items
        self.next_cursor = None
        self.has_more = False


def _make_server(
    server_id: str,
    name: str = "test-server",
    capability_refs: list[str] | None = None,
) -> McpServerDescriptor:
    return McpServerDescriptor(
        server_id=server_id,
        name=name,
        transport="stdio",
        capability_refs=capability_refs or [],
    )


def _make_skill(
    skill_id: str = "lawfirm/case_qa",
    required_tool_refs: list[str] | None = None,
) -> NeutralSkillDescriptor:
    return NeutralSkillDescriptor(
        skill_id=skill_id,
        name="case_qa",
        required_tool_refs=required_tool_refs or [],
    )


class ResolveToolRefsTests(unittest.TestCase):
    def test_resolve_tool_refs_all_resolved(self) -> None:
        """Skill with 2 tool_refs, both found → resolved_servers has servers, unresolved empty."""
        registry = _FakeMcpRegistry([
            _make_server("server-1", capability_refs=["law_search"]),
            _make_server("server-2", capability_refs=["case_lookup"]),
        ])
        skill = _make_skill(required_tool_refs=["law_search", "case_lookup"])
        result = resolve_tool_refs(skill, registry)
        self.assertEqual(len(result.resolved_servers), 2)
        self.assertEqual(result.unresolved_refs, [])
        self.assertEqual(result.skill_id, "lawfirm/case_qa")

    def test_resolve_tool_refs_none_resolved(self) -> None:
        """Skill with tool_refs not in any MCP server → resolved empty, unresolved has all."""
        registry = _FakeMcpRegistry([
            _make_server("server-1", capability_refs=["other_tool"]),
        ])
        skill = _make_skill(required_tool_refs=["law_search", "case_lookup"])
        result = resolve_tool_refs(skill, registry)
        self.assertEqual(len(result.resolved_servers), 0)
        self.assertEqual(sorted(result.unresolved_refs), ["case_lookup", "law_search"])

    def test_resolve_tool_refs_partial(self) -> None:
        """Skill with 2 tool_refs, 1 found → 1 resolved server, 1 unresolved."""
        registry = _FakeMcpRegistry([
            _make_server("server-1", capability_refs=["law_search"]),
        ])
        skill = _make_skill(required_tool_refs=["law_search", "case_lookup"])
        result = resolve_tool_refs(skill, registry)
        self.assertEqual(len(result.resolved_servers), 1)
        self.assertEqual(result.resolved_servers[0].server_id, "server-1")
        self.assertEqual(result.unresolved_refs, ["case_lookup"])

    def test_resolve_tool_refs_no_required_tools(self) -> None:
        """Skill with empty required_tool_refs → empty resolved, empty unresolved."""
        registry = _FakeMcpRegistry([
            _make_server("server-1", capability_refs=["law_search"]),
        ])
        skill = _make_skill(required_tool_refs=[])
        result = resolve_tool_refs(skill, registry)
        self.assertEqual(len(result.resolved_servers), 0)
        self.assertEqual(result.unresolved_refs, [])

    def test_resolve_tool_refs_deduplicates_servers(self) -> None:
        """2 tool_refs both on same server → resolved_servers has 1 entry."""
        registry = _FakeMcpRegistry([
            _make_server("server-1", capability_refs=["law_search", "case_lookup"]),
        ])
        skill = _make_skill(required_tool_refs=["law_search", "case_lookup"])
        result = resolve_tool_refs(skill, registry)
        self.assertEqual(len(result.resolved_servers), 1)
        self.assertEqual(result.resolved_servers[0].server_id, "server-1")

    def test_resolve_tool_refs_does_not_modify_skill(self) -> None:
        """skill.required_tool_refs unchanged after call."""
        registry = _FakeMcpRegistry([
            _make_server("server-1", capability_refs=["law_search"]),
        ])
        skill = _make_skill(required_tool_refs=["law_search", "case_lookup"])
        original_refs = list(skill.required_tool_refs)
        resolve_tool_refs(skill, registry)
        self.assertEqual(list(skill.required_tool_refs), original_refs)

    def test_resolve_tool_refs_with_empty_registry(self) -> None:
        """Empty MCP registry → all refs unresolved."""
        registry = _FakeMcpRegistry([])
        skill = _make_skill(required_tool_refs=["law_search"])
        result = resolve_tool_refs(skill, registry)
        self.assertEqual(len(result.resolved_servers), 0)
        self.assertEqual(result.unresolved_refs, ["law_search"])

    def test_tool_resolution_map_is_frozen(self) -> None:
        """ToolResolutionMap is a frozen dataclass."""
        trm = ToolResolutionMap(skill_id="test")
        with self.assertRaises(Exception):
            trm.skill_id = "other"  # type: ignore[misc]

    def test_resolve_tool_refs_preserves_required_tool_refs(self) -> None:
        """result.required_tool_refs matches skill.required_tool_refs."""
        registry = _FakeMcpRegistry([])
        skill = _make_skill(required_tool_refs=["law_search", "case_lookup"])
        result = resolve_tool_refs(skill, registry)
        self.assertEqual(result.required_tool_refs, ["law_search", "case_lookup"])


class ResolveAllToolRefsTests(unittest.TestCase):
    def test_resolve_all_tool_refs_multiple_skills(self) -> None:
        """2 skills → 2 ToolResolutionMap entries."""
        registry = _FakeMcpRegistry([
            _make_server("server-1", capability_refs=["law_search"]),
            _make_server("server-2", capability_refs=["drafting_tool"]),
        ])
        skills = [
            _make_skill(skill_id="skill-1", required_tool_refs=["law_search"]),
            _make_skill(skill_id="skill-2", required_tool_refs=["drafting_tool"]),
        ]
        results = resolve_all_tool_refs(skills, registry)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].skill_id, "skill-1")
        self.assertEqual(results[1].skill_id, "skill-2")
        self.assertEqual(len(results[0].resolved_servers), 1)
        self.assertEqual(len(results[1].resolved_servers), 1)

    def test_resolve_all_tool_refs_empty_skills(self) -> None:
        """Empty list → empty list."""
        registry = _FakeMcpRegistry([])
        results = resolve_all_tool_refs([], registry)
        self.assertEqual(results, [])

    def test_resolve_all_tool_refs_shared_servers(self) -> None:
        """Multiple skills sharing the same tool → each gets the server resolved."""
        registry = _FakeMcpRegistry([
            _make_server("shared-server", capability_refs=["common_tool"]),
        ])
        skills = [
            _make_skill(skill_id="skill-1", required_tool_refs=["common_tool"]),
            _make_skill(skill_id="skill-2", required_tool_refs=["common_tool"]),
        ]
        results = resolve_all_tool_refs(skills, registry)
        self.assertEqual(len(results), 2)
        self.assertEqual(len(results[0].resolved_servers), 1)
        self.assertEqual(len(results[1].resolved_servers), 1)
        self.assertEqual(results[0].resolved_servers[0].server_id, "shared-server")
        self.assertEqual(results[1].resolved_servers[0].server_id, "shared-server")


if __name__ == "__main__":
    unittest.main()
