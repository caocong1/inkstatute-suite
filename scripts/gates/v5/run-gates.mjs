import { execSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '..', '..', '..');

const GATES = [
  { name: 'engine-assembly', script: 'scripts/gates/v5/engine-assembly.mjs' },
  { name: 'event-mapping', script: 'scripts/gates/v5/event-mapping.mjs' },
  { name: 'token-budget', script: 'scripts/gates/v5/token-budget.mjs' },
  { name: 'guardrails', script: 'scripts/gates/v5/guardrails.mjs' },
];

function run(cmd) {
  return execSync(cmd, { encoding: 'utf8', cwd: REPO_ROOT });
}

function runNode(script) {
  return run(`node ${script}`);
}

function main() {
  const single = process.argv[2];
  const toRun = single
    ? GATES.filter(g => g.name === single)
    : GATES;

  if (toRun.length === 0) {
    console.error(`Unknown gate: ${single}`);
    console.error(`Known gates: ${GATES.map(g => g.name).join(', ')}`);
    process.exit(1);
  }

  let passed = 0;
  let failed = 0;

  for (const gate of toRun) {
    const start = Date.now();
    try {
      runNode(gate.script);
      const ms = Date.now() - start;
      console.log(`[PASS] ${gate.name} (${ms}ms)`);
      passed++;
    } catch (e) {
      const ms = Date.now() - start;
      console.log(`[FAIL] ${gate.name} (${ms}ms)`);
      console.error(e.stderr || e.message);
      failed++;
    }
  }

  console.log(`\n${passed} passed, ${failed} failed`);
  if (failed > 0) process.exit(1);
}

main();
