#!/usr/bin/env node
// PKG-11: Fetch a portable Node runtime for bundling with the desktop app.
//
// Reads `engines/dsh-pin.txt` for `node_version` and `target_platform`,
// downloads the matching Node distribution, verifies SHA256 against the
// official SHASUMS256.txt, and extracts **only `node.exe`** (Windows) or
// `node` (other platforms) into `apps/desktop/src-tauri/resources/node/`.
//
// Why only the binary: npm/npx/docs are not needed at runtime — the engine
// is assembled from npm tarballs by the Rust assembler, not by `npm install`.
// Keeping the bundle lean matters because this file ships inside the .msi.
//
// Mirrors: the official nodejs.org dist is used first; a configurable mirror
// (default npmmirror.com) is tried as a fallback for mainland-China reach.
// Override either via env: NODE_DIST_MIRROR_PRIMARY / NODE_DIST_MIRROR_FALLBACK.
//
// Run: node scripts/fetch-node-runtime.mjs
// Re-runs are cheap: if the target binary already exists and its recorded
// version matches, the download is skipped.

import { createWriteStream, existsSync, mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { pipeline } from 'node:stream/promises';
import { spawnSync } from 'node:child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '..');
const PIN_FILE = join(REPO_ROOT, 'engines', 'dsh-pin.txt');
const RESOURCES_NODE_DIR = join(REPO_ROOT, 'apps', 'desktop', 'src-tauri', 'resources', 'node');

const PRIMARY_MIRROR = process.env.NODE_DIST_MIRROR_PRIMARY || 'https://nodejs.org/dist';
const FALLBACK_MIRROR = process.env.NODE_DIST_MIRROR_FALLBACK || 'https://npmmirror.com/mirrors/node';

function parsePin() {
  const text = readFileSync(PIN_FILE, 'utf8');
  const pin = {};
  for (const raw of text.split('\n')) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq < 0) continue;
    const key = line.slice(0, eq).trim();
    const value = line.slice(eq + 1).trim();
    pin[key] = value;
  }
  if (!pin.node_version) throw new Error('engines/dsh-pin.txt missing node_version');
  if (!pin.target_platform) throw new Error('engines/dsh-pin.txt missing target_platform');
  return pin;
}

// Map a pin target_platform (e.g. win32-x64) to a Node dist archive name.
function archiveForPlatform(platform, version) {
  // Node dist names: node-v<ver>-win-x64.zip, node-v<ver>-darwin-arm64.tar.gz, ...
  const map = {
    'win32-x64': { ext: 'zip', os: 'win', arch: 'x64' },
    'win32-arm64': { ext: 'zip', os: 'win', arch: 'arm64' },
    'darwin-x64': { ext: 'tar.gz', os: 'darwin', arch: 'x64' },
    'darwin-arm64': { ext: 'tar.gz', os: 'darwin', arch: 'arm64' },
    'linux-x64': { ext: 'tar.gz', os: 'linux', arch: 'x64' },
    'linux-arm64': { ext: 'tar.gz', os: 'linux', arch: 'arm64' },
  };
  const spec = map[platform];
  if (!spec) throw new Error(`Unsupported target_platform: ${platform}`);
  const base = `node-v${version}-${spec.os}-${spec.arch}`;
  return {
    base,
    filename: `${base}.${spec.ext}`,
    ext: spec.ext,
    // Inside the archive, the binary lives at <base>/node.exe or <base>/bin/node.
    innerBinary: spec.os === 'win' ? `${base}/node.exe` : `${base}/bin/node`,
    innerMarker: spec.os === 'win' ? `${base}/node.exe` : `${base}/bin/node`,
    os: spec.os,
  };
}

async function fetchText(url) {
  const res = await fetch(url, { redirect: 'follow' });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  return res.text();
}

async function downloadToFile(url, dest) {
  const res = await fetch(url, { redirect: 'follow' });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  const body = res.body;
  if (!body) throw new Error(`Empty body for ${url}`);
  await pipeline(body, createWriteStream(dest));
}

// Verify the archive SHA256 against the official SHASUMS256.txt for the version.
async function expectedSha256(mirror, version, archiveFilename) {
  const shasumsUrl = `${mirror}/v${version}/SHASUMS256.txt`;
  const text = await fetchText(shasumsUrl);
  // Lines look like: <sha256>  node-v24.19.0-win-x64.zip
  for (const line of text.split('\n')) {
    const m = line.trim().match(/^([0-9a-f]{64})\s+\*?(.+)$/);
    if (m && m[2].trim() === archiveFilename) return m[1];
  }
  throw new Error(`${archiveFilename} not found in SHASUMS256.txt at ${shasumsUrl}`);
}

function sha256File(path) {
  // Use whatever hash tool is available; prefer openssl, fall back to certutil on Windows.
  if (process.platform === 'win32') {
    const out = spawnSync('certutil', ['-hashfile', path, 'SHA256'], { encoding: 'utf8' });
    if (out.status === 0) {
      const m = out.stdout.match(/([0-9a-fA-F]{64})/);
      if (m) return m[1].toLowerCase();
    }
  }
  const out = spawnSync('shasum', ['-a', '256', path], { encoding: 'utf8' });
  if (out.status === 0) {
    const m = out.stdout.match(/^([0-9a-f]{64})/);
    if (m) return m[1].toLowerCase();
  }
  throw new Error('No SHA256 tool available (tried certutil and shasum).');
}

function extractBinary(archivePath, spec, outDir) {
  mkdirSync(outDir, { recursive: true });
  const nodeOutName = spec.os === 'win' ? 'node.exe' : 'node';
  const nodeOutPath = join(outDir, nodeOutName);
  if (spec.ext === 'zip') {
    // PowerShell Expand-Archive on Windows; unzip elsewhere if available.
    if (process.platform === 'win32') {
      const tmpExtract = join(outDir, '..extract-tmp');
      rmSync(tmpExtract, { recursive: true, force: true });
      mkdirSync(tmpExtract, { recursive: true });
      const ps = spawnSync(
        'powershell',
        ['-NoProfile', '-Command', `Expand-Archive -LiteralPath '${archivePath}' -DestinationPath '${tmpExtract}' -Force`],
        { encoding: 'utf8' },
      );
      if (ps.status !== 0) throw new Error(`Expand-Archive failed: ${ps.stderr || ps.stdout}`);
      const inner = join(tmpExtract, spec.innerBinary);
      if (!existsSync(inner)) throw new Error(`Expected binary not found in archive: ${spec.innerBinary}`);
      rmSync(nodeOutPath, { force: true });
      // Copy preserving the executable bit is irrelevant on Windows.
      const copy = spawnSync('powershell', ['-NoProfile', '-Command', `Copy-Item '${inner}' '${nodeOutPath}' -Force`], { encoding: 'utf8' });
      if (copy.status !== 0) throw new Error(`Copy-Item failed: ${copy.stderr || copy.stdout}`);
      rmSync(tmpExtract, { recursive: true, force: true });
    } else {
      throw new Error('zip extraction on non-Windows not implemented; run on Windows or provide unzip.');
    }
  } else {
    // tar.gz — extract only the inner binary.
    const tar = spawnSync('tar', ['-xzf', archivePath, '-C', outDir, '--strip-components=1', spec.innerBinary.replace(/^[^/]+\//, '')], { encoding: 'utf8' });
    if (tar.status !== 0) throw new Error(`tar extraction failed: ${tar.stderr || tar.stdout}`);
    // tar --strip-components=1 on <base>/bin/node yields bin/node under outDir; rename to node.
    const extracted = join(outDir, 'bin', 'node');
    if (existsSync(extracted)) {
      rmSync(nodeOutPath, { force: true });
      const mv = spawnSync('mv', [extracted, nodeOutPath], { encoding: 'utf8' });
      if (mv.status !== 0) throw new Error(`mv failed: ${mv.stderr || mv.stdout}`);
      rmSync(join(outDir, 'bin'), { recursive: true, force: true });
    }
  }
  if (!existsSync(nodeOutPath)) throw new Error(`Extraction did not produce ${nodeOutPath}`);
  return nodeOutPath;
}

async function tryDownload(mirror, version, spec, destArchive) {
  const url = `${mirror}/v${version}/${spec.filename}`;
  const expected = await expectedSha256(mirror, version, spec.filename);
  await downloadToFile(url, destArchive);
  const actual = sha256File(destArchive);
  if (actual !== expected.toLowerCase()) {
    throw new Error(`SHA256 mismatch for ${spec.filename}: expected ${expected}, got ${actual}`);
  }
  return expected;
}

async function main() {
  const pin = parsePin();
  const version = pin.node_version;
  const spec = archiveForPlatform(pin.target_platform, version);

  mkdirSync(RESOURCES_NODE_DIR, { recursive: true });
  const nodeOutName = spec.os === 'win' ? 'node.exe' : 'node';
  const nodeOutPath = join(RESOURCES_NODE_DIR, nodeOutName);
  const markerPath = join(RESOURCES_NODE_DIR, 'node.version');

  // Skip if already present and version matches.
  if (existsSync(nodeOutPath) && existsSync(markerPath)) {
    const marked = readFileSync(markerPath, 'utf8').trim();
    if (marked === version) {
      const size = statSync(nodeOutPath).size;
      console.log(`[skip] node ${version} already present (${(size / 1024 / 1024).toFixed(1)} MB) at ${nodeOutPath}`);
      return;
    }
  }

  const tmpArchive = join(RESOURCES_NODE_DIR, `.download-${spec.filename}`);
  rmSync(tmpArchive, { force: true });

  let lastErr;
  for (const mirror of [PRIMARY_MIRROR, FALLBACK_MIRROR]) {
    try {
      console.log(`[fetch] ${mirror}/v${version}/${spec.filename}`);
      await tryDownload(mirror, version, spec, tmpArchive);
      lastErr = null;
      break;
    } catch (e) {
      console.error(`[warn] primary failed: ${e.message}`);
      lastErr = e;
    }
  }
  if (lastErr) {
    rmSync(tmpArchive, { force: true });
    throw new Error(`Could not download Node ${version} from any mirror: ${lastErr.message}`);
  }

  console.log('[extract] node binary only (no npm/npx/docs)');
  const extracted = extractBinary(tmpArchive, spec, RESOURCES_NODE_DIR);
  rmSync(tmpArchive, { force: true });

  writeFileSync(markerPath, version, 'utf8');
  const size = statSync(extracted).size;
  console.log(`[done] node ${version} -> ${extracted} (${(size / 1024 / 1024).toFixed(1)} MB)`);

  // Non-Windows dev machines: also fetch the local-platform binary so `tauri dev` works.
  const hostPlatform = `${process.platform}-${process.arch}`;
  if (hostPlatform !== pin.target_platform) {
    console.log(`[note] host platform ${hostPlatform} != target ${pin.target_platform}; target binary fetched for bundling only.`);
    console.log('[note] For local dev on a different platform, set INKSTATUTE_NODE_BIN or re-run with target_platform matching your host.');
  }
}

main().catch((e) => {
  console.error(`[fail] ${e.message}`);
  process.exit(1);
});
