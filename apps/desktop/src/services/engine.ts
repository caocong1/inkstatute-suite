/**
 * Engine service — single module for all engine interactions.
 *
 * Wraps Tauri commands and the `inkstatute://run-event` event channel.
 * Components and contexts should NEVER call `invoke` directly — all
 * engine access goes through this module.
 */
import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import type { RunEventEnvelope } from "@inkstatute/platform-sdk-ts/events";

// --- Engine status ---

export interface EngineStatus {
  running: boolean;
  engine_version: string;
  agent_name: string;
  failure: string;
}

export const RUN_EVENT = "inkstatute://run-event";

export async function engineStart(): Promise<EngineStatus> {
  return invoke<EngineStatus>("engine_start");
}

export async function engineStatus(): Promise<EngineStatus> {
  return invoke<EngineStatus>("engine_status");
}

export async function engineSend(conversationId: string, text: string): Promise<void> {
  await invoke("engine_send", { conversationId, text });
}

export async function engineCancel(conversationId: string): Promise<void> {
  await invoke("engine_cancel", { conversationId });
}

export async function engineRespondPermission(requestId: number, allow: boolean): Promise<void> {
  await invoke("engine_respond_permission", { requestId, allow });
}

// --- Event subscription ---

/** Subscribe to engine run events. Returns an unlisten function. */
export async function onRunEvent(handler: (e: RunEventEnvelope) => void): Promise<UnlistenFn> {
  return listen<RunEventEnvelope>(RUN_EVENT, (event) => {
    handler(event.payload);
  });
}

// --- History plane (Phase 124-02 read-only commands) ---

export interface SessionSummary {
  session_id: string;
  title: string | null;
  message_count: number;
  started_at: string | null;
  last_active_at: string | null;
}

export interface SearchHit {
  session_id: string;
  seq: number;
  role: string;
  content: string;
  snippet: string | null;
  title: string | null;
  occurred_at: string | null;
}

export async function listConversations(limit = 50, offset = 0): Promise<SessionSummary[]> {
  return invoke<SessionSummary[]>("list_conversations", { limit, offset });
}

export async function searchConversations(query: string, limit = 20): Promise<SearchHit[]> {
  return invoke<SearchHit[]>("search_conversations", { query, limit });
}

export async function getConversationDocs(sessionId: string): Promise<SearchHit[]> {
  return invoke<SearchHit[]>("get_conversation_docs", { sessionId });
}
