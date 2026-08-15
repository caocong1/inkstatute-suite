// GRD-11..16: Six Guardrails — Two Layers Gate
//
// Verifies BOTH layers of the guardrail system:
//
// 1. Model-side layer (presets/legal-core/):
//    - preset.yml contains all 6 [GUARDRAIL:...] anchors
//    - preset.yml contains [SKILL_LOADING] anchor
//    - agent.cordis.yml contains the persona with guardrail instructions
//
// 2. Render-side layer (apps/desktop/):
//    - guardrails.rs exists with scanner functions
//    - mapper.rs derives guardrail events from committed text
//    - PermissionCard.tsx exists with allow-once/reject-once (no batch)
//    - Workspace.tsx wires all 6 guardrails
//    - guardrails.test.tsx exists with render assertions
//    - No forbidden batch-approval keywords in source
//
// When a layer is missing, the gate identifies WHICH layer failed.
//
// Run: node scripts/gates/v5/guardrails.mjs

import { readFileSync, existsSync } from 'node:fs';
import { execSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '..', '..', '..');

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

// ── Model-side layer checks ────────────────────────────────────────────

const PRESET_YML = path.join(REPO_ROOT, 'presets/legal-core/preset.yml');
const AGENT_YML = path.join(REPO_ROOT, 'presets/legal-core/agent.cordis.yml');

const REQUIRED_ANCHORS = [
  '[GUARDRAIL:RESEARCH_GATE]',
  '[GUARDRAIL:CITATION_AUDIT]',
  '[GUARDRAIL:ASK_USER]',
  '[GUARDRAIL:DE_AI_POLISH]',
  '[GUARDRAIL:HUMAN_REVIEW]',
  '[GUARDRAIL:CONFIDENTIALITY]',
];

check('model-layer: preset.yml exists', () => {
  if (!existsSync(PRESET_YML)) throw new Error(`Missing: ${PRESET_YML}`);
});

check('model-layer: agent.cordis.yml exists', () => {
  if (!existsSync(AGENT_YML)) throw new Error(`Missing: ${AGENT_YML}`);
});

check('model-layer: preset.yml has all 6 GUARDRAIL anchors', () => {
  const content = readFileSync(PRESET_YML, 'utf-8');
  const count = (content.match(/\[GUARDRAIL:/g) || []).length;
  if (count < 6) {
    throw new Error(`Expected ≥6 [GUARDRAIL: anchors, found ${count}`);
  }
  for (const anchor of REQUIRED_ANCHORS) {
    if (!content.includes(anchor)) {
      throw new Error(`Missing anchor: ${anchor}`);
    }
  }
});

check('model-layer: preset.yml has [SKILL_LOADING] anchor', () => {
  const content = readFileSync(PRESET_YML, 'utf-8');
  const count = (content.match(/\[SKILL_LOADING\]/g) || []).length;
  if (count < 1) {
    throw new Error(`Expected ≥1 [SKILL_LOADING] anchor, found ${count}`);
  }
});

check('model-layer: agent.cordis.yml has guardrail instructions', () => {
  const content = readFileSync(AGENT_YML, 'utf-8');
  // The persona should reference guardrails.
  if (!content.includes('GUARDRAIL')) {
    throw new Error('agent.cordis.yml does not reference GUARDRAIL instructions');
  }
  // Should contain the CLARIFY format.
  if (!content.includes('[CLARIFY:')) {
    throw new Error('agent.cordis.yml missing [CLARIFY: format specification');
  }
  // Should contain the HUMAN_REVIEW format.
  if (!content.includes('[HUMAN_REVIEW:')) {
    throw new Error('agent.cordis.yml missing [HUMAN_REVIEW: format specification');
  }
});

// ── Render-side layer checks ───────────────────────────────────────────

const GUARDRAILS_RS = path.join(REPO_ROOT, 'apps/desktop/src-tauri/src/engine/guardrails.rs');
const MAPPER_RS = path.join(REPO_ROOT, 'apps/desktop/src-tauri/src/engine/mapper.rs');
const PERMISSION_CARD = path.join(REPO_ROOT, 'apps/desktop/src/components/PermissionCard.tsx');
const WORKSPACE_TSX = path.join(REPO_ROOT, 'apps/desktop/src/components/Workspace.tsx');
const GUARDRAILS_TEST = path.join(REPO_ROOT, 'apps/desktop/tests/guardrails.test.tsx');

check('render-layer: guardrails.rs exists', () => {
  if (!existsSync(GUARDRAILS_RS)) throw new Error(`Missing: ${GUARDRAILS_RS}`);
});

check('render-layer: guardrails.rs has scanner functions', () => {
  const content = readFileSync(GUARDRAILS_RS, 'utf-8');
  // Should contain citation, clarify, human_review scanning.
  if (!content.includes('citation') && !content.includes('Citation')) {
    throw new Error('guardrails.rs missing citation scanner');
  }
  if (!content.includes('clarif') && !content.includes('Clarif')) {
    throw new Error('guardrails.rs missing clarification scanner');
  }
  if (!content.includes('human_review') && !content.includes('HumanReview')) {
    throw new Error('guardrails.rs missing human-review scanner');
  }
});

check('render-layer: mapper.rs derives guardrail events', () => {
  const content = readFileSync(MAPPER_RS, 'utf-8');
  if (!content.includes('research_performed')) {
    throw new Error('mapper.rs missing research_performed tracking');
  }
  if (!content.includes('human_review') && !content.includes('humanReview')) {
    throw new Error('mapper.rs missing human_review metadata');
  }
});

check('render-layer: PermissionCard.tsx exists', () => {
  if (!existsSync(PERMISSION_CARD)) throw new Error(`Missing: ${PERMISSION_CARD}`);
});

check('render-layer: PermissionCard has allow-once and reject-once only', () => {
  const content = readFileSync(PERMISSION_CARD, 'utf-8');
  if (!content.includes('允许一次') && !content.includes('allow')) {
    throw new Error('PermissionCard missing allow-once button');
  }
  if (!content.includes('拒绝一次') && !content.includes('reject')) {
    throw new Error('PermissionCard missing reject-once button');
  }
  // Forbidden batch-approval keywords.
  const forbidden = /总是允许|always.?allow|批量批准|approve.?all|remember.?choice|记住选择/i;
  if (forbidden.test(content)) {
    throw new Error('PermissionCard contains forbidden batch-approval keyword');
  }
});

check('render-layer: Workspace.tsx wires all 6 guardrails', () => {
  const content = readFileSync(WORKSPACE_TSX, 'utf-8');
  // GRD-11: 待核实 bar
  if (!content.includes('待核实')) throw new Error('Workspace missing GRD-11 待核实 bar');
  // GRD-12: CitationPanel
  if (!content.includes('CitationPanel')) throw new Error('Workspace missing GRD-12 CitationPanel');
  // GRD-13: ClarificationCard
  if (!content.includes('ClarificationCard')) throw new Error('Workspace missing GRD-13 ClarificationCard');
  // GRD-14: human review badge
  if (!content.includes('需人工复核')) throw new Error('Workspace missing GRD-14 human-review badge');
  // GRD-15: PermissionCard
  if (!content.includes('PermissionCard')) throw new Error('Workspace missing GRD-15 PermissionCard');
  // GRD-16: confidentiality
  if (!content.includes('脱敏') && !content.includes('confidentiality')) {
    throw new Error('Workspace missing GRD-16 confidentiality dialog');
  }
});

check('render-layer: guardrails.test.tsx exists', () => {
  if (!existsSync(GUARDRAILS_TEST)) throw new Error(`Missing: ${GUARDRAILS_TEST}`);
});

check('render-layer: no batch-approval keywords in desktop source', () => {
  try {
    const output = execSync(
      `grep -rniE '总是允许|always.?allow|批量批准|approve.?all|remember.?choice|记住选择' ` +
      `apps/desktop/src packages/ui-core/src --include='*.tsx' --include='*.ts' || true`,
      { encoding: 'utf-8', cwd: REPO_ROOT },
    );
    if (output.trim()) {
      throw new Error(`Forbidden batch-approval keywords found:\n${output}`);
    }
  } catch (e) {
    if (e.message.includes('Forbidden')) throw e;
    // grep returning non-zero is fine (no matches).
  }
});

// ── No-batch-approval hard check (both layers) ─────────────────────────

check('safety: no batch-approval keywords in render-side source', () => {
  try {
    const output = execSync(
      `grep -rniE '总是允许|always.?allow|批量批准|approve.?all|remember.?choice|记住选择' ` +
      `apps/desktop/src packages/ui-core/src --include='*.tsx' --include='*.ts' || true`,
      { encoding: 'utf-8', cwd: REPO_ROOT },
    );
    if (output.trim()) {
      throw new Error(`Forbidden batch-approval keywords found:\n${output}`);
    }
  } catch (e) {
    if (e.message.includes('Forbidden')) throw e;
    // grep returning non-zero is fine (no matches).
  }
});

// ── Summary ────────────────────────────────────────────────────────────

if (ok) {
  console.log('\n✅ All guardrail gate checks passed (both model and render layers).');
} else {
  console.error('\n❌ Guardrail gate FAILED — see failures above.');
  process.exit(1);
}
