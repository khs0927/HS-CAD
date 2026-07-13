import { describe, expect, it } from "vitest";
import { generateDrawingSet, normalizeSpec, validateSpec } from "../src/cad-model";
import { drawingSetToDxf } from "../src/dxf";
import { drawingSetToSvgSheet, viewToSvg } from "../src/svg";

describe("HS-CAD mobile engine", () => {
  it("generates plan, four elevations and two sections", () => {
    const set = generateDrawingSet({ width: 12000, depth: 11300, eaveHeight: 3200, ridgeHeight: 5000, atticFloorHeight: 2600 }, "2026-07-13T00:00:00.000Z");
    expect(set.views).toHaveLength(7);
    expect(set.views.map((view) => view.id)).toEqual(["plan", "front", "rear", "left", "right", "section-a", "section-b"]);
    expect(set.metrics.footprintAreaM2).toBe(135.6);
    expect(set.openingSchedule.length).toBeGreaterThan(0);
    expect(set.engineVersion).toBe("0.2.0");
  });

  it("adds detailed stairs, dimensions, material lines and level markers", () => {
    const set = generateDrawingSet({});
    const layers = new Set(set.views.flatMap((view) => view.entities.map((entity) => entity.layer)));
    for (const layer of ["A-STRS", "A-DIMS", "A-MATL", "A-LEVEL", "A-CUT", "A-ROOF"]) expect(layers.has(layer)).toBe(true);
  });

  it("maps custom facade openings into elevations", () => {
    const set = generateDrawingSet({
      openings: [{ kind: "window", wallIndex: 0, offset: 1000, width: 2000, height: 1100, sill: 800, label: "WX" }],
    });
    const front = set.views.find((view) => view.id === "front")!;
    expect(front.entities.some((entity) => entity.type === "text" && entity.text === "WX")).toBe(true);
    expect(set.openingSchedule[0].width).toBe(2000);
  });

  it("warns for invalid roof and attic relationships", () => {
    const spec = normalizeSpec({ eaveHeight: 5000, ridgeHeight: 4000, atticFloorHeight: 5200, ceilingHeight: 5400 });
    const warnings = validateSpec(spec);
    expect(warnings).toContain("용마루 높이는 처마 높이보다 높아야 합니다.");
    expect(warnings).toContain("다락 바닥 높이는 처마 높이보다 낮아야 합니다.");
    expect(warnings).toContain("실내 천장 높이는 다락 바닥 높이보다 낮거나 같아야 합니다.");
  });

  it("detects self-intersecting outlines and openings beyond wall length", () => {
    const spec = normalizeSpec({
      outline: [{ x: 0, y: 0 }, { x: 10000, y: 10000 }, { x: 0, y: 10000 }, { x: 10000, y: 0 }],
      openings: [{ kind: "door", wallIndex: 0, offset: 14000, width: 900, height: 2100 }],
    });
    const warnings = validateSpec(spec);
    expect(warnings.some((warning) => warning.includes("자기 교차"))).toBe(true);
    expect(warnings.some((warning) => warning.includes("벽 길이를 초과"))).toBe(true);
  });

  it("exports a layered ASCII R12 DXF with extents and border", () => {
    const dxf = drawingSetToDxf(generateDrawingSet({}));
    expect(dxf).toContain("AC1009");
    expect(dxf).toContain("$EXTMIN");
    expect(dxf).toContain("DASHED");
    expect(dxf).toContain("A-BORDER");
    expect(dxf).toContain("POLYLINE");
    expect(dxf).toContain("CIRCLE");
    expect(dxf.endsWith("0\nEOF\n")).toBe(true);
  });

  it("exports valid standalone SVG previews and sheet", () => {
    const set = generateDrawingSet({ projectName: "A&B <Test>" });
    const svg = viewToSvg(set.views[0]);
    const sheet = drawingSetToSvgSheet(set);
    expect(svg.startsWith("<svg")).toBe(true);
    expect(svg).toContain("<circle");
    expect(sheet).toContain("A&amp;B &lt;Test&gt;");
    expect(sheet).toContain("HS-CAD Mobile");
  });
});
