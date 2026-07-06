"""Tests for FileUploadHandler — reference-only storage, no raw payloads."""

from __future__ import annotations

import unittest

from lawyer_web_chat.upload import FileUploadHandler


class FileUploadHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.handler = FileUploadHandler()

    def test_handle_upload_returns_references(self) -> None:
        result = self.handler.handle_upload(
            filename="contract.pdf",
            content_bytes=b"some content",
            mime_type="application/pdf",
            tenant_id="tenant-1",
            conversation_id="conv-1",
        )
        self.assertIsNotNone(result.upload_id)
        self.assertIsNotNone(result.payload_ref)
        self.assertIsNotNone(result.content_ref)
        self.assertIn("tenant-1", result.payload_ref)
        self.assertIn("conv-1", result.content_ref)

    def test_handle_upload_does_not_store_raw_content(self) -> None:
        result = self.handler.handle_upload(
            filename="secret.txt",
            content_bytes=b"SECRET LEGAL CONTENT",
            mime_type="text/plain",
            tenant_id="tenant-1",
            conversation_id="conv-1",
        )
        # The result should not contain raw content
        self.assertNotIn("SECRET LEGAL CONTENT", result.payload_ref)
        self.assertNotIn("SECRET LEGAL CONTENT", result.content_ref)
        self.assertNotIn("SECRET LEGAL CONTENT", result.metadata)
        # Only the hash is stored
        self.assertEqual(len(result.content_hash), 64)  # SHA-256 hex

    def test_handle_upload_sanitizes_filename(self) -> None:
        result = self.handler.handle_upload(
            filename="../../../etc/passwd",
            content_bytes=b"content",
            mime_type="text/plain",
            tenant_id="tenant-1",
            conversation_id="conv-1",
        )
        self.assertEqual(result.filename, "passwd")
        self.assertNotIn("..", result.filename)
        self.assertNotIn("/", result.filename)

    def test_handle_upload_records_size(self) -> None:
        content = b"x" * 1024
        result = self.handler.handle_upload(
            filename="test.bin",
            content_bytes=content,
            mime_type="application/octet-stream",
            tenant_id="tenant-1",
            conversation_id="conv-1",
        )
        self.assertEqual(result.size_bytes, 1024)

    def test_handle_upload_metadata_is_reference_only(self) -> None:
        result = self.handler.handle_upload(
            filename="doc.pdf",
            content_bytes=b"content",
            mime_type="application/pdf",
            tenant_id="tenant-1",
            conversation_id="conv-1",
        )
        self.assertTrue(result.metadata["reference_only"])
        self.assertTrue(result.metadata["no_raw_content_stored"])

    def test_get_upload_by_id(self) -> None:
        result = self.handler.handle_upload(
            filename="test.txt",
            content_bytes=b"content",
            mime_type="text/plain",
            tenant_id="tenant-1",
            conversation_id="conv-1",
        )
        retrieved = self.handler.get_upload(result.upload_id)
        self.assertIsNotNone(retrieved)
        assert retrieved is not None
        self.assertEqual(retrieved.upload_id, result.upload_id)

    def test_get_nonexistent_upload_returns_none(self) -> None:
        result = self.handler.get_upload("nonexistent")
        self.assertIsNone(result)

    def test_list_uploads_for_conversation(self) -> None:
        for i in range(3):
            self.handler.handle_upload(
                filename=f"file-{i}.txt",
                content_bytes=b"content",
                mime_type="text/plain",
                tenant_id="tenant-1",
                conversation_id="conv-1",
            )
        self.handler.handle_upload(
            filename="other.txt",
            content_bytes=b"content",
            mime_type="text/plain",
            tenant_id="tenant-1",
            conversation_id="conv-2",
        )
        uploads = self.handler.list_uploads("conv-1")
        self.assertEqual(len(uploads), 3)

    def test_content_hash_is_deterministic(self) -> None:
        content = b"same content"
        r1 = self.handler.handle_upload(
            filename="a.txt",
            content_bytes=content,
            mime_type="text/plain",
            tenant_id="t1",
            conversation_id="c1",
        )
        r2 = self.handler.handle_upload(
            filename="b.txt",
            content_bytes=content,
            mime_type="text/plain",
            tenant_id="t2",
            conversation_id="c2",
        )
        self.assertEqual(r1.content_hash, r2.content_hash)


if __name__ == "__main__":
    unittest.main()
