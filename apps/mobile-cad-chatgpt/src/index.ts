import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { registerAppResource, registerAppTool, RESOURCE_MIME_TYPE } from "@modelcontextprotocol/ext-apps/server";
import { createMcpHandler } from "agents/mcp";
import { z } from "zod";
import { ENGINE_VERSION, generateDrawingSet, normalizeSpec, validateSpec } from "./cad-model";

interface Env {
  ASSETS: Fetcher;
}

const WIDGET_URI = "ui://hscad-mobile/editor-v2.html";

const pointSchema = z.object({ x: z.number(), y: z.number() });
const segmentSchema = z.object({
  start: pointSchema,
  end: pointSchema,
  thickness: z.number().optional(),
  layer: z.string().optional(),
});
const openingSchema = z.object({
  kind: z.enum(["door", "window"]),
  wallIndex: z.number().int().min(0),
  offset: z.number().min(0),
  width: z.number().positive(),
  height: z.number().positive(),
  sill: z.number().min(0).optional(),
  swing: z.enum(["left", "right", "double"]).optional(),
  label: z.string().max(24).optional(),
});
const stairSchema = z.object({
  x: z.number(),
  y: z.number(),
  width: z.number().positive(),
  length: z.number().positive(),
  risers: z.number().int().min(3).max(40),
  direction: z.enum(["up-north", "up-south", "up-east", "up-west"]),
});

const specShape = {
  projectName: z.string().min(1).max(120).default("HS-CAD PROJECT"),
  width: z.number().min(3000).max(50000).default(12000),
  depth: z.number().min(3000).max(50000).default(11300),
  wallThickness: z.number().min(80).max(600).default(200),
  eaveHeight: z.number().min(2400).max(15000).default(3200),
  ridgeHeight: z.number().min(2600).max(20000).default(5000),
  atticFloorHeight: z.number().min(1800).max(12000).default(2600),
  ceilingHeight: z.number().min(2100).max(10000).default(2500),
  roofDirection: z.enum(["ridge-along-width", "ridge-along-depth"]).default("ridge-along-depth"),
  roofOverhang: z.number().min(0).max(2000).default(450),
  roofThickness: z.number().min(80).max(800).default(220),
  floorSlabThickness: z.number().min(80).max(800).default(180),
  foundationDepth: z.number().min(250).max(4000).default(700),
  roofFinish: z.string().max(120).default("Standing seam metal"),
  wallFinish: z.string().max(120).default("Exterior render / panel"),
  plinthFinish: z.string().max(120).default("Exposed concrete / stone"),
  outline: z.array(pointSchema).min(3).max(64).optional(),
  interiorWalls: z.array(segmentSchema).max(128).optional(),
  openings: z.array(openingSchema).max(128).optional(),
  stair: stairSchema.optional(),
};

const entitySchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("line"), layer: z.string(), start: pointSchema, end: pointSchema }),
  z.object({ type: z.literal("polyline"), layer: z.string(), points: z.array(pointSchema), closed: z.boolean() }),
  z.object({ type: z.literal("arc"), layer: z.string(), center: pointSchema, radius: z.number(), startAngle: z.number(), endAngle: z.number() }),
  z.object({ type: z.literal("circle"), layer: z.string(), center: pointSchema, radius: z.number() }),
  z.object({ type: z.literal("text"), layer: z.string(), at: pointSchema, text: z.string(), height: z.number(), rotation: z.number().optional() }),
]);
const buildingSpecSchema = z.object({ unit: z.literal("mm"), ...specShape });
const drawingViewSchema = z.object({
  id: z.enum(["plan", "front", "rear", "left", "right", "section-a", "section-b"]),
  title: z.string(),
  width: z.number(),
  height: z.number(),
  entities: z.array(entitySchema),
});
const metricsSchema = z.object({
  footprintAreaM2: z.number(),
  perimeterM: z.number(),
  roofPitchDegrees: z.number(),
  atticPeakHeight: z.number(),
  atticUsableWidthAt1800: z.number(),
  exteriorWallCount: z.number(),
  openingCount: z.number(),
});
const scheduleSchema = z.object({
  mark: z.string(),
  kind: z.enum(["door", "window"]),
  count: z.number(),
  width: z.number(),
  height: z.number(),
  sill: z.number(),
});
const drawingSetSchema = z.object({
  spec: buildingSpecSchema,
  views: z.array(drawingViewSchema),
  warnings: z.array(z.string()),
  metrics: metricsSchema,
  openingSchedule: z.array(scheduleSchema),
  generatedAt: z.string(),
  engineVersion: z.string(),
});

const getWidgetHtml = async (assets: Fetcher, requestUrl: string): Promise<string> => {
  const assetUrl = new URL("/", requestUrl);
  const response = await assets.fetch(new Request(assetUrl, { method: "GET" }));
  if (!response.ok) throw new Error(`Widget asset unavailable: ${response.status}`);
  return response.text();
};

function createServer(origin: string, assets: Fetcher, requestUrl: string): McpServer {
  const server = new McpServer(
    { name: "HS-CAD Mobile", version: ENGINE_VERSION },
    {
      instructions:
        "Use render_architectural_set when the user wants an interactive mobile drawing. Use generate_architectural_set for data-only recalculation from the widget. Preserve user dimensions unless they explicitly request changes. Always surface validation warnings and state that generated drawings require professional review before construction.",
    },
  );

  registerAppResource(server, "hscad-mobile-editor-v2", WIDGET_URI, {}, async () => ({
    contents: [{
      uri: WIDGET_URI,
      mimeType: RESOURCE_MIME_TYPE,
      text: await getWidgetHtml(assets, requestUrl),
      _meta: {
        ui: {
          prefersBorder: true,
          domain: origin,
          csp: { connectDomains: [], resourceDomains: [] },
        },
        "openai/widgetDescription": "모바일에서 건축 평면도, 박공지붕 입면도 4면, 단면도 2면을 편집·검토하고 DXF/SVG로 내려받는 HS-CAD 편집기입니다.",
        "openai/widgetPrefersBorder": true,
      },
    }],
  }));

  registerAppTool(server, "open_mobile_cad", {
    title: "Open HS-CAD mobile editor",
    description: "Use this when the user wants to open a mobile-only architectural CAD workspace with a default gable-roof drawing set.",
    inputSchema: {},
    outputSchema: { drawing: drawingSetSchema },
    annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false, idempotentHint: true },
    _meta: {
      ui: { resourceUri: WIDGET_URI },
      "openai/outputTemplate": WIDGET_URI,
      "openai/toolInvocation/invoking": "모바일 CAD 편집기를 여는 중",
      "openai/toolInvocation/invoked": "모바일 CAD 편집기를 열었습니다",
    },
  }, async () => {
    const drawing = generateDrawingSet({});
    return {
      structuredContent: { drawing },
      content: [{ type: "text", text: "HS-CAD 모바일 편집기를 열었습니다. 기본 박공지붕 도면 7면이 준비되었습니다." }],
    };
  });

  registerAppTool(server, "render_architectural_set", {
    title: "Render architectural drawing set",
    description: "Use this when the user asks to create and display an interactive floor plan, four elevations, gable roof, attic, and two building sections from supplied dimensions.",
    inputSchema: specShape,
    outputSchema: { drawing: drawingSetSchema },
    annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false, idempotentHint: true },
    _meta: {
      ui: { resourceUri: WIDGET_URI },
      "openai/outputTemplate": WIDGET_URI,
      "openai/toolInvocation/invoking": "상세 건축 도면을 작성하는 중",
      "openai/toolInvocation/invoked": "상세 건축 도면을 작성했습니다",
    },
  }, async (args) => {
    const drawing = generateDrawingSet(args);
    return {
      structuredContent: { drawing },
      content: [{
        type: "text",
        text: `${drawing.spec.projectName}: 평면도 1면, 입면도 4면, 단면도 2면을 작성했습니다. 검토 항목은 ${drawing.warnings.length}개입니다.`,
      }],
    };
  });

  registerAppTool(server, "generate_architectural_set", {
    title: "Recalculate architectural drawing data",
    description: "Use this for idempotent data-only recalculation from the mounted HS-CAD widget. It returns the complete drawing set without remounting a new widget.",
    inputSchema: specShape,
    outputSchema: { drawing: drawingSetSchema },
    annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false, idempotentHint: true },
    _meta: {
      ui: { visibility: ["app"] },
      "openai/toolInvocation/invoking": "도면 데이터를 계산하는 중",
      "openai/toolInvocation/invoked": "도면 데이터를 갱신했습니다",
    },
  }, async (args) => {
    const drawing = generateDrawingSet(args);
    return {
      structuredContent: { drawing },
      content: [{ type: "text", text: `도면 7면과 창호 일람표를 다시 계산했습니다. 경고 ${drawing.warnings.length}개.` }],
    };
  });

  registerAppTool(server, "validate_architectural_set", {
    title: "Validate architectural drawing parameters",
    description: "Use this before drawing generation to check roof, attic, ceiling, wall, outline, opening, roof pitch, and geometry relationships.",
    inputSchema: specShape,
    outputSchema: {
      spec: buildingSpecSchema,
      warnings: z.array(z.string()),
      valid: z.boolean(),
      metrics: metricsSchema,
    },
    annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false, idempotentHint: true },
    _meta: { ui: { visibility: ["model"] } },
  }, async (args) => {
    const spec = normalizeSpec(args);
    const drawing = generateDrawingSet(spec);
    const warnings = validateSpec(spec);
    return {
      structuredContent: { spec: drawing.spec, warnings, valid: warnings.length === 0, metrics: drawing.metrics },
      content: [{ type: "text", text: warnings.length ? `설계 검토 항목 ${warnings.length}개: ${warnings.join(" ")}` : "도면 생성 파라미터가 유효합니다." }],
    };
  });

  return server;
}

const securityHeaders = (response: Response): Response => {
  const headers = new Headers(response.headers);
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("Referrer-Policy", "no-referrer");
  headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
};

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/health") {
      return Response.json({ ok: true, service: "hscad-mobile-cad", version: ENGINE_VERSION, widget: WIDGET_URI, timestamp: new Date().toISOString() });
    }
    if (url.pathname === "/mcp" || url.pathname.startsWith("/mcp/")) {
      const server = createServer(url.origin, env.ASSETS, request.url);
      return createMcpHandler(server)(request, env, ctx);
    }
    return securityHeaders(await env.ASSETS.fetch(request));
  },
} satisfies ExportedHandler<Env>;
