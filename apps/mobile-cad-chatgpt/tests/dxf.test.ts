import { createHash } from "node:crypto";
import DxfParser from "dxf-parser";
import { describe, expect, it } from "vitest";
import { generateDrawingSet } from "../src/cad-model";
import { drawingSetToDxf } from "../src/dxf";

type ParsedEntity = Record<string, unknown> & { type?: string; layer?: string; vertices?: Array<{ x: number; y: number }>; shape?: boolean; text?: string };

const parse = (source: string): Record<string, unknown> => {
  const parsed = new DxfParser().parseSync(source);
  expect(parsed).toBeTruthy();
  return parsed as unknown as Record<string, unknown>;
};

const entitiesOf = (parsed: Record<string, unknown>): ParsedEntity[] => parsed.entities as ParsedEntity[];

describe("ASCII R12 DXF export", () => {
  it("opens in dxf-parser 1.1.2 with required sections, layers, views, and closed walls", () => {
    const dxf = drawingSetToDxf(generateDrawingSet({}, "2026-07-13T00:00:00.000Z"));
    const parsed = parse(dxf);
    const entities = entitiesOf(parsed);
    const layerTable = ((parsed.tables as Record<string, unknown>)?.layer as Record<string, unknown>)?.layers as Record<string, unknown>;
    expect(dxf).toContain("0\nSECTION\n2\nHEADER\n");
    expect(dxf).toContain("0\nSECTION\n2\nTABLES\n");
    expect(dxf).toContain("0\nSECTION\n2\nBLOCKS\n");
    expect(dxf).toContain("0\nSECTION\n2\nENTITIES\n");
    expect(dxf.endsWith("0\nEOF\n")).toBe(true);
    expect(Object.keys(layerTable)).toEqual(expect.arrayContaining(["A-WALL", "A-DOOR", "A-WIND", "A-STRS", "A-DIMS", "A-ROOF", "A-BORDER"]));
    expect(entities.filter((entity) => entity.type === "TEXT" && /PLAN|ELEVATION|SECTION/.test(entity.text ?? ""))).toHaveLength(7);
    expect(entities.some((entity) => entity.type === "POLYLINE" && entity.layer === "A-WALL" && entity.shape === true)).toBe(true);
  });

  it("is deterministic and contains only finite coordinates and nonzero lines", () => {
    const first = drawingSetToDxf(generateDrawingSet({ projectName: "DETERMINISTIC" }));
    const second = drawingSetToDxf(generateDrawingSet({ projectName: "DETERMINISTIC" }));
    expect(second).toBe(first);
    const entities = entitiesOf(parse(first));
    for (const entity of entities) {
      for (const vertex of entity.vertices ?? []) {
        expect(Number.isFinite(vertex.x)).toBe(true);
        expect(Number.isFinite(vertex.y)).toBe(true);
      }
      if (entity.type === "LINE" && entity.vertices?.length === 2) {
        expect(Math.hypot(entity.vertices[1].x - entity.vertices[0].x, entity.vertices[1].y - entity.vertices[0].y)).toBeGreaterThan(0);
      }
    }
    expect(first).not.toMatch(/(?:^|\n)(?:NaN|Infinity|-Infinity)(?:\n|$)/);
  });

  it("matches the compact golden hash for the 12000 × 11300 reference set", () => {
    const dxf = drawingSetToDxf(generateDrawingSet({
      width: 12_000,
      depth: 11_300,
      eaveHeight: 3_200,
      ridgeHeight: 5_000,
      atticFloorHeight: 2_600,
    }));
    expect(createHash("sha256").update(dxf).digest("hex"))
      .toBe("e428dc8d67c3bc116f4032a6cc76798f2d6da04780010050899eaf3939907094");
  });

  it("derives extents from translated entities instead of nominal view dimensions", () => {
    const set = generateDrawingSet({
      width: 10000,
      depth: 8000,
      outline: [{ x: 80000, y: 50000 }, { x: 90000, y: 50000 }, { x: 90000, y: 58000 }, { x: 80000, y: 58000 }],
      openings: [],
      interiorWalls: [],
      gridAxes: [],
      symbols: [],
      stairEnabled: false,
    });
    const parsed = parse(drawingSetToDxf(set));
    const header = parsed.header as Record<string, { x: number; y: number }>;
    expect(header.$EXTMAX.x).toBeGreaterThan(90000);
    expect(header.$EXTMAX.y).toBeGreaterThan(58000);
  });

  it("sanitizes group values and rejects non-finite or degenerate entities", () => {
    const safe = generateDrawingSet({
      openings: [],
      interiorWalls: [{ start: { x: 1000, y: 1000 }, end: { x: 2000, y: 1000 }, layer: "evil\n0\nEOF\n" }],
    });
    const dxf = drawingSetToDxf(safe);
    expect((dxf.match(/\nEOF\n/g) ?? [])).toHaveLength(1);
    expect(dxf).not.toContain("evil\n0\nEOF");
    expect(() => parse(dxf)).not.toThrow();

    const nonFinite = generateDrawingSet({});
    const line = nonFinite.views[0].entities.find((entity) => entity.type === "line");
    expect(line?.type).toBe("line");
    if (line?.type === "line") line.start.x = Number.NaN;
    expect(() => drawingSetToDxf(nonFinite)).toThrow(/finite/);

    const degenerate = generateDrawingSet({});
    degenerate.views[0].entities.push({ type: "line", layer: "A-WALL", start: { x: 1, y: 1 }, end: { x: 1, y: 1 } });
    expect(() => drawingSetToDxf(degenerate)).toThrow(/zero-length/);
  });
});
