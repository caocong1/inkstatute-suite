/**
 * upload — file upload utility for the web client.
 *
 * Reads a File via FileReader.readAsArrayBuffer(), converts to base64,
 * and calls gateway.upload() to upload the file reference-first.
 * Returns an AttachmentRef-shaped object for passing to sendMessage().
 */
import { gateway } from "../config/gateway";

export interface UploadedAttachment {
  attachment_id: string;
  kind: string;
  uri: string;
  name: string;
  mime_type: string;
}

/**
 * Convert an ArrayBuffer to a base64 string.
 */
function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

/**
 * Infer the attachment kind from mime_type.
 */
function inferKind(mimeType: string): string {
  if (mimeType.startsWith("image/")) return "image";
  if (mimeType.includes("pdf")) return "pdf";
  if (mimeType.includes("word") || mimeType.includes("docx")) return "docx";
  if (mimeType.includes("text")) return "text";
  return "file";
}

/**
 * Read a File as ArrayBuffer using FileReader (compatible with jsdom).
 */
function readFileAsArrayBuffer(file: File): Promise<ArrayBuffer> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as ArrayBuffer);
    reader.onerror = () => reject(new Error("Failed to read file"));
    reader.readAsArrayBuffer(file);
  });
}

/**
 * Upload a file to the Gateway and return an attachment ref.
 *
 * Reads the file content via FileReader.readAsArrayBuffer(), converts to
 * base64, and calls gateway.upload() with the file metadata + content.
 * The Gateway stores only references (SHA-256 hash + refs), not raw content.
 *
 * On failure, throws an Error with message "文件上传失败，请重试".
 */
export async function uploadFile(file: File): Promise<UploadedAttachment> {
  try {
    const arrayBuffer = await readFileAsArrayBuffer(file);
    const base64Content = arrayBufferToBase64(arrayBuffer);

    const result = await gateway.upload({
      filename: file.name,
      content: base64Content,
      mime_type: file.type || "application/octet-stream",
    }) as {
      upload_id?: string;
      payload_ref?: string;
      content_ref?: string;
      filename?: string;
      mime_type?: string;
    };

    const uploadId = result.upload_id ?? "";
    const uri = result.payload_ref ?? result.content_ref ?? "";
    const mimeType = result.mime_type ?? file.type ?? "application/octet-stream";

    return {
      attachment_id: uploadId,
      kind: inferKind(mimeType),
      uri,
      name: result.filename ?? file.name,
      mime_type: mimeType,
    };
  } catch {
    throw new Error("文件上传失败，请重试");
  }
}
