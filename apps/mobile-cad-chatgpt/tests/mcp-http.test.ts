import { describe, expect, it, vi } from "vitest";

// The production adapter imports Cloudflare's `cloudflare:workers` runtime module,
// which Node's test loader cannot resolve. Exercise the same official Web Standard
// MCP transport here while keeping the production Worker on `createMcpHandler`.
vi.mock("agents/mcp", async () => {
  const { WebStandardStreamableHTTPServerTransport } = await import(
    "@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js"
  );
  return {
    createMcpHandler: (
      server: { connect: (transport: unknown) => Promise<void> },
      options: { route?: string } = {},
    ) => async (request: Request): Promise<Response> => {
      if (options.route && new URL(request.url).pathname !== options.route) {
        return new Response("Not Found", { status: 404 });
      }
      const transport = new WebStandardStreamableHTTPServerTransport();
      await server.connect(transport);
      return transport.handleRequest(request);
    },
  };
});

import { WIDGET_URI } from "../src/app-constants";
import worker from "../src/index";

const MCP_URL = "https://cad.example.test/mcp";
const MCP_HEADERS = {
  accept: "application/json, text/event-stream",
  "content-type": "application/json",
  "mcp-protocol-version": "2025-11-25",
};

const assets = {
  async fetch(input: RequestInfo | URL): Promise<Response> {
    const request = input instanceof Request ? input : new Request(input);
    const url = new URL(request.url);
    if (url.pathname === "/") {
      return new Response("<!doctype html><html><body><main id=\"root\">HS-CAD</main></body></html>", {
        headers: { "content-type": "text/html; charset=utf-8" },
      });
    }
    return new Response("Not found", { status: 404 });
  },
} as Fetcher;

const env = { ASSETS: assets };
const ctx = {
  props: {},
  waitUntil: () => undefined,
  passThroughOnException: () => undefined,
} as unknown as ExecutionContext;

const fetchWorker = (request: Request): Promise<Response> => worker.fetch(request, env, ctx);

interface JsonRpcResponse<T = unknown> {
  jsonrpc: "2.0";
  id: string | number | null;
  result?: T;
  error?: { code: number; message: string; data?: unknown };
}

const parseProtocolResponse = async <T>(response: Response): Promise<JsonRpcResponse<T>> => {
  const body = await response.text();
  if (response.headers.get("content-type")?.includes("text/event-stream")) {
    const messages = body
      .split(/\r?\n/)
      .filter((line) => line.startsWith("data:"))
      .map((line) => JSON.parse(line.slice(5).trim()) as JsonRpcResponse<T>);
    if (messages.length === 0) throw new Error(`No JSON-RPC data event in SSE response: ${body.slice(0, 200)}`);
    return messages.at(-1)!;
  }
  return JSON.parse(body) as JsonRpcResponse<T>;
};

let nextId = 1;
const rpc = async <T>(method: string, params?: Record<string, unknown>): Promise<{
  response: Response;
  message: JsonRpcResponse<T>;
}> => {
  const id = nextId++;
  const response = await fetchWorker(new Request(MCP_URL, {
    method: "POST",
    headers: MCP_HEADERS,
    body: JSON.stringify({ jsonrpc: "2.0", id, method, ...(params ? { params } : {}) }),
  }));
  const message = await parseProtocolResponse<T>(response);
  expect(message.id).toBe(id);
  return { response, message };
};

interface ToolResult {
  content: Array<{ type: string; text?: string }>;
  structuredContent?: Record<string, unknown>;
  isError?: boolean;
  _meta?: Record<string, unknown>;
}

const callTool = async (name: string, args: Record<string, unknown>): Promise<ToolResult> => {
  const { response, message } = await rpc<ToolResult>("tools/call", {
    name,
    arguments: args,
  });
  expect(response.status).toBe(200);
  expect(message.error).toBeUndefined();
  expect(message.result).toBeDefined();
  return message.result!;
};

const expectSecureHeaders = (response: Response): void => {
  expect(response.headers.get("x-content-type-options")).toBe("nosniff");
  expect(response.headers.get("referrer-policy")).toBe("no-referrer");
  expect(response.headers.get("permissions-policy")).toContain("camera=()");
  expect(response.headers.get("x-request-id")).toMatch(/^[0-9a-f-]{36}$/);
};

describe("HS-CAD Worker HTTP boundary", () => {
  it("serves health with versioned widget metadata and security headers", async () => {
    const response = await fetchWorker(new Request("https://cad.example.test/health"));
    expect(response.status).toBe(200);
    expectSecureHeaders(response);
    expect(response.headers.get("cache-control")).toBe("no-store");
    await expect(response.json()).resolves.toMatchObject({
      ok: true,
      service: "hscad-mobile-cad",
      schemaVersion: "1.0",
      widget: WIDGET_URI,
    });
    expect(WIDGET_URI).toBe("ui://hscad-mobile/editor-v3.html");
  });

  it("rejects unsupported, malformed, wrong-media-type, and oversized MCP requests safely", async () => {
    const unsupported = await fetchWorker(new Request(MCP_URL, { method: "PUT" }));
    expect(unsupported.status).toBe(405);
    expect(unsupported.headers.get("allow")).toContain("POST");
    expectSecureHeaders(unsupported);
    await expect(unsupported.json()).resolves.toMatchObject({
      ok: false,
      error: { code: "METHOD_NOT_ALLOWED" },
    });

    const malformed = await fetchWorker(new Request(MCP_URL, {
      method: "POST",
      headers: MCP_HEADERS,
      body: "{not-json",
    }));
    expect(malformed.status).toBe(400);
    await expect(malformed.json()).resolves.toMatchObject({
      jsonrpc: "2.0",
      error: { code: -32700, message: "Parse error: invalid JSON." },
      id: null,
    });

    const wrongMedia = await fetchWorker(new Request(MCP_URL, {
      method: "POST",
      headers: { accept: MCP_HEADERS.accept, "content-type": "text/plain" },
      body: "{}",
    }));
    expect(wrongMedia.status).toBe(415);
    await expect(wrongMedia.json()).resolves.toMatchObject({
      error: { code: -32000 },
    });

    const oversized = await fetchWorker(new Request(MCP_URL, {
      method: "POST",
      headers: { ...MCP_HEADERS, "content-length": String(256 * 1024 + 1) },
      body: "{}",
    }));
    expect(oversized.status).toBe(413);
    const oversizedBody = await oversized.json() as { error: { message: string; data: { requestId: string } } };
    expect(oversizedBody.error.message).toContain("byte limit");
    expect(oversizedBody.error.data.requestId).toBe(oversized.headers.get("x-request-id"));
  });
});

describe("HS-CAD MCP Streamable HTTP contract", () => {
  it("initializes through Streamable HTTP", async () => {
    const { response, message } = await rpc<{
      protocolVersion: string;
      serverInfo: { name: string; version: string };
      capabilities: Record<string, unknown>;
    }>("initialize", {
      protocolVersion: "2025-11-25",
      capabilities: {},
      clientInfo: { name: "hscad-test", version: "1.0.0" },
    });
    expect(response.status).toBe(200);
    expectSecureHeaders(response);
    expect(response.headers.get("access-control-allow-origin")).toBe("https://cad.example.test");
    expect(message.error).toBeUndefined();
    expect(message.result).toMatchObject({
      protocolVersion: "2025-11-25",
      serverInfo: { name: "HS-CAD Mobile" },
    });
  });

  it("lists four tools with exact strict schemas and correct widget visibility", async () => {
    const { message } = await rpc<{
      tools: Array<{
        name: string;
        inputSchema: Record<string, unknown>;
        outputSchema: { properties: Record<string, unknown>; additionalProperties?: boolean };
        annotations: Record<string, boolean>;
        _meta: Record<string, unknown> & { ui?: { resourceUri?: string; visibility?: string[] } };
      }>;
    }>("tools/list");
    const tools = message.result!.tools;
    expect(tools.map((tool) => tool.name)).toEqual([
      "open_mobile_cad",
      "render_architectural_set",
      "generate_architectural_set",
      "validate_architectural_set",
    ]);
    for (const tool of tools) {
      expect(tool.inputSchema).toMatchObject({ type: "object", additionalProperties: false });
      expect(tool.outputSchema).toMatchObject({ type: "object", additionalProperties: false });
      expect(Object.keys(tool.outputSchema.properties).sort()).toEqual([
        "artifacts", "engineVersion", "generatedAt", "issues", "metrics", "schedules", "spec", "valid", "views", "warnings",
      ]);
      expect(tool.annotations).toMatchObject({
        readOnlyHint: true,
        destructiveHint: false,
        openWorldHint: false,
        idempotentHint: true,
      });
    }

    const open = tools.find((tool) => tool.name === "open_mobile_cad")!;
    const render = tools.find((tool) => tool.name === "render_architectural_set")!;
    const generate = tools.find((tool) => tool.name === "generate_architectural_set")!;
    expect(open._meta.ui?.resourceUri).toBe(WIDGET_URI);
    expect(render._meta.ui?.resourceUri).toBe(WIDGET_URI);
    expect(generate._meta.ui?.resourceUri).toBeUndefined();
    expect(generate._meta.ui?.visibility).toEqual(["model", "app"]);
    expect(generate._meta["openai/outputTemplate"]).toBeUndefined();
  });

  it("lists and reads the editor-v3 app resource with CSP and compatibility aliases", async () => {
    const listed = await rpc<{
      resources: Array<{
        uri: string;
        mimeType: string;
        _meta: Record<string, unknown> & { ui?: Record<string, unknown> };
      }>;
    }>("resources/list");
    expect(listed.message.result!.resources).toHaveLength(1);
    const resource = listed.message.result!.resources[0];
    expect(resource.uri).toBe(WIDGET_URI);
    expect(resource.mimeType).toBe("text/html;profile=mcp-app");
    expect(resource._meta.ui).toMatchObject({
      prefersBorder: true,
      domain: "https://cad.example.test",
      csp: { connectDomains: [], resourceDomains: ["https://cad.example.test"] },
    });
    expect(resource._meta["openai/widgetDescription"]).toEqual(expect.any(String));
    expect(resource._meta["openai/widgetPrefersBorder"]).toBe(true);
    expect(resource._meta["openai/widgetDomain"]).toBe("https://cad.example.test");
    expect(resource._meta["openai/widgetCSP"]).toEqual({
      connect_domains: [],
      resource_domains: ["https://cad.example.test"],
    });

    const read = await rpc<{
      contents: Array<{
        uri: string;
        mimeType: string;
        text: string;
        _meta: Record<string, unknown> & { ui?: Record<string, unknown> };
      }>;
    }>("resources/read", { uri: WIDGET_URI });
    expect(read.message.result!.contents[0]).toMatchObject({
      uri: WIDGET_URI,
      mimeType: "text/html;profile=mcp-app",
    });
    expect(read.message.result!.contents[0].text).toContain("HS-CAD");
    expect(read.message.result!.contents[0]._meta).toMatchObject(resource._meta);
  });

  it("calls all four tools and keeps full CAD/artifact payloads out of structuredContent", async () => {
    const generated = await callTool("generate_architectural_set", {
      projectName: "HTTP Contract Test",
      width: 12_000,
      depth: 11_300,
    });
    expect(generated.isError).not.toBe(true);
    expect(generated.structuredContent).toBeDefined();
    expect(generated.structuredContent).not.toHaveProperty("drawing");
    expect(generated.structuredContent).not.toHaveProperty("entities");
    expect(generated.structuredContent).toMatchObject({
      spec: { projectName: "HTTP Contract Test", unit: "mm" },
      views: expect.arrayContaining([expect.objectContaining({ id: "plan", entityCount: expect.any(Number) })]),
      artifacts: expect.arrayContaining([expect.objectContaining({ id: "dxf", sha256: expect.stringMatching(/^[a-f0-9]{64}$/) })]),
    });

    const metadata = generated.structuredContent!.artifacts as Array<Record<string, unknown>>;
    expect(metadata.every((artifact) => !("text" in artifact))).toBe(true);
    expect(JSON.stringify(generated.structuredContent)).not.toContain("<svg");
    expect(JSON.stringify(generated.structuredContent)).not.toContain("AC1009");
    expect(generated._meta).toHaveProperty("drawing.views.0.entities");
    expect(generated._meta).toHaveProperty("artifacts.dxf.text");
    expect(generated._meta).toHaveProperty("artifacts.sheetSvg.text");
    expect(generated._meta).toHaveProperty("artifacts.viewSvgs.0.text");
    expect(generated._meta).toHaveProperty("artifacts.projectJson.text");
    const projectJson = JSON.parse(
      ((generated._meta!.artifacts as { projectJson: { text: string } }).projectJson.text),
    ) as Record<string, unknown>;
    expect(projectJson).toMatchObject({ projectName: "HTTP Contract Test", unit: "mm" });
    expect(projectJson).not.toHaveProperty("views");

    const rendered = await callTool("render_architectural_set", {
      prepared: generated.structuredContent,
    });
    expect(rendered.isError).not.toBe(true);
    expect(rendered.structuredContent).toMatchObject({ spec: { projectName: "HTTP Contract Test" } });
    expect(rendered._meta).toHaveProperty("drawing.views.0.entities");

    const opened = await callTool("open_mobile_cad", {});
    expect(opened.isError).not.toBe(true);
    expect(opened.structuredContent).toHaveProperty("views");
    expect(opened._meta).toHaveProperty("artifacts.dxf.text");

    const validated = await callTool("validate_architectural_set", {
      eaveHeight: 5_000,
      ridgeHeight: 4_000,
    });
    expect(validated.isError).not.toBe(true);
    expect(validated.structuredContent).toMatchObject({ valid: false });
    expect((validated.structuredContent!.issues as unknown[]).length).toBeGreaterThan(0);
    expect(validated._meta).toHaveProperty("drawing");
  }, 30_000);

  it("returns a friendly tool error for strict-schema violations", async () => {
    const result = await callTool("generate_architectural_set", {
      width: 12_000,
      unexpectedPrivateField: "must-not-pass",
    });
    expect(result.isError).toBe(true);
    expect(result.structuredContent).toBeUndefined();
    expect(result.content[0].text).toContain("Input validation error");
  });

  it("rejects semantic generation errors before producing fallback artifacts", async () => {
    const result = await callTool("generate_architectural_set", {
      eaveHeight: 5_000,
      ridgeHeight: 4_000,
    });
    expect(result.isError).toBe(true);
    expect(result.content[0].text).toContain("blocking validation issue");
    expect(result.structuredContent).toBeUndefined();
    expect(result._meta).toMatchObject({
      error: {
        code: "VALIDATION_ERROR",
        issues: expect.arrayContaining([expect.objectContaining({ severity: "error" })]),
      },
    });
    expect(result._meta).not.toHaveProperty("drawing");
    expect(result._meta).not.toHaveProperty("artifacts");
  });
});
