import { BUILDING_SCHEMA_VERSION } from "./types";
import type {
  BuildingSpec,
  DrawingMetrics,
  DrawingSet,
  DrawingView,
  Entity,
  Facade,
  FacadeFeature,
  GridAxis,
  Opening,
  OpeningScheduleRow,
  Point,
  RoomLabel,
  Segment,
  StairSpec,
  SymbolItem,
  ValidationIssue,
} from "./types";

export const ENGINE_VERSION = "0.3.0";

const EPS = 1e-6;
const MAX_OUTLINE_POINTS = 64;
const MAX_INTERIOR_WALLS = 128;
const MAX_OPENINGS = 128;
const MAX_SYMBOLS = 256;
const COORDINATE_LIMIT = 100000;
const DEFAULT_GENERATED_AT = "1970-01-01T00:00:00.000Z";

const DEFAULT_OUTLINE = (width: number, depth: number): Point[] => [
  { x: 0, y: 0 },
  { x: width, y: 0 },
  { x: width, y: depth },
  { x: 0, y: depth },
];

const line = (start: Point, end: Point, layer = "A-WALL"): Entity => ({ type: "line", start, end, layer });
const poly = (points: Point[], closed = true, layer = "A-WALL"): Entity => ({ type: "polyline", points, closed, layer });
const arc = (center: Point, radius: number, startAngle: number, endAngle: number, layer = "A-DOOR"): Entity => ({
  type: "arc",
  center,
  radius,
  startAngle,
  endAngle,
  layer,
});
const circle = (center: Point, radius: number, layer = "A-ANNO"): Entity => ({ type: "circle", center, radius, layer });
const text = (at: Point, value: string, height = 180, layer = "A-TEXT", rotation = 0): Entity => ({
  type: "text",
  at,
  text: value,
  height,
  layer,
  rotation,
});

const rect = (x1: number, y1: number, x2: number, y2: number, layer = "A-WALL"): Entity =>
  poly([{ x: x1, y: y1 }, { x: x2, y: y1 }, { x: x2, y: y2 }, { x: x1, y: y2 }], true, layer);

const clamp = (value: number, min: number, max: number): number => Math.max(min, Math.min(max, value));
const round = (value: number, digits = 2): number => Number(value.toFixed(digits));
const samePoint = (a: Point, b: Point): boolean => Math.abs(a.x - b.x) < EPS && Math.abs(a.y - b.y) < EPS;

const normalizeOutline = (points: Point[]): Point[] => {
  const cleaned: Point[] = [];
  for (const point of points) {
    if (!cleaned.length || !samePoint(cleaned.at(-1)!, point)) cleaned.push({ x: Number(point.x), y: Number(point.y) });
  }
  if (cleaned.length > 1 && samePoint(cleaned[0], cleaned.at(-1)!)) cleaned.pop();
  return cleaned;
};

const polygonArea = (points: Point[]): number => {
  let area = 0;
  for (let i = 0; i < points.length; i += 1) {
    const a = points[i];
    const b = points[(i + 1) % points.length];
    area += a.x * b.y - b.x * a.y;
  }
  return Math.abs(area) / 2;
};

const polygonSignedArea = (points: Point[]): number => {
  let area = 0;
  for (let i = 0; i < points.length; i += 1) {
    const a = points[i];
    const b = points[(i + 1) % points.length];
    area += a.x * b.y - b.x * a.y;
  }
  return area / 2;
};

const polygonPerimeter = (points: Point[]): number => points.reduce((total, point, index) => {
  const next = points[(index + 1) % points.length];
  return total + Math.hypot(next.x - point.x, next.y - point.y);
}, 0);

const bounds = (points: Point[]): { minX: number; minY: number; maxX: number; maxY: number; width: number; height: number } => {
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const minX = Math.min(...xs);
  const minY = Math.min(...ys);
  const maxX = Math.max(...xs);
  const maxY = Math.max(...ys);
  return { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY };
};

const orientation = (a: Point, b: Point, c: Point): number => {
  const value = (b.y - a.y) * (c.x - b.x) - (b.x - a.x) * (c.y - b.y);
  if (Math.abs(value) < EPS) return 0;
  return value > 0 ? 1 : 2;
};

const onSegment = (a: Point, b: Point, c: Point): boolean =>
  b.x <= Math.max(a.x, c.x) + EPS && b.x + EPS >= Math.min(a.x, c.x) &&
  b.y <= Math.max(a.y, c.y) + EPS && b.y + EPS >= Math.min(a.y, c.y);

const segmentsIntersect = (p1: Point, q1: Point, p2: Point, q2: Point): boolean => {
  const o1 = orientation(p1, q1, p2);
  const o2 = orientation(p1, q1, q2);
  const o3 = orientation(p2, q2, p1);
  const o4 = orientation(p2, q2, q1);
  if (o1 !== o2 && o3 !== o4) return true;
  return (o1 === 0 && onSegment(p1, p2, q1)) || (o2 === 0 && onSegment(p1, q2, q1)) ||
    (o3 === 0 && onSegment(p2, p1, q2)) || (o4 === 0 && onSegment(p2, q1, q2));
};

const isSelfIntersecting = (points: Point[]): boolean => {
  for (let i = 0; i < points.length; i += 1) {
    const a1 = points[i];
    const a2 = points[(i + 1) % points.length];
    for (let j = i + 1; j < points.length; j += 1) {
      if (Math.abs(i - j) <= 1 || (i === 0 && j === points.length - 1)) continue;
      const b1 = points[j];
      const b2 = points[(j + 1) % points.length];
      if (segmentsIntersect(a1, a2, b1, b2)) return true;
    }
  }
  return false;
};

const wallLength = (outline: Point[], wallIndex: number): number => {
  if (!outline.length || wallIndex < 0 || wallIndex >= outline.length) return 0;
  const a = outline[wallIndex];
  const b = outline[(wallIndex + 1) % outline.length];
  return Math.hypot(b.x - a.x, b.y - a.y);
};

const pointOnWall = (outline: Point[], wallIndex: number, offset: number): { point: Point; angle: number; length: number } => {
  const index = ((wallIndex % outline.length) + outline.length) % outline.length;
  const a = outline[index];
  const b = outline[(index + 1) % outline.length];
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const length = Math.hypot(dx, dy);
  const t = clamp(offset / Math.max(length, 1), 0, 1);
  return { point: { x: a.x + dx * t, y: a.y + dy * t }, angle: Math.atan2(dy, dx), length };
};

const lineIntersection = (a: Point, directionA: Point, b: Point, directionB: Point): Point | null => {
  const cross = directionA.x * directionB.y - directionA.y * directionB.x;
  if (Math.abs(cross) < EPS) return null;
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const t = (dx * directionB.y - dy * directionB.x) / cross;
  return { x: a.x + directionA.x * t, y: a.y + directionA.y * t };
};

/** Parallel polygon offset used for both orthogonal and diagonal wall segments. */
const insetOutline = (points: Point[], thickness: number): Point[] => {
  if (points.length < 3) return points.map((point) => ({ ...point }));
  const ccw = polygonSignedArea(points) > 0;
  const edges = points.map((point, index) => {
    const next = points[(index + 1) % points.length];
    const dx = next.x - point.x;
    const dy = next.y - point.y;
    const length = Math.hypot(dx, dy) || 1;
    const direction = { x: dx / length, y: dy / length };
    const normal = ccw ? { x: -direction.y, y: direction.x } : { x: direction.y, y: -direction.x };
    return { direction, normal };
  });
  return points.map((point, index) => {
    const previous = edges[(index - 1 + edges.length) % edges.length];
    const current = edges[index];
    const previousPoint = { x: point.x + previous.normal.x * thickness, y: point.y + previous.normal.y * thickness };
    const currentPoint = { x: point.x + current.normal.x * thickness, y: point.y + current.normal.y * thickness };
    const intersection = lineIntersection(previousPoint, previous.direction, currentPoint, current.direction);
    if (intersection && Math.hypot(intersection.x - point.x, intersection.y - point.y) <= thickness * 8) return intersection;
    const average = { x: previous.normal.x + current.normal.x, y: previous.normal.y + current.normal.y };
    const length = Math.hypot(average.x, average.y) || 1;
    return { x: point.x + average.x / length * thickness, y: point.y + average.y / length * thickness };
  });
};

const thickSegment = (segment: Segment, defaultThickness: number): Entity => {
  const thickness = segment.thickness ?? defaultThickness;
  const dx = segment.end.x - segment.start.x;
  const dy = segment.end.y - segment.start.y;
  const length = Math.hypot(dx, dy) || 1;
  const nx = (-dy / length) * thickness / 2;
  const ny = (dx / length) * thickness / 2;
  return poly([
    { x: segment.start.x + nx, y: segment.start.y + ny },
    { x: segment.end.x + nx, y: segment.end.y + ny },
    { x: segment.end.x - nx, y: segment.end.y - ny },
    { x: segment.start.x - nx, y: segment.start.y - ny },
  ], true, segment.layer ?? "A-WALL");
};

const dimHorizontal = (entities: Entity[], x1: number, x2: number, y: number, value: string): void => {
  const tick = 120;
  entities.push(line({ x: x1, y: y - tick }, { x: x1, y: y + tick }, "A-DIMS"));
  entities.push(line({ x: x2, y: y - tick }, { x: x2, y: y + tick }, "A-DIMS"));
  entities.push(line({ x: x1, y }, { x: x2, y }, "A-DIMS"));
  entities.push(line({ x: x1, y }, { x: x1 + 100, y: y + 45 }, "A-DIMS"));
  entities.push(line({ x: x2, y }, { x: x2 - 100, y: y + 45 }, "A-DIMS"));
  entities.push(text({ x: (x1 + x2) / 2 - value.length * 40, y: y + 100 }, value, 140, "A-DIMS"));
};

const dimVertical = (entities: Entity[], y1: number, y2: number, x: number, value: string): void => {
  const tick = 120;
  entities.push(line({ x: x - tick, y: y1 }, { x: x + tick, y: y1 }, "A-DIMS"));
  entities.push(line({ x: x - tick, y: y2 }, { x: x + tick, y: y2 }, "A-DIMS"));
  entities.push(line({ x, y: y1 }, { x, y: y2 }, "A-DIMS"));
  entities.push(line({ x, y: y1 }, { x: x + 45, y: y1 + 100 }, "A-DIMS"));
  entities.push(line({ x, y: y2 }, { x: x + 45, y: y2 - 100 }, "A-DIMS"));
  entities.push(text({ x: x + 100, y: (y1 + y2) / 2 - value.length * 35 }, value, 140, "A-DIMS", 90));
};

const levelMarker = (entities: Entity[], x: number, y: number, label: string): void => {
  entities.push(poly([{ x, y }, { x: x + 130, y: y + 70 }, { x: x + 130, y: y - 70 }], true, "A-LEVEL"));
  entities.push(line({ x: x + 130, y }, { x: x + 650, y }, "A-LEVEL"));
  entities.push(text({ x: x + 180, y: y + 80 }, label, 130, "A-LEVEL"));
};

const sectionMarker = (entities: Entity[], start: Point, end: Point, label: string): void => {
  entities.push(line(start, end, "A-SECT"));
  entities.push(circle(start, 180, "A-SECT"));
  entities.push(circle(end, 180, "A-SECT"));
  entities.push(text({ x: start.x - 80, y: start.y - 55 }, label, 120, "A-SECT"));
  entities.push(text({ x: end.x - 80, y: end.y - 55 }, label, 120, "A-SECT"));
};

const defaultInteriorWalls = (width: number, depth: number, minX = 0, minY = 0): Segment[] => [
  { start: { x: minX + width * 0.34, y: minY }, end: { x: minX + width * 0.34, y: minY + depth * 0.58 } },
  { start: { x: minX + width * 0.34, y: minY + depth * 0.58 }, end: { x: minX + width, y: minY + depth * 0.58 } },
  { start: { x: minX + width * 0.68, y: minY + depth * 0.58 }, end: { x: minX + width * 0.68, y: minY + depth } },
];

const defaultOpenings = (width: number, depth: number): Opening[] => [
  { kind: "door", wallIndex: 0, offset: width * 0.44, width: 1800, height: 2400, swing: "double", label: "D1" },
  { kind: "window", wallIndex: 0, offset: width * 0.12, width: 1500, height: 1200, sill: 900, label: "W1" },
  { kind: "window", wallIndex: 0, offset: width * 0.74, width: 1500, height: 1200, sill: 900, label: "W1" },
  { kind: "window", wallIndex: 1, offset: depth * 0.25, width: 1200, height: 1200, sill: 900, label: "W2" },
  { kind: "door", wallIndex: 2, offset: width * 0.08, width: 900, height: 2100, swing: "right", label: "D2" },
  { kind: "window", wallIndex: 2, offset: width * 0.35, width: 1500, height: 1200, sill: 900, label: "W1" },
  { kind: "window", wallIndex: 3, offset: depth * 0.28, width: 1200, height: 1200, sill: 900, label: "W2" },
];

const defaultStair = (width: number, depth: number, minX = 0, minY = 0): StairSpec => ({
  x: minX + width * 0.39,
  y: minY + depth * 0.28,
  width: Math.min(3000, width * 0.26),
  length: Math.min(3600, depth * 0.3),
  risers: 14,
  direction: "up-north",
  treadDepth: 250,
  landingDepth: Math.min(1000, depth * 0.09),
  railing: "both",
});

const defaultWallIds = (count: number): string[] => Array.from({ length: count }, (_, index) => `WALL-${String(index + 1).padStart(3, "0")}`);

const defaultGridAxes = (b: ReturnType<typeof bounds>): GridAxis[] => [
  { id: "1", start: { x: b.minX + b.width * 0.25, y: b.minY - 450 }, end: { x: b.minX + b.width * 0.25, y: b.maxY + 450 } },
  { id: "2", start: { x: b.minX + b.width * 0.75, y: b.minY - 450 }, end: { x: b.minX + b.width * 0.75, y: b.maxY + 450 } },
  { id: "A", start: { x: b.minX - 450, y: b.minY + b.height * 0.25 }, end: { x: b.maxX + 450, y: b.minY + b.height * 0.25 } },
  { id: "B", start: { x: b.minX - 450, y: b.minY + b.height * 0.75 }, end: { x: b.maxX + 450, y: b.minY + b.height * 0.75 } },
];

const defaultRoomLabels = (b: ReturnType<typeof bounds>): RoomLabel[] => [
  { name: "LOBBY", at: { x: b.minX + b.width * 0.44, y: b.minY + b.height * 0.22 } },
  { name: "ROOM 1", at: { x: b.minX + b.width * 0.08, y: b.minY + b.height * 0.78 } },
  { name: "ROOM 2", at: { x: b.minX + b.width * 0.46, y: b.minY + b.height * 0.78 } },
  { name: "SERVICE", at: { x: b.minX + b.width * 0.76, y: b.minY + b.height * 0.78 } },
];

const defaultSymbols = (b: ReturnType<typeof bounds>): SymbolItem[] => [
  { id: "C1", kind: "column", at: { x: b.minX + b.width * 0.08, y: b.minY + b.height * 0.08 }, width: 300, depth: 300 },
  { id: "C2", kind: "column", at: { x: b.maxX - b.width * 0.08, y: b.minY + b.height * 0.08 }, width: 300, depth: 300 },
  { kind: "sink", at: { x: b.minX + b.width * 0.82, y: b.minY + b.height * 0.72 }, width: 700, depth: 500 },
  { kind: "toilet", at: { x: b.minX + b.width * 0.86, y: b.minY + b.height * 0.82 }, width: 420, depth: 680 },
  { kind: "cabinet", at: { x: b.minX + b.width * 0.72, y: b.minY + b.height * 0.64 }, width: b.width * 0.2, depth: 600 },
];

const defaultFacadeFeatures = (spec: BuildingSpec): FacadeFeature[] => [
  { id: "AW-1", kind: "attic-window", facade: "front", offset: spec.width / 2 - 500, width: 1000, height: 700, sill: spec.atticFloorHeight + 450, label: "AW1" },
  { id: "V-1", kind: "vent", facade: "front", offset: spec.width / 2 - 140, width: 280, height: 220, sill: spec.ridgeHeight - 520 },
  { id: "DS-1", kind: "downspout", facade: "front", offset: 190 },
  { id: "DS-2", kind: "downspout", facade: "front", offset: spec.width - 190 },
];

const wallIndexForOpening = (opening: Opening, wallIds: string[], count: number): number => {
  if (opening.wallId) return wallIds.indexOf(opening.wallId);
  return Number.isInteger(opening.wallIndex) && opening.wallIndex! >= 0 && opening.wallIndex! < count ? opening.wallIndex! : -1;
};

const wallInteriorNormal = (outline: Point[], angle: number): Point => {
  const sign = polygonSignedArea(outline) >= 0 ? 1 : -1;
  return { x: -Math.sin(angle) * sign, y: Math.cos(angle) * sign };
};

const lerpPoint = (a: Point, b: Point, t: number): Point => ({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t });

const exteriorWallEntities = (outline: Point[], thickness: number, openings: Opening[], wallIds: string[]): Entity[] => {
  const inner = insetOutline(outline, thickness);
  const entities: Entity[] = [];
  for (let wallIndex = 0; wallIndex < outline.length; wallIndex += 1) {
    const a = outline[wallIndex];
    const b = outline[(wallIndex + 1) % outline.length];
    const ia = inner[wallIndex];
    const ib = inner[(wallIndex + 1) % inner.length];
    const length = Math.hypot(b.x - a.x, b.y - a.y);
    if (length <= EPS) continue;
    const intervals = openings
      .filter((opening) => opening.placement !== "attic" && wallIndexForOpening(opening, wallIds, outline.length) === wallIndex)
      .map((opening) => ({ start: clamp(opening.offset, 0, length), end: clamp(opening.offset + opening.width, 0, length) }))
      .filter((interval) => interval.end - interval.start > EPS)
      .sort((first, second) => first.start - second.start);
    const merged: Array<{ start: number; end: number }> = [];
    for (const interval of intervals) {
      const previous = merged.at(-1);
      if (previous && interval.start <= previous.end + EPS) previous.end = Math.max(previous.end, interval.end);
      else merged.push({ ...interval });
    }
    let cursor = 0;
    const addPiece = (start: number, end: number): void => {
      if (end - start <= EPS) return;
      const t0 = start / length;
      const t1 = end / length;
      entities.push(poly([lerpPoint(a, b, t0), lerpPoint(a, b, t1), lerpPoint(ia, ib, t1), lerpPoint(ia, ib, t0)], true, "A-WALL"));
    };
    for (const interval of merged) {
      addPiece(cursor, interval.start);
      cursor = Math.max(cursor, interval.end);
    }
    addPiece(cursor, length);
  }
  return entities;
};

const normalizedAngle = (value: number): number => ((value % 360) + 360) % 360;

const shortArc = (center: Point, radius: number, firstAngle: number, secondAngle: number): Entity => {
  const first = normalizedAngle(firstAngle);
  const second = normalizedAngle(secondAngle);
  const delta = normalizedAngle(second - first);
  return delta <= 180 ? arc(center, radius, first, second, "A-DOOR") : arc(center, radius, second, first, "A-DOOR");
};

const addOpeningPlan = (entities: Entity[], outline: Point[], opening: Opening, wallThickness: number, wallIds: string[]): void => {
  if (opening.placement === "attic") return;
  const wallIndex = wallIndexForOpening(opening, wallIds, outline.length);
  if (wallIndex < 0) return;
  const start = pointOnWall(outline, wallIndex, opening.offset);
  const end = pointOnWall(outline, wallIndex, opening.offset + opening.width);
  const inward = wallInteriorNormal(outline, start.angle);
  const directionSign = opening.openingDirection === "out" ? -1 : 1;
  const nx = inward.x * directionSign;
  const ny = inward.y * directionSign;
  const wallNormal = wallInteriorNormal(outline, start.angle);
  entities.push(line(start.point, { x: start.point.x + wallNormal.x * wallThickness, y: start.point.y + wallNormal.y * wallThickness }, "A-OPEN"));
  entities.push(line(end.point, { x: end.point.x + wallNormal.x * wallThickness, y: end.point.y + wallNormal.y * wallThickness }, "A-OPEN"));
  if (opening.kind === "door") {
    const wallAngle = (start.angle * 180) / Math.PI;
    const openAngle = Math.atan2(ny, nx) * 180 / Math.PI;
    if (opening.swing === "double") {
      const half = opening.width / 2;
      const mid = pointOnWall(outline, wallIndex, opening.offset + half).point;
      entities.push(line(start.point, { x: start.point.x + nx * half, y: start.point.y + ny * half }, "A-DOOR"));
      entities.push(shortArc(start.point, half, wallAngle, openAngle));
      entities.push(line(end.point, { x: end.point.x + nx * half, y: end.point.y + ny * half }, "A-DOOR"));
      entities.push(shortArc(end.point, half, wallAngle + 180, openAngle));
      entities.push(circle(mid, 35, "A-DOOR"));
    } else {
      const hingeAtEnd = opening.swing === "left";
      const hinge = hingeAtEnd ? end.point : start.point;
      const leafEnd = {
        x: hinge.x + nx * opening.width,
        y: hinge.y + ny * opening.width,
      };
      entities.push(line(hinge, leafEnd, "A-DOOR"));
      entities.push(shortArc(hinge, opening.width, wallAngle + (hingeAtEnd ? 180 : 0), openAngle));
    }
  } else {
    const firstDepth = wallThickness * 0.3;
    const secondDepth = wallThickness * 0.7;
    entities.push(line({ x: start.point.x + wallNormal.x * firstDepth, y: start.point.y + wallNormal.y * firstDepth }, { x: end.point.x + wallNormal.x * firstDepth, y: end.point.y + wallNormal.y * firstDepth }, "A-WIND"));
    entities.push(line({ x: start.point.x + wallNormal.x * secondDepth, y: start.point.y + wallNormal.y * secondDepth }, { x: end.point.x + wallNormal.x * secondDepth, y: end.point.y + wallNormal.y * secondDepth }, "A-WIND"));
    const mid = pointOnWall(outline, wallIndex, opening.offset + opening.width / 2).point;
    entities.push(line({ x: mid.x, y: mid.y }, { x: mid.x + wallNormal.x * wallThickness, y: mid.y + wallNormal.y * wallThickness }, "A-WIND"));
  }
  if (opening.label) entities.push(text({ x: (start.point.x + end.point.x) / 2 + wallNormal.x * (wallThickness + 120), y: (start.point.y + end.point.y) / 2 + wallNormal.y * (wallThickness + 120) }, opening.label, 120, "A-TEXT"));
};

const addStairPlan = (entities: Entity[], stair: StairSpec): void => {
  const { x, y, width, length, risers } = stair;
  const map = (u: number, v: number): Point => {
    if (stair.direction === "up-south") return { x: x + width - u, y: y + length - v };
    if (stair.direction === "up-east") return { x: x + v, y: y + u };
    if (stair.direction === "up-west") return { x: x + length - v, y: y + width - u };
    return { x: x + u, y: y + v };
  };
  const landingDepth = clamp(stair.landingDepth ?? Math.max(750, length * 0.18), 300, Math.max(300, length * 0.4));
  const flightLength = Math.max(length - landingDepth, length * 0.5);
  const treadDepth = clamp(stair.treadDepth ?? flightLength / Math.max(risers, 1), 120, 450);
  entities.push(poly([map(0, 0), map(width, 0), map(width, length), map(0, length)], true, "A-STRS"));
  const treadCount = Math.max(1, Math.min(risers - 1, Math.floor(flightLength / treadDepth)));
  for (let index = 1; index <= treadCount; index += 1) {
    const v = Math.min(flightLength, index * flightLength / (treadCount + 1));
    entities.push(line(map(0, v), map(width, v), "A-STRS"));
  }
  entities.push(line(map(0, flightLength), map(width, flightLength), "A-STRS"));
  const railing = stair.railing ?? "both";
  if (railing === "left" || railing === "both") entities.push(line(map(90, 0), map(90, length), "A-STRS"));
  if (railing === "right" || railing === "both") entities.push(line(map(width - 90, 0), map(width - 90, length), "A-STRS"));
  const arrowStart = map(width / 2, Math.min(250, flightLength * 0.2));
  const arrowEnd = map(width / 2, flightLength * 0.82);
  const beforeEnd = map(width / 2, Math.max(0, flightLength * 0.82 - 170));
  const tangent = { x: arrowEnd.x - beforeEnd.x, y: arrowEnd.y - beforeEnd.y };
  const tangentLength = Math.hypot(tangent.x, tangent.y) || 1;
  const unit = { x: tangent.x / tangentLength, y: tangent.y / tangentLength };
  const side = { x: -unit.y, y: unit.x };
  entities.push(line(arrowStart, arrowEnd, "A-STRS"));
  entities.push(poly([
    arrowEnd,
    { x: arrowEnd.x - unit.x * 170 + side.x * 85, y: arrowEnd.y - unit.y * 170 + side.y * 85 },
    { x: arrowEnd.x - unit.x * 170 - side.x * 85, y: arrowEnd.y - unit.y * 170 - side.y * 85 },
  ], true, "A-STRS"));
  const upLabel = map(width * 0.1, Math.min(180, flightLength * 0.15));
  entities.push(text(upLabel, "UP", 130, "A-STRS"));
  if (stair.showDownArrow) entities.push(text(map(width * 0.1, length - 180), "DN", 130, "A-STRS"));
};

const addFurniturePlan = (entities: Entity[], width: number, depth: number, minX = 0, minY = 0): void => {
  const tableX = minX + width * 0.08;
  const tableY = minY + depth * 0.72;
  entities.push(rect(tableX, tableY, tableX + 1700, tableY + 800, "A-FURN"));
  for (const cx of [tableX + 280, tableX + 850, tableX + 1420]) {
    entities.push(rect(cx - 150, tableY - 350, cx + 150, tableY - 80, "A-FURN"));
    entities.push(rect(cx - 150, tableY + 880, cx + 150, tableY + 1150, "A-FURN"));
  }
  const roundX = minX + width * 0.14;
  const roundY = minY + depth * 0.18;
  entities.push(circle({ x: roundX, y: roundY }, 420, "A-FURN"));
  for (let index = 0; index < 4; index += 1) {
    const angle = (Math.PI / 2) * index;
    const cx = roundX + Math.cos(angle) * 700;
    const cy = roundY + Math.sin(angle) * 700;
    entities.push(rect(cx - 130, cy - 110, cx + 130, cy + 110, "A-FURN"));
  }
};

const addGridAxes = (entities: Entity[], axes: GridAxis[]): void => {
  for (const axis of axes) {
    entities.push(line(axis.start, axis.end, "A-GRID"));
    entities.push(circle(axis.start, 140, "A-GRID"));
    entities.push(circle(axis.end, 140, "A-GRID"));
    entities.push(text({ x: axis.start.x - 45, y: axis.start.y - 45 }, axis.id, 100, "A-GRID"));
    entities.push(text({ x: axis.end.x - 45, y: axis.end.y - 45 }, axis.id, 100, "A-GRID"));
  }
};

const addSymbolsPlan = (entities: Entity[], symbols: SymbolItem[]): void => {
  for (const symbol of symbols) {
    const width = symbol.width ?? 500;
    const depth = symbol.depth ?? 500;
    const x1 = symbol.at.x - width / 2;
    const y1 = symbol.at.y - depth / 2;
    const x2 = symbol.at.x + width / 2;
    const y2 = symbol.at.y + depth / 2;
    if (symbol.kind === "column") {
      entities.push(rect(x1, y1, x2, y2, "A-COLS"));
      entities.push(line({ x: x1, y: y1 }, { x: x2, y: y2 }, "A-COLS"));
      entities.push(line({ x: x1, y: y2 }, { x: x2, y: y1 }, "A-COLS"));
    } else if (symbol.kind === "toilet") {
      entities.push(rect(x1, y1, x2, y1 + depth * 0.3, "A-FIXT"));
      entities.push(circle({ x: symbol.at.x, y: y1 + depth * 0.65 }, Math.min(width, depth) * 0.3, "A-FIXT"));
    } else if (symbol.kind === "sink") {
      entities.push(rect(x1, y1, x2, y2, "A-FIXT"));
      entities.push(circle(symbol.at, Math.min(width, depth) * 0.18, "A-FIXT"));
    } else if (symbol.kind === "tub" || symbol.kind === "cabinet" || symbol.kind === "table") {
      entities.push(rect(x1, y1, x2, y2, symbol.kind === "cabinet" ? "A-FURN" : "A-FIXT"));
    } else if (symbol.kind === "chair") {
      entities.push(circle(symbol.at, Math.min(width, depth) / 2, "A-FURN"));
    }
    if (symbol.label || symbol.kind === "label") entities.push(text({ x: x1, y: y2 + 100 }, symbol.label ?? symbol.id ?? "", 110, "A-TEXT", symbol.rotation ?? 0));
  }
};

const planView = (spec: BuildingSpec): DrawingView => {
  const outline = normalizeOutline(spec.outline?.length ? spec.outline : DEFAULT_OUTLINE(spec.width, spec.depth));
  const b = bounds(outline);
  const wallIds = spec.wallIds?.length === outline.length ? spec.wallIds : defaultWallIds(outline.length);
  const openings = spec.openings ?? defaultOpenings(spec.width, spec.depth);
  const entities: Entity[] = [];
  addGridAxes(entities, spec.gridAxes ?? defaultGridAxes(b));
  entities.push(...exteriorWallEntities(outline, spec.wallThickness, openings, wallIds));
  const walls = spec.interiorWalls ?? defaultInteriorWalls(b.width, b.height, b.minX, b.minY);
  for (const wall of walls) entities.push(thickSegment(wall, spec.wallThickness));
  for (const opening of openings) addOpeningPlan(entities, outline, opening, spec.wallThickness, wallIds);
  if (spec.stairEnabled !== false) addStairPlan(entities, spec.stair ?? defaultStair(b.width, b.height, b.minX, b.minY));
  addFurniturePlan(entities, b.width, b.height, b.minX, b.minY);
  addSymbolsPlan(entities, spec.symbols ?? defaultSymbols(b));

  for (const room of spec.roomLabels ?? defaultRoomLabels(b)) {
    if (room.polygon && room.polygon.length >= 3) entities.push(poly(room.polygon, true, "A-HIDD"));
    entities.push(text(room.at, room.name, 180));
  }

  dimHorizontal(entities, b.minX, b.maxX, b.minY - 700, `${Math.round(b.width)}`);
  dimVertical(entities, b.minY, b.maxY, b.minX - 700, `${Math.round(b.height)}`);
  const sectionCuts = spec.sectionCuts ?? [
    { id: "A", start: { x: b.minX + b.width * 0.5, y: b.minY - 180 }, end: { x: b.minX + b.width * 0.5, y: b.maxY + 180 } },
    { id: "B", start: { x: b.minX - 180, y: b.minY + b.height * 0.5 }, end: { x: b.maxX + 180, y: b.minY + b.height * 0.5 } },
  ];
  for (const cut of sectionCuts) sectionMarker(entities, cut.start, cut.end, cut.id);

  const northX = b.maxX - 600;
  const northY = b.minY + 900;
  entities.push(circle({ x: northX, y: northY }, 260, "A-ANNO"));
  entities.push(line({ x: northX, y: northY - 180 }, { x: northX, y: northY + 480 }, "A-ANNO"));
  entities.push(poly([{ x: northX, y: northY + 480 }, { x: northX - 130, y: northY + 250 }, { x: northX + 130, y: northY + 250 }], true, "A-ANNO"));
  entities.push(text({ x: northX - 65, y: northY + 600 }, "N", 170, "A-ANNO"));

  return { id: "plan", title: "1F PLAN", width: b.width, height: b.height, entities };
};

const facadeWallIndex = (facade: Facade): number => ({ front: 0, right: 1, rear: 2, left: 3 })[facade];
const facadeLength = (spec: BuildingSpec, facade: Facade): number => facade === "front" || facade === "rear" ? spec.width : spec.depth;
const facadeIsGable = (spec: BuildingSpec, facade: Facade): boolean =>
  spec.roofDirection === "ridge-along-depth" ? facade === "front" || facade === "rear" : facade === "left" || facade === "right";

const openingElevationX = (opening: Opening, length: number): number =>
  opening.wallIndex === 2 || opening.wallIndex === 3 ? length - opening.offset - opening.width : opening.offset;

const addElevationOpening = (entities: Entity[], opening: Opening, length: number): void => {
  const x = openingElevationX(opening, length);
  if (opening.kind === "door") {
    entities.push(rect(x, 0, x + opening.width, opening.height, "A-DOOR"));
    if (opening.swing === "double") entities.push(line({ x: x + opening.width / 2, y: 0 }, { x: x + opening.width / 2, y: opening.height }, "A-DOOR"));
    entities.push(line({ x: x + 90, y: 260 }, { x: x + opening.width - 90, y: 260 }, "A-DOOR"));
  } else {
    const sill = opening.sill ?? 900;
    entities.push(rect(x, sill, x + opening.width, sill + opening.height, "A-WIND"));
    entities.push(rect(x + 65, sill + 65, x + opening.width - 65, sill + opening.height - 65, "A-GLAZ"));
    entities.push(line({ x: x + opening.width / 2, y: sill + 65 }, { x: x + opening.width / 2, y: sill + opening.height - 65 }, "A-GLAZ"));
    entities.push(line({ x: x + 65, y: sill + opening.height / 2 }, { x: x + opening.width - 65, y: sill + opening.height / 2 }, "A-GLAZ"));
    entities.push(line({ x: x - 80, y: sill - 60 }, { x: x + opening.width + 80, y: sill - 60 }, "A-WIND"));
  }
  if (opening.label) entities.push(text({ x: x + opening.width / 2 - 90, y: opening.kind === "door" ? opening.height + 140 : (opening.sill ?? 900) + opening.height + 140 }, opening.label, 120));
};

const addFacadeFeature = (entities: Entity[], feature: FacadeFeature, spec: BuildingSpec): void => {
  const width = feature.width ?? (feature.kind === "attic-window" ? 1000 : 280);
  const height = feature.height ?? (feature.kind === "attic-window" ? 700 : 220);
  const sill = feature.sill ?? (feature.kind === "attic-window" ? spec.atticFloorHeight + 450 : spec.ridgeHeight - 520);
  if (feature.kind === "downspout") {
    entities.push(line({ x: feature.offset, y: spec.eaveHeight - 40 }, { x: feature.offset, y: 220 }, "A-DRAIN"));
    return;
  }
  const layer = feature.kind === "attic-window" ? "A-WIND" : "A-VENT";
  entities.push(rect(feature.offset, sill, feature.offset + width, sill + height, layer));
  if (feature.kind === "attic-window") {
    entities.push(line({ x: feature.offset + width / 2, y: sill }, { x: feature.offset + width / 2, y: sill + height }, "A-GLAZ"));
  } else {
    const divisions = Math.max(2, Math.floor(height / 70));
    for (let index = 1; index < divisions; index += 1) {
      const y = sill + height * index / divisions;
      entities.push(line({ x: feature.offset, y }, { x: feature.offset + width, y }, "A-VENT"));
    }
  }
  if (feature.label) entities.push(text({ x: feature.offset, y: sill + height + 130 }, feature.label, 110, "A-TEXT"));
};

const addWallFinishPattern = (entities: Entity[], width: number, eaveHeight: number): void => {
  for (let y = 550; y < eaveHeight - 100; y += 260) entities.push(line({ x: 40, y }, { x: width - 40, y }, "A-MATL"));
  entities.push(rect(0, 0, width, 450, "A-PLIN"));
  for (let x = 120; x < width; x += 300) entities.push(line({ x, y: 0 }, { x: Math.max(0, x - 250), y: 450 }, "A-PLIN"));
};

const addRoofFinishPattern = (entities: Entity[], width: number, spec: BuildingSpec, gable: boolean): void => {
  if (gable) {
    for (let ratio = 0.08; ratio < 0.92; ratio += 0.08) {
      const x = width * ratio;
      const y = ratio <= 0.5
        ? spec.eaveHeight + (spec.ridgeHeight - spec.eaveHeight) * (ratio / 0.5)
        : spec.ridgeHeight - (spec.ridgeHeight - spec.eaveHeight) * ((ratio - 0.5) / 0.5);
      entities.push(line({ x, y: y - 140 }, { x, y: y + 30 }, "A-ROOF"));
    }
  } else {
    for (let x = 450; x < width; x += 650) entities.push(line({ x, y: spec.eaveHeight + 120 }, { x, y: spec.ridgeHeight - 100 }, "A-ROOF"));
  }
};

const elevationView = (spec: BuildingSpec, facade: Facade, title: string): DrawingView => {
  const width = facadeLength(spec, facade);
  const gable = facadeIsGable(spec, facade);
  const entities: Entity[] = [];
  if (gable) {
    entities.push(poly([
      { x: 0, y: 0 },
      { x: 0, y: spec.eaveHeight },
      { x: width / 2, y: spec.ridgeHeight },
      { x: width, y: spec.eaveHeight },
      { x: width, y: 0 },
    ], true, "A-ELEV"));
    entities.push(line({ x: -spec.roofOverhang, y: spec.eaveHeight - 70 }, { x: 140, y: spec.eaveHeight - 70 }, "A-ROOF"));
    entities.push(line({ x: width - 140, y: spec.eaveHeight - 70 }, { x: width + spec.roofOverhang, y: spec.eaveHeight - 70 }, "A-ROOF"));
  } else {
    entities.push(rect(0, 0, width, spec.eaveHeight, "A-ELEV"));
    entities.push(line({ x: -spec.roofOverhang, y: spec.eaveHeight - 70 }, { x: width + spec.roofOverhang, y: spec.eaveHeight - 70 }, "A-ROOF"));
    entities.push(line({ x: width * 0.08, y: spec.ridgeHeight }, { x: width * 0.92, y: spec.ridgeHeight }, "A-ROOF"));
    entities.push(line({ x: width * 0.08, y: spec.ridgeHeight }, { x: 0, y: spec.eaveHeight }, "A-ROOF"));
    entities.push(line({ x: width * 0.92, y: spec.ridgeHeight }, { x: width, y: spec.eaveHeight }, "A-ROOF"));
  }

  addWallFinishPattern(entities, width, spec.eaveHeight);
  addRoofFinishPattern(entities, width, spec, gable);
  const wallIndex = facadeWallIndex(facade);
  const outline = normalizeOutline(spec.outline?.length ? spec.outline : DEFAULT_OUTLINE(spec.width, spec.depth));
  const wallIds = spec.wallIds?.length === outline.length ? spec.wallIds : defaultWallIds(outline.length);
  const openings = spec.openings ?? defaultOpenings(spec.width, spec.depth);
  for (const opening of openings.filter((item) => wallIndexForOpening(item, wallIds, outline.length) === wallIndex)) addElevationOpening(entities, opening, wallLength(outline, wallIndex) || width);
  for (const feature of (spec.facadeFeatures ?? defaultFacadeFeatures(spec)).filter((item) => item.facade === facade)) addFacadeFeature(entities, feature, spec);

  entities.push(line({ x: 0, y: spec.atticFloorHeight }, { x: width, y: spec.atticFloorHeight }, "A-HIDD"));
  entities.push(line({ x: -500, y: 0 }, { x: width + 500, y: 0 }, "A-GRID"));
  levelMarker(entities, width + 250, 0, "±0");
  levelMarker(entities, width + 250, spec.atticFloorHeight, `ATTIC ${spec.atticFloorHeight}`);
  levelMarker(entities, width + 250, spec.eaveHeight, `EAVE ${spec.eaveHeight}`);
  levelMarker(entities, width + 250, spec.ridgeHeight, `RIDGE ${spec.ridgeHeight}`);
  dimHorizontal(entities, 0, width, -650, `${Math.round(width)}`);
  dimVertical(entities, 0, spec.eaveHeight, -700, `${Math.round(spec.eaveHeight)}`);
  dimVertical(entities, 0, spec.ridgeHeight, -1300, `${Math.round(spec.ridgeHeight)}`);
  entities.push(text({ x: width * 0.03, y: spec.ridgeHeight + 380 }, `ROOF: ${spec.roofFinish}`, 130, "A-NOTE"));
  entities.push(text({ x: width * 0.03, y: spec.ridgeHeight + 150 }, `WALL: ${spec.wallFinish}`, 130, "A-NOTE"));

  return { id: facade, title, width, height: spec.ridgeHeight + 500, entities };
};

const addFoundation = (entities: Entity[], width: number, spec: BuildingSpec): void => {
  entities.push(rect(0, -spec.floorSlabThickness, width, 0, "A-CUT"));
  entities.push(rect(-120, -spec.foundationDepth, spec.wallThickness + 220, 0, "A-CUT"));
  entities.push(rect(width - spec.wallThickness - 220, -spec.foundationDepth, width + 120, 0, "A-CUT"));
  for (let x = 80; x < width; x += 280) entities.push(line({ x, y: -spec.floorSlabThickness + 20 }, { x: Math.max(0, x - 180), y: -20 }, "A-HATCH"));
};

const addFoldDownLadder = (entities: Entity[], x: number, floorY: number): void => {
  entities.push(line({ x, y: 0 }, { x: x - 500, y: floorY - 100 }, "A-STRS"));
  entities.push(line({ x: x + 340, y: 0 }, { x: x - 160, y: floorY - 100 }, "A-STRS"));
  for (let i = 1; i < 7; i += 1) {
    const y = (floorY / 7) * i;
    const shift = (500 / floorY) * y;
    entities.push(line({ x: x - shift + 20, y }, { x: x + 340 - shift, y }, "A-STRS"));
  }
  entities.push(text({ x: x - 80, y: floorY * 0.45 }, "ATTIC LADDER", 120, "A-NOTE", 75));
};

const sectionA = (spec: BuildingSpec): DrawingView => {
  const width = spec.roofDirection === "ridge-along-depth" ? spec.width : spec.depth;
  const t = spec.wallThickness;
  const entities: Entity[] = [];
  addFoundation(entities, width, spec);
  entities.push(rect(0, 0, t, spec.eaveHeight, "A-CUT"));
  entities.push(rect(width - t, 0, width, spec.eaveHeight, "A-CUT"));
  entities.push(rect(t, spec.atticFloorHeight - 140, width - t, spec.atticFloorHeight, "A-CUT"));
  entities.push(line({ x: -spec.roofOverhang, y: spec.eaveHeight }, { x: width / 2, y: spec.ridgeHeight }, "A-ROOF"));
  entities.push(line({ x: width / 2, y: spec.ridgeHeight }, { x: width + spec.roofOverhang, y: spec.eaveHeight }, "A-ROOF"));
  const roofDy = spec.ridgeHeight - spec.eaveHeight;
  const roofDx = width / 2 + spec.roofOverhang;
  const normalLength = Math.hypot(roofDx, roofDy) || 1;
  const nx = (-roofDy / normalLength) * spec.roofThickness;
  const ny = (roofDx / normalLength) * spec.roofThickness;
  entities.push(line({ x: -spec.roofOverhang + nx, y: spec.eaveHeight + ny }, { x: width / 2 + nx, y: spec.ridgeHeight + ny }, "A-ROOF"));
  entities.push(line({ x: width / 2 - nx, y: spec.ridgeHeight + ny }, { x: width + spec.roofOverhang - nx, y: spec.eaveHeight + ny }, "A-ROOF"));
  for (let ratio = 0.12; ratio < 0.9; ratio += 0.1) {
    const lx = -spec.roofOverhang + roofDx * ratio;
    const ly = spec.eaveHeight + roofDy * ratio;
    entities.push(line({ x: lx, y: ly }, { x: lx + nx, y: ly + ny }, "A-HATCH"));
    const rx = width + spec.roofOverhang - roofDx * ratio;
    entities.push(line({ x: rx, y: ly }, { x: rx - nx, y: ly + ny }, "A-HATCH"));
  }
  entities.push(line({ x: t, y: spec.ceilingHeight }, { x: width - t, y: spec.ceilingHeight }, "A-CEIL"));
  entities.push(line({ x: 0, y: 0 }, { x: width, y: 0 }, "A-LEVEL"));
  addFoldDownLadder(entities, width * 0.73, spec.atticFloorHeight);
  entities.push(rect(width * 0.42, spec.atticFloorHeight, width * 0.58, spec.atticFloorHeight + 700, "A-FURN"));
  entities.push(text({ x: width * 0.45, y: spec.atticFloorHeight + 330 }, "STORAGE", 130));
  entities.push(text({ x: width * 0.42, y: spec.atticFloorHeight + 950 }, "ATTIC", 190));
  entities.push(text({ x: width * 0.4, y: 1200 }, "MAIN FLOOR", 190));
  levelMarker(entities, width + 250, 0, "FFL ±0");
  levelMarker(entities, width + 250, spec.ceilingHeight, `CL ${spec.ceilingHeight}`);
  levelMarker(entities, width + 250, spec.atticFloorHeight, `AFL ${spec.atticFloorHeight}`);
  levelMarker(entities, width + 250, spec.eaveHeight, `EAVE ${spec.eaveHeight}`);
  levelMarker(entities, width + 250, spec.ridgeHeight, `RIDGE ${spec.ridgeHeight}`);
  dimHorizontal(entities, 0, width, -900, `${Math.round(width)}`);
  dimVertical(entities, 0, spec.atticFloorHeight, -800, `${Math.round(spec.atticFloorHeight)}`);
  dimVertical(entities, 0, spec.ridgeHeight, -1450, `${Math.round(spec.ridgeHeight)}`);
  entities.push(text({ x: width * 0.05, y: spec.ridgeHeight + 360 }, `ROOF BUILD-UP T=${spec.roofThickness}`, 130, "A-NOTE"));
  entities.push(text({ x: width * 0.05, y: spec.ridgeHeight + 130 }, "FINISH / MEMBRANE / INSULATION / RAFTER", 120, "A-NOTE"));
  return { id: "section-a", title: "SECTION A-A", width, height: spec.ridgeHeight + 500, entities };
};

const sectionB = (spec: BuildingSpec): DrawingView => {
  const width = spec.roofDirection === "ridge-along-depth" ? spec.depth : spec.width;
  const entities: Entity[] = [];
  addFoundation(entities, width, spec);
  entities.push(rect(0, 0, spec.wallThickness, spec.eaveHeight, "A-CUT"));
  entities.push(rect(width - spec.wallThickness, 0, width, spec.eaveHeight, "A-CUT"));
  entities.push(rect(spec.wallThickness, spec.atticFloorHeight - 140, width - spec.wallThickness, spec.atticFloorHeight, "A-CUT"));
  entities.push(line({ x: -spec.roofOverhang, y: spec.eaveHeight }, { x: width * 0.08, y: spec.ridgeHeight }, "A-ROOF"));
  entities.push(line({ x: width * 0.08, y: spec.ridgeHeight }, { x: width * 0.92, y: spec.ridgeHeight }, "A-ROOF"));
  entities.push(line({ x: width * 0.92, y: spec.ridgeHeight }, { x: width + spec.roofOverhang, y: spec.eaveHeight }, "A-ROOF"));
  entities.push(line({ x: spec.wallThickness, y: spec.ceilingHeight }, { x: width - spec.wallThickness, y: spec.ceilingHeight }, "A-CEIL"));
  for (const ratio of [0.32, 0.62]) {
    const x = width * ratio;
    entities.push(rect(x, 0, x + spec.wallThickness, spec.atticFloorHeight, "A-CUT"));
  }
  const outline = normalizeOutline(spec.outline?.length ? spec.outline : DEFAULT_OUTLINE(spec.width, spec.depth));
  const wallIds = spec.wallIds?.length === outline.length ? spec.wallIds : defaultWallIds(outline.length);
  const sectionWallIndexes = spec.roofDirection === "ridge-along-depth" ? [1, 3] : [0, 2];
  const projected = new Set<string>();
  for (const opening of spec.openings ?? []) {
    const wallIndex = wallIndexForOpening(opening, wallIds, outline.length);
    if (!sectionWallIndexes.includes(wallIndex) || opening.placement === "attic") continue;
    const key = `${opening.kind}|${opening.offset}|${opening.width}|${opening.height}|${opening.sill ?? 0}`;
    if (projected.has(key)) continue;
    projected.add(key);
    addElevationOpening(entities, { ...opening, wallIndex: sectionWallIndexes[0] }, width);
  }
  addFoldDownLadder(entities, width * 0.56, spec.atticFloorHeight);
  entities.push(text({ x: width * 0.44, y: spec.atticFloorHeight + 900 }, "ATTIC SPACE", 180));
  entities.push(text({ x: width * 0.1, y: 1200 }, "ROOM", 150));
  entities.push(text({ x: width * 0.42, y: 1200 }, "LOBBY", 150));
  entities.push(text({ x: width * 0.72, y: 1200 }, "ROOM", 150));
  levelMarker(entities, width + 250, 0, "FFL ±0");
  levelMarker(entities, width + 250, spec.atticFloorHeight, `AFL ${spec.atticFloorHeight}`);
  levelMarker(entities, width + 250, spec.ridgeHeight, `RIDGE ${spec.ridgeHeight}`);
  dimHorizontal(entities, 0, width, -900, `${Math.round(width)}`);
  dimVertical(entities, 0, spec.ridgeHeight, -950, `${Math.round(spec.ridgeHeight)}`);
  return { id: "section-b", title: "SECTION B-B", width, height: spec.ridgeHeight + 500, entities };
};

const openingSchedule = (openings: Opening[]): OpeningScheduleRow[] => {
  const grouped = new Map<string, OpeningScheduleRow>();
  for (const opening of openings) {
    const mark = opening.label || `${opening.kind === "door" ? "D" : "W"}-${opening.width}x${opening.height}`;
    const key = `${mark}|${opening.kind}|${opening.width}|${opening.height}|${opening.sill ?? 0}`;
    const current = grouped.get(key);
    if (current) current.count += 1;
    else grouped.set(key, { mark, kind: opening.kind, count: 1, width: opening.width, height: opening.height, sill: opening.sill ?? 0 });
  }
  return [...grouped.values()].sort((a, b) => a.mark.localeCompare(b.mark));
};

const calculateMetrics = (spec: BuildingSpec, outline: Point[], openings: Opening[]): DrawingMetrics => {
  const span = spec.roofDirection === "ridge-along-depth" ? spec.width : spec.depth;
  const halfSpan = span / 2 + spec.roofOverhang;
  const rise = spec.ridgeHeight - spec.eaveHeight;
  const roofPitchDegrees = Math.atan2(rise, halfSpan) * 180 / Math.PI;
  const atticPeakHeight = spec.ridgeHeight - spec.atticFloorHeight;
  const usableWidthAt = (heightAtUse: number): number => {
    if (atticPeakHeight <= heightAtUse) return 0;
    const usableRatio = (atticPeakHeight - heightAtUse) / Math.max(atticPeakHeight - (spec.eaveHeight - spec.atticFloorHeight), 1);
    return clamp(span * usableRatio, 0, span);
  };
  const minimumHeight = spec.atticMinimumClearHeight ?? 1800;
  const atticUsableWidthAt1800 = usableWidthAt(1800);
  const ratioDenominator = rise > EPS ? halfSpan / rise : 0;
  return {
    footprintAreaM2: round(polygonArea(outline) / 1_000_000, 2),
    perimeterM: round(polygonPerimeter(outline) / 1000, 2),
    roofPitchDegrees: round(roofPitchDegrees, 1),
    atticPeakHeight: round(atticPeakHeight, 0),
    atticUsableWidthAt1800: round(atticUsableWidthAt1800, 0),
    exteriorWallCount: outline.length,
    openingCount: openings.length,
    roofPitchRatio: ratioDenominator > 0 ? `1:${round(ratioDenominator, 2)}` : "invalid",
    atticMinimumClearHeight: minimumHeight,
    atticUsableWidthAtMinimum: round(usableWidthAt(minimumHeight), 0),
  };
};

const boundedNumber = (value: unknown, fallback: number, min: number, max: number): number => {
  const numeric = Number(value ?? fallback);
  return Number.isFinite(numeric) ? clamp(numeric, min, max) : fallback;
};

const finiteCoordinate = (value: unknown): number => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
};

const stableInputLayer = (value: string | undefined): string | undefined => {
  if (value === undefined) return undefined;
  const normalized = value.normalize("NFKD").toUpperCase().replace(/[^A-Z0-9_-]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 31);
  return /^A-[A-Z0-9_-]+$/.test(normalized) ? normalized : "A-WALL";
};

const normalizePoint = (point: Point): Point => ({ x: finiteCoordinate(point.x), y: finiteCoordinate(point.y) });

export const normalizeSpec = (input: Partial<BuildingSpec>): BuildingSpec => {
  const width = boundedNumber(input.width, 12000, 3000, 50000);
  const depth = boundedNumber(input.depth, 11300, 3000, 50000);
  const outline = input.outline === undefined ? undefined : normalizeOutline(input.outline.slice(0, MAX_OUTLINE_POINTS).map(normalizePoint));
  const wallIds = input.wallIds?.slice(0, MAX_OUTLINE_POINTS).map((id, index) => id.trim().slice(0, 48) || `WALL-${String(index + 1).padStart(3, "0")}`);
  const interiorWalls = input.interiorWalls === undefined ? undefined : input.interiorWalls.slice(0, MAX_INTERIOR_WALLS).map((wall, index) => ({
    id: wall.id?.trim().slice(0, 48) || `IW-${String(index + 1).padStart(3, "0")}`,
    start: normalizePoint(wall.start),
    end: normalizePoint(wall.end),
    thickness: wall.thickness === undefined ? undefined : boundedNumber(wall.thickness, 200, 20, 2000),
    layer: stableInputLayer(wall.layer),
  }));
  const openings = input.openings === undefined ? undefined : input.openings.slice(0, MAX_OPENINGS).map((opening) => ({
    ...opening,
    wallId: opening.wallId?.trim().slice(0, 48) || undefined,
    wallIndex: opening.wallIndex === undefined || !Number.isFinite(Number(opening.wallIndex)) ? undefined : Math.trunc(Number(opening.wallIndex)),
    offset: finiteCoordinate(opening.offset),
    width: finiteCoordinate(opening.width),
    height: finiteCoordinate(opening.height),
    sill: opening.sill === undefined ? undefined : finiteCoordinate(opening.sill),
    label: opening.label?.trim().slice(0, 48),
  }));
  const stair = input.stair ? {
    ...input.stair,
    x: finiteCoordinate(input.stair.x),
    y: finiteCoordinate(input.stair.y),
    width: finiteCoordinate(input.stair.width),
    length: finiteCoordinate(input.stair.length),
    risers: Math.trunc(finiteCoordinate(input.stair.risers)),
    treadDepth: input.stair.treadDepth === undefined ? undefined : finiteCoordinate(input.stair.treadDepth),
    landingDepth: input.stair.landingDepth === undefined ? undefined : finiteCoordinate(input.stair.landingDepth),
  } : undefined;
  return {
    schemaVersion: BUILDING_SCHEMA_VERSION,
    projectName: input.projectName?.trim().slice(0, 120) || "HS-CAD PROJECT",
    unit: "mm",
    width,
    depth,
    wallThickness: boundedNumber(input.wallThickness, 200, 80, 600),
    eaveHeight: boundedNumber(input.eaveHeight, 3200, 2400, 15000),
    ridgeHeight: boundedNumber(input.ridgeHeight, 5000, 2600, 20000),
    atticFloorHeight: boundedNumber(input.atticFloorHeight, 2600, 1800, 12000),
    ceilingHeight: boundedNumber(input.ceilingHeight, 2500, 2100, 10000),
    roofDirection: input.roofDirection === "ridge-along-width" ? "ridge-along-width" : "ridge-along-depth",
    roofOverhang: boundedNumber(input.roofOverhang, 450, 0, 2000),
    roofThickness: boundedNumber(input.roofThickness, 220, 80, 800),
    floorSlabThickness: boundedNumber(input.floorSlabThickness, 180, 80, 800),
    foundationDepth: boundedNumber(input.foundationDepth, 700, 250, 4000),
    drawingScale: input.drawingScale?.trim().slice(0, 24) || "1:100",
    atticMinimumClearHeight: boundedNumber(input.atticMinimumClearHeight, 1800, 900, 3000),
    roofFinish: input.roofFinish?.trim().slice(0, 120) || "Standing seam metal",
    wallFinish: input.wallFinish?.trim().slice(0, 120) || "Exterior render / panel",
    plinthFinish: input.plinthFinish?.trim().slice(0, 120) || "Exposed concrete / stone",
    frameFinish: input.frameFinish?.trim().slice(0, 120) || "Powder-coated metal / timber",
    gutterDownspoutSpec: input.gutterDownspoutSpec?.trim().slice(0, 120) || "150 mm gutter / 100 mm downspout",
    outline,
    wallIds,
    interiorWalls,
    openings,
    stair,
    stairEnabled: input.stairEnabled ?? true,
    roomLabels: input.roomLabels?.slice(0, 128).map((room) => ({ ...room, name: room.name.trim().slice(0, 80), at: normalizePoint(room.at), polygon: room.polygon?.slice(0, MAX_OUTLINE_POINTS).map(normalizePoint) })),
    gridAxes: input.gridAxes?.slice(0, 64).map((axis) => ({ ...axis, id: axis.id.trim().slice(0, 24), start: normalizePoint(axis.start), end: normalizePoint(axis.end) })),
    sectionCuts: input.sectionCuts?.slice(0, 16).map((cut) => ({ ...cut, id: cut.id.trim().slice(0, 24), start: normalizePoint(cut.start), end: normalizePoint(cut.end) })),
    symbols: input.symbols?.slice(0, MAX_SYMBOLS).map((symbol) => ({ ...symbol, at: normalizePoint(symbol.at), width: symbol.width === undefined ? undefined : finiteCoordinate(symbol.width), depth: symbol.depth === undefined ? undefined : finiteCoordinate(symbol.depth), label: symbol.label?.trim().slice(0, 80) })),
    facadeFeatures: input.facadeFeatures?.slice(0, 128).map((feature) => ({ ...feature, offset: finiteCoordinate(feature.offset), width: feature.width === undefined ? undefined : finiteCoordinate(feature.width), height: feature.height === undefined ? undefined : finiteCoordinate(feature.height), sill: feature.sill === undefined ? undefined : finiteCoordinate(feature.sill), label: feature.label?.trim().slice(0, 48) })),
  };
};

const issue = (code: string, path: string, severity: ValidationIssue["severity"], message: string): ValidationIssue => ({ code, path, severity, message });
const allFinite = (point: Point): boolean => Number.isFinite(Number(point.x)) && Number.isFinite(Number(point.y));

export const validateSpecDetailed = (input: Partial<BuildingSpec>): ValidationIssue[] => {
  const issues: ValidationIssue[] = [];
  const suppliedVersion = input.schemaVersion as unknown;
  if (suppliedVersion !== undefined && suppliedVersion !== BUILDING_SCHEMA_VERSION) issues.push(issue("schema.version", "schemaVersion", "error", `지원하지 않는 schemaVersion입니다. ${BUILDING_SCHEMA_VERSION}을 사용해야 합니다.`));
  const suppliedUnit = input.unit as unknown;
  if (suppliedUnit !== undefined && suppliedUnit !== "mm") issues.push(issue("schema.unit", "unit", "error", "unit은 mm로 고정되어야 합니다."));
  const suppliedRoofDirection = input.roofDirection as unknown;
  if (suppliedRoofDirection !== undefined && suppliedRoofDirection !== "ridge-along-width" && suppliedRoofDirection !== "ridge-along-depth") issues.push(issue("schema.roof-direction", "roofDirection", "error", "roofDirection 값이 유효하지 않습니다."));
  const numericRanges: Array<[keyof BuildingSpec, number, number]> = [
    ["width", 3000, 50000], ["depth", 3000, 50000], ["wallThickness", 80, 600], ["eaveHeight", 2400, 15000],
    ["ridgeHeight", 2600, 20000], ["atticFloorHeight", 1800, 12000], ["ceilingHeight", 2100, 10000],
    ["roofOverhang", 0, 2000], ["roofThickness", 80, 800], ["floorSlabThickness", 80, 800], ["foundationDepth", 250, 4000],
  ];
  for (const [key, min, max] of numericRanges) {
    const value = input[key];
    if (value === undefined) continue;
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) issues.push(issue("number.nonfinite", String(key), "error", `${String(key)} 값은 유한한 숫자여야 합니다.`));
    else if (numeric < min || numeric > max) issues.push(issue("number.range", String(key), "error", `${String(key)} 값은 ${min}~${max} 범위여야 합니다.`));
  }
  const spec = normalizeSpec(input);
  if (spec.ridgeHeight <= spec.eaveHeight) issues.push(issue("height.ridge", "ridgeHeight", "error", "용마루 높이는 처마 높이보다 높아야 합니다."));
  if (spec.atticFloorHeight >= spec.eaveHeight) issues.push(issue("height.attic", "atticFloorHeight", "error", "다락 바닥 높이는 처마 높이보다 낮아야 합니다."));
  if (spec.ceilingHeight > spec.atticFloorHeight) issues.push(issue("height.ceiling", "ceilingHeight", "error", "실내 천장 높이는 다락 바닥 높이보다 낮거나 같아야 합니다."));
  if (spec.ridgeHeight - spec.atticFloorHeight < (spec.atticMinimumClearHeight ?? 1800)) issues.push(issue("height.attic-clear", "atticMinimumClearHeight", "warning", "다락 최고 유효높이가 설정된 최소 높이보다 낮습니다."));
  if (spec.wallThickness > Math.min(spec.width, spec.depth) / 8) issues.push(issue("wall.thickness", "wallThickness", "warning", "벽체 두께가 건물 크기에 비해 과도합니다."));

  if (input.outline && input.outline.length > MAX_OUTLINE_POINTS) issues.push(issue("count.outline", "outline", "error", `외곽점은 ${MAX_OUTLINE_POINTS}개를 초과할 수 없습니다.`));
  if (input.interiorWalls && input.interiorWalls.length > MAX_INTERIOR_WALLS) issues.push(issue("count.interiorWalls", "interiorWalls", "error", `내부 벽은 ${MAX_INTERIOR_WALLS}개를 초과할 수 없습니다.`));
  if (input.openings && input.openings.length > MAX_OPENINGS) issues.push(issue("count.openings", "openings", "error", `개구부는 ${MAX_OPENINGS}개를 초과할 수 없습니다.`));
  if (input.symbols && input.symbols.length > MAX_SYMBOLS) issues.push(issue("count.symbols", "symbols", "error", `기호는 ${MAX_SYMBOLS}개를 초과할 수 없습니다.`));
  if (input.gridAxes && input.gridAxes.length > 64) issues.push(issue("count.gridAxes", "gridAxes", "error", "그리드 축은 64개를 초과할 수 없습니다."));
  if (input.sectionCuts && input.sectionCuts.length > 16) issues.push(issue("count.sectionCuts", "sectionCuts", "error", "단면선은 16개를 초과할 수 없습니다."));
  if (input.roomLabels && input.roomLabels.length > 128) issues.push(issue("count.roomLabels", "roomLabels", "error", "실 정보는 128개를 초과할 수 없습니다."));
  if (input.facadeFeatures && input.facadeFeatures.length > 128) issues.push(issue("count.facadeFeatures", "facadeFeatures", "error", "입면 요소는 128개를 초과할 수 없습니다."));
  const validatePoint = (point: Point, path: string, label: string): void => {
    if (!allFinite(point)) issues.push(issue("coordinate.nonfinite", path, "error", `${label} 좌표는 유한해야 합니다.`));
    else if (Math.abs(Number(point.x)) > COORDINATE_LIMIT || Math.abs(Number(point.y)) > COORDINATE_LIMIT) issues.push(issue("coordinate.range", path, "error", `${label} 좌표는 ±${COORDINATE_LIMIT} mm 범위여야 합니다.`));
  };
  input.outline?.forEach((point, index) => {
    validatePoint(point, `outline[${index}]`, `외곽점 ${index + 1}의`);
  });
  const outline = normalizeOutline(spec.outline?.length ? spec.outline : DEFAULT_OUTLINE(spec.width, spec.depth));
  if (input.outline !== undefined && normalizeOutline(input.outline.map(normalizePoint)).length < 3) issues.push(issue("outline.points", "outline", "error", "외곽 폴리라인은 최소 3개 점이 필요합니다."));
  if (polygonArea(outline) < 1_000_000) issues.push(issue("outline.area", "outline", "error", "외곽 폴리라인 면적이 지나치게 작습니다."));
  if (outline.length >= 3 && isSelfIntersecting(outline)) issues.push(issue("outline.self-intersection", "outline", "error", "외곽 폴리라인이 자기 교차합니다."));
  if (spec.outline && outline.length !== 4) issues.push(issue("outline.nonrectangular", "outline", "warning", "비정형 외곽선의 입면·단면은 경계상자 기준 개념도로 생성됩니다."));
  const outlineBounds = bounds(outline);
  if (spec.outline && (Math.abs(outlineBounds.width - spec.width) > EPS || Math.abs(outlineBounds.height - spec.depth) > EPS)) issues.push(issue("outline.dimension-mismatch", "outline", "warning", "외곽선 경계 크기와 width/depth가 일치하지 않습니다."));

  const wallIds = spec.wallIds?.length === outline.length ? spec.wallIds : defaultWallIds(outline.length);
  if (spec.wallIds && spec.wallIds.length !== outline.length) issues.push(issue("wallIds.count", "wallIds", "error", "wallIds 개수는 외곽 벽 개수와 같아야 합니다."));
  if (new Set(wallIds).size !== wallIds.length) issues.push(issue("wallIds.duplicate", "wallIds", "error", "wallIds는 중복될 수 없습니다."));
  input.interiorWalls?.forEach((wall, index) => {
    validatePoint(wall.start, `interiorWalls[${index}].start`, `내부 벽 ${index + 1} 시작점의`);
    validatePoint(wall.end, `interiorWalls[${index}].end`, `내부 벽 ${index + 1} 끝점의`);
    if (allFinite(wall.start) && allFinite(wall.end) && samePoint(wall.start, wall.end)) issues.push(issue("wall.zero-length", `interiorWalls[${index}]`, "error", `내부 벽 ${index + 1}의 길이는 0일 수 없습니다.`));
    if (wall.thickness !== undefined && (!Number.isFinite(Number(wall.thickness)) || Number(wall.thickness) <= 0)) issues.push(issue("wall.thickness", `interiorWalls[${index}].thickness`, "error", `내부 벽 ${index + 1}의 두께는 양의 유한한 숫자여야 합니다.`));
    if (wall.layer && stableInputLayer(wall.layer) !== wall.layer) issues.push(issue("layer.invalid", `interiorWalls[${index}].layer`, "error", `내부 벽 ${index + 1}의 레이어 이름이 안전하지 않습니다.`));
  });
  input.gridAxes?.forEach((axis, index) => {
    validatePoint(axis.start, `gridAxes[${index}].start`, `그리드 축 ${index + 1} 시작점의`);
    validatePoint(axis.end, `gridAxes[${index}].end`, `그리드 축 ${index + 1} 끝점의`);
    if (allFinite(axis.start) && allFinite(axis.end) && samePoint(axis.start, axis.end)) issues.push(issue("grid.zero-length", `gridAxes[${index}]`, "error", `그리드 축 ${index + 1}의 길이는 0일 수 없습니다.`));
  });
  input.sectionCuts?.forEach((cut, index) => {
    validatePoint(cut.start, `sectionCuts[${index}].start`, `단면선 ${index + 1} 시작점의`);
    validatePoint(cut.end, `sectionCuts[${index}].end`, `단면선 ${index + 1} 끝점의`);
    if (allFinite(cut.start) && allFinite(cut.end) && samePoint(cut.start, cut.end)) issues.push(issue("section.zero-length", `sectionCuts[${index}]`, "error", `단면선 ${index + 1}의 길이는 0일 수 없습니다.`));
  });
  input.symbols?.forEach((symbol, index) => {
    validatePoint(symbol.at, `symbols[${index}].at`, `기호 ${index + 1}의`);
    for (const [key, value] of [["width", symbol.width], ["depth", symbol.depth]] as const) {
      if (value !== undefined && (!Number.isFinite(Number(value)) || Number(value) <= 0)) issues.push(issue("symbol.dimension", `symbols[${index}].${key}`, "error", `기호 ${index + 1}의 ${key}는 양의 유한한 숫자여야 합니다.`));
    }
  });
  input.roomLabels?.forEach((room, index) => {
    validatePoint(room.at, `roomLabels[${index}].at`, `실명 ${index + 1}의`);
    room.polygon?.forEach((point, pointIndex) => validatePoint(point, `roomLabels[${index}].polygon[${pointIndex}]`, `실 경계점의`));
  });
  input.facadeFeatures?.forEach((feature, index) => {
    const facade = feature.facade as unknown;
    const kind = feature.kind as unknown;
    if (!["front", "right", "rear", "left"].includes(String(facade))) issues.push(issue("facade.reference", `facadeFeatures[${index}].facade`, "error", `입면 요소 ${index + 1}의 facade가 유효하지 않습니다.`));
    if (!["attic-window", "vent", "louver", "downspout"].includes(String(kind))) issues.push(issue("facade.kind", `facadeFeatures[${index}].kind`, "error", `입면 요소 ${index + 1}의 kind가 유효하지 않습니다.`));
    for (const [key, value] of [["offset", feature.offset], ["width", feature.width], ["height", feature.height], ["sill", feature.sill]] as const) {
      if (value !== undefined && (!Number.isFinite(Number(value)) || Math.abs(Number(value)) > COORDINATE_LIMIT || ((key === "width" || key === "height") && Number(value) <= 0))) issues.push(issue("facade.dimension", `facadeFeatures[${index}].${key}`, "error", `입면 요소 ${index + 1}의 ${key} 값이 유효하지 않습니다.`));
    }
  });

  const openings = spec.openings ?? defaultOpenings(spec.width, spec.depth);
  const intervals = new Map<number, Array<{ start: number; end: number; index: number }>>();
  openings.forEach((opening, index) => {
    const path = `openings[${index}]`;
    if (opening.kind !== "door" && opening.kind !== "window") issues.push(issue("opening.kind", `${path}.kind`, "error", `개구부 ${index + 1}의 kind가 유효하지 않습니다.`));
    if (opening.swing && !["left", "right", "double"].includes(opening.swing)) issues.push(issue("opening.swing", `${path}.swing`, "error", `개구부 ${index + 1}의 swing 값이 유효하지 않습니다.`));
    if (![opening.offset, opening.width, opening.height, opening.sill ?? 0].every(Number.isFinite)) {
      issues.push(issue("opening.nonfinite", path, "error", `개구부 ${index + 1}의 치수는 유한해야 합니다.`));
      return;
    }
    if (opening.offset < 0 || opening.width <= 0 || opening.height <= 0 || (opening.sill ?? 0) < 0) issues.push(issue("opening.dimension", path, "error", `개구부 ${index + 1}의 치수가 유효하지 않습니다.`));
    const wallIndex = wallIndexForOpening(opening, wallIds, outline.length);
    if (wallIndex < 0) {
      issues.push(issue("opening.wall-reference", `${path}.${opening.wallId ? "wallId" : "wallIndex"}`, "error", `개구부 ${index + 1}의 벽 참조가 외곽 벽 범위를 벗어났습니다.`));
      return;
    }
    const length = wallLength(outline, wallIndex);
    if (opening.offset + opening.width > length + EPS) issues.push(issue("opening.wall-overflow", path, "error", `개구부 ${index + 1}가 해당 벽 길이를 초과합니다.`));
    if (opening.kind === "window" && (opening.sill ?? 0) + opening.height > spec.ridgeHeight) issues.push(issue("opening.window-head", path, "error", `창호 ${index + 1}의 상단이 지붕 최고 높이를 초과합니다.`));
    if (opening.kind === "door" && opening.height > spec.eaveHeight) issues.push(issue("opening.door-head", path, "error", `문 ${index + 1}의 높이가 처마 높이를 초과합니다.`));
    const list = intervals.get(wallIndex) ?? [];
    if (opening.placement !== "attic") list.push({ start: opening.offset, end: opening.offset + opening.width, index });
    intervals.set(wallIndex, list);
  });
  for (const list of intervals.values()) {
    list.sort((first, second) => first.start - second.start);
    for (let index = 1; index < list.length; index += 1) {
      if (list[index].start < list[index - 1].end - EPS) issues.push(issue("opening.overlap", `openings[${list[index].index}]`, "error", "같은 벽의 개구부가 서로 겹칩니다."));
    }
  }
  if (input.stair) {
    validatePoint({ x: input.stair.x, y: input.stair.y }, "stair", "계단 원점의");
    const stairValues = [input.stair.x, input.stair.y, input.stair.width, input.stair.length, input.stair.risers, input.stair.treadDepth ?? 250, input.stair.landingDepth ?? 900];
    if (!stairValues.every((value) => Number.isFinite(Number(value)))) issues.push(issue("stair.nonfinite", "stair", "error", "계단 좌표와 치수는 유한해야 합니다."));
    if (Number(input.stair.width) <= 0 || Number(input.stair.length) <= 0 || !Number.isInteger(Number(input.stair.risers)) || Number(input.stair.risers) < 3 || Number(input.stair.risers) > 40) issues.push(issue("stair.dimension", "stair", "error", "계단 폭·길이·단수는 유효한 범위여야 합니다."));
    if (!["up-north", "up-south", "up-east", "up-west"].includes(String(input.stair.direction))) issues.push(issue("stair.direction", "stair.direction", "error", "계단 direction 값이 유효하지 않습니다."));
  }
  const span = spec.roofDirection === "ridge-along-depth" ? spec.width : spec.depth;
  const pitch = Math.atan2(spec.ridgeHeight - spec.eaveHeight, span / 2 + spec.roofOverhang) * 180 / Math.PI;
  if (pitch < 5) issues.push(issue("roof.pitch-low", "ridgeHeight", "warning", "지붕 경사가 5° 미만으로 배수 상세 검토가 필요합니다."));
  if (pitch > 60) issues.push(issue("roof.pitch-high", "ridgeHeight", "warning", "지붕 경사가 60°를 초과합니다."));
  const seen = new Set<string>();
  return issues.filter((item) => {
    const key = `${item.code}|${item.path}|${item.message}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

export const validateSpec = (spec: Partial<BuildingSpec>): string[] => [...new Set(validateSpecDetailed(spec).map((item) => item.message))];

const canRenderOutline = (outline: Point[]): boolean => outline.length >= 3 && outline.every(allFinite) && polygonArea(outline) >= 1_000_000 && !isSelfIntersecting(outline);

export const generateDrawingSet = (input: Partial<BuildingSpec>, generatedAt = DEFAULT_GENERATED_AT): DrawingSet => {
  const validationIssues = validateSpecDetailed(input);
  const spec = normalizeSpec(input);
  const requestedOutline = normalizeOutline(spec.outline ?? DEFAULT_OUTLINE(spec.width, spec.depth));
  const outline = canRenderOutline(requestedOutline) ? requestedOutline : DEFAULT_OUTLINE(spec.width, spec.depth);
  const wallIds = spec.wallIds?.length === outline.length && new Set(spec.wallIds).size === spec.wallIds.length ? spec.wallIds : defaultWallIds(outline.length);
  const requestedOpenings = spec.openings ?? defaultOpenings(spec.width, spec.depth);
  const openings = requestedOpenings.flatMap((opening) => {
    const wallIndex = wallIndexForOpening(opening, wallIds, outline.length);
    const length = wallIndex >= 0 ? wallLength(outline, wallIndex) : 0;
    const finite = [opening.offset, opening.width, opening.height, opening.sill ?? 0].every(Number.isFinite);
    if (!finite || wallIndex < 0 || opening.offset < 0 || opening.width <= EPS || opening.height <= EPS || opening.offset + opening.width > length + EPS) return [];
    return [{ ...opening, wallIndex, wallId: wallIds[wallIndex] }];
  });
  const interiorWalls = spec.interiorWalls?.filter((wall) => allFinite(wall.start) && allFinite(wall.end) && !samePoint(wall.start, wall.end));
  const stair = spec.stair && [spec.stair.x, spec.stair.y, spec.stair.width, spec.stair.length, spec.stair.risers].every(Number.isFinite) && spec.stair.width > EPS && spec.stair.length > EPS && spec.stair.risers >= 3
    ? spec.stair
    : undefined;
  const gridAxes = spec.gridAxes?.filter((axis) => allFinite(axis.start) && allFinite(axis.end) && !samePoint(axis.start, axis.end));
  const sectionCuts = spec.sectionCuts?.filter((cut) => allFinite(cut.start) && allFinite(cut.end) && !samePoint(cut.start, cut.end));
  const symbols = spec.symbols?.filter((symbol) => allFinite(symbol.at) && (symbol.width === undefined || symbol.width > EPS) && (symbol.depth === undefined || symbol.depth > EPS));
  const facadeFeatures = (spec.facadeFeatures ?? defaultFacadeFeatures(spec)).filter((feature) => Number.isFinite(feature.offset) && (feature.width === undefined || feature.width > EPS) && (feature.height === undefined || feature.height > EPS));
  const drawingSpec: BuildingSpec = {
    ...spec,
    outline,
    wallIds,
    openings,
    interiorWalls,
    stair,
    gridAxes,
    sectionCuts,
    symbols,
    facadeFeatures,
  };
  const views: DrawingView[] = [
    planView(drawingSpec),
    elevationView(drawingSpec, "front", "FRONT ELEVATION"),
    elevationView(drawingSpec, "rear", "REAR ELEVATION"),
    elevationView(drawingSpec, "left", "LEFT ELEVATION"),
    elevationView(drawingSpec, "right", "RIGHT ELEVATION"),
    sectionA(drawingSpec),
    sectionB(drawingSpec),
  ];
  const schedule = openingSchedule(openings);
  const layerList = [...new Set(views.flatMap((view) => view.entities.map((entity) => entity.layer)))].sort();
  return {
    spec: drawingSpec,
    views,
    warnings: [...new Set(validationIssues.map((item) => item.message))],
    validationIssues,
    metrics: calculateMetrics(drawingSpec, outline, openings),
    openingSchedule: schedule,
    doorSchedule: schedule.filter((row) => row.kind === "door"),
    windowSchedule: schedule.filter((row) => row.kind === "window"),
    drawingViewList: views.map((view) => ({ id: view.id, title: view.title })),
    layerList,
    generatedAt,
    engineVersion: ENGINE_VERSION,
  };
};
