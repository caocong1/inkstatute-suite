"""E2E test: track-changes docx generation through the full turn loop.

Exercises the complete pipeline: FixtureProvider calls generate_review_docx
through the dispatching executor, which imports TrackChangesBuilder, generates
a docx with native Word track changes, and emits artifact.created.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from lxml import etree

from platform_contract.enums import ArtifactKind, RunEventType
from platform_contract.events import RunEvent

from inkstatute_agent_core.config import AgentCoreConfig
from inkstatute_agent_core.event_emitter import EventEmitter
from inkstatute_agent_core.fixtures import FixtureProvider, TurnScript
from inkstatute_agent_core.model.provider import ContentDelta, FinishDelta, ToolCallDelta
from inkstatute_agent_core.tools.builtin_registry import create_builtin_registry
from inkstatute_agent_core.tools.executor import create_dispatching_executor
from inkstatute_agent_core.turn_loop import run_turn

from fixtures.mcp_law_fixtures import LAW_FIXTURE_RESPONSES

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _create_minimal_docx(path: Path, paragraphs: list[str]) -> None:
    """Create a minimal .docx with the given paragraphs."""
    try:
        from docx import Document

        doc = Document()
        for text in paragraphs:
            doc.add_paragraph(text)
        doc.save(str(path))
        return
    except ImportError:
        pass

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


async def _collect_events(gen) -> list[RunEvent]:
    events: list[RunEvent] = []
    async for event in gen:
        events.append(event)
    return events


@unittest.skipUnless(
    os.path.isfile(os.path.expanduser(
        "~/workspace/lawfirm-profile/scripts/contract_review_trackchanges.py"
    )),
    "TrackChangesBuilder script not available",
)
class TestE2ETrackChanges(unittest.TestCase):
    """Track-changes docx e2e: full pipeline through the turn loop."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name) / "workspace"
        self.root.mkdir()

        self.input_docx = self.root / "input_contract.docx"
        _create_minimal_docx(
            self.input_docx,
            ["根据《中华人民共和国合同法》的规定，双方签订本合同。"],
        )
        self.output_docx = self.root / "output" / "reviewed.docx"

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_trackchanges_e2e_pipeline(self) -> None:
        """Full pipeline: LLM calls generate_review_docx → docx generated → artifact.created."""
        review_items_json = (
            '[{"id": 1, "find_text": "根据《中华人民共和国", '
            '"old_text": "根据《中华人民共和国合同法》的规定", '
            '"new_text": "根据《中华人民共和国民法典》的规定", '
            '"comment": "合同法已废止", "level": "P0"}]'
        )

        script: list[TurnScript] = [
            TurnScript(deltas=[
                ToolCallDelta(
                    tool_call_id="call_1",
                    tool_name="generate_review_docx",
                    arguments=(
                        '{"input_docx_path": "' + str(self.input_docx) + '", '
                        '"review_items": ' + review_items_json + ', '
                        '"output_path": "' + str(self.output_docx) + '"}'
                    ),
                ),
                FinishDelta(finish_reason="tool_calls"),
            ]),
            TurnScript(deltas=[
                ContentDelta(content="修订版已生成。"),
                FinishDelta(finish_reason="stop"),
            ]),
        ]

        provider = FixtureProvider(script)
        config = AgentCoreConfig()
        emitter = EventEmitter("run-trackchanges-e2e", config)

        registry = create_builtin_registry(
            sandbox_roots=[str(self.root)],
            emitter=emitter,
            fixture_responses=LAW_FIXTURE_RESPONSES,
        )
        executor = create_dispatching_executor(registry)

        events = asyncio.new_event_loop().run_until_complete(
            _collect_events(run_turn(
                messages=[{"role": "user", "content": "审查合同并生成修订版"}],
                tools=registry.get_tool_definitions(),
                provider=provider,
                emitter=emitter,
                config=config,
                tool_executor=executor,
                run_id="run-trackchanges-e2e",
            ))
        )

        # Tool call events
        tool_started = [e for e in events if e.event_type == RunEventType.TOOL_CALL_STARTED_V3]
        tool_completed = [e for e in events if e.event_type == RunEventType.TOOL_CALL_COMPLETED_V3]
        self.assertEqual(len(tool_started), 1)
        self.assertEqual(tool_started[0].payload.get("tool_name"), "generate_review_docx")
        self.assertEqual(len(tool_completed), 1)
        self.assertEqual(tool_completed[0].payload.get("status"), "succeeded")

        # Artifact.created event
        artifact_events = [e for e in events if e.event_type == RunEventType.ARTIFACT_CREATED_V3]
        self.assertEqual(len(artifact_events), 1)
        artifact = artifact_events[0].payload["artifact"]
        self.assertEqual(artifact["kind"], ArtifactKind.TRACKCHANGES_DOCX)
        self.assertTrue(artifact["uri"].startswith("file://"))
        self.assertIn("artifact_id", artifact)

        # Output docx exists and is valid
        self.assertTrue(self.output_docx.is_file())
        self.assertTrue(zipfile.is_zipfile(str(self.output_docx)))

        # OOXML track-changes markers present
        with zipfile.ZipFile(str(self.output_docx), "r") as z:
            doc_xml = z.read("word/document.xml")
        tree = etree.fromstring(doc_xml)
        ins_elements = tree.findall(f".//{{{W_NS}}}ins")
        del_elements = tree.findall(f".//{{{W_NS}}}del")
        self.assertGreater(len(ins_elements), 0, "No <w:ins> elements")
        self.assertGreater(len(del_elements), 0, "No <w:del> elements")

        # No raw docx content in the artifact event (reference-first)
        artifact_str = str(artifact_events[0].payload)
        self.assertNotIn("word/document.xml", artifact_str)

        # Run succeeded
        run_state = [e for e in events if e.event_type == RunEventType.RUN_STATE_CHANGED]
        self.assertEqual(run_state[-1].payload["status"], "succeeded")


if __name__ == "__main__":
    unittest.main()
