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

// Workflow types — used by channel-layer contexts (SessionContext, etc.)
export type {
  ClarificationAnswer,
  ClarificationRequest,
  ClarificationQuestion,
  ClarificationOption,
  WorkflowState,
  WorkflowStep,
  WorkflowStepState,
} from "./types/workflow";

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

// TitleBar — top bar with theme switch, window controls via WindowAdapter
export { TitleBar } from "./components/TitleBar";
export type { TitleBarProps } from "./components/TitleBar";

// HomePage — landing page with greeting, starter prompt, doc type cards
export { HomePage } from "./components/HomePage";
export type { HomePageProps } from "./components/HomePage";

// Doc types — document type cards and icon inference
export { DOC_TYPES, iconForConversationTitle } from "./utils/docTypes";
export type { DocType } from "./utils/docTypes";

// Evidence flow utilities
export { pathToRefAlias, extractDirectoryPaths, mergeDirectoryRefs } from "./utils/evidenceFlow";

// WindowAdapter — for desktop window controls
export type { WindowAdapter } from "./adapters";

// ConversationDrawer — conversation list with search, rename, delete
export { ConversationDrawer } from "./components/ConversationDrawer";
export type { ConversationDrawerProps } from "./components/ConversationDrawer";

// AgentTracePanel — developer trace panel for agent execution visualization
export { AgentTracePanel } from "./components/AgentTracePanel";
export type { AgentTracePanelProps } from "./components/AgentTracePanel";

// Trace store and types
export { useTrace } from "./stores/trace";
export type { Conversation, ConversationStore } from "./types/conversation";
export type { TraceKind, AgentTraceEvent, TraceUsage, TraceEntry, TraceTurn } from "./types/trace";

// JSON syntax highlighting utility
export { highlightJson, looksLikeJson, prettyJson } from "./utils/jsonHighlight";

// Conversation title validation
export { validateConversationTitle, CONVERSATION_TITLE_MIN, CONVERSATION_TITLE_MAX } from "./utils/conversationTitle";

// Arena UI — multi-agent arena workflow creator + parallel stream panel (UI-01/UI-02)
export { ArenaWorkflowCreator, ARENA_MODES, clampMaxRounds } from "./components/ArenaWorkflowCreator";
export type { ArenaWorkflowCreatorProps, ArenaModeOption } from "./components/ArenaWorkflowCreator";
