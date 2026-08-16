import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '..', '..', '..');

function run(cmd, opts = {}) {
  return execSync(cmd, { encoding: 'utf8', cwd: REPO_ROOT, ...opts });
}

function fail(msg) {
  console.error(`FAIL: ${msg}`);
  process.exit(1);
}

let ok = true;
function check(name, fn) {
  try {
    fn();
    console.log(`[PASS] ${name}`);
  } catch (e) {
    ok = false;
    console.log(`[FAIL] ${name}: ${e.message}`);
  }
}

// 1. dsh-pin.txt: no dist-tags in package list.
check('GATE-11.1: dsh-pin.txt no dist-tags', () => {
  const text = readFileSync(path.join(REPO_ROOT, 'engines', 'dsh-pin.txt'), 'utf8');
  const lines = text.split('\n').filter(l => l && !l.trimStart().startsWith('#') && !l.includes('='));
  for (const line of lines) {
    if (/\b@(latest|next)\b/.test(line)) {
      throw new Error(`dist-tag found: ${line}`);
    }
  }
});

// 2. acp.cordis.yml defects fixed.
check('GATE-11.2: acp.cordis.yml config defects', () => {
  const text = readFileSync(path.join(REPO_ROOT, 'engines', 'acp.cordis.yml'), 'utf8');
  const active = text.split('\n').filter(l => !l.trimStart().startsWith('#')).join('\n');
  if (/\$\{DSH_HOME\}/.test(active)) throw new Error('literal ${DSH_HOME} in active config');
  if (!/process\.env\.DSH_HOME/.test(active)) throw new Error('missing process.env.DSH_HOME');
  if (!/packChunks:\s*false/.test(active)) throw new Error('missing packChunks: false');
  if (!/persistenceCompression:\s*none/.test(active)) throw new Error('missing persistenceCompression: none');
  if (/sk-[A-Za-z0-9]{16,}/.test(text)) throw new Error('suspected API key in config');
});

// 3. engine-lock.json structure.
check('GATE-11.3: engine-lock.json structure', () => {
  const lock = JSON.parse(readFileSync(path.join(REPO_ROOT, 'engines', 'engine-lock.json'), 'utf8'));
  if (lock.schema_version !== '1.0.0') throw new Error(`bad schema_version: ${lock.schema_version}`);
  if (lock.engine_version !== '0.1.0-rc.6') throw new Error(`bad engine_version: ${lock.engine_version}`);
  const keys = Object.keys(lock.packages);
  if (keys.length < 100) throw new Error(`too few packages: ${keys.length}`);
  for (const k of keys) {
    const pkg = lock.packages[k];
    if (!k.startsWith('node_modules/')) throw new Error(`bad key: ${k}`);
    if (!pkg.integrity.startsWith('sha512-')) throw new Error(`bad integrity for ${k}`);
    if (!pkg.tarball_path.startsWith('/') || pkg.tarball_path.includes('://')) throw new Error(`bad tarball_path for ${k}: ${pkg.tarball_path}`);
  }
  // cordis sha256 must match actual file.
  // CRLF→LF normalization must match gen-engine-lock.mjs and lock.rs.
  const cordis = readFileSync(path.join(REPO_ROOT, 'engines', 'acp.cordis.yml'), 'utf8').replaceAll('\r\n', '\n');
  const actual = createHash('sha256').update(cordis).digest('hex');
  if (actual !== lock.cordis_config_sha256) throw new Error('cordis_config_sha256 mismatch');
});

// 4. Rust compile + unit tests.
check('GATE-11.4: cargo check', () => {
  run('cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml');
});

check('GATE-11.5: cargo test (unit)', () => {
  run('cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml -- --test-threads=1');
});

// 5. Real engine assembly + smoke (ignored integration tests, run explicitly).
check('GATE-11.6: real engine assembly + smoke', () => {
  // Phase 123 real-API replay gate is a separate, human-gated manual test.
  run('cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml --test engine_assemble_test --test engine_smoke_test -- --ignored --test-threads=1');
});

// 6. No plaintext API keys in tracked files (excluding planning archives and tests).
check('GATE-11.7: no plaintext API keys', () => {
  const files = run("git ls-files -z").split('\0').filter(Boolean);
  const bad = [];
  for (const f of files) {
    if (f.startsWith('.planning/milestones/') || f.startsWith('.planning/phases/')) continue;
    if (/(^|\/)tests(\/)/.test(f) || f.includes('/test_')) continue;
    if (/\.(png|jpg|jpeg|gif|svg|ico|woff|ttf|eot|mp3|mp4|zip|tar\.gz|tgz|node|exe|dll|so|dylib)$/i.test(f)) continue;
    const full = path.join(REPO_ROOT, f);
    try {
      const text = readFileSync(full, 'utf8');
      // Scan line by line so an inline test fixture can be exempted explicitly
      // without blinding a whole file or a whole `#[cfg(test)]` region — a real
      // key placed next to an exempted line still trips the gate.
      // To exempt, put `gate-allow-secret:` plus a reason on the same line.
      const hits = text.split('\n').filter(
        (line) => /\bsk-[A-Za-z0-9]{16,}\b/.test(line) && !line.includes('gate-allow-secret:'),
      );
      if (hits.length) bad.push(`${f} (${hits.length} line(s))`);
    } catch {
      // binary or unreadable, skip
    }
  }
  if (bad.length) {
    throw new Error(
      `suspected keys in: ${bad.slice(0, 5).join(', ')}\n` +
        `  If a hit is a deliberate test fixture, append a same-line comment:\n` +
        `    gate-allow-secret: <why this is not a real credential>`,
    );
  }
});

// 7. Developer credential file must never reach a release build.
check('GATE-11.8: dev credential store is debug-only', () => {
  const src = readFileSync(
    path.join(REPO_ROOT, 'apps/desktop/src-tauri/src/engine/credentials.rs'),
    'utf8',
  );
  // The whole module is compiled out of release builds.
  if (!/#\[cfg\(debug_assertions\)\]\s*\nmod dev_store/.test(src)) {
    throw new Error('dev_store module is not gated behind #[cfg(debug_assertions)]');
  }
  // Release still goes to the OS credential store.
  if (!src.includes('#[cfg(not(debug_assertions))]')) {
    throw new Error('no release-only keyring path found');
  }
  // The dev file lives outside the repo, so it can never be committed.
  if (src.includes('dev-credentials.json') && !src.includes('.inkstatute')) {
    throw new Error('dev credential path must live under the user home directory');
  }
  const tracked = run('git ls-files -z').split('\0').filter(Boolean);
  if (tracked.some((f) => f.includes('dev-credentials'))) {
    throw new Error('a dev credential file is tracked by git');
  }
});

if (!ok) {
  process.exit(1);
}
