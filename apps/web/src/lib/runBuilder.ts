/**
 * runBuilder — constructs the POST /v1/runs body from simple web-client inputs.
 *
 * The Gateway's `_handle_create_run()` expects a body with:
 * - `turn`: An AgentTurn payload (turn_id, conversation_id, channel, user_id,
 *   message_type, received_at, content, attachments, ...)
 * - `solution`: A SolutionBinding payload (solution_id, backend_id?, ...)
 * - Optional: tenant_id, session_id, workspace_id, bot_instance_id, metadata
 *
 * This module centralizes the body shape so changes to the Gateway contract
 * only require updating this one file.
 */

export interface RunBodyAttachment {
  attachment_id: string;
  kind: string;
  uri: string;
  name?: string;
  mime_type?: string;
}

export interface RunBodyOptions {
  conversationId: string;
  prompt: string;
  userId: string;
  tenantId: string;
  sessionId?: string;
  attachments?: RunBodyAttachment[];
  backendId?: string;
}

/**
 * Build the POST /v1/runs body from simple web-client inputs.
 *
 * The returned object is typed as `unknown` because the Gateway accepts
 * a raw JSON body — the shape is validated server-side by `_build_agent_turn()`
 * and `_build_solution_binding()`.
 */
export function buildRunBody(options: RunBodyOptions): unknown {
  const turn: Record<string, unknown> = {
    turn_id: crypto.randomUUID(),
    conversation_id: options.conversationId,
    channel: "web",
    user_id: options.userId,
    message_type: "text",
    received_at: new Date().toISOString(),
    content: options.prompt,
    attachments: options.attachments ?? [],
  };

  const solution: Record<string, unknown> = {
    solution_id: "inkstatute-default",
  };
  if (options.backendId) {
    solution.backend_id = options.backendId;
  }

  const body: Record<string, unknown> = {
    turn,
    solution,
    tenant_id: options.tenantId,
  };

  if (options.sessionId) {
    body.session_id = options.sessionId;
  }

  return body;
}
