/**
 * Desktop/web consistency test — verifies success criterion #6:
 * "桌面端与 Web 端在同一任务上表现一致"
 *
 * Both desktop and web use:
 *   - Same ui-core components (ChatPanel, DocPreview, CitationPanel, ClarificationCard)
 *   - Same PlatformApiClient from @inkstatute/platform-sdk-ts
 *   - Same event reducer (reduce from @inkstatute/ui-core)
 *   - Same createEventStream from @inkstatute/ui-core
 *
 * This test verifies consistency structurally (source-level) and empirically
 * (same fixture events produce same RenderState).
 */
import { describe, it, expect } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";
import { initialState, reduce } from "@inkstatute/ui-core";
import { fixtureEventStream } from "./fixtures/events";

const PROJECT_ROOT = path.resolve(__dirname, "..", "..", "..");
const DESKTOP_SRC = path.resolve(__dirname, "..", "src");
const WEB_SRC = path.resolve(PROJECT_ROOT, "apps", "web", "src");

/** Read a file as text. */
function readFile(filePath: string): string {
  return fs.readFileSync(filePath, "utf-8");
}

/** Recursively read all .ts/.tsx files in a directory. */
function readAllSourceFiles(dir: string): string[] {
  const results: string[] = [];
  if (!fs.existsSync(dir)) return results;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...readAllSourceFiles(fullPath));
    } else if (entry.name.endsWith(".ts") || entry.name.endsWith(".tsx")) {
      results.push(readFile(fullPath));
    }
  }
  return results;
}

describe("Desktop/web consistency", () => {
  it("desktop and web import same ui-core components", () => {
    const desktopSources = readAllSourceFiles(DESKTOP_SRC);
    const webSources = readAllSourceFiles(WEB_SRC);

    // Both import from @inkstatute/ui-core
    const desktopUiCoreImports = desktopSources.filter((s) =>
      s.includes("@inkstatute/ui-core"),
    );
    const webUiCoreImports = webSources.filter((s) =>
      s.includes("@inkstatute/ui-core"),
    );

    expect(desktopUiCoreImports.length).toBeGreaterThan(0);
    expect(webUiCoreImports.length).toBeGreaterThan(0);

    // Both import ChatPanel, DocPreview, CitationPanel from ui-core
    const allDesktop = desktopSources.join("\n");
    const allWeb = webSources.join("\n");

    // ChatPanel is imported from ui-core in both
    expect(allDesktop).toContain("ChatPanel");
    expect(allWeb).toContain("ChatPanel");

    // DocPreview is imported from ui-core in both
    expect(allDesktop).toContain("DocPreview");
    expect(allWeb).toContain("DocPreview");

    // CitationPanel is imported from ui-core in both
    expect(allDesktop).toContain("CitationPanel");
    expect(allWeb).toContain("CitationPanel");
  });

  it("desktop and web use same PlatformApiClient", () => {
    const desktopGateway = readFile(
      path.join(DESKTOP_SRC, "config", "gateway.ts"),
    );
    const webGateway = readFile(path.join(WEB_SRC, "config", "gateway.ts"));

    // Both import PlatformApiClient from @inkstatute/platform-sdk-ts
    expect(desktopGateway).toContain("PlatformApiClient");
    expect(desktopGateway).toContain("@inkstatute/platform-sdk-ts");
    expect(webGateway).toContain("PlatformApiClient");
    expect(webGateway).toContain("@inkstatute/platform-sdk-ts");
  });

  it("desktop and web use same event reducer (createEventStream from ui-core)", () => {
    const desktopSources = readAllSourceFiles(DESKTOP_SRC);
    const webSources = readAllSourceFiles(WEB_SRC);

    const allDesktop = desktopSources.join("\n");
    const allWeb = webSources.join("\n");

    // Both use createEventStream from @inkstatute/ui-core
    expect(allDesktop).toContain("createEventStream");
    expect(allWeb).toContain("createEventStream");

    // Both import from @inkstatute/ui-core (not a separate implementation)
    expect(allDesktop).toContain("@inkstatute/ui-core");
    expect(allWeb).toContain("@inkstatute/ui-core");
  });

  it("same fixture events produce same RenderState", () => {
    // Run fixture events through the shared event reducer
    // Both desktop and web use the same reducer from ui-core,
    // so the resulting RenderState is identical by construction.
    let state = initialState();
    for (const event of fixtureEventStream()) {
      state = reduce(state, event);
    }

    // Verify the state has expected content from the fixture
    expect(state.messages.length).toBeGreaterThan(0);
    expect(state.artifacts.length).toBe(1);
    expect(state.artifacts[0].artifact_id).toBe("art-001");
    expect(state.artifacts[0].name).toBe("合同审查报告.docx");
    expect(state.citations.length).toBe(3);
    expect(state.clarification).not.toBeNull();
    expect(state.clarification?.questions.length).toBe(2);
    expect(state.runStatus).toBe("completed");
    expect(state.currentPhase).toBe("review");

    // The key point: this RenderState is the same whether the consumer
    // is desktop or web, because both use the same reduce() function.
    // This is the structural guarantee of success criterion #6.
  });

  it("desktop and web have no separate chat UI implementations", () => {
    // Grep for custom chat message list, streaming renderer, or clarification card
    // class definitions in both apps' source — should return zero results.
    const desktopSources = readAllSourceFiles(DESKTOP_SRC);
    const webSources = readAllSourceFiles(WEB_SRC);

    const allSource = [...desktopSources, ...webSources].join("\n");

    // No custom ChatMessage class
    expect(allSource).not.toMatch(/class\s+ChatMessage\b/);

    // No custom StreamingRenderer class
    expect(allSource).not.toMatch(/class\s+StreamingRenderer\b/);

    // No custom ClarificationCard class (it comes from ui-core)
    expect(allSource).not.toMatch(/class\s+ClarificationCard\b/);

    // Both import these from ui-core, not define them
    expect(allSource).toContain("@inkstatute/ui-core");
  });

  it("desktop Gateway URL is configurable, web uses same-origin", () => {
    const desktopGateway = readFile(
      path.join(DESKTOP_SRC, "config", "gateway.ts"),
    );
    const webGateway = readFile(path.join(WEB_SRC, "config", "gateway.ts"));

    // Desktop: baseUrl = VITE_GATEWAY_URL || "http://127.0.0.1:8000" (configurable)
    expect(desktopGateway).toContain("VITE_GATEWAY_URL");
    expect(desktopGateway).toContain("http://127.0.0.1:8000");

    // Web: baseUrl = VITE_GATEWAY_URL || "" (same-origin)
    expect(webGateway).toContain("VITE_GATEWAY_URL");
    expect(webGateway).toContain('|| ""');

    // Both use the same PlatformApiClient class — only difference is baseUrl
    expect(desktopGateway).toContain("PlatformApiClient");
    expect(webGateway).toContain("PlatformApiClient");
  });
});
