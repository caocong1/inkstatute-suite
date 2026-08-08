"""Verification test — checks generated docx has native Word track changes markers.

This test verifies CORE-03's requirement that "产出的 docx 在 Word 中显示为
原生修订标记" — the OOXML elements that Word interprets as native track
changes are present:

- ``<w:ins>`` elements (insertions) with ``w:author`` and ``w:date``
- ``<w:del>`` elements (deletions) with ``w:author`` and ``w:date``
- ``<w:delText>`` elements (deleted text, converted from ``<w:t>``)
- ``word/comments.xml`` part exists in the zip
- ``<w:comment>`` elements in ``comments.xml``
- ``<w:commentRangeStart>`` / ``<w:commentRangeEnd>`` / ``<w:commentReference>``
- ``[Content_Types].xml`` has an ``Override`` for ``comments.xml``
- ``word/_rels/document.xml.rels`` has a ``Relationship`` targeting ``comments.xml``
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from lxml import etree

from inkstatute_agent_core.event_emitter import EventEmitter
from inkstatute_agent_core.tools.document_generate import (
    DEFAULT_TRACKCHANGES_SCRIPT_PATH,
    create_document_generate_tool,
)
from inkstatute_agent_core.tools.path_sandbox import PathSandbox

from platform_contract.enums import ArtifactKind, RunEventType

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


# ---------------------------------------------------------------------------
# Inlined test helpers (shared with test_document_generate_tool.py)
# ---------------------------------------------------------------------------


def _create_minimal_docx(path: Path, paragraphs: list[str]) -> None:
    """Create a minimal .docx file with the given paragraphs."""
    try:
        from docx import Document

        doc = Document()
        for para_text in paragraphs:
            doc.add_paragraph(para_text)
        doc.save(str(path))
        return
    except ImportError:
        pass
    _create_minimal_docx_manual(path, paragraphs)


def _create_minimal_docx_manual(path: Path, paragraphs: list[str]) -> None:
    """Build a minimal .docx from raw OOXML parts."""
    paras_xml = ""
    for text in paragraphs:
        paras_xml += f'<w:p><w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'

    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<w:body>
{paras_xml}
</w:body>
</w:document>"""

    content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

    rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

    styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
</w:styles>"""

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


@unittest.skipUnless(
    os.path.isfile(DEFAULT_TRACKCHANGES_SCRIPT_PATH),
    "TrackChangesBuilder script not available",
)
class TestTrackChangesVerification(unittest.TestCase):
    """Verify the generated docx contains native Word track changes OOXML elements."""

    def setUp(self) -> None:
        """Create a temporary workspace with a known input docx."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name) / "workspace"
        self.root.mkdir()

        # Create a minimal input docx with known text for review items to match
        self.input_docx = self.root / "trackchanges_input.docx"
        _create_minimal_docx(
            self.input_docx,
            [
                "根据《中华人民共和国合同法》的规定，双方签订本技术开发委托合同。",
                "每逾期一日按合同总额1%向甲方支付违约金，逾期超过10日，甲方有权解除合同。",
                "本合同适用中华人民共和国法律，争议由甲方所在地法院管辖。",
            ],
        )

        self.output_docx = self.root / "output" / "trackchanges_output.docx"

        self.sandbox = PathSandbox([self.root])
        self.emitter = RecordingEmitter("test-run-trackchanges-verify")
        self.handler = create_document_generate_tool(
            self.sandbox,
            self.emitter,
            script_path=DEFAULT_TRACKCHANGES_SCRIPT_PATH,
        )

        # Review items that will produce ins, del, and comment elements
        self.review_items = [
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
                "find_text": "每逾期一日按合同总额",
                "old_text": "每逾期一日按合同总额1%向甲方支付违约金",
                "new_text": "每逾期一日按合同总额万分之五向甲方支付违约金",
                "comment": "【P0】违约金过高，建议降至万分之五",
                "level": "P0",
            },
            {
                "id": 3,
                "find_text": "本合同适用中华人民共和国法律",
                "old_text": None,
                "new_text": None,
                "comment": "【P1】建议增加仲裁条款作为争议解决方式",
                "level": "P1",
            },
        ]

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _run(self, coro):
        return asyncio.new_event_loop().run_until_complete(coro)

    def _generate_docx(self) -> Path:
        """Run the document_generate tool and return the output docx path."""
        result = self._run(self.handler({
            "input_docx_path": str(self.input_docx),
            "review_items": self.review_items,
            "output_path": str(self.output_docx),
        }))
        self.assertIsNone(result.error, f"Tool returned error: {result.error}")
        self.assertTrue(self.output_docx.is_file())
        return self.output_docx

    def _read_zip_part(self, zip_path: Path, part_name: str) -> bytes:
        """Read a part from a docx zip file."""
        with zipfile.ZipFile(str(zip_path), "r") as z:
            return z.read(part_name)

    # ------------------------------------------------------------------
    # Zip validity
    # ------------------------------------------------------------------

    def test_output_is_valid_zip(self) -> None:
        """The output docx should be a valid zip file."""
        output = self._generate_docx()
        self.assertTrue(zipfile.is_zipfile(str(output)))

    def test_output_contains_document_xml(self) -> None:
        """The output docx should contain word/document.xml."""
        output = self._generate_docx()
        with zipfile.ZipFile(str(output), "r") as z:
            names = z.namelist()
            self.assertIn("word/document.xml", names)

    # ------------------------------------------------------------------
    # w:ins elements (insertions)
    # ------------------------------------------------------------------

    def test_document_contains_ins_elements(self) -> None:
        """word/document.xml should contain <w:ins> elements."""
        output = self._generate_docx()
        doc_bytes = self._read_zip_part(output, "word/document.xml")
        tree = etree.fromstring(doc_bytes)
        ins_elements = tree.findall(f".//{{{W_NS}}}ins")
        self.assertGreater(len(ins_elements), 0, "No <w:ins> elements found")

    def test_ins_elements_have_author_and_date(self) -> None:
        """<w:ins> elements should have w:author and w:date attributes."""
        output = self._generate_docx()
        doc_bytes = self._read_zip_part(output, "word/document.xml")
        tree = etree.fromstring(doc_bytes)
        ins_elements = tree.findall(f".//{{{W_NS}}}ins")
        for ins in ins_elements:
            author = ins.get(f"{{{W_NS}}}author")
            date = ins.get(f"{{{W_NS}}}date")
            self.assertIsNotNone(author, "w:ins missing w:author")
            self.assertIsNotNone(date, "w:ins missing w:date")

    # ------------------------------------------------------------------
    # w:del elements (deletions)
    # ------------------------------------------------------------------

    def test_document_contains_del_elements(self) -> None:
        """word/document.xml should contain <w:del> elements."""
        output = self._generate_docx()
        doc_bytes = self._read_zip_part(output, "word/document.xml")
        tree = etree.fromstring(doc_bytes)
        del_elements = tree.findall(f".//{{{W_NS}}}del")
        self.assertGreater(len(del_elements), 0, "No <w:del> elements found")

    def test_del_elements_have_author_and_date(self) -> None:
        """<w:del> elements should have w:author and w:date attributes."""
        output = self._generate_docx()
        doc_bytes = self._read_zip_part(output, "word/document.xml")
        tree = etree.fromstring(doc_bytes)
        del_elements = tree.findall(f".//{{{W_NS}}}del")
        for del_elem in del_elements:
            author = del_elem.get(f"{{{W_NS}}}author")
            date = del_elem.get(f"{{{W_NS}}}date")
            self.assertIsNotNone(author, "w:del missing w:author")
            self.assertIsNotNone(date, "w:del missing w:date")

    # ------------------------------------------------------------------
    # w:delText elements
    # ------------------------------------------------------------------

    def test_document_contains_delText_elements(self) -> None:
        """word/document.xml should contain <w:delText> elements (deleted text)."""
        output = self._generate_docx()
        doc_bytes = self._read_zip_part(output, "word/document.xml")
        tree = etree.fromstring(doc_bytes)
        del_text_elements = tree.findall(f".//{{{W_NS}}}delText")
        self.assertGreater(len(del_text_elements), 0, "No <w:delText> elements found")

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    def test_comments_xml_exists(self) -> None:
        """The output docx should contain word/comments.xml."""
        output = self._generate_docx()
        with zipfile.ZipFile(str(output), "r") as z:
            names = z.namelist()
            self.assertIn("word/comments.xml", names)

    def test_comments_xml_contains_comment_elements(self) -> None:
        """word/comments.xml should contain <w:comment> elements."""
        output = self._generate_docx()
        comments_bytes = self._read_zip_part(output, "word/comments.xml")
        tree = etree.fromstring(comments_bytes)
        comment_elements = tree.findall(f".//{{{W_NS}}}comment")
        self.assertGreater(len(comment_elements), 0, "No <w:comment> elements found")

    def test_document_contains_comment_range_markers(self) -> None:
        """word/document.xml should contain commentRangeStart, commentRangeEnd, commentReference."""
        output = self._generate_docx()
        doc_bytes = self._read_zip_part(output, "word/document.xml")
        tree = etree.fromstring(doc_bytes)

        range_starts = tree.findall(f".//{{{W_NS}}}commentRangeStart")
        range_ends = tree.findall(f".//{{{W_NS}}}commentRangeEnd")
        references = tree.findall(f".//{{{W_NS}}}commentReference")

        self.assertGreater(len(range_starts), 0, "No <w:commentRangeStart> elements")
        self.assertGreater(len(range_ends), 0, "No <w:commentRangeEnd> elements")
        self.assertGreater(len(references), 0, "No <w:commentReference> elements")

    # ------------------------------------------------------------------
    # Content Types and Rels
    # ------------------------------------------------------------------

    def test_content_types_has_comments_override(self) -> None:
        """[Content_Types].xml should have an Override for /word/comments.xml."""
        output = self._generate_docx()
        ct_bytes = self._read_zip_part(output, "[Content_Types].xml")
        ct_tree = etree.fromstring(ct_bytes)
        # Find Override elements with PartName="/word/comments.xml"
        ct_ns = "http://schemas.openxmlformats.org/package/2006/content-types"
        overrides = ct_tree.findall(f".//{{{ct_ns}}}Override")
        comments_override = [
            o for o in overrides
            if o.get("PartName") == "/word/comments.xml"
        ]
        self.assertGreater(len(comments_override), 0, "No Override for /word/comments.xml")

    def test_rels_has_comments_relationship(self) -> None:
        """word/_rels/document.xml.rels should have a Relationship targeting comments.xml."""
        output = self._generate_docx()
        rels_bytes = self._read_zip_part(output, "word/_rels/document.xml.rels")
        rels_tree = etree.fromstring(rels_bytes)
        # Find Relationship elements with Target="comments.xml"
        rels_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
        relationships = rels_tree.findall(f".//{{{rels_ns}}}Relationship")
        comments_rels = [
            r for r in relationships
            if r.get("Target") == "comments.xml"
        ]
        self.assertGreater(len(comments_rels), 0, "No Relationship targeting comments.xml")

    # ------------------------------------------------------------------
    # Reviewer author
    # ------------------------------------------------------------------

    def test_default_reviewer_in_output(self) -> None:
        """The default reviewer '乙方律师审查' should appear in the output docx."""
        output = self._generate_docx()
        doc_bytes = self._read_zip_part(output, "word/document.xml")
        doc_str = doc_bytes.decode("utf-8")
        self.assertIn("乙方律师审查", doc_str)

    # ------------------------------------------------------------------
    # Artifact event
    # ------------------------------------------------------------------

    def test_artifact_kind_is_trackchanges_docx(self) -> None:
        """The artifact.created event should have kind=trackchanges_docx."""
        self._generate_docx()
        artifact_events = [
            e for e in self.emitter.events
            if e.event_type == RunEventType.ARTIFACT_CREATED_V3
        ]
        self.assertEqual(len(artifact_events), 1)
        artifact = artifact_events[0].payload["artifact"]
        self.assertEqual(artifact["kind"], ArtifactKind.TRACKCHANGES_DOCX)

    def test_artifact_uri_is_file_reference(self) -> None:
        """The artifact URI should be a file:// reference (no raw content in events)."""
        self._generate_docx()
        artifact_events = [
            e for e in self.emitter.events
            if e.event_type == RunEventType.ARTIFACT_CREATED_V3
        ]
        artifact = artifact_events[0].payload["artifact"]
        self.assertTrue(artifact["uri"].startswith("file://"))


if __name__ == "__main__":
    unittest.main()
