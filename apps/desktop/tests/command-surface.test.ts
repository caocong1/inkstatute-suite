/**
 * Command surface audit — the Tauri backend stays a thin desktop shell with
 * zero agent logic. DSH owns the execution core; 墨律 owns the shell.
 *
 * Restored 2026-08-16 after Phase 125 deleted this file wholesale. The file
 * had one stale assertion — `expect(cargo).not.toContain("reqwest")` — which
 * Phase 122 legitimately broke by adding reqwest for the lockfile assembler.
 * Deleting the file to make the suite green also removed the architectural
 * guards below, which are the strongest executable statement of the project's
 * central constraint. The stale assertion is replaced, the guards are kept.
 *
 * 1. Command surface stays small
 * 2. No agent logic modules in Rust source        ← the crown jewel
 * 3. No LLM API calling code in Rust              ← replaces the reqwest ban
 * 4. No MCP bridge plugin
 * 5. No Gateway client anywhere in the desktop app (v5: Gateway is gone)
 * 6. ui-core remains the single chat UI implementation
 */
import { describe, it, expect } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";

function readFile(filePath: string): string {
  return fs.readFileSync(filePath, "utf-8");
}

function dirExists(dirPath: string): boolean {
  return fs.existsSync(dirPath) && fs.statSync(dirPath).isDirectory();
}

/** Every .rs file under a directory, recursively. */
function rustFiles(dir: string): string[] {
  if (!dirExists(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) return rustFiles(full);
    return e.isFile() && e.name.endsWith(".rs") ? [full] : [];
  });
}

/** Count entries inside generate_handler![]. */
function countCommandsInHandler(libRsContent: string): number {
  const match = libRsContent.match(/generate_handler!\[([\s\S]*?)\]/);
  if (!match) return 0;
  return match[1]
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.length > 0 && !l.startsWith("//") && l.includes("::")).length;
}

const DESKTOP_SRC = path.resolve(__dirname, "..", "src");
const TAURI_SRC = path.resolve(__dirname, "..", "src-tauri", "src");
const CARGO = path.resolve(__dirname, "..", "src-tauri", "Cargo.toml");
const LIB_RS = path.resolve(TAURI_SRC, "lib.rs");

/**
 * Directories that must never reappear under src-tauri/src/. Each is a piece of
 * the self-built agent loop that v5 retired to DSH. Their return would mean
 * 墨律 started re-implementing the execution core.
 */
const AGENT_MODULE_DIRS = [
  "llm",
  "skills",
  "mcp",
  "skill_opt",
  "sync",
  "citations",
  "law_library",
  "documents",
  "workspace", // self-built FTS5 index, retired in favour of DSH fs tools
];

/** Files whose names denote agent-loop responsibilities. */
const AGENT_FILE_NAMES = [
  "chat.rs",
  "chat_tools.rs",
  "router.rs",
  "agent_classifier.rs",
  "tool_leak.rs",
  "turn_loop.rs",
];

describe("Command surface audit", () => {
  it("Tauri command surface stays small", () => {
    const count = countCommandsInHandler(readFile(LIB_RS));
    // 23 at Phase 125, 32 at Phase 127 (added 4 updater + 3 setup commands).
    // The cap leaves room for post-v5.0 without becoming a rubber stamp.
    expect(count).toBeGreaterThan(0);
    expect(count).toBeLessThanOrEqual(35);
  });

  it("no agent logic modules in Rust source", () => {
    for (const dir of AGENT_MODULE_DIRS) {
      expect(
        dirExists(path.join(TAURI_SRC, dir)),
        `Agent logic directory "${dir}" reappeared in src-tauri/src/ — DSH owns the execution core`,
      ).toBe(false);
    }
  });

  it("no agent-loop files in Rust source", () => {
    const present = rustFiles(TAURI_SRC).map((f) => path.basename(f));
    for (const name of AGENT_FILE_NAMES) {
      expect(present, `"${name}" reappeared — DSH owns the agent loop`).not.toContain(name);
    }
  });

  it("no LLM API calling code in Rust", () => {
    // reqwest itself is legitimate: the engine assembler and updater download
    // npm tarballs over HTTP. What must never appear is Rust code that talks to
    // a model provider — that is the engine's job, reached over ACP stdio.
    const forbidden = [
      "api.deepseek.com",
      "api.openai.com",
      "api.anthropic.com",
      "chat/completions",
      "/v1/messages",
    ];
    for (const file of rustFiles(TAURI_SRC)) {
      const text = readFile(file);
      for (const needle of forbidden) {
        expect(
          text.includes(needle),
          `${path.relative(TAURI_SRC, file)} contains "${needle}" — the app must not call model APIs directly`,
        ).toBe(false);
      }
    }
  });

  it("no MCP bridge plugin in Cargo.toml", () => {
    expect(readFile(CARGO)).not.toContain("tauri-plugin-mcp-bridge");
  });

  it("no Gateway client in the desktop app", () => {
    // v5 removed the Gateway. platform-sdk-ts survives only as a pure type
    // module (`/events`); importing its root would pull the HTTP client back in.
    const offenders: string[] = [];
    const walk = (dir: string) => {
      if (!dirExists(dir)) return;
      for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, e.name);
        if (e.isDirectory()) walk(full);
        else if (/\.tsx?$/.test(e.name)) {
          const text = readFile(full);
          if (text.includes("PlatformApiClient")) offenders.push(full);
          if (/from\s+["']@inkstatute\/platform-sdk-ts["']/.test(text)) offenders.push(full);
        }
      }
    };
    walk(DESKTOP_SRC);
    expect(offenders, `Gateway client referenced in: ${offenders.join(", ")}`).toEqual([]);
  });

  it("ui-core remains the single chat UI implementation", () => {
    // The desktop app wires adapters and routes; it must not grow its own
    // ChatPanel/DocPreview copies.
    const localCopies = ["ChatPanel.tsx", "DocPreview.tsx", "ConversationDrawer.tsx"];
    const walk = (dir: string): string[] => {
      if (!dirExists(dir)) return [];
      return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
        const full = path.join(dir, e.name);
        if (e.isDirectory()) return walk(full);
        return localCopies.includes(e.name) ? [full] : [];
      });
    };
    expect(walk(DESKTOP_SRC), "chat UI must live in packages/ui-core only").toEqual([]);
  });
});
