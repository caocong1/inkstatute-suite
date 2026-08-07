/**
 * runBuilder tests — verifies the POST /v1/runs body shape.
 */
import { describe, it, expect } from "vitest";
import { buildRunBody } from "../src/lib/runBuilder";

describe("buildRunBody", () => {
  it("produces correct shape with all required turn fields", () => {
    const body = buildRunBody({
      conversationId: "conv-1",
      prompt: "起草一份买卖合同",
      userId: "user-1",
      tenantId: "tenant-1",
    }) as Record<string, any>;

    const turn = body.turn;
    expect(turn).toBeDefined();
    expect(turn.turn_id).toEqual(expect.any(String));
    expect(turn.turn_id.length).toBeGreaterThan(0);
    expect(turn.conversation_id).toBe("conv-1");
    expect(turn.channel).toBe("web");
    expect(turn.user_id).toBe("user-1");
    expect(turn.message_type).toBe("text");
    expect(turn.received_at).toEqual(expect.any(String));
    expect(turn.content).toBe("起草一份买卖合同");
    expect(turn.attachments).toEqual([]);
  });

  it("produces solution with solution_id set", () => {
    const body = buildRunBody({
      conversationId: "conv-1",
      prompt: "test",
      userId: "user-1",
      tenantId: "tenant-1",
    }) as Record<string, any>;

    expect(body.solution).toBeDefined();
    expect(body.solution.solution_id).toBe("inkstatute-default");
  });

  it("generates unique turn_id per call", () => {
    const body1 = buildRunBody({
      conversationId: "conv-1",
      prompt: "test",
      userId: "user-1",
      tenantId: "tenant-1",
    }) as Record<string, any>;
    const body2 = buildRunBody({
      conversationId: "conv-1",
      prompt: "test",
      userId: "user-1",
      tenantId: "tenant-1",
    }) as Record<string, any>;

    expect(body1.turn.turn_id).not.toBe(body2.turn.turn_id);
  });

  it("includes attachments when provided", () => {
    const attachments = [
      {
        attachment_id: "att-1",
        kind: "file",
        uri: "upload://att-1",
        name: "contract.pdf",
        mime_type: "application/pdf",
      },
    ];
    const body = buildRunBody({
      conversationId: "conv-1",
      prompt: "test",
      userId: "user-1",
      tenantId: "tenant-1",
      attachments,
    }) as Record<string, any>;

    expect(body.turn.attachments).toEqual(attachments);
  });

  it("omits attachments (defaults to empty array) when not provided", () => {
    const body = buildRunBody({
      conversationId: "conv-1",
      prompt: "test",
      userId: "user-1",
      tenantId: "tenant-1",
    }) as Record<string, any>;

    expect(body.turn.attachments).toEqual([]);
  });

  it("includes tenant_id and session_id when provided", () => {
    const body = buildRunBody({
      conversationId: "conv-1",
      prompt: "test",
      userId: "user-1",
      tenantId: "tenant-1",
      sessionId: "sess-1",
    }) as Record<string, any>;

    expect(body.tenant_id).toBe("tenant-1");
    expect(body.session_id).toBe("sess-1");
  });

  it("includes backend_id in solution when provided", () => {
    const body = buildRunBody({
      conversationId: "conv-1",
      prompt: "test",
      userId: "user-1",
      tenantId: "tenant-1",
      backendId: "hermes",
    }) as Record<string, any>;

    expect(body.solution.backend_id).toBe("hermes");
  });
});
