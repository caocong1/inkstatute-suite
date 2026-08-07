/**
 * Shared SolidJS UI core — single chat UI implementation.
 *
 * @inkstatute/ui-core provides the one implementation of chat-related UI
 * components, extracted from lawyer-desktop. All consumers (apps/web,
 * apps/desktop) import from this package — no second chat UI exists.
 */

export { useTheme } from "./stores/theme";
export type { ThemeVariant } from "./stores/theme";

export {
  reduce,
  initialState,
  traceToolLabel,
  normalizeClarification,
} from "./event-reducer";
export type {
  RenderState,
  ChatMessage,
} from "./event-reducer";

export { createEventStream } from "./stores/eventStream";
export type {
  EventStreamStore,
  EventStreamOptions,
} from "./stores/eventStream";

export { AdapterContext, useAdapters } from "./adapters";
export type {
  FileAdapter,
  DropAdapter,
  DroppedPath,
  AppInfoAdapter,
  UpdateInfo,
  WorkspaceAdapter,
  WorkspaceFile,
  DocumentParser,
  AdapterContextValue,
} from "./adapters";

export { ChatPanel } from "./components/ChatPanel";
export type { ChatPanelProps } from "./components/ChatPanel";

export { ClarificationCard } from "./components/ClarificationCard";
export type { ClarificationCardProps } from "./components/ClarificationCard";

export { DraftingProgressSteps, DRAFTING_STEPS, phaseToActiveIndex, stepState } from "./components/DraftingProgressSteps";
export type { DraftingProgressStepsProps } from "./components/DraftingProgressSteps";

export { MessageFeedback } from "./components/MessageFeedback";
export type { MessageFeedbackProps } from "./components/MessageFeedback";

export { DocDraftingLoader } from "./components/DocDraftingLoader";
export type { DocDraftingLoaderProps } from "./components/DocDraftingLoader";

export { WorkflowProgressSteps, WorkflowNotice, ModeSwitchCard, WorkflowSuggestions } from "./components/WorkflowProgressSteps";
export type { WorkflowProgressStepsProps, ModeSwitchCardProps } from "./components/WorkflowProgressSteps";

// Legal types — ported verbatim from lawyer-desktop/src/types/legal.ts
export type {
  TextSegment,
  DocParty,
  ArticleNote,
  ArticleBlock,
  Article,
  CitationVerification,
  CitationCard,
  CitationAuditItem,
  CitationAudit,
  DocMeta,
  LegalCitation,
  LegalParty,
  LegalClause,
  LegalSection,
  LegalDocumentModel,
  ParseLegalDocumentResponse,
  CitationGroups,
} from "./types/legal";

// Utility functions — ported verbatim from lawyer-desktop/src/utils/
export { renderSegs } from "./utils/renderSegs";
export type { RenderSegsOptions } from "./utils/renderSegs";

export {
  cnNum,
  extractLegalDocumentJson,
  splitMarkdownBlocks,
  modelToParties,
  modelToRecital,
  modelToArticles,
  modelToCitationGroups,
  modelToDocMeta,
  extractDraftOutputEnvelope,
  containsToolLeakage,
  isInstructionLikeTitle,
  sanitizeLlmDocumentContent,
  looksLikeLegalProse,
  isPublishableDocument,
  stripReportPreamble,
  markdownReportTitle,
  markdownToLegalDocument,
} from "./utils/legalDocument";
export type { DraftOutputEnvelope } from "./utils/legalDocument";

export {
  auditToCitationGroups,
  mergeAuditIntoGroups,
  auditSummaryLine,
  auditChecklistMarkdown,
} from "./utils/citationAudit";

export {
  parseTimeMs,
  shouldShowTimeDivider,
  formatTimeDivider,
  formatFullTime,
} from "./utils/chatTime";

export { groupCitations } from "./utils/groupCitations";

export { Icon, Icons } from "./components/Icons";
export type { IconName } from "./components/Icons";

export { CitationPanel } from "./components/CitationPanel";
export type { CitationPanelProps } from "./components/CitationPanel";

export { DocPreview } from "./components/DocPreview";
export type { DocPreviewProps } from "./components/DocPreview";

// Mention components — @-mention autocomplete with WorkspaceAdapter
export { MentionComposer } from "./components/MentionComposer";
export type { MentionComposerProps, MentionComposerApi } from "./components/MentionComposer";
export { MentionMenu } from "./components/MentionMenu";
export type { MentionMenuProps } from "./components/MentionMenu";

// Context ref types — for @-mention candidates
export type { ContextRefPayload } from "./types/contextRefs";

// Mention utility functions
export {
  detectAtTrigger,
  filterMentionCandidates,
  buildMentionInsert,
  isRefMentioned,
  resolveInlineMentions,
  validateMentionPaths,
  serializeEditor,
} from "./utils/mentions";
