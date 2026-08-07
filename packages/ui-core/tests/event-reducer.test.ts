/**
 * Event reducer tests — fixture-driven tests proving the pure reducer
 * correctly processes all 13 unified event types.
 */

import { describe, it, expect } from "vitest";
import { reduce, initialState, traceToolLabel, normalizeClarification } from "../src/event-reducer";
import type { RenderState } from "../src/event-reducer";
import type { RunEventEnvelope } from "@inkstatute/platform-sdk-ts/events";
import type { ElicitationRequestedPayload } from "@inkstatute/platform-sdk-ts/events";
import fixtureEvents from "./fixtures/events.json";

const events = fixtureEvents as RunEventEnvelope[];

function feedAll(events: RunEventEnvelope[]): RenderState {
  return events.reduce((state, event) => reduce(state, event), initialState());
}

describe("event-reducer", () => {
  describe("session.started", () => {
    it("sets backendId and runStatus", () => {
      const state = reduce(initialState(), events[0]);
      expect(state.backendId).toBe("hermes");
      expect(state.runStatus).toBe("running");
      expect(state.runId).toBe("run-test-001");
    });
  });

  describe("full fixture feed", () => {
    const finalState = feedAll(events);

    it("has 1 finalized message", () => {
      expect(finalState.messages).toHaveLength(1);
      expect(finalState.messages[0].content).toContain("合同审查报告");
      expect(finalState.messages[0].completed).toBe(true);
    });

    it("has currentPhase = review", () => {
      expect(finalState.currentPhase).toBe("review");
    });

    it("has 1 artifact", () => {
      expect(finalState.artifacts).toHaveLength(1);
      expect(finalState.artifacts[0].name).toBe("合同审查报告.docx");
    });

    it("has 3 citations", () => {
      expect(finalState.citations).toHaveLength(3);
      expect(finalState.citations[0].status).toBe("verified");
      expect(finalState.citations[1].status).toBe("retrieved");
      expect(finalState.citations[2].status).toBe("unverified");
    });

    it("has runStatus = completed", () => {
      expect(finalState.runStatus).toBe("completed");
    });

    it("has lastSeq = 15", () => {
      expect(finalState.lastSeq).toBe(15);
    });

    it("has thinking text from thought.delta", () => {
      expect(finalState.thinking).toBe("正在分析需求...");
    });

    it("has clarification from elicitation.requested", () => {
      expect(finalState.clarification).not.toBeNull();
      expect(finalState.clarification?.id).toBe("int-1");
      expect(finalState.clarification?.intro).toBe("需要补充信息");
      expect(finalState.clarification?.questions).toHaveLength(2);
    });

    it("has streamingBuffer cleared after message.completed", () => {
      expect(finalState.streamingBuffer).toBe("");
    });
  });

  describe("message.delta accumulation", () => {
    it("accumulates deltas in streamingBuffer", () => {
      let state = initialState();
      state = reduce(state, events[0]); // session.started
      state = reduce(state, events[8]); // message.delta seq 9
      expect(state.streamingBuffer).toBe("根据您的要求，");
      state = reduce(state, events[9]); // message.delta seq 10
      expect(state.streamingBuffer).toBe("根据您的要求，拟定以下文书：");
    });
  });

  describe("message.completed finalization", () => {
    it("finalizes message and clears streamingBuffer", () => {
      let state = initialState();
      state = reduce(state, events[0]); // session.started
      state = reduce(state, events[8]); // delta 1
      state = reduce(state, events[9]); // delta 2
      expect(state.streamingBuffer).not.toBe("");
      state = reduce(state, events[10]); // message.completed
      expect(state.messages).toHaveLength(1);
      expect(state.messages[0].content).toBe("根据您的要求，拟定以下文书：合同审查报告");
      expect(state.streamingBuffer).toBe("");
    });
  });

  describe("lastSeq update", () => {
    it("updates lastSeq on every event", () => {
      let state = initialState();
      for (let i = 0; i < 5; i++) {
        state = reduce(state, events[i]);
        expect(state.lastSeq).toBe(events[i].seq);
      }
    });
  });

  describe("traceToolLabel", () => {
    it("maps legal_search to 聚合检索法律依据", () => {
      expect(traceToolLabel("legal_search").label).toBe("聚合检索法律依据");
    });

    it("maps mcp__* law to 检索法律法规与类案", () => {
      expect(traceToolLabel("mcp__law_search").label).toBe("检索法律法规与类案");
    });

    it("maps mcp__* legal to 检索法律法规与类案", () => {
      expect(traceToolLabel("mcp__legal_db").label).toBe("检索法律法规与类案");
    });

    it("maps ask_user to 发现还需要补充信息", () => {
      expect(traceToolLabel("ask_user").label).toBe("发现还需要补充信息");
    });

    it("maps unknown tools to 处理辅助任务", () => {
      expect(traceToolLabel("unknown_tool").label).toBe("处理辅助任务");
    });
  });

  describe("normalizeClarification", () => {
    it("caps at 4 questions", () => {
      const payload: ElicitationRequestedPayload = {
        interrupt_id: "int-test",
        intro: "test",
        questions: Array.from({ length: 5 }, (_, i) => ({
          id: `q${i + 1}`,
          question: `问题${i + 1}`,
          options: [{ label: "选项A", value: "a" }],
        })),
      };
      const result = normalizeClarification(payload);
      expect(result.questions).toHaveLength(4);
    });

    it("generates option IDs when missing", () => {
      const payload: ElicitationRequestedPayload = {
        interrupt_id: "int-test",
        intro: "test",
        questions: [
          {
            id: "q1",
            question: "test question",
            options: [
              { label: "选项A", value: "a" },
              { label: "选项B", value: "b" },
            ],
          },
        ],
      };
      const result = normalizeClarification(payload);
      // Options already have no id field — normalizeClarification generates them
      expect(result.questions[0].options[0].id).toBe("q1-o1");
      expect(result.questions[0].options[1].id).toBe("q1-o2");
    });

    it("maps interrupt_id to clarification id", () => {
      const payload: ElicitationRequestedPayload = {
        interrupt_id: "int-xyz",
        intro: "test intro",
        questions: [
          { id: "q1", question: "test", options: [{ label: "A", value: "a" }] },
        ],
      };
      const result = normalizeClarification(payload);
      expect(result.id).toBe("int-xyz");
      expect(result.intro).toBe("test intro");
      expect(result.status).toBe("pending");
    });
  });

  describe("idempotency", () => {
    it("replayed events produce the same state (no duplication)", () => {
      const state1 = feedAll(events);
      // Feed the same events again on top of the final state
      const state2 = events.reduce(
        (state, event) => reduce(state, event),
        state1,
      );
      // Messages should not duplicate
      expect(state2.messages).toHaveLength(state1.messages.length);
      // Artifacts should not duplicate
      expect(state2.artifacts).toHaveLength(state1.artifacts.length);
      // Citations should not duplicate
      expect(state2.citations).toHaveLength(state1.citations.length);
      // lastSeq should stay the same (events have same seq)
      expect(state2.lastSeq).toBe(state1.lastSeq);
    });
  });

  describe("all 13 event types handled", () => {
    const eventTypes = new Set(events.map((e) => e.event_type));
    const expectedTypes = [
      "session.started",
      "message.delta",
      "message.completed",
      "thought.delta",
      "tool_call.started",
      "tool_call.completed",
      "phase.changed",
      "elicitation.requested",
      "artifact.created",
      "citation.recorded",
      "run.state_changed",
    ];

    it("fixture covers all expected event types", () => {
      for (const type of expectedTypes) {
        expect(eventTypes.has(type)).toBe(true);
      }
    });

    it("reducer processes all events without throwing", () => {
      expect(() => feedAll(events)).not.toThrow();
    });
  });

  describe("error event", () => {
    it("sets error state", () => {
      const errorEvent: RunEventEnvelope = {
        event_id: "evt-err",
        run_id: "run-err",
        event_type: "error",
        occurred_at: "2026-08-08T10:00:00Z",
        seq: 99,
        payload: {
          error: {
            category: "runtime",
            code: "INTERNAL",
            message: "Something went wrong",
            retryable: false,
          },
        },
      };
      const state = reduce(initialState(), errorEvent);
      expect(state.runStatus).toBe("error");
      expect(state.error).not.toBeNull();
      expect(state.error?.message).toBe("Something went wrong");
    });
  });

  describe("permission.requested", () => {
    it("sets permissionRequest", () => {
      const permEvent: RunEventEnvelope = {
        event_id: "evt-perm",
        run_id: "run-perm",
        event_type: "permission.requested",
        occurred_at: "2026-08-08T10:00:00Z",
        seq: 50,
        payload: {
          permission_id: "perm-1",
          tool_call_id: "tc-1",
          description: "Run shell command",
          kind: "terminal",
        },
      };
      const state = reduce(initialState(), permEvent);
      expect(state.permissionRequest).not.toBeNull();
      expect(state.permissionRequest?.permission_id).toBe("perm-1");
    });
  });

  describe("tool_call.delta", () => {
    it("updates tool step", () => {
      const startEvent: RunEventEnvelope = {
        event_id: "evt-tc-start",
        run_id: "run-tc",
        event_type: "tool_call.started",
        occurred_at: "2026-08-08T10:00:00Z",
        seq: 1,
        payload: {
          tool_call_id: "tc-delta",
          tool_name: "legal_search",
        },
      };
      const deltaEvent: RunEventEnvelope = {
        event_id: "evt-tc-delta",
        run_id: "run-tc",
        event_type: "tool_call.delta",
        occurred_at: "2026-08-08T10:00:01Z",
        seq: 2,
        payload: {
          tool_call_id: "tc-delta",
          content: "searching...",
          status: "running",
        },
      };
      let state = reduce(initialState(), startEvent);
      state = reduce(state, deltaEvent);
      const step = state.workflow.steps.find((s) => s.id === "tool-tc-delta");
      expect(step).toBeDefined();
      expect(step?.state).toBe("run");
    });
  });

  describe("plan.updated", () => {
    it("updates workflow steps from plan", () => {
      const planEvent: RunEventEnvelope = {
        event_id: "evt-plan",
        run_id: "run-plan",
        event_type: "plan.updated",
        occurred_at: "2026-08-08T10:00:00Z",
        seq: 1,
        payload: {
          plan: [
            { title: "分析需求", status: "done" },
            { title: "检索法规", status: "run" },
            { title: "起草文书", status: "pending" },
          ],
        },
      };
      const state = reduce(initialState(), planEvent);
      expect(state.workflow.steps).toHaveLength(3);
      expect(state.workflow.steps[0].label).toBe("分析需求");
      expect(state.workflow.steps[0].state).toBe("done");
    });
  });
});
