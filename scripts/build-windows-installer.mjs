#!/usr/bin/env node
/**
 * build-windows-installer.mjs — one-command Windows installer build.
 *
 * Steps:
 *   1. Pre-flight: engine-lock.json exists, portable Node exists, gates green.
 *   2. Assemble engine baseline to resources/engine/<version>/.
 *   3. Materialize presets and skills to resources/presets/ and resources/skills/.
 *   4. Run `tauri build --target x86_64-pc-windows-msvc`.
 *   5. Print artifact paths and assert size < 300MB.
 *
 * Usage: node scripts/build-windows-installer.mjs
 */
import { execSync, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync, statSync, readdirSync } from "node:fs";
import { resolve, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const REPO_ROOT = resolve(__dirname, "..", "..");
const DESKTOP_TAURI = join(REPO_ROOT, "apps", "desktop", "src-tauri");
const RESOURCES = join(DESKTOP_TAURI, "resources");

function fail(msg) {
  console.error(`[BUILD FAIL] ${msg}`);
  process.exit(1);
}

function step(name) {
  console.log(`\n=== ${name} ===`);
}

// --- Step 1: Pre-flight checks ---
step("Step 1: Pre-flight checks");

const lockPath = join(REPO_ROOT, "engines", "engine-lock.json");
if (!existsSync(lockPath)) fail("engines/engine-lock.json not found");

const nodeExe = join(RESOURCES, "node", "node.exe");
if (!existsSync(nodeExe)) fail("Portable Node not found. Run: node scripts/fetch-node-runtime.mjs");

// Run gates
console.log("Running V5 gates...");
try {
  execSync("node scripts/gates/v5/run-gates.mjs", {
    cwd: REPO_ROOT,
    stdio: "inherit",
    timeout: 600000,
  });
} catch {
  fail("V5 gates failed. Fix gate failures before building.");
}
console.log("Gates passed.");

// --- Step 2: Assemble engine baseline ---
step("Step 2: Assemble engine baseline");

// Read the engine version from the lock.
const lock = JSON.parse(execSync(`node -e "console.log(JSON.stringify(require('${lockPath.replace(/\\/g, "/")}')))`, { encoding: "utf8" }));
const engineVersion = lock.engine_version;
if (!engineVersion) fail("engine-lock.json has no engine_version");

const engineOutDir = join(RESOURCES, "engine", engineVersion);
console.log(`Assembling engine v${engineVersion} to ${engineOutDir}...`);

// Use the Rust assemble binary if available, otherwise use the test harness.
// For now, we use cargo to run a small assembly command.
// The engine is assembled via the existing assemble() function.
// We'll use a simple Node script that calls the cargo test for assembly.
// In production, a dedicated `assemble-engine` bin would be preferred.
try {
  // Clean previous assembly
  if (existsSync(engineOutDir)) rmSync(engineOutDir, { recursive: true });
  mkdirSync(engineOutDir, { recursive: true });

  // Run the engine assembly via cargo test (ignored integration test)
  // This is the same path the gate uses.
  execSync(
    `cargo test --manifest-path "${join(DESKTOP_TAURI, "Cargo.toml")}" --test engine_assemble_test -- --ignored --test-threads=1`,
    {
      cwd: REPO_ROOT,
      stdio: "inherit",
      timeout: 300000,
      env: {
        ...process.env,
        INKSTATUTE_APP_ROOT: RESOURCES,
      },
    }
  );
  console.log(`Engine assembled to ${engineOutDir}`);
} catch (e) {
  fail(`Engine assembly failed: ${e.message}`);
}

// --- Step 3: Materialize presets and skills ---
step("Step 3: Materialize presets and skills");

const presetsSrc = join(REPO_ROOT, "presets");
const presetsDst = join(RESOURCES, "presets");
const skillsSrc = join(REPO_ROOT, "presets"); // skills are in presets/<domain>/
const skillsDst = join(RESOURCES, "skills");

if (existsSync(presetsSrc)) {
  if (existsSync(presetsDst)) rmSync(presetsDst, { recursive: true });
  execSync(`xcopy /E /I /Y "${presetsSrc}" "${presetsDst}"`, { stdio: "inherit" });
  console.log(`Presets copied to ${presetsDst}`);
} else {
  console.log("No presets directory found — skipping.");
}

// Create skills directory (content packs are fetched at runtime)
if (!existsSync(skillsDst)) {
  mkdirSync(skillsDst, { recursive: true });
}

// --- Step 4: Tauri build ---
step("Step 4: Tauri build (x86_64-pc-windows-msvc)");

try {
  execSync("bunx tauri build --target x86_64-pc-windows-msvc", {
    cwd: join(REPO_ROOT, "apps", "desktop"),
    stdio: "inherit",
    timeout: 1800000,
  });
} catch (e) {
  fail(`Tauri build failed: ${e.message}`);
}

// --- Step 5: Print artifacts and check size ---
step("Step 5: Verify artifacts");

const bundleDir = join(DESKTOP_TAURI, "target", "x86_64-pc-windows-msvc", "release", "bundle");
if (!existsSync(bundleDir)) {
  fail(`Bundle directory not found: ${bundleDir}`);
}

console.log("\nBundle artifacts:");
let totalSize = 0;
function walkDir(dir) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const stat = statSync(full);
    if (stat.isDirectory()) {
      walkDir(full);
    } else {
      const sizeMB = (stat.size / 1024 / 1024).toFixed(1);
      console.log(`  ${full} (${sizeMB} MB)`);
      totalSize += stat.size;
    }
  }
}
walkDir(bundleDir);

const totalMB = totalSize / 1024 / 1024;
console.log(`\nTotal bundle size: ${totalMB.toFixed(1)} MB`);

if (totalMB > 300) {
  fail(`Bundle size ${totalMB.toFixed(1)} MB exceeds 300 MB limit`);
}

console.log("\n=== BUILD COMPLETE ===");
console.log(`Installer artifacts in: ${bundleDir}`);
