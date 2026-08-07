/**
 * ChatPanel rendering test — proves the ChatPanel renders messages
 * from the event reducer state (fixture-driven).
 */

import { describe, it, expect, vi } from "vitest";
import { render } from "solid-js/web";
import { AdapterContext } from "../src/adapters";
import type { AdapterContextValue } from "../src/adapters";
import { ChatPanel } from "../src/components/ChatPanel";
import { reduce, initialState } from "../src/event-reducer";
import type { RenderState } from "../src/event-reducer";
import type { RunEventEnvelope } from "@inkstatute/platform-sdk-ts/events";
import fixtureEvents from "./fixtures/events.json";

const events = fixtureEvents as RunEventEnvelope[];

function feedAll(events: RunEventEnvelope[]): RenderState {
  return events.reduce((state, event) => reduce(state, event), initialState());
}

/** Mock adapter context for testing. */
const mockAdapters: AdapterContextValue = {
  file: {
    open: async () => null,
    save: async () => null,
  },
  drop: {
    classifyDroppedPaths: async () => [],
  },
  appInfo: {
    getVersion: async () => "0.0.0-test",
  },
  workspace: {
    listFiles: async () => [],
  },
  documentParser: {
    parseLegalDocument: async () => ({}),
  },
};

function renderChatPanel(state: RenderState, onSend?: (text: string) => void) {
  const sendFn = onSend ?? vi.fn();
  const dispose = render(() => (
    <AdapterContext.Provider value={mockAdapters}>
      <ChatPanel state={state} onSend={sendFn} />
    </AdapterContext.Provider>
  ));
  return { dispose, sendFn };
}

describe("ChatPanel rendering", () => {
  it("renders messages from RenderState", () => {
    const state = feedAll(events);
    const container = document.createElement("div");
    document.body.appendChild(container);
    const dispose = render(
      () => (
        <AdapterContext.Provider value={mockAdapters}>
          <ChatPanel state={state} onSend={vi.fn()} />
        </AdapterContext.Provider>
      ),
      container,
    );
    try {
      // The finalized message should be rendered
      expect(container.innerHTML).toContain("合同审查报告");
      // The assistant avatar should be present
      expect(container.innerHTML).toContain("墨");
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });

  it("shows stage pill with run status", () => {
    const state = feedAll(events);
    const container = document.createElement("div");
    document.body.appendChild(container);
    const dispose = render(
      () => (
        <AdapterContext.Provider value={mockAdapters}>
          <ChatPanel state={state} onSend={vi.fn()} />
        </AdapterContext.Provider>
      ),
      container,
    );
    try {
      // After run.state_changed succeeded, status is "completed" → "已就绪"
      expect(container.innerHTML).toContain("已就绪");
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });

  it("renders composer textarea", () => {
    const state = feedAll(events);
    const container = document.createElement("div");
    document.body.appendChild(container);
    const dispose = render(
      () => (
        <AdapterContext.Provider value={mockAdapters}>
          <ChatPanel state={state} onSend={vi.fn()} />
        </AdapterContext.Provider>
      ),
      container,
    );
    try {
      const textarea = container.querySelector("textarea.chat-input");
      expect(textarea).not.toBeNull();
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });

  it("renders send button", () => {
    const state = feedAll(events);
    const container = document.createElement("div");
    document.body.appendChild(container);
    const dispose = render(
      () => (
        <AdapterContext.Provider value={mockAdapters}>
          <ChatPanel state={state} onSend={vi.fn()} />
        </AdapterContext.Provider>
      ),
      container,
    );
    try {
      const sendBtn = container.querySelector("button.send-btn");
      expect(sendBtn).not.toBeNull();
      expect(sendBtn?.textContent).toContain("发送");
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });

  it("Ctrl+Enter triggers onSend callback", () => {
    const state = feedAll(events);
    const onSend = vi.fn();
    const container = document.createElement("div");
    document.body.appendChild(container);
    const dispose = render(
      () => (
        <AdapterContext.Provider value={mockAdapters}>
          <ChatPanel state={state} onSend={onSend} />
        </AdapterContext.Provider>
      ),
      container,
    );
    try {
      const textarea = container.querySelector("textarea.chat-input") as HTMLTextAreaElement;
      expect(textarea).not.toBeNull();
      // Type some text
      textarea.value = "测试消息";
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
      // Simulate Ctrl+Enter
      const keydownEvent = new KeyboardEvent("keydown", {
        key: "Enter",
        ctrlKey: true,
        bubbles: true,
      });
      textarea.dispatchEvent(keydownEvent);
      expect(onSend).toHaveBeenCalledWith("测试消息");
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });

  it("renders clarification intro text when state.clarification is non-null", () => {
    // Feed events up to elicitation.requested (seq 7)
    const state = events.slice(0, 7).reduce(
      (state, event) => reduce(state, event),
      initialState(),
    );
    expect(state.clarification).not.toBeNull();

    const container = document.createElement("div");
    document.body.appendChild(container);
    const dispose = render(
      () => (
        <AdapterContext.Provider value={mockAdapters}>
          <ChatPanel state={state} onSend={vi.fn()} />
        </AdapterContext.Provider>
      ),
      container,
    );
    try {
      expect(container.innerHTML).toContain("需要补充信息");
      // Should also render the questions
      expect(container.innerHTML).toContain("合同类型是什么？");
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });

  it("shows fallback message when no messages", () => {
    const state = initialState();
    const container = document.createElement("div");
    document.body.appendChild(container);
    const dispose = render(
      () => (
        <AdapterContext.Provider value={mockAdapters}>
          <ChatPanel state={state} onSend={vi.fn()} />
        </AdapterContext.Provider>
      ),
      container,
    );
    try {
      expect(container.innerHTML).toContain("描述法律问题");
    } finally {
      dispose();
      document.body.removeChild(container);
    }
  });
});
