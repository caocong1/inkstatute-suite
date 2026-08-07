/**
 * upload.test.ts — tests for the uploadFile utility.
 *
 * Verifies:
 * - uploadFile calls gateway.upload with file data
 * - uploadFile returns an attachment ref with correct fields
 * - uploadFile throws on gateway error with "文件上传失败，请重试"
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const { mockGateway } = vi.hoisted(() => ({
  mockGateway: {
    upload: vi.fn(),
  },
}));

vi.mock("../src/config/gateway", () => ({
  gateway: mockGateway,
}));

import { uploadFile } from "../src/lib/upload";

describe("uploadFile", () => {
  beforeEach(() => {
    mockGateway.upload.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls gateway.upload with file data", async () => {
    mockGateway.upload.mockResolvedValue({
      upload_id: "upload-1",
      payload_ref: "ref://default/conv-1/upload-1/payload",
      content_ref: "ref://default/conv-1/upload-1/content",
      filename: "doc.pdf",
      mime_type: "application/pdf",
    });

    const file = new File(["test content"], "doc.pdf", { type: "application/pdf" });
    await uploadFile(file);

    expect(mockGateway.upload).toHaveBeenCalledTimes(1);
    const body = mockGateway.upload.mock.calls[0][0];
    expect(body.filename).toBe("doc.pdf");
    expect(body.mime_type).toBe("application/pdf");
    expect(typeof body.content).toBe("string");
    expect(body.content.length).toBeGreaterThan(0);
  });

  it("returns an attachment ref with correct fields", async () => {
    mockGateway.upload.mockResolvedValue({
      upload_id: "upload-1",
      payload_ref: "ref://default/conv-1/upload-1/payload",
      content_ref: "ref://default/conv-1/upload-1/content",
      filename: "doc.pdf",
      mime_type: "application/pdf",
    });

    const file = new File(["test content"], "doc.pdf", { type: "application/pdf" });
    const result = await uploadFile(file);

    expect(result.attachment_id).toBe("upload-1");
    expect(result.kind).toBe("pdf");
    expect(result.uri).toBe("ref://default/conv-1/upload-1/payload");
    expect(result.name).toBe("doc.pdf");
    expect(result.mime_type).toBe("application/pdf");
  });

  it("throws on gateway error with 文件上传失败，请重试", async () => {
    mockGateway.upload.mockRejectedValue(new Error("network error"));

    const file = new File(["test content"], "doc.pdf", { type: "application/pdf" });

    await expect(uploadFile(file)).rejects.toThrow("文件上传失败，请重试");
  });
});
