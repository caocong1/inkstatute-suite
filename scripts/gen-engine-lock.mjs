#!/usr/bin/env node
// 本脚本是构建期工具，运行时不使用；装配由 Rust 侧完成。
//
// 职责：读 engines/dsh-pin.txt → 在临时目录 npm install 精确版本 →
//       读 package-lock.json 并校验 → 裁剪 → 产出 engines/engine-lock.json。

import { createHash } from 'node:crypto';
import { mkdtempSync, writeFileSync, readFileSync, rmSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, '..');
const PIN_FILE = join(REPO_ROOT, 'engines', 'dsh-pin.txt');
const CORDIS_FILE = join(REPO_ROOT, 'engines', 'acp.cordis.yml');
const OUTPUT_FILE = join(REPO_ROOT, 'engines', 'engine-lock.json');

function parsePin() {
  const text = readFileSync(PIN_FILE, 'utf8');
  const cfg = {};
  let inPackages = false;
  for (const raw of text.split('\n')) {
    const line = raw.split('#')[0].trimEnd();
    if (!line) continue;
    if (line.startsWith('packages=')) {
      inPackages = true;
      cfg.packages = [];
      const first = line.slice('packages='.length).trim();
      if (first) cfg.packages.push(first);
      continue;
    }
    if (inPackages) {
      if (line.startsWith('  ') || line.startsWith('\t')) {
        const pkg = line.trim();
        if (pkg) cfg.packages.push(pkg);
      } else if (line.includes('=')) {
        inPackages = false;
        const [k, ...v] = line.split('=');
        cfg[k.trim()] = v.join('=').trim();
      } else {
        inPackages = false;
      }
      continue;
    }
    if (line.includes('=')) {
      const [k, ...v] = line.split('=');
      cfg[k.trim()] = v.join('=').trim();
    }
  }
  return cfg;
}

function sha256File(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}

function tarballPathFromResolved(resolved) {
  const url = new URL(resolved);
  const path = url.pathname;
  if (!path.startsWith('/')) throw new Error(`unexpected resolved path: ${resolved}`);
  return path;
}

function main() {
  const pin = parsePin();
  const required = ['dsh_version', 'node_version', 'target_platform', 'registry', 'registry_fallback'];
  for (const k of required) {
    if (!pin[k]) throw new Error(`missing pin key: ${k}`);
  }
  if (!Array.isArray(pin.packages) || pin.packages.length === 0) {
    throw new Error('pin packages list empty');
  }

  const dshVersion = pin.dsh_version;
  const pkgsWithVersion = pin.packages.map(p => `${p}@${dshVersion}`);

  const tempDir = mkdtempSync(join(tmpdir(), 'dsh-lock-'));
  try {
    const packageJson = {
      name: 'inkstatute-engine-lock',
      version: '0.0.0',
      dependencies: Object.fromEntries(pin.packages.map(p => [p, dshVersion])),
    };
    writeFileSync(join(tempDir, 'package.json'), JSON.stringify(packageJson, null, 2));

    const registryArg = `--registry=${pin.registry}`;
    console.log(`npm install in ${tempDir} ...`);
    execSync(`npm install ${pkgsWithVersion.join(' ')} --no-audit --no-fund ${registryArg}`, {
      cwd: tempDir,
      stdio: 'inherit',
    });

    const lockPath = join(tempDir, 'package-lock.json');
    const lock = JSON.parse(readFileSync(lockPath, 'utf8'));

    if (lock.lockfileVersion !== 3) {
      throw new Error(`expected lockfileVersion 3, got ${lock.lockfileVersion}`);
    }

    const packages = lock.packages || {};
    let nestedCount = 0;
    for (const [k, v] of Object.entries(packages)) {
      if (!k) continue; // root entry
      const nestCount = k.split('node_modules').length - 1;
      if (nestCount > 1) {
        // npm may place a package nested when its required version conflicts
        // with the top-level version. The assembler handles any lock key as a
        // relative path under <engineDir>.
        nestedCount++;
      }
      if (!v.resolved) {
        throw new Error(`missing resolved in lock entry: ${k}`);
      }
      if (!v.integrity) {
        throw new Error(`missing integrity in lock entry: ${k}`);
      }
    }

    const outPackages = {};
    let sizeTotal = 0;
    const hasSize = [];
    for (const [k, v] of Object.entries(packages)) {
      if (!k) continue;
      const name = v.name || k.replace(/^node_modules\//, '');
      outPackages[k] = {
        name,
        version: v.version,
        integrity: v.integrity,
        tarball_path: tarballPathFromResolved(v.resolved),
      };
      if (v.size !== undefined) {
        sizeTotal += v.size;
        hasSize.push(true);
      } else {
        hasSize.push(false);
      }
    }

    const engineLock = {
      schema_version: '1.0.0',
      engine_version: dshVersion,
      node_version: pin.node_version,
      target_platform: pin.target_platform,
      compatible_app_range: '>=0.1.0 <1.0.0',
      cordis_config_sha256: sha256File(CORDIS_FILE),
      generated_at: new Date().toISOString(),
      prune: {
        'node-pty/prebuilds': pin.target_platform === 'win32-x64'
          ? ['darwin-arm64', 'darwin-x64', 'win32-arm64']
          : [],
      },
      packages: outPackages,
    };

    writeFileSync(OUTPUT_FILE, JSON.stringify(engineLock, null, 2) + '\n');

    const sizeText = hasSize.every(Boolean)
      ? `${(sizeTotal / 1024 / 1024).toFixed(2)} MB estimated`
      : 'unknown';
    console.log(`Wrote ${OUTPUT_FILE}`);
    console.log(`Packages: ${Object.keys(outPackages).length}`);
    console.log(`Nested lock entries: ${nestedCount}`);
    console.log(`Total download size: ${sizeText}`);
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
}

main();
