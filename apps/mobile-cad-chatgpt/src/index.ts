import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import {
  registerAppResource,
  registerAppTool,
  RESOURCE_MIME_TYPE,
} from "@modelcontextprotocol/ext-apps/server";
import { createMcpHandler } from "agents/mcp";
import { z } from "zod";
import {
  ENGINE_VERSION,
  generateDrawingSet,
  normalizeSpec,
  validateSpecDetailed,
} from "./cad-model";
import { drawingSetToDxf } from "./dxf";
import { drawingSetToSvgSheet, viewToSvg } from "./svg";
import {
  BUILDING_SCHEMA_VERSION,
  type BuildingSpec,
  type DrawingSet,
  type ValidationIssue,
} from "./types";

interface Env {
  ASSETS: Fetcher;
}

export const WIDGET_URI = "ui://hscad-mobile/editor-v3.html";

const MCP_ROUTE = "/mcp";
const MAX_REQUEST_BYTES = 256 * 1024;
const MAX_WIDGET_BYTES = 2 * 1024 * 1024;
const MAX_TOOL_OUTPUT_BYTES = 8 * 1024 * 1024;
const RESPONSE_START_TIMEOUT_MS = 10_000;
const TOOL_TIMEOUT_MS = 10_000;
const PROTOCOL_VERSION = "2025-11-25";
const encoder = new TextEncoder();

const finiteCoordinate = z.number({ error: "Coordinates must be numbers." })
  .finite("Coordinates must be finite.")
  .min(-100_000, "Coordinates must be at least -100000 mm.")
  .max(100_000, "Coordinates must be at most 100000 mm.");

const pointSchema = z.strictObject({
  x: finiteCoordinate,
  y: finiteCoordinate,
});

const segmentSchema = z.strictObject({
  id: z.string().trim().min(1).max(64).optional(),
  start: pointSchema,
  end: pointSchema,
  thickness: z.number().finite().min(1).max(2_000).optional(),
  layer: z.string().trim().min(1).max(64).optional(),
});

const openingSchema = z.strictObject({
  kind: z.enum(["door", "window"]),
  wallId: z.string().trim().min(1).max(64).optional(),
  wallIndex: z.number().int().min(0).max(63).optional(),
  offset: z.number().finite().min(0).max(100_000),
  width: z.number().finite().positive().max(20_000),
  height: z.number().finite().positive().max(20_000),
  sill: z.number().finite().min(0).max(20_000).optional(),
  swing: z.enum(["left", "right", "double"]).optional(),
  openingDirection: z.enum(["in", "out"]).optional(),
  panelType: z.enum(["fixed", "single", "double", "sliding", "louvered"]).optional(),
  placement: z.enum(["main", "attic"]).optional(),
  label: z.string().trim().min(1).max(48).optional(),
}).refine((opening) => opening.wallId !== undefined || opening.wallIndex !== undefined, {
  message: "Each opening needs wallId or wallIndex.",
  path: ["wallId"],
});

const stairSchema = z.strictObject({
  x: finiteCoordinate,
  y: finiteCoordinate,
  width: z.number().finite().positive().max(20_000),
  length: z.number().finite().positive().max(30_000),
  risers: z.number().int().min(3).max(40),
  direction: z.enum(["up-north", "up-south", "up-east", "up-west"]),
  treadDepth: z.number().finite().min(100).max(1_000).optional(),
  landingDepth: z.number().finite().min(0).max(10_000).optional(),
  railing: z.enum(["none", "left", "right", "both"]).optional(),
  showDownArrow: z.boolean().optional(),
});

const gridAxisSchema = z.strictObject({
  id: z.string().trim().min(1).max(32),
  start: pointSchema,
  end: pointSchema,
});

const sectionCutSchema = z.strictObject({
  id: z.string().trim().min(1).max(32),
  start: pointSchema,
  end: pointSchema,
});

const roomLabelSchema = z.strictObject({
  id: z.string().trim().min(1).max(64).optional(),
  name: z.string().trim().min(1).max(120),
  at: pointSchema,
  polygon: z.array(pointSchema).min(3).max(64).optional(),
});

const symbolSchema = z.strictObject({
  id: z.string().trim().min(1).max(64).optional(),
  kind: z.enum(["column", "sink", "toilet", "tub", "table", "chair", "cabinet", "label"]),
  at: pointSchema,
  width: z.number().finite().positive().max(20_000).optional(),
  depth: z.number().finite().positive().max(20_000).optional(),
  rotation: z.number().finite().min(-360).max(360).optional(),
  label: z.string().trim().min(1).max(120).optional(),
});

const facadeFeatureSchema = z.strictObject({
  id: z.string().trim().min(1).max(64).optional(),
  kind: z.enum(["attic-window", "vent", "louver", "downspout"]),
  facade: z.enum(["front", "right", "rear", "left"]),
  offset: z.number().finite().min(0).max(100_000),
  width: z.number().finite().positive().max(20_000).optional(),
  height: z.number().finite().positive().max(20_000).optional(),
  sill: z.number().finite().min(0).max(20_000).optional(),
  label: z.string().trim().min(1).max(120).optional(),
});

const buildingSpecSchema = z.strictObject({
  schemaVersion: z.literal(BUILDING_SCHEMA_VERSION).optional(),
  projectName: z.string().trim().min(1).max(120),
  unit: z.literal("mm"),
  width: z.number().finite().min(3_000).max(50_000),
  depth: z.number().finite().min(3_000).max(50_000),
  wallThickness: z.number().finite().min(80).max(600),
  eaveHeight: z.number().finite().min(2_400).max(15_000),
  ridgeHeight: z.number().finite().min(2_600).max(20_000),
  atticFloorHeight: z.number().finite().min(1_800).max(12_000),
  ceilingHeight: z.number().finite().min(2_100).max(10_000),
  roofDirection: z.enum(["ridge-along-width", "ridge-along-depth"]),
  roofOverhang: z.number().finite().min(0).max(2_000),
  roofThickness: z.number().finite().min(80).max(800),
  floorSlabThickness: z.number().finite().min(80).max(800),
  foundationDepth: z.number().finite().min(250).max(4_000),
  drawingScale: z.string().trim().min(1).max(32).optional(),
  atticMinimumClearHeight: z.number().finite().min(0).max(10_000).optional(),
  roofFinish: z.string().trim().min(1).max(120),
  wallFinish: z.string().trim().min(1).max(120),
  plinthFinish: z.string().trim().min(1).max(120),
  frameFinish: z.string().trim().min(1).max(120).optional(),
  gutterDownspoutSpec: z.string().trim().min(1).max(240).optional(),
  outline: z.array(pointSchema).min(3).max(64).optional(),
  wallIds: z.array(z.string().trim().min(1).max(64)).max(64).optional(),
  interiorWalls: z.array(segmentSchema).max(128).optional(),
  openings: z.array(openingSchema).max(128).optional(),
  stair: stairSchema.optional(),
  stairEnabled: z.boolean().optional(),
  roomLabels: z.array(roomLabelSchema).max(128).optional(),
  gridAxes: z.array(gridAxisSchema).max(128).optional(),
  sectionCuts: z.array(sectionCutSchema).max(32).optional(),
  symbols: z.array(symbolSchema).max(256).optional(),
  facadeFeatures: z.array(facadeFeatureSchema).max(128).optional(),
});

const specInputSchema = buildingSpecSchema.partial().describe(
  "A partial HS-CAD building specification in millimetres. Omitted values use safe defaults.",
);

const metricsSchema = z.strictObject({
  footprintAreaM2: z.number().finite(),
  perimeterM: z.number().finite(),
  roofPitchDegrees: z.number().finite(),
  atticPeakHeight: z.number().finite(),
  atticUsableWidthAt1800: z.number().finite(),
  exteriorWallCount: z.number().int().min(0),
  openingCount: z.number().int().min(0),
  roofPitchRatio: z.string().max(32).optional(),
  atticMinimumClearHeight: z.number().finite().optional(),
  atticUsableWidthAtMinimum: z.number().finite().optional(),
});

const scheduleRowSchema = z.strictObject({
  mark: z.string().max(120),
  kind: z.enum(["door", "window"]),
  count: z.number().int().min(0),
  width: z.number().finite(),
  height: z.number().finite(),
  sill: z.number().finite(),
});

const issueSchema = z.strictObject({
  code: z.string().min(1).max(120),
  path: z.string().max(240),
  severity: z.enum(["error", "warning"]),
  message: z.string().min(1).max(1_000),
});

const viewSummarySchema = z.strictObject({
  id: z.enum(["plan", "front", "rear", "left", "right", "section-a", "section-b"]),
  title: z.string().max(120),
  width: z.number().finite(),
  height: z.number().finite(),
  entityCount: z.number().int().min(0),
  layers: z.array(z.string().max(64)).max(128),
});

const artifactMetadataSchema = z.strictObject({
  id: z.string().min(1).max(120),
  fileName: z.string().min(1).max(180),
  mimeType: z.string().min(1).max(120),
  bytes: z.number().int().min(0),
  sha256: z.string().regex(/^[a-f0-9]{64}$/),
});

const preparedDrawingSchema = z.strictObject({
  spec: buildingSpecSchema,
  valid: z.boolean(),
  metrics: metricsSchema,
  warnings: z.array(z.string().max(1_000)).max(256),
  issues: z.array(issueSchema).max(256),
  schedules: z.strictObject({
    openings: z.array(scheduleRowSchema).max(256),
    doors: z.array(scheduleRowSchema).max(256),
    windows: z.array(scheduleRowSchema).max(256),
  }),
  views: z.array(viewSummarySchema).max(16),
  artifacts: z.array(artifactMetadataSchema).max(32),
  generatedAt: z.string().datetime({ offset: true }),
  engineVersion: z.string().min(1).max(32),
});

const renderInputSchema = z.strictObject({
  spec: specInputSchema.optional().describe("A new or edited partial building specification."),
  prepared: preparedDrawingSchema.optional().describe(
    "Concise prepared data returned by generate_architectural_set. Its spec is reused for rendering.",
  ),
}).refine((value) => (value.spec === undefined) !== (value.prepared === undefined), {
  message: "Provide exactly one of spec or prepared.",
});

type PreparedDrawing = z.infer<typeof preparedDrawingSchema>;
type ArtifactMetadata = z.infer<typeof artifactMetadataSchema>;

interface TextArtifact extends ArtifactMetadata {
  text: string;
}

interface ViewSvgArtifact extends TextArtifact {
  title: string;
}

interface ToolArtifacts {
  dxf: TextArtifact;
  sheetSvg: TextArtifact;
  viewSvgs: ViewSvgArtifact[];
  projectJson: TextArtifact;
}

class SafeRuntimeError extends Error {
  constructor(
    readonly code: "PAYLOAD_TOO_LARGE" | "OUTPUT_TOO_LARGE" | "TIMEOUT" | "ASSET_UNAVAILABLE" | "VALIDATION_ERROR",
    message: string,
  ) {
    super(message);
    this.name = "SafeRuntimeError";
  }
}

class SemanticValidationError extends SafeRuntimeError {
  constructor(readonly issues: ValidationIssue[]) {
    super("VALIDATION_ERROR", "The drawing has blocking validation issues.");
    this.name = "SemanticValidationError";
  }
}

const byteLength = (value: string): number => encoder.encode(value).byteLength;

const sha256 = async (value: string): Promise<string> => {
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(value));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
};

const slugify = (value: string): string => {
  const slug = value.normalize("NFKD").replace(/[^a-zA-Z0-9]+/g, "-").replace(/^-+|-+$/g, "").toLowerCase();
  return slug.slice(0, 64) || "hscad-project";
};

const materializeArtifact = async (
  id: string,
  fileName: string,
  mimeType: string,
  text: string,
): Promise<TextArtifact> => ({
  id,
  fileName,
  mimeType,
  text,
  bytes: byteLength(text),
  sha256: await sha256(text),
});

const buildArtifacts = async (drawing: DrawingSet): Promise<ToolArtifacts> => {
  const baseName = slugify(drawing.spec.projectName);
  const dxfText = drawingSetToDxf(drawing);
  const sheetSvgText = drawingSetToSvgSheet(drawing);
  // The project artifact is intentionally the importable BuildingSpec, not a
  // serialized DrawingSet. The full generated drawing remains in `_meta.drawing`.
  const projectJsonText = JSON.stringify(drawing.spec, null, 2);

  const [dxf, sheetSvg, projectJson, ...viewSvgs] = await Promise.all([
    materializeArtifact("dxf", `${baseName}.dxf`, "application/dxf", dxfText),
    materializeArtifact("sheetSvg", `${baseName}-drawing-set.svg`, "image/svg+xml", sheetSvgText),
    materializeArtifact("projectJson", `${baseName}.hscad.json`, "application/json", projectJsonText),
    ...drawing.views.map(async (view): Promise<ViewSvgArtifact> => ({
      ...await materializeArtifact(
        `viewSvg:${view.id}`,
        `${baseName}-${view.id}.svg`,
        "image/svg+xml",
        viewToSvg(view),
      ),
      title: view.title,
    })),
  ]);

  return { dxf, sheetSvg, viewSvgs, projectJson };
};

const metadataForArtifacts = (artifacts: ToolArtifacts): ArtifactMetadata[] => [
  artifacts.dxf,
  artifacts.sheetSvg,
  ...artifacts.viewSvgs,
  artifacts.projectJson,
].map(({ id, fileName, mimeType, bytes, sha256: hash }) => ({
  id,
  fileName,
  mimeType,
  bytes,
  sha256: hash,
}));

const prepareDrawing = async (input: Partial<BuildingSpec>, rejectSemanticErrors = true): Promise<{
  drawing: DrawingSet;
  prepared: PreparedDrawing;
  artifacts: ToolArtifacts;
}> => {
  const inputIssues = validateSpecDetailed(input);
  const blockingIssues = inputIssues.filter((issue) => issue.severity === "error");
  if (rejectSemanticErrors && blockingIssues.length > 0) {
    throw new SemanticValidationError(blockingIssues);
  }
  const drawing = generateDrawingSet(input);
  const issues = drawing.validationIssues?.length ? drawing.validationIssues : inputIssues;
  const warnings = [...new Set(issues
    .filter((issue) => issue.severity === "warning")
    .map((issue) => issue.message))];
  const artifacts = await buildArtifacts(drawing);
  const openings = drawing.openingSchedule;
  const doors = drawing.doorSchedule ?? openings.filter((row) => row.kind === "door");
  const windows = drawing.windowSchedule ?? openings.filter((row) => row.kind === "window");

  const prepared: PreparedDrawing = {
    spec: drawing.spec,
    valid: !issues.some((issue) => issue.severity === "error"),
    metrics: drawing.metrics,
    warnings,
    issues,
    schedules: { openings, doors, windows },
    views: drawing.views.map((view) => ({
      id: view.id,
      title: view.title,
      width: view.width,
      height: view.height,
      entityCount: view.entities.length,
      layers: [...new Set(view.entities.map((entity) => entity.layer))].sort(),
    })),
    artifacts: metadataForArtifacts(artifacts),
    generatedAt: drawing.generatedAt,
    engineVersion: drawing.engineVersion,
  };

  const privatePayloadBytes = byteLength(JSON.stringify({ drawing, artifacts }));
  if (privatePayloadBytes > MAX_TOOL_OUTPUT_BYTES) {
    throw new SafeRuntimeError(
      "OUTPUT_TOO_LARGE",
      `The generated drawing exceeds the ${MAX_TOOL_OUTPUT_BYTES} byte response limit. Reduce custom geometry and try again.`,
    );
  }

  return { drawing, prepared, artifacts };
};

const withTimeout = async <T>(task: () => Promise<T>, timeoutMs: number): Promise<T> => {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new SafeRuntimeError("TIMEOUT", "The operation timed out. Try a simpler drawing.")), timeoutMs);
  });
  try {
    return await Promise.race([Promise.resolve().then(task), timeout]);
  } finally {
    if (timer !== undefined) clearTimeout(timer);
  }
};

const safeToolError = (requestId: string, toolName: string, error: unknown) => {
  const code = error instanceof SafeRuntimeError ? error.code : "INTERNAL_ERROR";
  console.error(JSON.stringify({ event: "tool_error", requestId, tool: toolName, code }));
  const validationIssues = error instanceof SemanticValidationError ? error.issues : undefined;
  const message = validationIssues
    ? `Drawing generation was stopped because ${validationIssues.length} blocking validation issue${validationIssues.length === 1 ? " was" : "s were"} found: ${validationIssues.slice(0, 3).map((issue) => issue.message).join(" ")}`
    : error instanceof SafeRuntimeError
      ? error.message
      : "HS-CAD could not process this drawing. Check the supplied dimensions and geometry, then try again.";
  return {
    isError: true as const,
    content: [{ type: "text" as const, text: message }],
    ...(validationIssues ? {
      structuredContent: {
        valid: false,
        issues: validationIssues,
        warnings: [] as string[],
      },
    } : {}),
    _meta: { requestId, error: { code, ...(validationIssues ? { issues: validationIssues } : {}) } },
  };
};

const toolResult = (
  requestId: string,
  drawing: DrawingSet,
  prepared: PreparedDrawing,
  artifacts: ToolArtifacts,
  text: string,
) => ({
  structuredContent: prepared,
  content: [{ type: "text" as const, text }],
  _meta: { requestId, drawing, artifacts },
});

const readBodyWithLimit = async (body: ReadableStream<Uint8Array> | null, limit: number): Promise<Uint8Array> => {
  if (!body) return new Uint8Array();
  const reader = body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > limit) {
        await reader.cancel();
        throw new SafeRuntimeError("PAYLOAD_TOO_LARGE", `Request body exceeds the ${limit} byte limit.`);
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return bytes;
};

const getWidgetHtml = async (assets: Fetcher, requestUrl: string): Promise<string> => {
  const assetUrl = new URL("/", requestUrl);
  let response: Response;
  try {
    response = await assets.fetch(new Request(assetUrl, { method: "GET" }));
  } catch {
    throw new SafeRuntimeError("ASSET_UNAVAILABLE", "The HS-CAD widget is temporarily unavailable.");
  }
  if (!response.ok) {
    throw new SafeRuntimeError("ASSET_UNAVAILABLE", "The HS-CAD widget is temporarily unavailable.");
  }
  const declaredLength = Number(response.headers.get("content-length") ?? "0");
  if (Number.isFinite(declaredLength) && declaredLength > MAX_WIDGET_BYTES) {
    throw new SafeRuntimeError("OUTPUT_TOO_LARGE", "The HS-CAD widget exceeds its configured size limit.");
  }
  const bytes = await readBodyWithLimit(response.body, MAX_WIDGET_BYTES);
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    throw new SafeRuntimeError("ASSET_UNAVAILABLE", "The HS-CAD widget is not valid UTF-8.");
  }
};

const resourceUiMeta = (origin: string) => ({
  ui: {
    prefersBorder: true,
    domain: origin,
    csp: {
      connectDomains: [] as string[],
      resourceDomains: [origin],
    },
  },
  "openai/widgetDescription": "A mobile architectural CAD editor for reviewing plans, elevations, sections, schedules, and export artifacts.",
  "openai/widgetPrefersBorder": true,
  "openai/widgetDomain": origin,
  "openai/widgetCSP": {
    connect_domains: [] as string[],
    resource_domains: [origin],
  },
});

const drawingToolAnnotations = {
  readOnlyHint: true,
  destructiveHint: false,
  openWorldHint: false,
  idempotentHint: true,
} as const;

export function createServer(origin: string, assets: Fetcher, requestUrl: string, requestId: string): McpServer {
  const server = new McpServer(
    { name: "HS-CAD Mobile", version: ENGINE_VERSION },
    {
      instructions:
        "Use open_mobile_cad for the default editor, render_architectural_set to attach the editor to supplied or prepared data, generate_architectural_set for model- or app-callable data-only recalculation, and validate_architectural_set to review parameters. Preserve user dimensions unless changes are requested. Surface warnings and remind users that generated drawings require professional review before construction.",
    },
  );

  const resourceMeta = resourceUiMeta(origin);
  registerAppResource(
    server,
    "HS-CAD Mobile editor v3",
    WIDGET_URI,
    {
      title: "HS-CAD Mobile architectural editor",
      description: "Interactive mobile editor for the HS-CAD architectural drawing set.",
      mimeType: RESOURCE_MIME_TYPE,
      _meta: resourceMeta,
    },
    async () => ({
      contents: [{
        uri: WIDGET_URI,
        mimeType: RESOURCE_MIME_TYPE,
        text: await getWidgetHtml(assets, requestUrl),
        _meta: resourceMeta,
      }],
    }),
  );

  registerAppTool(server, "open_mobile_cad", {
    title: "Open HS-CAD mobile editor",
    description: "Use this when the user wants to open a mobile architectural CAD workspace with a safe default gable-roof drawing set.",
    inputSchema: z.strictObject({}),
    outputSchema: preparedDrawingSchema,
    annotations: drawingToolAnnotations,
    _meta: {
      ui: { resourceUri: WIDGET_URI, visibility: ["model", "app"] },
      "openai/outputTemplate": WIDGET_URI,
      "openai/widgetAccessible": true,
      "openai/toolInvocation/invoking": "Opening the HS-CAD mobile editor…",
      "openai/toolInvocation/invoked": "HS-CAD mobile editor is ready",
    },
  }, async () => {
    try {
      const result = await withTimeout(() => prepareDrawing({}), TOOL_TIMEOUT_MS);
      return toolResult(
        requestId,
        result.drawing,
        result.prepared,
        result.artifacts,
        `Opened ${result.prepared.spec.projectName} with ${result.prepared.views.length} drawing views and ${result.prepared.warnings.length} warnings.`,
      );
    } catch (error) {
      return safeToolError(requestId, "open_mobile_cad", error);
    }
  });

  registerAppTool(server, "render_architectural_set", {
    title: "Render architectural drawing set",
    description: "Use this when the user wants an interactive HS-CAD editor attached to either a building spec or concise prepared data returned by generate_architectural_set.",
    inputSchema: renderInputSchema,
    outputSchema: preparedDrawingSchema,
    annotations: drawingToolAnnotations,
    _meta: {
      ui: { resourceUri: WIDGET_URI, visibility: ["model", "app"] },
      "openai/outputTemplate": WIDGET_URI,
      "openai/widgetAccessible": true,
      "openai/toolInvocation/invoking": "Rendering the architectural drawing set…",
      "openai/toolInvocation/invoked": "Architectural drawing set is ready",
    },
  }, async ({ spec, prepared }) => {
    try {
      const input = spec ?? prepared?.spec ?? {};
      const result = await withTimeout(() => prepareDrawing(input as Partial<BuildingSpec>), TOOL_TIMEOUT_MS);
      return toolResult(
        requestId,
        result.drawing,
        result.prepared,
        result.artifacts,
        `Rendered ${result.prepared.spec.projectName}: ${result.prepared.views.length} views, ${result.prepared.schedules.openings.length} opening schedule rows, and ${result.prepared.warnings.length} warnings.`,
      );
    } catch (error) {
      return safeToolError(requestId, "render_architectural_set", error);
    }
  });

  registerAppTool(server, "generate_architectural_set", {
    title: "Generate architectural drawing data",
    description: "Use this when the model or mounted HS-CAD app needs idempotent data-only recalculation without attaching another widget.",
    inputSchema: specInputSchema,
    outputSchema: preparedDrawingSchema,
    annotations: drawingToolAnnotations,
    _meta: {
      ui: { visibility: ["model", "app"] },
      "openai/widgetAccessible": true,
      "openai/toolInvocation/invoking": "Generating architectural drawing data…",
      "openai/toolInvocation/invoked": "Architectural drawing data is ready",
    },
  }, async (args) => {
    try {
      const result = await withTimeout(() => prepareDrawing(args as Partial<BuildingSpec>), TOOL_TIMEOUT_MS);
      return toolResult(
        requestId,
        result.drawing,
        result.prepared,
        result.artifacts,
        `Generated ${result.prepared.views.length} concise view summaries and ${result.prepared.artifacts.length} artifact records.`,
      );
    } catch (error) {
      return safeToolError(requestId, "generate_architectural_set", error);
    }
  });

  registerAppTool(server, "validate_architectural_set", {
    title: "Validate architectural drawing parameters",
    description: "Use this when the user or app needs roof, attic, wall, outline, opening, stair, and geometry checks before construction-document review.",
    inputSchema: specInputSchema,
    outputSchema: preparedDrawingSchema,
    annotations: drawingToolAnnotations,
    _meta: {
      ui: { visibility: ["model", "app"] },
      "openai/widgetAccessible": true,
      "openai/toolInvocation/invoking": "Validating architectural parameters…",
      "openai/toolInvocation/invoked": "Architectural validation is complete",
    },
  }, async (args) => {
    try {
      const normalized = normalizeSpec(args as Partial<BuildingSpec>);
      const result = await withTimeout(() => prepareDrawing(normalized, false), TOOL_TIMEOUT_MS);
      const text = result.prepared.valid
        ? "The architectural parameters passed the available automated checks. Professional review is still required before construction."
        : `Validation found ${result.prepared.issues.length} issues or warnings. Review them before using the drawing set.`;
      return toolResult(requestId, result.drawing, result.prepared, result.artifacts, text);
    } catch (error) {
      return safeToolError(requestId, "validate_architectural_set", error);
    }
  });

  return server;
}

const jsonError = (
  status: number,
  requestId: string,
  code: string,
  message: string,
  headers?: HeadersInit,
): Response => Response.json(
  { ok: false, error: { code, message }, requestId },
  { status, headers },
);

const jsonRpcError = (
  status: number,
  requestId: string,
  rpcCode: number,
  message: string,
): Response => Response.json(
  { jsonrpc: "2.0", error: { code: rpcCode, message, data: { requestId } }, id: null },
  { status },
);

const allowedCorsOrigin = (request: Request, endpointOrigin: string): string => {
  const requestOrigin = request.headers.get("origin");
  return requestOrigin === endpointOrigin ? requestOrigin : endpointOrigin;
};

const secureResponse = (
  response: Response,
  request: Request,
  requestId: string,
  endpointOrigin: string,
  isMcp: boolean,
): Response => {
  const headers = new Headers(response.headers);
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("Referrer-Policy", "no-referrer");
  headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  headers.set("Strict-Transport-Security", "max-age=31536000; includeSubDomains");
  headers.set("X-Robots-Tag", "noindex, nofollow");
  headers.set("X-Request-Id", requestId);
  if (isMcp) {
    headers.set("Access-Control-Allow-Origin", allowedCorsOrigin(request, endpointOrigin));
    headers.set("Access-Control-Expose-Headers", "mcp-session-id, x-request-id");
    headers.set("Vary", "Origin");
    headers.set("Cache-Control", "no-store");
  }
  return new Response(request.method === "HEAD" ? null : response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
};

const rebuiltJsonRequest = async (request: Request): Promise<Request> => {
  const declaredLength = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(declaredLength) && declaredLength > MAX_REQUEST_BYTES) {
    throw new SafeRuntimeError("PAYLOAD_TOO_LARGE", `Request body exceeds the ${MAX_REQUEST_BYTES} byte limit.`);
  }
  const bytes = await readBodyWithLimit(request.body, MAX_REQUEST_BYTES);
  let body: string;
  try {
    body = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    JSON.parse(body);
  } catch {
    throw new SyntaxError("Invalid JSON");
  }
  const headers = new Headers(request.headers);
  headers.delete("content-length");
  return new Request(request.url, {
    method: "POST",
    headers,
    body,
    signal: request.signal,
  });
};

const handleMcp = async (request: Request, env: Env, ctx: ExecutionContext, requestId: string): Promise<Response> => {
  const url = new URL(request.url);
  const allowedMethods = "GET, POST, DELETE, OPTIONS";
  if (!["GET", "POST", "DELETE", "OPTIONS"].includes(request.method)) {
    return jsonError(405, requestId, "METHOD_NOT_ALLOWED", "Use GET, POST, DELETE, or OPTIONS for the MCP endpoint.", {
      Allow: allowedMethods,
    });
  }
  if (request.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        "Access-Control-Allow-Headers": "Content-Type, Accept, Authorization, mcp-session-id, MCP-Protocol-Version",
        "Access-Control-Allow-Methods": allowedMethods,
        "Access-Control-Max-Age": "600",
      },
    });
  }

  let forwardedRequest = request;
  if (request.method === "POST") {
    const contentType = request.headers.get("content-type")?.split(";", 1)[0].trim().toLowerCase() ?? "";
    if (contentType !== "application/json") {
      return jsonRpcError(415, requestId, -32000, "Content-Type must be application/json.");
    }
    try {
      forwardedRequest = await rebuiltJsonRequest(request);
    } catch (error) {
      if (error instanceof SafeRuntimeError && error.code === "PAYLOAD_TOO_LARGE") {
        return jsonRpcError(413, requestId, -32000, error.message);
      }
      return jsonRpcError(400, requestId, -32700, "Parse error: invalid JSON.");
    }
  }

  const server = createServer(url.origin, env.ASSETS, request.url, requestId);
  const handler = createMcpHandler(server, {
    route: MCP_ROUTE,
    corsOptions: {
      origin: allowedCorsOrigin(request, url.origin),
      headers: "Content-Type, Accept, Authorization, mcp-session-id, MCP-Protocol-Version",
      methods: allowedMethods,
      exposeHeaders: "mcp-session-id, x-request-id",
      maxAge: 600,
    },
  });

  try {
    return await withTimeout(() => handler(forwardedRequest, env, ctx), RESPONSE_START_TIMEOUT_MS);
  } catch (error) {
    const timedOut = error instanceof SafeRuntimeError && error.code === "TIMEOUT";
    return jsonRpcError(
      timedOut ? 504 : 500,
      requestId,
      -32603,
      timedOut ? "The MCP request timed out." : "Internal server error.",
    );
  }
};

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const startedAt = Date.now();
    const requestId = crypto.randomUUID();
    const url = new URL(request.url);
    let response: Response;
    let isMcp = false;

    try {
      if (url.pathname === "/health") {
        if (request.method !== "GET" && request.method !== "HEAD") {
          response = jsonError(405, requestId, "METHOD_NOT_ALLOWED", "Use GET or HEAD for the health endpoint.", {
            Allow: "GET, HEAD",
          });
        } else {
          response = Response.json({
            ok: true,
            service: "hscad-mobile-cad",
            version: ENGINE_VERSION,
            schemaVersion: BUILDING_SCHEMA_VERSION,
            protocolVersion: PROTOCOL_VERSION,
            widget: WIDGET_URI,
            timestamp: new Date().toISOString(),
          });
        }
      } else if (url.pathname === MCP_ROUTE) {
        isMcp = true;
        response = await handleMcp(request, env, ctx, requestId);
      } else if (url.pathname.startsWith(`${MCP_ROUTE}/`)) {
        isMcp = true;
        response = jsonError(404, requestId, "NOT_FOUND", "MCP endpoint not found.");
      } else {
        try {
          response = await env.ASSETS.fetch(request);
        } catch {
          response = jsonError(502, requestId, "ASSET_UNAVAILABLE", "Static assets are temporarily unavailable.");
        }
      }
    } catch {
      response = isMcp
        ? jsonRpcError(500, requestId, -32603, "Internal server error.")
        : jsonError(500, requestId, "INTERNAL_ERROR", "Internal server error.");
    }

    const secured = secureResponse(response, request, requestId, url.origin, isMcp || url.pathname === "/health");
    console.info(JSON.stringify({
      event: "http_request",
      requestId,
      method: request.method,
      path: url.pathname,
      status: secured.status,
      durationMs: Date.now() - startedAt,
    }));
    return secured;
  },
} satisfies ExportedHandler<Env>;
