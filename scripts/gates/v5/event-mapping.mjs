// GATE-12: Event Mapping + Replay Token Budget
//
// Verifies that:
//   1. The committed `expected-envelopes.json` fixture (produced by
//      `cargo test -- --ignored dump_envelopes_from_fixture`) contains only
//      the 15 unified event types.
//   2. Feeding those envelopes through `packages/ui-core`'s `reduce` +
//      `initialState` produces a non-empty `RenderState` with at least one
//      assistant message and a terminal run status (completed/error).
//   3. No envelope payload leaks raw engine internals (no `stack`, `trace`,
//      `raw_payload`, `customer_document`, or `api_key` keys).
//   4. The replay token budget metadata is present: at least one envelope
//      carries `metadata.usage.prompt_tokens` > 0, satisfying the Phase 123
//      decision artifact's "prompt-token counts come from the observation
//      plane" requirement.
//
// Run: node scripts/gates/v5/event-mapping.mjs

import { readFileSync } from 'node:fs';
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

// Load the committed envelope fixture.
const fixturePath = path.join(
  REPO_ROOT,
  'apps/desktop/src-tauri/tests/fixtures/expected-envelopes.json',
);
const envelopes = JSON.parse(readFileSync(fixturePath, 'utf8'));

// Stub DOM globals before importing ui-core dist (which touches `document`
// and registers event listeners at module-load time). The reducer itself is
// pure — these stubs only satisfy the module's top-level side effects.
const noop = () => {};
const elementStub = {
  setAttribute: noop,
  getAttribute: () => null,
  addEventListener: noop,
  removeEventListener: noop,
  classList: { add: noop, remove: noop, contains: () => false, toggle: noop },
  style: {},
  dataset: {},
};
globalThis.document = {
  documentElement: elementStub,
  body: elementStub,
  head: elementStub,
  createElement: () => elementStub,
  createTextNode: () => elementStub,
  querySelector: () => null,
  querySelectorAll: () => [],
  getElementById: () => null,
  addEventListener: noop,
  removeEventListener: noop,
};
globalThis.window = globalThis;
globalThis.localStorage = {
  getItem: () => null,
  setItem: noop,
  removeItem: noop,
  clear: noop,
};
globalThis.matchMedia = () => ({ matches: false, addEventListener: noop, removeEventListener: noop });

// Load the reducer from the built ui-core dist.
// On Windows, dynamic import() requires a file:// URL, not a bare C:\ path.
const { pathToFileURL } = await import('node:url');
const uiCore = await import(
  pathToFileURL(path.join(REPO_ROOT, 'packages/ui-core/dist/index.js')).href
);
const { initialState, reduce } = uiCore;

const VALID_TYPES = new Set([
  'session.started',
  'message.delta',
  'message.completed',
  'thought.delta',
  'tool_call.started',
  'tool_call.delta',
  'tool_call.completed',
  'plan.updated',
  'phase.changed',
  'elicitation.requested',
  'permission.requested',
  'artifact.created',
  'citation.recorded',
  'run.state_changed',
  'error',
]);

check('fixture is non-empty array', () => {
  if (!Array.isArray(envelopes) || envelopes.length === 0) {
    throw new Error('expected-envelopes.json must be a non-empty array');
  }
});

check('all envelopes use the 15-type vocabulary', () => {
  for (const env of envelopes) {
    if (!VALID_TYPES.has(env.event_type)) {
      throw new Error(`invalid event_type: ${env.event_type}`);
    }
  }
});

check('seq is monotonic non-decreasing', () => {
  let prev = -1;
  for (const env of envelopes) {
    if (typeof env.seq !== 'number' || env.seq < prev) {
      throw new Error(`seq regression at envelope ${env.event_id}: ${env.seq} < ${prev}`);
    }
    prev = env.seq;
  }
});

check('no raw engine internals leak into payloads', () => {
  const FORBIDDEN_KEYS = new Set([
    'stack',
    'trace',
    'raw_payload',
    'customer_document',
    'api_key',
    'apiKey',
    'authorization',
  ]);
  function scan(obj, pathStr) {
    if (obj == null) return;
    if (typeof obj === 'string') {
      // Scan for accidental key-like tokens in strings too.
      for (const key of FORBIDDEN_KEYS) {
        if (obj.toLowerCase().includes(key.toLowerCase())) {
          throw new Error(`forbidden key "${key}" appears in string at ${pathStr}`);
        }
      }
      return;
    }
    if (typeof obj !== 'object') return;
    for (const [k, v] of Object.entries(obj)) {
      if (FORBIDDEN_KEYS.has(k)) {
        throw new Error(`forbidden key "${k}" at ${pathStr}.${k}`);
      }
      scan(v, `${pathStr}.${k}`);
    }
  }
  for (const env of envelopes) {
    scan(env.payload, `${env.event_id}.payload`);
    scan(env.metadata, `${env.event_id}.metadata`);
  }
});

check('reducer produces a non-empty RenderState', () => {
  let state = initialState();
  for (const env of envelopes) {
    state = reduce(state, env);
  }
  if (!state) throw new Error('reducer returned null/undefined state');
  if (!Array.isArray(state.messages)) {
    throw new Error('state.messages is not an array');
  }
  if (state.messages.length === 0) {
    throw new Error('state.messages is empty — expected at least one assistant message');
  }
  const hasAssistant = state.messages.some((m) => m.role === 'assistant');
  if (!hasAssistant) {
    throw new Error('no assistant message in RenderState');
  }
  if (state.runStatus === 'idle') {
    throw new Error('runStatus is still idle — expected terminal status');
  }
});

check('reducer reaches a terminal run status', () => {
  let state = initialState();
  for (const env of envelopes) {
    state = reduce(state, env);
  }
  const terminal = ['completed', 'cancelled', 'error'];
  if (!terminal.includes(state.runStatus)) {
    throw new Error(`runStatus is "${state.runStatus}", expected one of ${terminal.join(', ')}`);
  }
});

check('replay token budget metadata is present', () => {
  const usageEnv = envelopes.find(
    (e) => e.metadata && e.metadata.usage && typeof e.metadata.usage.prompt_tokens === 'number',
  );
  if (!usageEnv) {
    throw new Error('no envelope carries metadata.usage.prompt_tokens — token budget not measurable');
  }
  if (usageEnv.metadata.usage.prompt_tokens <= 0) {
    throw new Error(`prompt_tokens is ${usageEnv.metadata.usage.prompt_tokens}, expected > 0`);
  }
});

check('session title metadata is attached', () => {
  const titleEnv = envelopes.find(
    (e) => e.metadata && typeof e.metadata.session_title === 'string',
  );
  if (!titleEnv) {
    throw new Error('no envelope carries metadata.session_title');
  }
  if (!titleEnv.metadata.session_title.trim()) {
    throw new Error('session_title is empty');
  }
});

if (!ok) {
  console.error('\nGATE-12 FAILED');
  process.exit(1);
}
console.log('\nGATE-12 PASSED');
