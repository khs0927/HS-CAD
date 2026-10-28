import { describe, expect, it } from "vitest";
import { generateDrawingSet, normalizeSpec, validateSpec, validateSpecDetailed } from "../src/cad-model";
import type { ArcEntity, LineEntity, Opening, Point, PolylineEntity } from "../src/types";

const distance = (first: Point, second: Point): number => Math.hypot(second.x - first.x, second.y - first.y);
const arcPoint = (arc: ArcEntity, angle: number): Point => ({
  x: arc.center.x + arc.radius * Math.cos(angle * Math.PI / 180),
  y: arc.center.y + arc.radius * Math.sin(angle * Math.PI / 180),
});

describe("HS-CAD architectural model", () => {
  it("normalizes a versioned millimetre contract and generates all seven views", () => {
    const set = generateDrawingSet({ width: 12000, depth: 11300, eaveHeight: 3200, ridgeHeight: 5000, atticFloorHeight: 2600 }, "2026-07-13T00:00:00.000Z");
    expect(set.spec.schemaVersion).toBe("1.0");
    expect(set.spec.unit).toBe("mm");
    expect(set.views.map((view) => view.id)).toEqual(["plan", "front", "rear", "left", "right", "section-a", "section-b"]);
    expect(set.metrics.footprintAreaM2).toBe(135.6);
    expect(set.metrics.roofPitchRatio).toMatch(/^1:/);
    expect(set.openingSchedule.length).toBeGreaterThan(0);
    expect(set.doorSchedule?.every((row) => row.kind === "door")).toBe(true);
    expect(set.windowSchedule?.every((row) => row.kind === "window")).toBe(true);
    expect(set.layerList).toContain("A-WALL");
    expect(set.engineVersion).toBe("0.3.0");
  });

  it("is deterministic when no generatedAt value is supplied", () => {
    const first = generateDrawingSet({ projectName: "DETERMINISTIC" });
    const second = generateDrawingSet({ projectName: "DETERMINISTIC" });
    expect(first.generatedAt).toBe("1970-01-01T00:00:00.000Z");
    expect(second).toEqual(first);
  });

  it("preserves explicit empty collections rather than silently adding defaults", () => {
    const set = generateDrawingSet({ openings: [], interiorWalls: [], gridAxes: [], symbols: [], facadeFeatures: [], stairEnabled: false });
    const layers = set.views[0].entities.map((entity) => entity.layer);
    expect(set.spec.openings).toEqual([]);
    expect(set.spec.interiorWalls).toEqual([]);
    expect(set.openingSchedule).toEqual([]);
    expect(layers).not.toContain("A-OPEN");
    expect(layers).not.toContain("A-DOOR");
    expect(layers).not.toContain("A-WIND");
    expect(layers).not.toContain("A-GRID");
    expect(layers).not.toContain("A-STRS");
  });

  it("reports schema, finite-coordinate, count, and wall-reference errors", () => {
    const openings = Array.from({ length: 129 }, (_, index): Opening => ({ kind: "window", wallIndex: index === 0 ? 99 : 0, offset: index * 10, width: 5, height: 5 }));
    const issues = validateSpecDetailed({
      schemaVersion: "0.9" as never,
      outline: [{ x: 0, y: 0 }, { x: Number.NaN, y: 0 }, { x: 0, y: 10000 }],
      openings,
    });
    const codes = new Set(issues.map((item) => item.code));
    expect(codes).toContain("schema.version");
    expect(codes).toContain("coordinate.nonfinite");
    expect(codes).toContain("count.openings");
    expect(codes).toContain("opening.wall-reference");
    expect(normalizeSpec({ openings }).openings).toHaveLength(128);
  });

  it("enforces the engine coordinate envelope for every geometry collection", () => {
    const issues = validateSpecDetailed({
      outline: [{ x: 0, y: 0 }, { x: 100001, y: 0 }, { x: 0, y: 10000 }],
      interiorWalls: [{ start: { x: -100001, y: 0 }, end: { x: 0, y: 10 } }],
      gridAxes: [{ id: "X", start: { x: 0, y: 0 }, end: { x: 0, y: 100001 } }],
      sectionCuts: [{ id: "X", start: { x: 0, y: -100001 }, end: { x: 10, y: 10 } }],
      symbols: [{ kind: "column", at: { x: 100001, y: 0 } }],
    });
    const rangePaths = issues.filter((item) => item.code === "coordinate.range").map((item) => item.path);
    expect(rangePaths).toEqual(expect.arrayContaining([
      "outline[1]",
      "interiorWalls[0].start",
      "gridAxes[0].end",
      "sectionCuts[0].start",
      "symbols[0].at",
    ]));
  });

  it("warns for invalid height relationships", () => {
    const spec = normalizeSpec({ eaveHeight: 5000, ridgeHeight: 4000, atticFloorHeight: 5200, ceilingHeight: 5400 });
    const warnings = validateSpec(spec);
    expect(warnings).toContain("용마루 높이는 처마 높이보다 높아야 합니다.");
    expect(warnings).toContain("다락 바닥 높이는 처마 높이보다 낮아야 합니다.");
    expect(warnings).toContain("실내 천장 높이는 다락 바닥 높이보다 낮거나 같아야 합니다.");
  });

  it("detects self-intersection and opening overflow", () => {
    const issues = validateSpecDetailed({
      outline: [{ x: 0, y: 0 }, { x: 10000, y: 10000 }, { x: 0, y: 10000 }, { x: 10000, y: 0 }],
      openings: [{ kind: "door", wallIndex: 0, offset: 14000, width: 900, height: 2100 }],
    });
    expect(issues.some((item) => item.code === "outline.self-intersection")).toBe(true);
    expect(issues.some((item) => item.code === "opening.wall-overflow")).toBe(true);
  });

  it("creates closed constant-offset wall pieces for an L-shaped exterior", () => {
    const set = generateDrawingSet({
      width: 10000,
      depth: 10000,
      outline: [{ x: 0, y: 0 }, { x: 10000, y: 0 }, { x: 10000, y: 4000 }, { x: 4000, y: 4000 }, { x: 4000, y: 10000 }, { x: 0, y: 10000 }],
      openings: [],
      interiorWalls: [],
      gridAxes: [],
      symbols: [],
      stairEnabled: false,
    });
    const walls = set.views[0].entities.filter((entity): entity is PolylineEntity => entity.type === "polyline" && entity.layer === "A-WALL");
    expect(set.metrics.footprintAreaM2).toBe(64);
    expect(walls).toHaveLength(6);
    expect(walls.every((wall) => wall.closed && wall.points.length === 4)).toBe(true);
  });

  it("cuts wall pieces and generates a door leaf whose end matches its swing arc", () => {
    const set = generateDrawingSet({
      openings: [{ kind: "door", wallIndex: 0, offset: 3000, width: 900, height: 2100, swing: "right", openingDirection: "in", label: "D-X" }],
      interiorWalls: [],
      gridAxes: [],
      symbols: [],
      stairEnabled: false,
    });
    const plan = set.views[0];
    const leaf = plan.entities.find((entity): entity is LineEntity => entity.type === "line" && entity.layer === "A-DOOR")!;
    const swing = plan.entities.find((entity): entity is ArcEntity => entity.type === "arc" && entity.layer === "A-DOOR")!;
    const arcEnds = [arcPoint(swing, swing.startAngle), arcPoint(swing, swing.endAngle)];
    expect(distance(leaf.start, leaf.end)).toBeCloseTo(900, 6);
    expect(arcEnds.some((point) => distance(point, leaf.end) < 1e-5)).toBe(true);
    const wallPieces = plan.entities.filter((entity) => entity.type === "polyline" && entity.layer === "A-WALL");
    expect(wallPieces.length).toBe(5);
  });

  it("honours stair direction, tread, landing, railing, and UP/DN annotations", () => {
    const set = generateDrawingSet({
      openings: [],
      interiorWalls: [],
      gridAxes: [],
      symbols: [],
      facadeFeatures: [],
      roomLabels: [],
      stair: { x: 1000, y: 1000, width: 1200, length: 3600, risers: 14, direction: "up-east", treadDepth: 250, landingDepth: 900, railing: "both", showDownArrow: true },
    });
    const stairEntities = set.views[0].entities.filter((entity) => entity.layer === "A-STRS");
    const outline = stairEntities.find((entity) => entity.type === "polyline" && entity.points.length === 4)!;
    const xs = outline.type === "polyline" ? outline.points.map((point) => point.x) : [];
    const ys = outline.type === "polyline" ? outline.points.map((point) => point.y) : [];
    expect(Math.max(...xs) - Math.min(...xs)).toBe(3600);
    expect(Math.max(...ys) - Math.min(...ys)).toBe(1200);
    expect(stairEntities.filter((entity) => entity.type === "line").length).toBeGreaterThan(10);
    expect(stairEntities.some((entity) => entity.type === "text" && entity.text === "UP")).toBe(true);
    expect(stairEntities.some((entity) => entity.type === "text" && entity.text === "DN")).toBe(true);
  });

  it("renders only configured attic windows, vents, louvers, and downspouts", () => {
    const empty = generateDrawingSet({ facadeFeatures: [] });
    expect(empty.views.slice(1, 5).flatMap((view) => view.entities).some((entity) => entity.layer === "A-VENT" || entity.layer === "A-DRAIN")).toBe(false);
    const configured = generateDrawingSet({
      facadeFeatures: [
        { kind: "attic-window", facade: "rear", offset: 3000, width: 900, height: 600, sill: 3500, label: "AW-X" },
        { kind: "louver", facade: "right", offset: 2500, width: 500, height: 350, sill: 3900 },
        { kind: "downspout", facade: "left", offset: 400 },
      ],
    });
    expect(configured.views.find((view) => view.id === "rear")?.entities.some((entity) => entity.type === "text" && entity.text === "AW-X")).toBe(true);
    expect(configured.views.find((view) => view.id === "right")?.entities.some((entity) => entity.layer === "A-VENT")).toBe(true);
    expect(configured.views.find((view) => view.id === "left")?.entities.some((entity) => entity.layer === "A-DRAIN")).toBe(true);
  });

  it("projects configured openings to elevations and the longitudinal section", () => {
    const set = generateDrawingSet({
      openings: [{ kind: "window", wallIndex: 1, offset: 1000, width: 1200, height: 1000, sill: 850, label: "WX" }],
    });
    expect(set.views.find((view) => view.id === "right")?.entities.some((entity) => entity.type === "text" && entity.text === "WX")).toBe(true);
    expect(set.views.find((view) => view.id === "section-b")?.entities.some((entity) => entity.type === "text" && entity.text === "WX")).toBe(true);
    expect(set.openingSchedule[0].width).toBe(1200);
  });
});
