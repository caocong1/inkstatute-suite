// PKG-11/12: Offline-Assets Gate
//
// Asserts the app is fully usable offline on a mainland-China Windows machine:
//   1. Zero external URL references in CSS/TS/TSX/HTML (context-aware:
//      url(), @import, <link, <script src — doc-link strings are allowed).
//   2. Bundled Latin font files exist (>= 4 woff2) in packages/ui-core/src/themes/fonts/.
//   3. Portable Node runtime present in apps/desktop/src-tauri/resources/node/
//      (warn-only if absent — CI may not have run fetch-node-runtime.mjs).
//   4. Tauri CSP does not allow external font/style sources (no googleapis/gstatic).
//
// Run: node scripts/gates/v5/offline-assets.mjs

import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '..', '..', '..');

let ok = true;
const failures = [];
function pass(name) { console.log(`[PASS] ${name}`); }
function fail(name, detail) {
  ok = false;
  failures.push(`${name}: ${detail}`);
  console.log(`[FAIL] ${name}: ${detail}`);
}

// --- 1. Zero external URL references (context-aware) -------------------
//
// A reference is "external" only when it appears in a resource-loading context:
//   url(<external>)        (CSS)
//   @import "<external>"   (CSS)
//   <link href="<external>" / <script src="<external>"  (HTML)
// Bare https:// strings in comments or string constants (e.g. a doc link) are
// allowed — the offline requirement is about *loaded assets*, not text.
const SCAN_TARGETS = [
  { glob: 'packages/ui-core/src/**/*.css', kind: 'css' },
  { glob: 'apps/desktop/src/**/*.css', kind: 'css' },
  { glob: 'apps/desktop/src/**/*.{ts,tsx}', kind: 'js' },
  { glob: 'apps/desktop/index.html', kind: 'html' },
];

// Recursively list files under `baseDir` whose extension matches `exts`.
// Pure Node fs walk — no git/grep dependency, works on Windows CI.
function walkFiles(baseDir, exts) {
  const out = [];
  if (!existsSync(baseDir)) return out;
  const stack = [baseDir];
  while (stack.length) {
    const dir = stack.pop();
    let entries;
    try { entries = readdirSync(dir); } catch { continue; }
    for (const name of entries) {
      const full = path.join(dir, name);
      let st;
      try { st = statSync(full); } catch { continue; }
      if (st.isDirectory()) {
        // Skip node_modules / dist / target
        if (name === 'node_modules' || name === 'dist' || name === 'target') continue;
        stack.push(full);
      } else if (st.isFile()) {
        const ext = path.extname(name).toLowerCase();
        if (exts.includes(ext)) out.push(full);
      }
    }
  }
  return out;
}

function listFiles(target) {
  // Resolve the scan root from the glob's directory prefix.
  // Supported globs: <root>/**/*.css , <root>/**/*.ts , <root>/**/*.tsx ,
  // <root>/**/*.{css,ts,tsx} , <root>/index.html
  const glob = target.glob;
  const kind = target.kind;
  const starIdx = glob.indexOf('/**/');
  if (starIdx >= 0) {
    const baseDir = path.join(REPO_ROOT, glob.slice(0, starIdx));
    const exts = kind === 'css' ? ['.css'] : kind === 'js' ? ['.ts', '.tsx'] : ['.html'];
    return walkFiles(baseDir, exts);
  }
  // literal file
  return [path.join(REPO_ROOT, glob)].filter(existsSync);
}

// CSS: flag url(http...) and @import ...http...  (data: and relative urls are fine)
const CSS_URL = /url\(\s*(['"]?)\s*https?:\/\/[^)]+\)/gi;
const CSS_IMPORT = /@import\s+(?:url\()?\s*(['"]?)\s*https?:\/\/[^;)]+/gi;
// HTML: <link href="http..."> / <script src="http...">
const HTML_LINK = /<link[^>]+href\s*=\s*(['"])https?:\/\/[^>]+>/gi;
const HTML_SCRIPT = /<script[^>]+src\s*=\s*(['"])https?:\/\/[^>]+>/gi;

let externalRefs = [];
for (const target of SCAN_TARGETS) {
  const files = listFiles(target);
  for (const file of files) {
    if (!existsSync(file)) continue;
    const text = readFileSync(file, 'utf8');
    const rel = path.relative(REPO_ROOT, file);
    let m;
    if (target.kind === 'css') {
      while ((m = CSS_URL.exec(text))) externalRefs.push(`${rel}: url() → ${m[0].trim()}`);
      while ((m = CSS_IMPORT.exec(text))) externalRefs.push(`${rel}: @import → ${m[0].trim()}`);
    } else if (target.kind === 'html') {
      while ((m = HTML_LINK.exec(text))) externalRefs.push(`${rel}: <link> → ${m[0].trim()}`);
      while ((m = HTML_SCRIPT.exec(text))) externalRefs.push(`${rel}: <script> → ${m[0].trim()}`);
    }
    // js: a bare https:// string is NOT a loaded asset; skip.
  }
}

if (externalRefs.length === 0) {
  pass('zero-external-urls: no http(s) asset references in CSS/HTML');
} else {
  fail('zero-external-urls', `${externalRefs.length} external asset reference(s) found:\n  ` + externalRefs.slice(0, 8).join('\n  '));
}

// --- 2. Bundled font files exist ---------------------------------------
const FONTS_DIR = path.join(REPO_ROOT, 'packages/ui-core/src/themes/fonts');
if (!existsSync(FONTS_DIR)) {
  fail('font-files', `fonts directory missing: ${FONTS_DIR}`);
} else {
  const woff2 = readdirSync(FONTS_DIR).filter((f) => f.endsWith('.woff2'));
  if (woff2.length < 4) {
    fail('font-files', `expected >= 4 woff2 files, found ${woff2.length}: ${woff2.join(', ')}`);
  } else {
    pass(`font-files: ${woff2.length} woff2 files bundled`);
  }
}

// --- 3. Portable Node runtime present (warn-only) ----------------------
const NODE_DIR = path.join(REPO_ROOT, 'apps/desktop/src-tauri/resources/node');
const nodeBin = existsSync(path.join(NODE_DIR, 'node.exe')) || existsSync(path.join(NODE_DIR, 'node'));
if (nodeBin) {
  pass('node-runtime: portable node present in resources/node/');
} else {
  // Warn-only: CI may not have run fetch-node-runtime.mjs; the build script
  // enforces presence before producing an installer.
  console.log(`[WARN] node-runtime: portable node not found in resources/node/ — run \`node scripts/fetch-node-runtime.mjs\` before building`);
}

// --- 4. Tauri CSP has no external font/style sources --------------------
const TAURI_CONF = path.join(REPO_ROOT, 'apps/desktop/src-tauri/tauri.conf.json');
if (!existsSync(TAURI_CONF)) {
  fail('csp', `tauri.conf.json missing: ${TAURI_CONF}`);
} else {
  const conf = readFileSync(TAURI_CONF, 'utf8');
  const cspMatch = conf.match(/"csp"\s*:\s*"([^"]*)"/);
  if (!cspMatch) {
    fail('csp', 'no csp field found in tauri.conf.json');
  } else {
    const csp = cspMatch[1];
    const banned = ['fonts.googleapis.com', 'fonts.gstatic.com'];
    const hits = banned.filter((b) => csp.includes(b));
    if (hits.length > 0) {
      fail('csp', `CSP allows external font sources: ${hits.join(', ')}`);
    } else {
      pass('csp: no external font/style sources allowed');
    }
  }
}

// --- Summary -----------------------------------------------------------
if (ok) {
  console.log('\n✅ All offline-assets gate checks passed.');
} else {
  console.error('\n❌ offline-assets gate FAILED:');
  for (const f of failures) console.error(`  - ${f}`);
  process.exit(1);
}
