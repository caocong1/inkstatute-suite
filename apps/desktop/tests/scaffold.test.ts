/**
 * Scaffold test — verifies the desktop app structure exists.
 * More tests are added in subsequent tasks (adapters, auth, tracer).
 */
import { describe, it, expect } from "vitest";

describe("desktop scaffold", () => {
  it("package.json has correct name", async () => {
    const pkg = await import("../package.json") as Record<string, unknown>;
    expect(pkg.name).toBe("@inkstatute/desktop");
  });

  it("package.json has workspace deps", async () => {
    const pkg = await import("../package.json");
    expect(pkg.dependencies["@inkstatute/ui-core"]).toBe("workspace:*");
    expect(pkg.dependencies["@inkstatute/platform-sdk-ts"]).toBe("workspace:*");
  });

  it("package.json has tauri deps", async () => {
    const pkg = await import("../package.json");
    expect(pkg.dependencies["@tauri-apps/api"]).toBeDefined();
    expect(pkg.dependencies["@tauri-apps/plugin-dialog"]).toBeDefined();
  });

  it("package.json has no router dep", async () => {
    const pkg = await import("../package.json") as { dependencies: Record<string, string> };
    expect(pkg.dependencies["@solidjs/router"]).toBeUndefined();
  });
});
