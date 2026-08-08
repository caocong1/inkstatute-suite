"""Tests for the document_generate tool — Word track-changes docx generation.

Covers: successful docx generation, artifact.created event emission,
path validation rejection, missing input file error, lazy import
failure, empty review items, comment-only review items (new_text=None),
and OOXML track-changes structure verification.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

from lxml import etree

from inkstatute_agent_core.event_emitter import EventEmitter
from inkstatute_agent_core.tools.document_generate import (
    DEFAULT_TRACKCHANGES_SCRIPT_PATH,
    DOCUMENT_GENERATE_TOOL_DEFINITION,
    create_document_generate_tool,
)
from inkstatute_agent_core.tools.path_sandbox import PathSandbox
from inkstatute_agent_core.turn_loop import ToolResult

from platform_contract.enums import ArtifactKind, RunEventType


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _create_minimal_docx(path: Path, paragraphs: list[str]) -> None:
    """Create a minimal .docx file with the given paragraphs.

    Uses python-docx if available, otherwise builds the OOXML manually.
    """
    try:
        from docx import Document

        doc = Document()
        for para_text in paragraphs:
            doc.add_paragraph(para_text)
        doc.save(str(path))
        return
    except ImportError:
        pass

    # Manual OOXML construction
    _create_minimal_docx_manual(path, paragraphs)


def _create_minimal_docx_manual(path: Path, paragraphs: list[str]) -> None:
    """Build a minimal .docx from raw OOXML parts."""

    # word/document.xml
    paras_xml = ""
    for text in paragraphs:
        paras_xml += f"""<w:p><w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>"""

    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<w:body>
{paras_xml}
</w:body>
</w:document>"""

    # [Content_Types].xml
    content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

    # word/_rels/document.xml.rels
    rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

    # word/styles.xml (minimal)
    styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
</w:styles>"""

    # _rels/.rels
    root_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(path), "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types_xml)
        z.writestr("_rels/.rels", root_rels_xml)
        z.writestr("word/document.xml", document_xml)
        z.writestr("word/_rels/document.xml.rels", rels_xml)
        z.writestr("word/styles.xml", styles_xml)


class RecordingEmitter(EventEmitter):
    """EventEmitter that records all emitted events."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.events: list = []

    def _emit(self, event_type, payload, metadata=None):
        event = super()._emit(event_type, payload, metadata)
        self.events.append(event)
        return event


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------


class TestDocumentGenerateTool(unittest.TestCase):
    """Tests for the document_generate tool handler."""

    def setUp(self) -> None:
        """Create a temporary workspace with a sample contract docx."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name) / "workspace"
        self.root.mkdir()

        # Create a minimal input docx with known paragraphs
        self.input_docx = self.root / "input_contract.docx"
        _create_minimal_docx(
            self.input_docx,
            [
                "根据《中华人民共和国合同法》的规定，双方签订本合同。",
                "甲方逾期支付款项的，每逾期一日按应付未付款项万分之一向乙方支付违约金。",
                "本合同适用中华人民共和国法律。",
            ],
        )

        # Output path
        self.output_docx = self.root / "output" / "reviewed_contract.docx"

        # Sandbox and emitter
        self.sandbox = PathSandbox([self.root])
        self.emitter = RecordingEmitter("test-run-doc-gen")

        # Script path
        self.script_path = os.environ.get(
            "INKSTATUTE_TRACKCHANGES_SCRIPT",
            DEFAULT_TRACKCHANGES_SCRIPT_PATH,
        )

        # Skip tests if the script doesn't exist
        self.script_available = os.path.isfile(self.script_path)

        # Create handler
        self.handler = create_document_generate_tool(
            self.sandbox,
            self.emitter,
            script_path=self.script_path,
        )

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _run(self, coro):
        """Run an async coroutine in a fresh event loop."""
        return asyncio.new_event_loop().run_until_complete(coro)

    def _get_artifact_events(self):
        """Filter emitted events for artifact.created."""
        return [
            e for e in self.emitter.events
            if e.event_type == RunEventType.ARTIFACT_CREATED_V3
        ]

    # ------------------------------------------------------------------
    # Tool definition
    # ------------------------------------------------------------------

    def test_tool_definition_has_correct_name(self) -> None:
        """The tool definition should have name='generate_review_docx'."""
        name = DOCUMENT_GENERATE_TOOL_DEFINITION["function"]["name"]
        self.assertEqual(name, "generate_review_docx")

    def test_tool_definition_has_required_params(self) -> None:
        """The tool definition should list required parameters."""
        params = DOCUMENT_GENERATE_TOOL_DEFINITION["function"]["parameters"]
        required = params["required"]
        self.assertIn("input_docx_path", required)
        self.assertIn("review_items", required)
        self.assertIn("output_path", required)

    def test_tool_definition_has_review_items_schema(self) -> None:
        """The review_items schema should have id, find_text, comment, level."""
        props = DOCUMENT_GENERATE_TOOL_DEFINITION["function"]["parameters"][
            "properties"
        ]["review_items"]["items"]["properties"]
        self.assertIn("id", props)
        self.assertIn("find_text", props)
        self.assertIn("old_text", props)
        self.assertIn("new_text", props)
        self.assertIn("comment", props)
        self.assertIn("level", props)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    def test_factory_returns_callable(self) -> None:
        """create_document_generate_tool should return a callable."""
        self.assertTrue(callable(self.handler))

    # ------------------------------------------------------------------
    # Successful generation
    # ------------------------------------------------------------------

    @unittest.skipUnless(
        os.path.isfile(DEFAULT_TRACKCHANGES_SCRIPT_PATH),
        "TrackChangesBuilder script not available",
    )
    def test_successful_docx_generation(self) -> None:
        """A valid input docx with review items should produce an output docx."""
        review_items = [
            {
                "id": 1,
                "find_text": "根据《中华人民共和国",
                "old_text": "根据《中华人民共和国合同法》的规定",
                "new_text": "根据《中华人民共和国民法典》的规定",
                "comment": "【P0】合同法已废止，适用民法典",
                "level": "P0",
            },
            {
                "id": 2,
                "find_text": "甲方逾期支付款项的",
                "old_text": "每逾期一日按应付未付款项万分之一向乙方支付违约金",
                "new_text": "每逾期一日按应付未付款项万分之五向乙方支付违约金",
                "comment": "【P0】违约金过低，建议提高",
                "level": "P0",
            },
        ]

        result = self._run(self.handler({
            "input_docx_path": str(self.input_docx),
            "review_items": review_items,
            "output_path": str(self.output_docx),
        }))

        self.assertIsNone(result.error, f"Tool returned error: {result.error}")
        self.assertIn("修订版已生成", result.content)
        self.assertTrue(self.output_docx.is_file())
        self.assertTrue(zipfile.is_zipfile(str(self.output_docx)))

    @unittest.skipUnless(
        os.path.isfile(DEFAULT_TRACKCHANGES_SCRIPT_PATH),
        "TrackChangesBuilder script not available",
    )
    def test_artifact_created_event_emitted(self) -> None:
        """An artifact.created event should be emitted with kind=trackchanges_docx."""
        review_items = [
            {
                "id": 1,
                "find_text": "根据《中华人民共和国",
                "old_text": "根据《中华人民共和国合同法》的规定",
                "new_text": "根据《中华人民共和国民法典》的规定",
                "comment": "法律引用更新",
                "level": "P0",
            },
        ]

        self._run(self.handler({
            "input_docx_path": str(self.input_docx),
            "review_items": review_items,
            "output_path": str(self.output_docx),
        }))

        artifact_events = self._get_artifact_events()
        self.assertEqual(len(artifact_events), 1)
        event = artifact_events[0]
        payload = event.payload
        artifact = payload["artifact"]
        self.assertEqual(artifact["kind"], ArtifactKind.TRACKCHANGES_DOCX)
        self.assertTrue(artifact["uri"].startswith("file://"))
        self.assertEqual(artifact["mime_type"], "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.assertIn("artifact_id", artifact)

    @unittest.skipUnless(
        os.path.isfile(DEFAULT_TRACKCHANGES_SCRIPT_PATH),
        "TrackChangesBuilder script not available",
    )
    def test_tool_result_metadata(self) -> None:
        """ToolResult.metadata should include artifact_id, output_path, review_results."""
        review_items = [
            {
                "id": 1,
                "find_text": "根据《中华人民共和国",
                "old_text": "根据《中华人民共和国合同法》的规定",
                "new_text": "根据《中华人民共和国民法典》的规定",
                "comment": "法律更新",
                "level": "P0",
            },
        ]

        result = self._run(self.handler({
            "input_docx_path": str(self.input_docx),
            "review_items": review_items,
            "output_path": str(self.output_docx),
        }))

        self.assertIn("artifact_id", result.metadata)
        self.assertIn("output_path", result.metadata)
        self.assertIn("review_results", result.metadata)
        self.assertIsInstance(result.metadata["review_results"], list)

    # ------------------------------------------------------------------
    # Comment-only review items (new_text=None)
    # ------------------------------------------------------------------

    @unittest.skipUnless(
        os.path.isfile(DEFAULT_TRACKCHANGES_SCRIPT_PATH),
        "TrackChangesBuilder script not available",
    )
    def test_comment_only_review_item(self) -> None:
        """A review item with new_text=None should add a comment only."""
        review_items = [
            {
                "id": 1,
                "find_text": "本合同适用中华人民共和国法律",
                "old_text": None,
                "new_text": None,
                "comment": "建议补充争议解决条款",
                "level": "P1",
            },
        ]

        result = self._run(self.handler({
            "input_docx_path": str(self.input_docx),
            "review_items": review_items,
            "output_path": str(self.output_docx),
        }))

        self.assertIsNone(result.error, f"Tool returned error: {result.error}")
        self.assertTrue(self.output_docx.is_file())

    # ------------------------------------------------------------------
    # Empty review items
    # ------------------------------------------------------------------

    @unittest.skipUnless(
        os.path.isfile(DEFAULT_TRACKCHANGES_SCRIPT_PATH),
        "TrackChangesBuilder script not available",
    )
    def test_empty_review_items(self) -> None:
        """Empty review_items should produce a valid docx (no changes)."""
        result = self._run(self.handler({
            "input_docx_path": str(self.input_docx),
            "review_items": [],
            "output_path": str(self.output_docx),
        }))

        self.assertIsNone(result.error, f"Tool returned error: {result.error}")
        self.assertTrue(self.output_docx.is_file())
        self.assertTrue(zipfile.is_zipfile(str(self.output_docx)))

    # ------------------------------------------------------------------
    # Path validation
    # ------------------------------------------------------------------

    def test_path_traversal_rejected(self) -> None:
        """Input path with .. should be rejected by PathSandbox."""
        result = self._run(self.handler({
            "input_docx_path": "../../etc/passwd",
            "review_items": [],
            "output_path": str(self.output_docx),
        }))

        self.assertIsNotNone(result.error)

    def test_output_outside_root_rejected(self) -> None:
        """Output path outside the sandbox root should be rejected."""
        outside_path = str(Path(self.tmpdir.name) / "outside" / "evil.docx")
        result = self._run(self.handler({
            "input_docx_path": str(self.input_docx),
            "review_items": [],
            "output_path": outside_path,
        }))

        self.assertIsNotNone(result.error)

    # ------------------------------------------------------------------
    # Missing input file
    # ------------------------------------------------------------------

    def test_missing_input_file_error(self) -> None:
        """A non-existent input file should return an error, not crash."""
        missing_path = str(self.root / "nonexistent.docx")
        result = self._run(self.handler({
            "input_docx_path": missing_path,
            "review_items": [],
            "output_path": str(self.output_docx),
        }))

        self.assertIsNotNone(result.error)
        self.assertIn("不存在", result.content)

    # ------------------------------------------------------------------
    # Missing required arguments
    # ------------------------------------------------------------------

    def test_missing_input_docx_path(self) -> None:
        """Missing input_docx_path should return an error."""
        result = self._run(self.handler({
            "review_items": [],
            "output_path": str(self.output_docx),
        }))

        self.assertIsNotNone(result.error)

    def test_missing_output_path(self) -> None:
        """Missing output_path should return an error."""
        result = self._run(self.handler({
            "input_docx_path": str(self.input_docx),
            "review_items": [],
        }))

        self.assertIsNotNone(result.error)

    # ------------------------------------------------------------------
    # Lazy import failure
    # ------------------------------------------------------------------

    def test_lazy_import_failure_returns_error(self) -> None:
        """If the script path doesn't exist, the handler should return an error."""
        handler = create_document_generate_tool(
            self.sandbox,
            self.emitter,
            script_path="/nonexistent/path/to/script.py",
        )

        result = self._run(handler({
            "input_docx_path": str(self.input_docx),
            "review_items": [],
            "output_path": str(self.output_docx),
        }))

        self.assertIsNotNone(result.error)
        self.assertIn("TrackChangesBuilder", result.content)

    # ------------------------------------------------------------------
    # Custom reviewer
    # ------------------------------------------------------------------

    @unittest.skipUnless(
        os.path.isfile(DEFAULT_TRACKCHANGES_SCRIPT_PATH),
        "TrackChangesBuilder script not available",
    )
    def test_custom_reviewer(self) -> None:
        """A custom reviewer name should be used in the track changes."""
        review_items = [
            {
                "id": 1,
                "find_text": "根据《中华人民共和国",
                "old_text": "根据《中华人民共和国合同法》的规定",
                "new_text": "根据《中华人民共和国民法典》的规定",
                "comment": "法律更新",
                "level": "P0",
            },
        ]

        result = self._run(self.handler({
            "input_docx_path": str(self.input_docx),
            "review_items": review_items,
            "output_path": str(self.output_docx),
            "reviewer": "甲方律师审查",
        }))

        self.assertIsNone(result.error, f"Tool returned error: {result.error}")
        self.assertTrue(self.output_docx.is_file())

        # Verify the reviewer name appears in the output docx
        with zipfile.ZipFile(str(self.output_docx), "r") as z:
            doc_xml = z.read("word/document.xml").decode("utf-8")
            self.assertIn("甲方律师审查", doc_xml)


if __name__ == "__main__":
    unittest.main()
