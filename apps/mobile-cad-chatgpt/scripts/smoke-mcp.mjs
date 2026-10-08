import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

const endpoint = new URL(process.argv[2] ?? "http://127.0.0.1:8787/mcp");
if (endpoint.protocol !== "http:" && endpoint.protocol !== "https:") {
  throw new Error("MCP URL must use http or https");
}
if (endpoint.pathname !== "/mcp") throw new Error("MCP URL must end in /mcp");

const origin = new URL(endpoint.origin);
const timeoutMs = 30_000;
const expectedTools = [
  "open_mobile_cad",
  "render_architectural_set",
  "generate_architectural_set",
  "validate_architectural_set",
];
const sampleSpec = {
  schemaVersion: "1.0",
  projectName: "HS-CAD REMOTE SMOKE",
  unit: "mm",
  width: 12_000,
  depth: 11_300,
  wallThickness: 200,
  ceilingHeight: 2_500,
  eaveHeight: 3_200,
  ridgeHeight: 5_000,
  atticFloorHeight: 2_600,
  roofDirection: "ridge-along-depth",
};

const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};

const request = async (url, init = {}) => {
  const signal = init.signal
    ? AbortSignal.any([init.signal, AbortSignal.timeout(timeoutMs)])
    : AbortSignal.timeout(timeoutMs);
  return fetch(url, { ...init, signal });
};

const healthUrl = new URL("/health", origin);
const healthResponse = await request(healthUrl);
assert(healthResponse.status === 200, `/health returned ${healthResponse.status}`);
assert(healthResponse.headers.get("x-content-type-options") === "nosniff", "/health lacks nosniff");
assert(healthResponse.headers.get("cache-control") === "no-store", "/health is cacheable");
const health = await healthResponse.json();
assert(health.ok === true && health.widget === "ui://hscad-mobile/editor-v3.html", "unexpected health metadata");

const rootResponse = await request(origin);
assert(rootResponse.status === 200, `/ returned ${rootResponse.status}`);
assert(rootResponse.headers.get("content-type")?.includes("text/html"), "/ is not HTML");
const csp = rootResponse.headers.get("content-security-policy");
assert(csp?.includes("default-src 'self'"), "PWA response lacks the production CSP");
const rootHtml = await rootResponse.text();
assert(!rootHtml.includes("sourceMappingURL="), "production HTML contains a source map reference");
assert(!/[A-Za-z]:\\Users\\|\/(?:Users|home)\/[^\s"']+/.test(rootHtml), "production HTML leaks a local path");

const sourceResponse = await request(new URL("/src/index.ts", origin));
assert(sourceResponse.status === 404, `development source path returned ${sourceResponse.status}`);

const malformed = await request(endpoint, {
  method: "POST",
  headers: { accept: "application/json, text/event-stream", "content-type": "application/json" },
  body: "{bad-json",
});
assert(malformed.status === 400, `malformed JSON returned ${malformed.status}`);

const oversized = await request(endpoint, {
  method: "POST",
  headers: {
    accept: "application/json, text/event-stream",
    "content-type": "application/json",
  },
  body: JSON.stringify({ padding: "x".repeat(256 * 1024) }),
});
assert(oversized.status === 413, `oversized request returned ${oversized.status}`);

const unsupported = await request(endpoint, { method: "PUT" });
assert(unsupported.status === 405, `unsupported method returned ${unsupported.status}`);

const transport = new StreamableHTTPClientTransport(endpoint, { fetch: request });
const client = new Client({ name: "hscad-release-smoke", version: "1.0.0" }, { capabilities: {} });

try {
  await client.connect(transport);
  const negotiatedProtocol = transport.protocolVersion;
  assert(typeof negotiatedProtocol === "string", "MCP initialization did not negotiate a protocol");
  assert(client.getServerVersion()?.name === "HS-CAD Mobile", "unexpected MCP server identity");

  const listed = await client.listTools();
  const toolNames = listed.tools.map((tool) => tool.name);
  assert(JSON.stringify(toolNames) === JSON.stringify(expectedTools), `unexpected tools: ${toolNames.join(", ")}`);

  const resources = await client.listResources();
  assert(resources.resources.length === 1, `expected one widget resource, got ${resources.resources.length}`);
  const resource = resources.resources[0];
  assert(resource.uri === health.widget, "health and resources/list widget URIs differ");
  assert(resource.mimeType === "text/html;profile=mcp-app", `unexpected widget MIME: ${resource.mimeType}`);

  const widget = await client.readResource({ uri: resource.uri });
  assert(widget.contents.length === 1, "resources/read did not return one widget document");
  assert(widget.contents[0].mimeType === "text/html;profile=mcp-app", "widget read MIME is incorrect");
  assert("text" in widget.contents[0] && widget.contents[0].text.includes("HS-CAD"), "widget HTML is missing");

  const calls = [
    ["open_mobile_cad", {}],
    ["render_architectural_set", { spec: sampleSpec }],
    ["generate_architectural_set", sampleSpec],
    ["validate_architectural_set", sampleSpec],
  ];
  const callSummaries = [];
  for (const [name, args] of calls) {
    const result = await client.callTool({ name, arguments: args });
    assert(result.isError !== true, `${name} returned a tool error`);
    assert(result.structuredContent && typeof result.structuredContent === "object", `${name} lacks structuredContent`);
    const visible = JSON.stringify(result.structuredContent);
    assert(Buffer.byteLength(visible) < 128 * 1024, `${name} structuredContent is not concise`);
    assert(!visible.includes("<svg") && !visible.includes("AC1009") && !visible.includes('"entities"'), `${name} leaked a full artifact to the model`);
    assert(result._meta && typeof result._meta === "object", `${name} lacks widget metadata`);
    callSummaries.push({ name, visibleBytes: Buffer.byteLength(visible) });
  }

  const badInput = await client.callTool({
    name: "generate_architectural_set",
    arguments: { width: 12_000, unexpectedPrivateField: "rejected" },
  });
  assert(badInput.isError === true, "strict unknown-field input was not rejected");

  const impossible = await client.callTool({
    name: "generate_architectural_set",
    arguments: { eaveHeight: 5_000, ridgeHeight: 4_000 },
  });
  assert(impossible.isError === true, "semantically impossible generation was not rejected");

  console.log(JSON.stringify({
    ok: true,
    endpoint: endpoint.href,
    protocolVersion: negotiatedProtocol,
    tools: toolNames,
    widget: { uri: resource.uri, mimeType: resource.mimeType, htmlBytes: Buffer.byteLength(widget.contents[0].text) },
    calls: callSummaries,
    http: { health: 200, root: 200, source: 404, malformed: 400, oversized: 413, unsupported: 405 },
  }, null, 2));
} finally {
  await client.close();
}
