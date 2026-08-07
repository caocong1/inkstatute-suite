/**
 * Command surface audit — verifies the Tauri command surface is minimal
 * and desktop-specific, with zero agent logic.
 *
 * Tests:
 * 1. Tauri command surface is minimal (≤ 21 commands)
 * 2. No agent logic modules in Rust source
 * 3. No LLM provider code in Rust (no reqwest, aes-gcm)
 * 4. No MCP bridge plugin in Cargo.toml
 * 5. Desktop and web share same Gateway client (PlatformApiClient)
 * 6. Desktop and web share same ui-core
 */
import { describe, it, expect } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";

/** Read a file as text. */
function readFile(filePath: string): string {
  return fs.readFileSync(filePath, "utf-8");
}

/** Check if a directory exists. */
function dirExists(dirPath: string): boolean {
  return fs.existsSync(dirPath) && fs.statSync(dirPath).isDirectory();
}

/** Count commands in generate_handler![] block. */
function countCommandsInHandler(libRsContent: string): number {
  const match = libRsContent.match(/generate_handler!\[([\s\S]*?)\]/);
  if (!match) return 0;
  const lines = match[1]
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.length > 0 && !l.startsWith("//"));
  // Each command is on its own line like `commands::files::read_file_content,`
  return lines.filter((l) => l.includes("::")).length;
}

const PROJECT_ROOT = path.resolve(__dirname, "..", "..", "..");
const DESKTOP_TAURI_SRC = path.resolve(__dirname, "..", "src-tauri", "src");
const DESKTOP_CARGO = path.resolve(__dirname, "..", "src-tauri", "Cargo.toml");
const DESKTOP_LIB_RS = path.resolve(__dirname, "..", "src-tauri", "src", "lib.rs");
const DESKTOP_PKG = path.resolve(__dirname, "..", "package.json");
const DESKTOP_GATEWAY = path.resolve(__dirname, "..", "src", "config", "gateway.ts");
const WEB_PKG = path.resolve(PROJECT_ROOT, "apps", "web", "package.json");
const WEB_GATEWAY = path.resolve(PROJECT_ROOT, "apps", "web", "src", "config", "gateway.ts");

/** Agent logic module directories that must NOT exist in src-tauri/src/. */
const AGENT_MODULE_DIRS = [
  "llm",
  "skills",
  "mcp",
  "skill_opt",
  "sync",
  "citations",
  "law_library",
  "documents",
];

describe("Command surface audit", () => {
  it("Tauri command surface is minimal (≤ 21 commands)", () => {
    const libRs = readFile(DESKTOP_LIB_RS);
    const count = countCommandsInHandler(libRs);
    // Expected: 7 file + 3 workspace + 9 offline cache + 2 settings = 21
    expect(count).toBeLessThanOrEqual(21);
    expect(count).toBe(21); // Document the exact count
  });

  it("no agent logic modules in Rust source", () => {
    for (const dir of AGENT_MODULE_DIRS) {
      const fullPath = path.join(DESKTOP_TAURI_SRC, dir);
      expect(
        !dirExists(fullPath),
        `Agent logic directory "${dir}" found in src-tauri/src/ — should not exist`,
      ).toBe(true);
    }
  });

  it("no LLM provider code in Rust (no reqwest, aes-gcm in Cargo.toml)", () => {
    const cargo = readFile(DESKTOP_CARGO);
    expect(cargo).not.toContain("reqwest");
    expect(cargo).not.toContain("aes-gcm");
  });

  it("no MCP bridge plugin in Cargo.toml", () => {
    const cargo = readFile(DESKTOP_CARGO);
    expect(cargo).not.toContain("tauri-plugin-mcp-bridge");
  });

  it("desktop and web share same Gateway client (PlatformApiClient)", () => {
    const desktopGateway = readFile(DESKTOP_GATEWAY);
    const webGateway = readFile(WEB_GATEWAY);
    expect(desktopGateway).toContain("PlatformApiClient");
    expect(desktopGateway).toContain("@inkstatute/platform-sdk-ts");
    expect(webGateway).toContain("PlatformApiClient");
    expect(webGateway).toContain("@inkstatute/platform-sdk-ts");
  });

  it("desktop and web share same ui-core", () => {
    const desktopPkg = JSON.parse(readFile(DESKTOP_PKG));
    const webPkg = JSON.parse(readFile(WEB_PKG));
    expect(desktopPkg.dependencies["@inkstatute/ui-core"]).toBe("workspace:*");
    expect(webPkg.dependencies["@inkstatute/ui-core"]).toBe("workspace:*");
  });
});
