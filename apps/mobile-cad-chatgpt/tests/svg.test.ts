// @vitest-environment happy-dom

import { describe, expect, it } from "vitest";
import { generateDrawingSet } from "../src/cad-model";
import { drawingSetToSvgSheet, viewToSvg } from "../src/svg";

const parseSvg = (source: string): SVGSVGElement => new DOMParser().parseFromString(source, "image/svg+xml").documentElement as unknown as SVGSVGElement;

describe("SVG architectural previews", () => {
  it("emits a valid standalone root with a finite entity-derived viewBox", () => {
    const set = generateDrawingSet({});
    const source = viewToSvg(set.views[0]);
    const root = parseSvg(source);
    const viewBox = root.getAttribute("viewBox")!.split(/\s+/).map(Number);
    expect(root.localName).toBe("svg");
    expect(root.getAttribute("data-view-id")).toBe("plan");
    expect(viewBox).toHaveLength(4);
    expect(viewBox.every(Number.isFinite)).toBe(true);
    expect(viewBox[2]).toBeGreaterThan(0);
    expect(viewBox[3]).toBeGreaterThan(0);
    expect(root.querySelector("circle")).not.toBeNull();
  });

  it("identifies all seven views on the complete SVG sheet", () => {
    const root = parseSvg(drawingSetToSvgSheet(generateDrawingSet({})));
    const ids = [...root.querySelectorAll("g[data-view-id]")].map((element) => element.getAttribute("data-view-id"));
    expect(ids).toEqual(["plan", "front", "rear", "left", "right", "section-a", "section-b"]);
    expect(root.getAttribute("data-drawing-set")).toBe("1.0");
  });

  it("is byte-identical across repeated default generations", () => {
    const first = drawingSetToSvgSheet(generateDrawingSet({ projectName: "DETERMINISTIC" }));
    const second = drawingSetToSvgSheet(generateDrawingSet({ projectName: "DETERMINISTIC" }));
    expect(second).toBe(first);
  });

  it("escapes user text and sanitizes layer attributes without script injection", () => {
    const set = generateDrawingSet({
      projectName: `</text><script>alert("x")</script>`,
      openings: [{ kind: "window", wallIndex: 0, offset: 1000, width: 1200, height: 1000, sill: 800, label: `"><script>alert(1)</script>` }],
      interiorWalls: [{ start: { x: 1000, y: 1000 }, end: { x: 3000, y: 1000 }, layer: `x" onload="alert(1)` }],
    });
    const source = drawingSetToSvgSheet(set);
    const root = parseSvg(source);
    expect(source).toContain("&lt;/text&gt;&lt;script&gt;");
    expect(source).not.toContain("onload=");
    expect(root.querySelector("script")).toBeNull();
    for (const element of root.querySelectorAll("[class]")) expect(element.getAttribute("class")).toMatch(/^A-[A-Z0-9_-]+$/);
  });

  it("includes translated geometry and annotations in the standalone viewBox", () => {
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
    const root = parseSvg(viewToSvg(set.views[0]));
    const [minX, , width] = root.getAttribute("viewBox")!.split(/\s+/).map(Number);
    expect(minX).toBeLessThan(80000);
    expect(minX + width).toBeGreaterThan(90000);
  });

  it("rejects non-finite SVG entity coordinates", () => {
    const set = generateDrawingSet({});
    const line = set.views[0].entities.find((entity) => entity.type === "line");
    expect(line?.type).toBe("line");
    if (line?.type === "line") line.end.y = Number.POSITIVE_INFINITY;
    expect(() => viewToSvg(set.views[0])).toThrow(/finite/);
  });
});
