/**
 * Desktop DocumentParser — client-side legal document parsing.
 *
 * Uses ui-core's extractLegalDocumentJson() + markdownToLegalDocument()
 * utilities to parse legal document content. Same implementation as web —
 * the desktop app has no local Rust parser for this.
 */
import {
  extractLegalDocumentJson,
  markdownToLegalDocument,
} from "@inkstatute/ui-core";
import type { DocumentParser, LegalDocumentModel } from "@inkstatute/ui-core";

export const desktopDocumentParser: DocumentParser = {
  async parseLegalDocument(rawJson: string): Promise<LegalDocumentModel> {
    const jsonText = extractLegalDocumentJson(rawJson);
    if (jsonText) {
      const doc = markdownToLegalDocument(jsonText);
      if (doc) return doc;
    }
    const doc = markdownToLegalDocument(rawJson);
    if (doc) return doc;
    // Return a minimal model if parsing fails
    return {
      title: "解析失败",
      sections: [],
    };
  },
};
