/**
 * Scaffold test — verifies the desktop app structure exists.
 * More tests are added in subsequent tasks (adapters, auth, tracer).
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const pkg = JSON.parse(readFileSync(resolve(__dirname, "..", "package.json"), "utf-8"));

describe("desktop scaffold", () => {
  it("package.json has correct name", () => {
    expect(pkg.name).toBe("@inkstatute/desktop");
    expect(pkg.private).toBe(true);
  });

  it("package.json has workspace deps", () => {
    expect(pkg.dependencies["@inkstatute/ui-core"]).toBe("workspace:*");
    expect(pkg.dependencies["@inkstatute/platform-sdk-ts"]).toBe("workspace:*");
  });

  it("package.json has tauri deps", () => {
    expect(pkg.dependencies["@tauri-apps/api"]).toBeDefined();
    expect(pkg.dependencies["@tauri-apps/plugin-dialog"]).toBeDefined();
  });

  it("package.json has no router dep", () => {
    expect(pkg.dependencies["@solidjs/router"]).toBeUndefined();
  });
});
