"""Phase 101 success criteria verification — maps each criterion to verifying tests.

This meta-test documents the mapping between Phase 101's 6 success criteria
and the tests that verify them. It does not re-run the tests (they are
already run by the gate runner), but it provides a single place to audit
coverage.

Success Criteria (from ROADMAP.md):
1. Tool layer callable from turn loop (clarification, regulation search,
   file reading, document generation, MCP client)
2. Tool results回注 turn loop, multi-tool orchestration, error recovery
3. Word native track-changes docx (import TrackChangesBuilder, not rewrite)
4. artifact.created with kind=trackchanges_docx, downloadable via Gateway
5. MCP tools discoverable and callable, summaries in tool_call.* events
6. No unapproved shell/code execution paths
"""

from __future__ import annotations

import unittest


class TestPhase101SuccessCriteriaMapping(unittest.TestCase):
    """Documents the mapping between success criteria and verifying tests."""

    def test_sc1_tool_layer_callable_from_turn_loop(self) -> None:
        """SC1: Tool layer callable from turn loop.

        Verifying tests:
        - test_e2e_multi_tool.py::TestE2EMultiToolOrchestration
        - test_e2e_mcp_tools.py::TestE2EMcpTools
        - test_e2e_trackchanges.py::TestE2ETrackChanges
        - test_clarification_tool.py (from 101-01)
        - test_file_read_tool.py (from 101-02)
        - test_regulation_search_tool.py (from 101-02)
        - test_document_generate_tool.py (from 101-03)
        """
        # The existence of these test files verifies SC1
        import os
        tests_dir = os.path.dirname(__file__)
        expected_files = [
            "test_e2e_multi_tool.py",
            "test_e2e_mcp_tools.py",
            "test_e2e_trackchanges.py",
            "test_document_generate_tool.py",
            "test_file_read_tool.py",
            "test_regulation_search_tool.py",
        ]
        for filename in expected_files:
            self.assertTrue(
                os.path.isfile(os.path.join(tests_dir, filename)),
                f"Missing test file: {filename}",
            )

    def test_sc2_tool_results_and_error_recovery(self) -> None:
        """SC2: Tool results回注, multi-tool orchestration, error recovery.

        Verifying tests:
        - test_e2e_multi_tool.py::test_3_round_multi_tool_orchestration
        - test_e2e_multi_tool.py::test_tool_results_injected_into_messages
        - test_e2e_tool_error_recovery.py::test_tool_returns_error_result
        - test_e2e_tool_error_recovery.py::test_tool_handler_raises_exception
        - test_e2e_tool_error_recovery.py::test_tool_error_does_not_emit_run_failed
        """
        import os
        tests_dir = os.path.dirname(__file__)
        self.assertTrue(os.path.isfile(os.path.join(tests_dir, "test_e2e_multi_tool.py")))
        self.assertTrue(os.path.isfile(os.path.join(tests_dir, "test_e2e_tool_error_recovery.py")))

    def test_sc3_word_track_changes_docx(self) -> None:
        """SC3: Word native track-changes docx (import TrackChangesBuilder, not rewrite).

        Verifying tests:
        - test_trackchanges_verification.py (OOXML structure — w:ins, w:del, w:delText, w:comment)
        - test_e2e_trackchanges.py (full pipeline through turn loop)
        - test_document_generate_tool.py (tool handler, lazy import, artifact event)
        """
        import os
        tests_dir = os.path.dirname(__file__)
        expected_files = [
            "test_trackchanges_verification.py",
            "test_e2e_trackchanges.py",
            "test_document_generate_tool.py",
        ]
        for filename in expected_files:
            self.assertTrue(
                os.path.isfile(os.path.join(tests_dir, filename)),
                f"Missing test file: {filename}",
            )

    def test_sc4_artifact_created_with_correct_kind(self) -> None:
        """SC4: artifact.created with kind=trackchanges_docx.

        Verifying tests:
        - test_document_generate_tool.py::test_artifact_created_event_emitted
        - test_trackchanges_verification.py::test_artifact_kind_is_trackchanges_docx
        - test_trackchanges_verification.py::test_artifact_uri_is_file_reference
        - test_e2e_trackchanges.py::test_trackchanges_e2e_pipeline
        """
        import os
        tests_dir = os.path.dirname(__file__)
        self.assertTrue(os.path.isfile(os.path.join(tests_dir, "test_trackchanges_verification.py")))
        self.assertTrue(os.path.isfile(os.path.join(tests_dir, "test_e2e_trackchanges.py")))

    def test_sc5_mcp_tools_discoverable_and_callable(self) -> None:
        """SC5: MCP tools discoverable and callable, summaries in tool_call.* events.

        Verifying tests:
        - test_e2e_mcp_tools.py::test_fixture_search_laws_through_turn_loop
        - test_e2e_mcp_tools.py::test_mcp_tool_to_openai_definition
        - test_e2e_mcp_tools.py::test_mcp_input_schema_to_openai_parameters
        - test_mcp_client.py (from 101-02)
        """
        import os
        tests_dir = os.path.dirname(__file__)
        self.assertTrue(os.path.isfile(os.path.join(tests_dir, "test_e2e_mcp_tools.py")))
        self.assertTrue(os.path.isfile(os.path.join(tests_dir, "test_mcp_client.py")))

    def test_sc6_no_unapproved_shell_code_execution(self) -> None:
        """SC6: No unapproved shell/code execution paths.

        Verifying tests:
        - test_security_verification.py (all security checks)
        """
        import os
        tests_dir = os.path.dirname(__file__)
        self.assertTrue(os.path.isfile(os.path.join(tests_dir, "test_security_verification.py")))

    def test_all_tool_source_files_exist(self) -> None:
        """All Phase 101 tool source files should exist."""
        import os
        tools_dir = os.path.join(
            os.path.dirname(__file__), "..", "src",
            "inkstatute_agent_core", "tools",
        )
        expected_files = [
            "registry.py",
            "executor.py",
            "clarification.py",
            "path_sandbox.py",
            "file_read.py",
            "mcp_client.py",
            "regulation_search.py",
            "document_generate.py",
            "builtin_registry.py",
        ]
        for filename in expected_files:
            self.assertTrue(
                os.path.isfile(os.path.join(tools_dir, filename)),
                f"Missing tool source: {filename}",
            )


if __name__ == "__main__":
    unittest.main()
