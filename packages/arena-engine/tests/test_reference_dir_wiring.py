"""Tests for reference_dir wiring in ``mode1._build_run_request`` (Plan 111-05).

Verifies that when ``ArenaWorkflowConfig.reference_dir`` is set:

- reference files are read through ``FSSandbox.read_text_file`` (the
  Phase 106 five-layer path sandbox — never bypassed with raw
  ``open()`` / ``Path.read_text()``),
- file content is sanitized via ``ReferenceSanitizer.sanitize`` and
  appended to the task instruction with clear delimiters,
- path-traversal / symlink-escape attempts are rejected by ``FSSandbox``
  and the arena run continues without that file's content,
- an empty ``reference_dir`` produces no reference content and no crash.

And when ``reference_dir`` is ``None``:

- ``_build_run_request`` behaves exactly as before (no sandbox call,
  instruction equals ``config.task_instruction`` verbatim).
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from platform_contract.arena_contract import ArenaWorkflowConfig

from arena_engine.mode1 import _build_run_request, _collect_reference_context


def _make_config(
    *,
    reference_dir: str | None = None,
    task_instruction: str = "请审查以下合同条款。",
    agent_slots: list[str] | None = None,
) -> ArenaWorkflowConfig:
    return ArenaWorkflowConfig(
        arena_id="arena-test",
        mode="mode1_parallel",
        agent_slots=agent_slots or ["slot1"],
        task_instruction=task_instruction,
        reference_dir=reference_dir,
    )


class TestReferenceDirContentInjected(unittest.TestCase):
    """When ``reference_dir`` is set, sanitized content reaches the RunRequest."""

    def test_reference_dir_content_injected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref_dir = Path(tmp)
            (ref_dir / "note.txt").write_text("test reference content", encoding="utf-8")

            config = _make_config(reference_dir=str(ref_dir))
            req = _build_run_request(config, "slot1")

            # The raw file content must appear inside the instruction,
            # wrapped in the sanitizer delimiters + the arena reference
            # section markers.
            self.assertIn("test reference content", req.turn.content)
            self.assertIn("--- BEGIN REFERENCE CONTENT ---", req.turn.content)
            self.assertIn("--- END REFERENCE CONTENT ---", req.turn.content)
            self.assertIn("--- 参考文件 ---", req.turn.content)
            self.assertIn("--- 参考文件结束 ---", req.turn.content)
            # The original task instruction is preserved.
            self.assertIn(config.task_instruction, req.turn.content)

    def test_reference_dir_path_in_delimiter(self) -> None:
        """The reference file path is recorded in the sanitizer delimiter."""
        with tempfile.TemporaryDirectory() as tmp:
            ref_dir = Path(tmp)
            (ref_dir / "note.txt").write_text("payload", encoding="utf-8")

            config = _make_config(reference_dir=str(ref_dir))
            req = _build_run_request(config, "slot1")

            self.assertIn('<reference_file path="', req.turn.content)
            self.assertIn("note.txt", req.turn.content)


class TestNoReferenceDirNoChange(unittest.TestCase):
    """When ``reference_dir`` is None/empty, behaviour is unchanged."""

    def test_no_reference_dir_no_change(self) -> None:
        config = _make_config(reference_dir=None)
        req = _build_run_request(config, "slot1")
        self.assertEqual(req.turn.content, config.task_instruction)

    def test_empty_reference_dir_string_no_change(self) -> None:
        config = _make_config(reference_dir="")
        req = _build_run_request(config, "slot1")
        self.assertEqual(req.turn.content, config.task_instruction)

    def test_no_sandbox_call_when_reference_dir_none(self) -> None:
        """No FSSandbox is constructed and no read_text_file call is made."""
        with mock.patch(
            "inkstatute_acp_client.fs_sandbox.FSSandbox"
        ) as sandbox_cls, mock.patch(
            "inkstatute_acp_client.sanitizer.ReferenceSanitizer"
        ):
            config = _make_config(reference_dir=None)
            req = _build_run_request(config, "slot1")
            sandbox_cls.assert_not_called()
            self.assertEqual(req.turn.content, config.task_instruction)


class TestFSSandboxActuallyCalled(unittest.TestCase):
    """FSSandbox.read_text_file is the sanctioned read path — assert it is used."""

    def test_fssandbox_read_text_file_called(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref_dir = Path(tmp)
            (ref_dir / "a.txt").write_text("alpha", encoding="utf-8")
            (ref_dir / "b.md").write_text("beta", encoding="utf-8")

            config = _make_config(reference_dir=str(ref_dir))

            # Spy on the real FSSandbox.read_text_file so we can assert
            # it is invoked while still letting it read the files.
            # autospec=True ensures ``self`` is passed so the wrapped
            # unbound method receives a proper bound call.
            from inkstatute_acp_client.fs_sandbox import FSSandbox

            with mock.patch.object(
                FSSandbox,
                "read_text_file",
                autospec=True,
                wraps=FSSandbox.read_text_file,
            ) as spy:
                req = _build_run_request(config, "slot1")

            self.assertGreaterEqual(spy.call_count, 2)
            self.assertIn("alpha", req.turn.content)
            self.assertIn("beta", req.turn.content)


class TestPathTraversalRejected(unittest.TestCase):
    """FSSandbox rejects traversal/symlink escapes; the run continues."""

    def test_traversal_path_rejected_by_sandbox(self) -> None:
        from inkstatute_acp_client.fs_sandbox import FSSandbox, FSSandboxConfig, FSSandboxError

        with tempfile.TemporaryDirectory() as tmp:
            ref_dir = Path(tmp)
            sandbox = FSSandbox(FSSandboxConfig(allowed_root=ref_dir))

            # A path containing ".." is rejected before canonicalization.
            with self.assertRaises(FSSandboxError) as ctx:
                sandbox.validate_path(ref_dir / ".." / "secret.txt")
            self.assertEqual(ctx.exception.reason, "traversal")

    def test_symlink_escape_rejected_and_run_continues(self) -> None:
        """A symlink pointing outside reference_dir is rejected; run continues."""
        from inkstatute_acp_client.fs_sandbox import FSSandboxError

        with tempfile.TemporaryDirectory() as inside, tempfile.TemporaryDirectory() as outside:
            outside_file = Path(outside) / "secret.txt"
            outside_file.write_text("should-not-appear", encoding="utf-8")

            ref_dir = Path(inside)
            link = ref_dir / "escape.txt"
            try:
                os.symlink(outside_file, link)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation not supported on this platform")

            config = _make_config(reference_dir=str(ref_dir))
            # The symlink must be rejected by the sandbox and the run
            # must NOT crash — it proceeds with the task instruction only.
            req = _build_run_request(config, "slot1")

            self.assertNotIn("should-not-appear", req.turn.content)
            # Task instruction is still present.
            self.assertIn(config.task_instruction, req.turn.content)

    def test_collect_reference_context_swallows_sandbox_error(self) -> None:
        """_collect_reference_context catches FSSandboxError and returns gracefully."""
        from inkstatute_acp_client.fs_sandbox import FSSandboxError

        with tempfile.TemporaryDirectory() as tmp:
            ref_dir = Path(tmp)
            (ref_dir / "ok.txt").write_text("good content", encoding="utf-8")

            config = _make_config(reference_dir=str(ref_dir))

            with mock.patch(
                "inkstatute_acp_client.fs_sandbox.FSSandbox.read_text_file",
                side_effect=FSSandboxError("boom", reason="traversal"),
            ):
                result = _collect_reference_context(config)

            # Every file rejected → empty reference section, no crash.
            self.assertEqual(result, "")


class TestEmptyReferenceDir(unittest.TestCase):
    """An empty reference_dir yields no reference content and no crash."""

    def test_empty_reference_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref_dir = Path(tmp)  # no files

            config = _make_config(reference_dir=str(ref_dir))
            req = _build_run_request(config, "slot1")

            self.assertEqual(req.turn.content, config.task_instruction)
            self.assertNotIn("--- 参考文件 ---", req.turn.content)

    def test_reference_dir_only_non_text_files(self) -> None:
        """Binary/unsupported extensions are skipped by the sandbox allowlist."""
        with tempfile.TemporaryDirectory() as tmp:
            ref_dir = Path(tmp)
            (ref_dir / "image.bin").write_bytes(b"\x00\x01\x02")

            config = _make_config(reference_dir=str(ref_dir))
            req = _build_run_request(config, "slot1")

            # No reference content injected; instruction unchanged.
            self.assertEqual(req.turn.content, config.task_instruction)


if __name__ == "__main__":
    unittest.main()
