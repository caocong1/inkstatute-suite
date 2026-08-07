/**
 * invoke() migration verification — static analysis test.
 *
 * Verifies that the desktop app's invoke() migration is complete:
 * - No agent/session/message/skill/document invoke() calls remain
 * - Only desktop-specific Tauri commands are in the allowlist
 * - Gateway HTTP/SSE equivalents are properly wired
 * - SSE event stream is used (not Tauri events)
 * - Only desktop-specific Tauri event listeners remain
 *
 * This test scans the actual source files on disk (not module imports)
 * to ensure the migration is structurally complete.
 */
import { describe, it, expect } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";

/** Recursively collect all .ts and .tsx files in a directory. */
function collectSourceFiles(dir: string): string[] {
  const results: string[] = [];
  if (!fs.existsSync(dir)) return results;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...collectSourceFiles(fullPath));
    } else if (entry.name.endsWith(".ts") || entry.name.endsWith(".tsx")) {
      results.push(fullPath);
    }
  }
  return results;
}

const SRC_DIR = path.resolve(__dirname, "..", "src");

/** Read all source files and return a map of path → content. */
function readAllSources(): Map<string, string> {
  const files = collectSourceFiles(SRC_DIR);
  const map = new Map<string, string>();
  for (const file of files) {
    map.set(file, fs.readFileSync(file, "utf-8"));
  }
  return map;
}

/** Extract all invoke("command_name") calls from source text. */
function extractInvokeCalls(content: string): string[] {
  const calls: string[] = [];
  // Match invoke("command_name") or invoke('command_name')
  const regex = /invoke\s*\(\s*["']([^"']+)["']/g;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(content)) !== null) {
    calls.push(match[1]);
  }
  return calls;
}

/** Extract all listen("event_name") calls from source text. */
function extractListenCalls(content: string): string[] {
  const calls: string[] = [];
  const regex = /listen\s*\(\s*["']([^"']+)["']/g;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(content)) !== null) {
    calls.push(match[1]);
  }
  return calls;
}

/** Desktop-specific Tauri command allowlist (from 94-CONTEXT §2 Category B). */
const DESKTOP_ALLOWLIST = new Set([
  "read_file_content",
  "list_directory",
  "prepare_attachment",
  "classify_dropped_paths",
  "grant_path_access",
  "get_allowed_file_dirs",
  "set_allowed_file_dirs",
  "bind_workspace",
  "get_workspace_index_status",
  "search_workspace",
  "cache_session",
  "cache_run",
  "cache_event",
  "cache_artifact",
  "get_cached_sessions",
  "get_cached_runs",
  "get_cached_events",
  "get_cached_artifact",
  "get_cached_artifacts_by_session",
]);

/** Removed agent/session/message/skill/document/sync commands that must NOT appear. */
const REMOVED_COMMANDS = [
  "send_message",
  "classify_agent_mode",
  "create_conversation",
  "get_conversations",
  "get_messages",
  "update_message_metadata",
  "generate_followup_prompts",
  "delete_conversation",
  "set_active_conversation",
  "update_conversation_title",
  "get_active_provider",
  "get_fast_model_presets",
  "get_fast_provider",
  "setup_fast_provider",
  "test_fast_provider",
  "get_provider_presets",
  "setup_provider",
  "test_provider",
  "get_skills_root",
  "set_skills_root",
  "reload_skills",
  "get_mcp_health",
  "get_law_library_status",
  "reindex_law_library",
  "parse_legal_document",
  "generate_docx",
  "get_skillopt_settings",
  "set_skillopt_settings",
  "list_eval_cases",
  "set_eval_case_active",
  "run_eval_case",
  "list_eval_runs",
  "list_proposals",
  "adopt_proposal",
  "reject_proposal",
  "run_skill_refinement",
  "mine_eval_cases",
  "get_skillopt_overview",
  "get_sync_settings",
  "set_sync_settings",
  "get_sync_status_cmd",
  "flush_feedback_outbox",
  "test_sync_connection",
  "submit_message_feedback",
  "get_message_feedback",
  "list_all_feedback",
];

/** Removed Tauri event listeners that must NOT appear. */
const REMOVED_EVENTS = [
  "chat-stream",
  "agent-trace",
  "law-update-alert",
  "skills-updated",
  "skillopt-progress",
];

describe("invoke() migration verification", () => {
  const sources = readAllSources();

  it("no agent invoke() calls in frontend source — only desktop-specific allowlist", () => {
    const allCalls: string[] = [];
    for (const [_file, content] of sources) {
      allCalls.push(...extractInvokeCalls(content));
    }
    // Every invoke() call must be in the desktop allowlist
    for (const cmd of allCalls) {
      expect(
        DESKTOP_ALLOWLIST.has(cmd),
        `invoke("${cmd}") is not in the desktop-specific allowlist — should be migrated to Gateway HTTP/SSE`,
      ).toBe(true);
    }
  });

  it("no removed invoke() commands present", () => {
    for (const [file, content] of sources) {
      const calls = extractInvokeCalls(content);
      for (const cmd of calls) {
        expect(
          !REMOVED_COMMANDS.includes(cmd),
          `Removed command "${cmd}" found in ${path.relative(SRC_DIR, file)} — should be Gateway HTTP/SSE or removed`,
        ).toBe(true);
      }
    }
  });

  it("Gateway HTTP equivalents are wired", () => {
    const allContent = Array.from(sources.values()).join("\n");
    // Check for gateway.* calls that replace the removed invoke() commands
    expect(allContent).toMatch(/gateway\.createRun/);
    expect(allContent).toMatch(/gateway\.createSession/);
    expect(allContent).toMatch(/gateway\.listSessions/);
    expect(allContent).toMatch(/gateway\.submitElicitation/);
    expect(allContent).toMatch(/gateway\.submitFeedback/);
    expect(allContent).toMatch(/gateway\.getArtifact/);
    expect(allContent).toMatch(/gateway\.cancelRun/);
  });

  it("SSE event stream is used (not Tauri events)", () => {
    const allContent = Array.from(sources.values()).join("\n");
    // createEventStream or useEventStream must be imported and used
    expect(allContent).toMatch(/createEventStream|useEventStream/);
    // Removed Tauri event listeners must NOT appear
    for (const event of REMOVED_EVENTS) {
      const listenRegex = new RegExp(`listen\\s*\\(\\s*["']${event}["']`);
      expect(
        !listenRegex.test(allContent),
        `listen("${event}") found — should be replaced by SSE EventStreamStore`,
      ).toBe(true);
    }
  });

  it("only desktop-specific Tauri event listeners remain", () => {
    for (const [file, content] of sources) {
      const listens = extractListenCalls(content);
      for (const evt of listens) {
        // The only allowed Tauri event listener is workspace-index-progress
        expect(
          evt === "workspace-index-progress",
          `Unexpected Tauri event listener "${evt}" in ${path.relative(SRC_DIR, file)} — only "workspace-index-progress" is allowed`,
        ).toBe(true);
      }
    }
  });
});
