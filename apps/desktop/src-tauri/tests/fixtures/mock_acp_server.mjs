#!/usr/bin/env node
// Mock ACP server for offline Rust integration tests.
// Reads NDJSON from stdin and emits the protocol shapes documented in Phase 123.

import { createInterface } from 'readline';
import process from 'process';

const rl = createInterface({ input: process.stdin });

let nextId = 1;
const sessions = new Map();
const pendingPermissions = new Map();

function send(obj) {
  process.stdout.write(JSON.stringify(obj) + '\n');
}

function initializeResponse(id) {
  send({
    jsonrpc: '2.0',
    id,
    result: {
      protocolVersion: 1,
      agentInfo: { name: 'deepseek-harness-acp', version: '0.0.1' },
      agentCapabilities: {
        promptCapabilities: { image: false, audio: false, embeddedContext: false },
      },
      authMethods: [],
    },
  });
}

function newSessionResponse(id, cwd) {
  if (cwd[0] !== '/' && !/^\w:[\\/]/.test(cwd)) {
    send({
      jsonrpc: '2.0',
      id,
      error: { code: -32602, message: 'cwd must be absolute' },
    });
    return;
  }
  const sessionId = `mock-session-${nextId++}`;
  sessions.set(sessionId, { chunks: 0, timer: null });
  send({
    jsonrpc: '2.0',
    id,
    result: { sessionId },
  });
}

function streamChunk(sessionId) {
  send({
    jsonrpc: '2.0',
    method: 'session/update',
    params: {
      sessionId,
      update: {
        sessionUpdate: 'agent_message_chunk',
        content: { type: 'text', text: 'chunk' },
      },
    },
  });
}

function promptResponse(id, sessionId, cancelled) {
  send({
    jsonrpc: '2.0',
    id,
    result: { stopReason: cancelled ? 'cancelled' : 'end_turn' },
  });
}

async function handlePrompt(id, sessionId) {
  const state = sessions.get(sessionId);
  if (!state) return;

  let cancelled = false;
  let emitted = 0;
  const targetChunks = 5;

  const permissionMode = process.env.MOCK_REQUEST_PERMISSION === '1';

  await new Promise((resolve) => {
    const interval = setInterval(() => {
      if (state.cancelled) {
        cancelled = true;
        clearInterval(interval);
        resolve();
        return;
      }

      if (emitted < targetChunks) {
        streamChunk(sessionId);
        emitted++;
      }

      if (emitted >= targetChunks && !permissionMode) {
        clearInterval(interval);
        resolve();
      }
    }, 250);

    state.timer = interval;
    state.resolve = resolve;

    if (permissionMode) {
      const permissionId = 9001;
      pendingPermissions.set(permissionId, () => {
        if (state.resolve) state.resolve();
      });
      setTimeout(() => {
        send({
          jsonrpc: '2.0',
          id: permissionId,
          method: 'session/request_permission',
          params: {
            sessionId,
            toolCall: { toolCallId: 'tc-1' },
            options: [
              { optionId: 'allow-once', name: 'Allow once', kind: 'allow' },
              { optionId: 'reject-once', name: 'Reject once', kind: 'reject' },
            ],
          },
        });
      }, 300);
    }
  });

  promptResponse(id, sessionId, cancelled);
}

rl.on('line', (line) => {
  let msg;
  try {
    msg = JSON.parse(line);
  } catch {
    return;
  }

  const method = msg.method;
  const id = msg.id;
  const params = msg.params || {};

  if (method === 'initialize') {
    initializeResponse(id);
  } else if (method === 'session/new') {
    newSessionResponse(id, params.cwd);
  } else if (method === 'session/prompt') {
    const sessionId = params.sessionId;
    if (typeof id === 'number' || typeof id === 'string') {
      handlePrompt(id, sessionId);
    }
  } else if (method === 'session/cancel') {
    const sessionId = params.sessionId;
    const state = sessions.get(sessionId);
    if (state) {
      state.cancelled = true;
    }
    // Notifications do not receive a response.
  } else if (method === undefined && id !== undefined && id !== null) {
    // Client-to-server response (e.g. permission answer).
    const resolve = pendingPermissions.get(id);
    if (resolve) {
      resolve();
      pendingPermissions.delete(id);
    }
  } else if (id !== undefined && id !== null) {
    // Unknown request: respond to avoid client hang, but keep it generic.
    send({
      jsonrpc: '2.0',
      id,
      error: { code: -32601, message: `Method not found: ${method}` },
    });
  }
});
