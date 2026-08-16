// SKL-13: Token Budget Gate
//
// Verifies that the skill catalog rendered into the model prefix does not
// exceed the token budget (default 8,000 characters, overridable via
// INKSTATUTE_SKILL_BUDGET env var).
//
// The gate:
//   1. Scans `presets/*/` and (if exists) `<app_root>/skills/current/*/`
//      for `SKILL.md` files.
//   2. Parses each `SKILL.md` frontmatter for `name` and `description`.
//   3. Estimates render length per skill as: `- \`{name}\`: {description}\n`
//   4. Asserts total length ≤ budget (INKSTATUTE_SKILL_BUDGET, default 8000).
//   5. On overflow: prints the overflow amount and the top 10 longest
//      descriptions for diagnosis.
//   6. Asserts: every SKILL.md frontmatter is parseable, `name` is unique,
//      and `name` matches the directory name.
//
// Run: node scripts/gates/v5/token-budget.mjs
// Override budget: INKSTATUTE_SKILL_BUDGET=10000 node scripts/gates/v5/token-budget.mjs

import { readFileSync, readdirSync, existsSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '..', '..', '..');

const DEFAULT_BUDGET = 8000;
const BUDGET = parseInt(process.env.INKSTATUTE_SKILL_BUDGET || String(DEFAULT_BUDGET), 10);

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

/**
 * Parses YAML-like frontmatter from a SKILL.md file.
 * Expects:
 *   ---
 *   name: skill-name
 *   description: some description
 *   ---
 *
 * Returns { name, description } or throws if frontmatter is unparseable.
 */
function parseFrontmatter(content, filePath) {
  // Normalize CRLF → LF so the regex works on Windows-checked-out files.
  const normalized = content.replace(/\r\n/g, '\n');
  const fmMatch = normalized.match(/^---\n([\s\S]*?)\n---/);
  if (!fmMatch) {
    throw new Error(`no frontmatter block found in ${filePath}`);
  }
  const fm = fmMatch[1];

  const nameMatch = fm.match(/^name:\s*(.+)$/m);
  if (!nameMatch) {
    throw new Error(`frontmatter missing 'name' field in ${filePath}`);
  }
  const name = nameMatch[1].trim();

  const descMatch = fm.match(/^description:\s*(.+)$/m);
  if (!descMatch) {
    throw new Error(`frontmatter missing 'description' field in ${filePath}`);
  }
  const description = descMatch[1].trim();

  return { name, description };
}

/**
 * Recursively finds all SKILL.md files under a given root directory.
 * Returns array of { filePath, dirName } where dirName is the immediate
 * parent directory name (should match the skill name).
 */
function findSkillFiles(rootDir) {
  const results = [];

  if (!existsSync(rootDir)) return results;

  function walk(dir) {
    let entries;
    try {
      entries = readdirSync(dir);
    } catch {
      return;
    }

    for (const entry of entries) {
      const fullPath = path.join(dir, entry);
      let stat;
      try {
        stat = statSync(fullPath);
      } catch {
        continue;
      }

      if (stat.isDirectory()) {
        walk(fullPath);
      } else if (entry === 'SKILL.md') {
        // The skill name directory is the parent of SKILL.md.
        // But in our structure: <root>/<domain>/<skill-name>/SKILL.md
        // or: <root>/<skill-name>/SKILL.md
        // We want the immediate parent directory name.
        const dirName = path.basename(path.dirname(fullPath));
        results.push({ filePath: fullPath, dirName });
      }
    }
  }

  walk(rootDir);
  return results;
}

/**
 * Scans the presets directory and returns all skill entries.
 * Structure: presets/<domain>/skills/<skill-name>/SKILL.md
 */
function scanPresets() {
  const presetsRoot = path.join(REPO_ROOT, 'presets');
  const skillFiles = [];

  if (!existsSync(presetsRoot)) return skillFiles;

  const domains = readdirSync(presetsRoot).filter((d) => {
    const dPath = path.join(presetsRoot, d);
    return statSync(dPath).isDirectory() && d.startsWith('legal-');
  });

  for (const domain of domains) {
    const domainSkills = path.join(presetsRoot, domain, 'skills');
    if (!existsSync(domainSkills)) continue;
    const files = findSkillFiles(domainSkills);
    for (const f of files) {
      skillFiles.push({ ...f, domain });
    }
  }

  return skillFiles;
}

/**
 * Scans the content pack skills directory if it exists.
 * Structure: <app_root>/skills/current/<domain>/<skill-name>/SKILL.md
 */
function scanContentPack() {
  const appRoot = process.env.INKSTATUTE_APP_ROOT;
  if (!appRoot) return [];

  const contentSkills = path.join(appRoot, 'skills', 'current');
  if (!existsSync(contentSkills)) return [];

  return findSkillFiles(contentSkills);
}

function main() {
  // Gather all skill files from presets and content pack.
  const presetFiles = scanPresets();
  const contentFiles = scanContentPack();

  const allFiles = [...presetFiles, ...contentFiles];

  if (allFiles.length === 0) {
    console.error('FAIL: no SKILL.md files found in presets/ or content pack');
    process.exit(1);
  }

  // Parse all frontmatter and collect entries.
  const entries = [];
  const nameSet = new Set();
  const errors = [];

  for (const { filePath, dirName, domain } of allFiles) {
    try {
      const content = readFileSync(filePath, 'utf8');
      const { name, description } = parseFrontmatter(content, filePath);
      entries.push({ name, description, filePath, dirName, domain });

      // Check name uniqueness.
      if (nameSet.has(name)) {
        errors.push(`duplicate skill name: '${name}' (in ${filePath})`);
      }
      nameSet.add(name);

      // Check name matches directory name.
      if (name !== dirName) {
        errors.push(
          `skill name '${name}' does not match directory name '${dirName}' (in ${filePath})`
        );
      }
    } catch (e) {
      errors.push(e.message);
    }
  }

  // Gate 1: Frontmatter parseable, name unique, name matches dir.
  check('frontmatter parseable + name unique + name matches dir', () => {
    if (errors.length > 0) {
      throw new Error(`${errors.length} error(s):\n  ${errors.slice(0, 10).join('\n  ')}`);
    }
  });

  // Gate 2: Token budget — total render length ≤ budget.
  // Render format per skill: `- \`{name}\`: {description}\n`
  check(`token budget ≤ ${BUDGET} chars`, () => {
    let totalLength = 0;
    const perSkill = [];

    for (const entry of entries) {
      const rendered = `- \`${entry.name}\`: ${entry.description}\n`;
      totalLength += rendered.length;
      perSkill.push({ ...entry, rendered, renderedLength: rendered.length });
    }

    console.log(`  Total skills: ${entries.length}`);
    console.log(`  Total render length: ${totalLength} chars (budget: ${BUDGET})`);

    if (totalLength > BUDGET) {
      const overflow = totalLength - BUDGET;
      console.log(`  OVERFLOW: ${overflow} chars over budget`);

      // Print top 10 longest descriptions.
      const sorted = perSkill.sort((a, b) => b.renderedLength - a.renderedLength);
      console.log('  Top 10 longest entries:');
      for (let i = 0; i < Math.min(10, sorted.length); i++) {
        const e = sorted[i];
        console.log(
          `    ${i + 1}. [${e.renderedLength} chars] ${e.name}: ${e.description.substring(0, 60)}${e.description.length > 60 ? '...' : ''}`
        );
      }

      throw new Error(`token budget exceeded: ${totalLength} > ${BUDGET} (overflow: ${overflow} chars)`);
    }
  });

  console.log(`\n${ok ? 'ALL CHECKS PASSED' : 'SOME CHECKS FAILED'}`);
  if (!ok) process.exit(1);
}

main();
