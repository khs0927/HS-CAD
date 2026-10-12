// @vitest-environment happy-dom

import { afterEach, describe, expect, it, vi } from "vitest";
import { MCP_APPS_PROTOCOL_VERSION, McpAppsBridge, type OpenAiWindow } from "../src/mcp-bridge";

const setOpenAi = (value: OpenAiWindow["openai"]): void => {
  Object.defineProperty(window, "openai", { configurable: true, writable: true, value });
};

afterEach(() => {
  setOpenAi(undefined);
});

describe("manual MCP Apps JSON-RPC bridge", () => {
  it("uses a canonical initialize/initialized handshake and receives tool results", async () => {
    const postMessage = vi.fn();
    const host = { postMessage } as unknown as Window;
    const bridge = new McpAppsBridge({ eventWindow: window, targetWindow: host, initializeTimeoutMs: 500 });
    const snapshots: number[] = [];
    const unsubscribe = bridge.subscribe((snapshot) => snapshots.push(snapshot.toolRevision));
    const connecting = bridge.connect();

    await vi.waitFor(() => expect(postMessage).toHaveBeenCalled());
    const initialize = postMessage.mock.calls[0][0];
    expect(initialize).toMatchObject({
      jsonrpc: "2.0",
      method: "ui/initialize",
      params: { protocolVersion: MCP_APPS_PROTOCOL_VERSION },
    });
    window.dispatchEvent(new MessageEvent("message", {
      source: host,
      data: {
        jsonrpc: "2.0",
        id: initialize.id,
        result: {
          protocolVersion: MCP_APPS_PROTOCOL_VERSION,
          hostInfo: { name: "test-host", version: "1" },
          hostCapabilities: { message: {} },
          hostContext: { theme: "dark", displayMode: "inline" },
        },
      },
    }));
    await expect(connecting).resolves.toBe(true);
    expect(postMessage.mock.calls.some(([message]) => message.method === "ui/notifications/initialized")).toBe(true);

    window.dispatchEvent(new MessageEvent("message", {
      source: host,
      data: { jsonrpc: "2.0", method: "ui/notifications/tool-result", params: { structuredContent: { valid: true } } },
    }));
    expect(bridge.getSnapshot().toolResult?.structuredContent).toEqual({ valid: true });
    expect(snapshots.at(-1)).toBe(1);
    unsubscribe();
    bridge.close();
  });

  it("feature-detects follow-up messaging in standalone mode", async () => {
    const bridge = new McpAppsBridge({ eventWindow: window, targetWindow: window });
    await bridge.connect();
    await expect(bridge.sendUserMessage("Review this drawing")).resolves.toBe(false);

    const sendFollowUpMessage = vi.fn(async () => undefined);
    setOpenAi({ sendFollowUpMessage });
    await expect(bridge.sendUserMessage("Review this drawing")).resolves.toBe(true);
    expect(sendFollowUpMessage).toHaveBeenCalledWith({ prompt: "Review this drawing", scrollToBottom: true });
  });

  it("uses window.openai.callTool only as an additive fallback", async () => {
    const callTool = vi.fn(async () => ({ structuredContent: { valid: true } }));
    setOpenAi({ callTool });
    const bridge = new McpAppsBridge({ eventWindow: window, targetWindow: window });
    await bridge.connect();
    await expect(bridge.callTool("generate_architectural_set", { width: 12_000 })).resolves.toEqual({ structuredContent: { valid: true } });
    expect(callTool).toHaveBeenCalledWith("generate_architectural_set", { width: 12_000 });
  });
});

