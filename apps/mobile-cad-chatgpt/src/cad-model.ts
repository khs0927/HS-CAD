import type {
  BuildingSpec,
  DrawingMetrics,
  DrawingSet,
  DrawingView,
  Entity,
  Facade,
  Opening,
  OpeningScheduleRow,
  Point,
  Segment,
  StairSpec,
} from "./types";

export const ENGINE_VERSION = "0.2.0";

const EPS = 1e-6;

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

const insetOutline = (points: Point[], thickness: number): Point[] => {
  const b = bounds(points);
  const isAxisRect = points.length === 4 && points.every((point) =>
    (Math.abs(point.x - b.minX) < EPS || Math.abs(point.x - b.maxX) < EPS) &&
    (Math.abs(point.y - b.minY) < EPS || Math.abs(point.y - b.maxY) < EPS));
  if (isAxisRect) {
    return [
      { x: b.minX + thickness, y: b.minY + thickness },
      { x: b.maxX - thickness, y: b.minY + thickness },
      { x: b.maxX - thickness, y: b.maxY - thickness },
      { x: b.minX + thickness, y: b.maxY - thickness },
    ];
  }
  const centroid = points.reduce((acc, point) => ({ x: acc.x + point.x, y: acc.y + point.y }), { x: 0, y: 0 });
  centroid.x /= points.length;
  centroid.y /= points.length;
  return points.map((point) => {
    const dx = centroid.x - point.x;
    const dy = centroid.y - point.y;
    const length = Math.hypot(dx, dy) || 1;
    return { x: point.x + (dx / length) * thickness, y: point.y + (dy / length) * thickness };
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

const defaultInteriorWalls = (width: number, depth: number): Segment[] => [
  { start: { x: width * 0.34, y: 0 }, end: { x: width * 0.34, y: depth * 0.58 } },
  { start: { x: width * 0.34, y: depth * 0.58 }, end: { x: width, y: depth * 0.58 } },
  { start: { x: width * 0.68, y: depth * 0.58 }, end: { x: width * 0.68, y: depth } },
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

const defaultStair = (width: number, depth: number): StairSpec => ({
  x: width * 0.39,
  y: depth * 0.28,
  width: Math.min(3000, width * 0.26),
  length: Math.min(3600, depth * 0.3),
  risers: 14,
  direction: "up-north",
});

const addOpeningPlan = (entities: Entity[], outline: Point[], opening: Opening, wallThickness: number): void => {
  if (opening.wallIndex < 0 || opening.wallIndex >= outline.length) return;
  const start = pointOnWall(outline, opening.wallIndex, opening.offset);
  const end = pointOnWall(outline, opening.wallIndex, opening.offset + opening.width);
  const nx = -Math.sin(start.angle);
  const ny = Math.cos(start.angle);
  const tx = Math.cos(start.angle);
  const ty = Math.sin(start.angle);
  const jamb = wallThickness * 0.55;
  entities.push(line({ x: start.point.x - nx * jamb, y: start.point.y - ny * jamb }, { x: start.point.x + nx * jamb, y: start.point.y + ny * jamb }, "A-OPEN"));
  entities.push(line({ x: end.point.x - nx * jamb, y: end.point.y - ny * jamb }, { x: end.point.x + nx * jamb, y: end.point.y + ny * jamb }, "A-OPEN"));
  if (opening.kind === "door") {
    const angle = (start.angle * 180) / Math.PI;
    const side = opening.swing === "left" ? -1 : 1;
    if (opening.swing === "double") {
      const half = opening.width / 2;
      const mid = pointOnWall(outline, opening.wallIndex, opening.offset + half).point;
      entities.push(line(start.point, { x: start.point.x + tx * half + nx * half, y: start.point.y + ty * half + ny * half }, "A-DOOR"));
      entities.push(arc(start.point, half, angle, angle + 90, "A-DOOR"));
      entities.push(line(end.point, { x: end.point.x - tx * half + nx * half, y: end.point.y - ty * half + ny * half }, "A-DOOR"));
      entities.push(arc(end.point, half, angle + 90, angle + 180, "A-DOOR"));
      entities.push(circle(mid, 35, "A-DOOR"));
    } else {
      const leafEnd = {
        x: start.point.x + tx * opening.width + nx * opening.width * side,
        y: start.point.y + ty * opening.width + ny * opening.width * side,
      };
      entities.push(line(start.point, leafEnd, "A-DOOR"));
      entities.push(arc(start.point, opening.width, side > 0 ? angle : angle - 90, side > 0 ? angle + 90 : angle, "A-DOOR"));
    }
  } else {
    const gap = 45;
    entities.push(line({ x: start.point.x + nx * gap, y: start.point.y + ny * gap }, { x: end.point.x + nx * gap, y: end.point.y + ny * gap }, "A-WIND"));
    entities.push(line({ x: start.point.x - nx * gap, y: start.point.y - ny * gap }, { x: end.point.x - nx * gap, y: end.point.y - ny * gap }, "A-WIND"));
    const mid = pointOnWall(outline, opening.wallIndex, opening.offset + opening.width / 2).point;
    entities.push(line({ x: mid.x - nx * 95, y: mid.y - ny * 95 }, { x: mid.x + nx * 95, y: mid.y + ny * 95 }, "A-WIND"));
  }
  if (opening.label) entities.push(text({ x: (start.point.x + end.point.x) / 2 + nx * 280, y: (start.point.y + end.point.y) / 2 + ny * 280 }, opening.label, 120, "A-TEXT"));
};

const addStairPlan = (entities: Entity[], stair: StairSpec): void => {
  const { x, y, width, length, risers } = stair;
  entities.push(rect(x, y, x + width, y + length, "A-STRS"));
  const landing = length * 0.32;
  const flightWidth = width * 0.38;
  entities.push(rect(x + flightWidth, y + landing, x + width - flightWidth, y + length - landing, "A-STRS"));
  const lowerSteps = Math.max(4, Math.floor(risers / 2));
  const upperSteps = Math.max(4, risers - lowerSteps);
  for (let i = 1; i < lowerSteps; i += 1) {
    const yy = y + (landing / lowerSteps) * i;
    entities.push(line({ x, y: yy }, { x: x + flightWidth, y: yy }, "A-STRS"));
  }
  for (let i = 1; i < upperSteps; i += 1) {
    const yy = y + length - (landing / upperSteps) * i;
    entities.push(line({ x: x + width - flightWidth, y: yy }, { x: x + width, y: yy }, "A-STRS"));
  }
  for (let i = 1; i < 7; i += 1) {
    const xx = x + flightWidth + ((width - 2 * flightWidth) / 7) * i;
    entities.push(line({ x: xx, y: y + landing }, { x: xx, y: y + length - landing }, "A-STRS"));
  }
  entities.push(line({ x: x + flightWidth / 2, y: y + 250 }, { x: x + flightWidth / 2, y: y + landing - 120 }, "A-STRS"));
  entities.push(poly([
    { x: x + flightWidth / 2, y: y + landing - 40 },
    { x: x + flightWidth / 2 - 80, y: y + landing - 180 },
    { x: x + flightWidth / 2 + 80, y: y + landing - 180 },
  ], true, "A-STRS"));
  entities.push(text({ x: x + 180, y: y + 120 }, "UP", 130, "A-STRS"));
};

const addFurniturePlan = (entities: Entity[], width: number, depth: number): void => {
  const tableX = width * 0.08;
  const tableY = depth * 0.72;
  entities.push(rect(tableX, tableY, tableX + 1700, tableY + 800, "A-FURN"));
  for (const cx of [tableX + 280, tableX + 850, tableX + 1420]) {
    entities.push(rect(cx - 150, tableY - 350, cx + 150, tableY - 80, "A-FURN"));
    entities.push(rect(cx - 150, tableY + 880, cx + 150, tableY + 1150, "A-FURN"));
  }
  const roundX = width * 0.14;
  const roundY = depth * 0.18;
  entities.push(circle({ x: roundX, y: roundY }, 420, "A-FURN"));
  for (let index = 0; index < 4; index += 1) {
    const angle = (Math.PI / 2) * index;
    const cx = roundX + Math.cos(angle) * 700;
    const cy = roundY + Math.sin(angle) * 700;
    entities.push(rect(cx - 130, cy - 110, cx + 130, cy + 110, "A-FURN"));
  }
};

const planView = (spec: BuildingSpec): DrawingView => {
  const outline = normalizeOutline(spec.outline?.length ? spec.outline : DEFAULT_OUTLINE(spec.width, spec.depth));
  const b = bounds(outline);
  const entities: Entity[] = [poly(outline, true, "A-WALL"), poly(insetOutline(outline, spec.wallThickness), true, "A-WALL")];
  const walls = spec.interiorWalls?.length ? spec.interiorWalls : defaultInteriorWalls(spec.width, spec.depth);
  for (const wall of walls) entities.push(thickSegment(wall, spec.wallThickness));
  const openings = spec.openings?.length ? spec.openings : defaultOpenings(spec.width, spec.depth);
  for (const opening of openings) addOpeningPlan(entities, outline, opening, spec.wallThickness);
  addStairPlan(entities, spec.stair ?? defaultStair(spec.width, spec.depth));
  addFurniturePlan(entities, spec.width, spec.depth);

  entities.push(text({ x: b.minX + b.width * 0.44, y: b.minY + b.height * 0.22 }, "LOBBY", 220));
  entities.push(text({ x: b.minX + b.width * 0.08, y: b.minY + b.height * 0.78 }, "ROOM 1", 180));
  entities.push(text({ x: b.minX + b.width * 0.46, y: b.minY + b.height * 0.78 }, "ROOM 2", 180));
  entities.push(text({ x: b.minX + b.width * 0.76, y: b.minY + b.height * 0.78 }, "SERVICE", 180));

  dimHorizontal(entities, b.minX, b.maxX, b.minY - 700, `${Math.round(b.width)}`);
  dimVertical(entities, b.minY, b.maxY, b.minX - 700, `${Math.round(b.height)}`);
  sectionMarker(entities, { x: b.minX + b.width * 0.5, y: b.minY - 180 }, { x: b.minX + b.width * 0.5, y: b.maxY + 180 }, "A");
  sectionMarker(entities, { x: b.minX - 180, y: b.minY + b.height * 0.5 }, { x: b.maxX + 180, y: b.minY + b.height * 0.5 }, "B");

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
    entities.push(rect(width / 2 - 500, spec.atticFloorHeight + 450, width / 2 + 500, spec.atticFloorHeight + 1150, "A-WIND"));
    entities.push(line({ x: width / 2, y: spec.atticFloorHeight + 450 }, { x: width / 2, y: spec.atticFloorHeight + 1150 }, "A-GLAZ"));
    entities.push(rect(width / 2 - 140, spec.ridgeHeight - 520, width / 2 + 140, spec.ridgeHeight - 300, "A-VENT"));
  } else {
    entities.push(rect(0, 0, width, spec.eaveHeight, "A-ELEV"));
    entities.push(line({ x: -spec.roofOverhang, y: spec.eaveHeight - 70 }, { x: width + spec.roofOverhang, y: spec.eaveHeight - 70 }, "A-ROOF"));
    entities.push(line({ x: width * 0.08, y: spec.ridgeHeight }, { x: width * 0.92, y: spec.ridgeHeight }, "A-ROOF"));
    entities.push(line({ x: width * 0.08, y: spec.ridgeHeight }, { x: 0, y: spec.eaveHeight }, "A-ROOF"));
    entities.push(line({ x: width * 0.92, y: spec.ridgeHeight }, { x: width, y: spec.eaveHeight }, "A-ROOF"));
    entities.push(rect(width / 2 - 450, spec.atticFloorHeight + 500, width / 2 + 450, spec.atticFloorHeight + 1100, "A-WIND"));
  }

  addWallFinishPattern(entities, width, spec.eaveHeight);
  addRoofFinishPattern(entities, width, spec, gable);
  const wallIndex = facadeWallIndex(facade);
  const outline = normalizeOutline(spec.outline?.length ? spec.outline : DEFAULT_OUTLINE(spec.width, spec.depth));
  const openings = spec.openings?.length ? spec.openings : defaultOpenings(spec.width, spec.depth);
  for (const opening of openings.filter((item) => item.wallIndex === wallIndex)) addElevationOpening(entities, opening, wallLength(outline, wallIndex) || width);

  entities.push(line({ x: 0, y: spec.atticFloorHeight }, { x: width, y: spec.atticFloorHeight }, "A-HIDD"));
  entities.push(line({ x: 190, y: spec.eaveHeight - 40 }, { x: 190, y: 220 }, "A-DRAIN"));
  entities.push(line({ x: width - 190, y: spec.eaveHeight - 40 }, { x: width - 190, y: 220 }, "A-DRAIN"));
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
  entities.push(rect(width * 0.12, 900, width * 0.23, 2100, "A-WIND"));
  entities.push(rect(width * 0.42, 0, width * 0.5, 2100, "A-DOOR"));
  entities.push(rect(width * 0.74, 900, width * 0.85, 2100, "A-WIND"));
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
  const heightAtUse = 1800;
  const usableRatio = atticPeakHeight > heightAtUse ? (atticPeakHeight - heightAtUse) / Math.max(atticPeakHeight - (spec.eaveHeight - spec.atticFloorHeight), 1) : 0;
  const atticUsableWidthAt1800 = clamp(span * usableRatio, 0, span);
  return {
    footprintAreaM2: round(polygonArea(outline) / 1_000_000, 2),
    perimeterM: round(polygonPerimeter(outline) / 1000, 2),
    roofPitchDegrees: round(roofPitchDegrees, 1),
    atticPeakHeight: round(atticPeakHeight, 0),
    atticUsableWidthAt1800: round(atticUsableWidthAt1800, 0),
    exteriorWallCount: outline.length,
    openingCount: openings.length,
  };
};

export const normalizeSpec = (input: Partial<BuildingSpec>): BuildingSpec => ({
  projectName: input.projectName?.trim() || "HS-CAD PROJECT",
  unit: "mm",
  width: clamp(Number(input.width ?? 12000), 3000, 50000),
  depth: clamp(Number(input.depth ?? 11300), 3000, 50000),
  wallThickness: clamp(Number(input.wallThickness ?? 200), 80, 600),
  eaveHeight: clamp(Number(input.eaveHeight ?? 3200), 2400, 15000),
  ridgeHeight: clamp(Number(input.ridgeHeight ?? 5000), 2600, 20000),
  atticFloorHeight: clamp(Number(input.atticFloorHeight ?? 2600), 1800, 12000),
  ceilingHeight: clamp(Number(input.ceilingHeight ?? 2500), 2100, 10000),
  roofDirection: input.roofDirection ?? "ridge-along-depth",
  roofOverhang: clamp(Number(input.roofOverhang ?? 450), 0, 2000),
  roofThickness: clamp(Number(input.roofThickness ?? 220), 80, 800),
  floorSlabThickness: clamp(Number(input.floorSlabThickness ?? 180), 80, 800),
  foundationDepth: clamp(Number(input.foundationDepth ?? 700), 250, 4000),
  roofFinish: input.roofFinish?.trim() || "Standing seam metal",
  wallFinish: input.wallFinish?.trim() || "Exterior render / panel",
  plinthFinish: input.plinthFinish?.trim() || "Exposed concrete / stone",
  outline: input.outline ? normalizeOutline(input.outline) : undefined,
  interiorWalls: input.interiorWalls,
  openings: input.openings,
  stair: input.stair,
});

export const validateSpec = (spec: BuildingSpec): string[] => {
  const warnings: string[] = [];
  const outline = normalizeOutline(spec.outline?.length ? spec.outline : DEFAULT_OUTLINE(spec.width, spec.depth));
  const openings = spec.openings?.length ? spec.openings : defaultOpenings(spec.width, spec.depth);
  if (spec.ridgeHeight <= spec.eaveHeight) warnings.push("용마루 높이는 처마 높이보다 높아야 합니다.");
  if (spec.atticFloorHeight >= spec.eaveHeight) warnings.push("다락 바닥 높이는 처마 높이보다 낮아야 합니다.");
  if (spec.ceilingHeight > spec.atticFloorHeight) warnings.push("실내 천장 높이는 다락 바닥 높이보다 낮거나 같아야 합니다.");
  if (spec.ridgeHeight - spec.atticFloorHeight < 1800) warnings.push("다락 최고 유효높이가 1.8m 미만입니다.");
  if (spec.wallThickness > Math.min(spec.width, spec.depth) / 8) warnings.push("벽체 두께가 건물 크기에 비해 과도합니다.");
  if (outline.length < 3) warnings.push("외곽 폴리라인은 최소 3개 점이 필요합니다.");
  if (polygonArea(outline) < 1_000_000) warnings.push("외곽 폴리라인 면적이 지나치게 작습니다.");
  if (isSelfIntersecting(outline)) warnings.push("외곽 폴리라인이 자기 교차합니다.");
  if (spec.outline && outline.length !== 4) warnings.push("비정형 외곽선의 입면·단면은 경계상자 기준 개념도로 생성됩니다.");
  for (const [index, opening] of openings.entries()) {
    if (opening.wallIndex < 0 || opening.wallIndex >= outline.length) {
      warnings.push(`개구부 ${index + 1}의 wallIndex가 외곽 벽 범위를 벗어났습니다.`);
      continue;
    }
    const length = wallLength(outline, opening.wallIndex);
    if (opening.offset + opening.width > length + EPS) warnings.push(`개구부 ${index + 1}가 해당 벽 길이를 초과합니다.`);
    if (opening.kind === "window" && (opening.sill ?? 0) + opening.height > spec.eaveHeight) warnings.push(`창호 ${index + 1}의 상단이 처마 높이를 초과합니다.`);
    if (opening.kind === "door" && opening.height > spec.eaveHeight) warnings.push(`문 ${index + 1}의 높이가 처마 높이를 초과합니다.`);
  }
  const span = spec.roofDirection === "ridge-along-depth" ? spec.width : spec.depth;
  const pitch = Math.atan2(spec.ridgeHeight - spec.eaveHeight, span / 2 + spec.roofOverhang) * 180 / Math.PI;
  if (pitch < 5) warnings.push("지붕 경사가 5° 미만으로 배수 상세 검토가 필요합니다.");
  if (pitch > 60) warnings.push("지붕 경사가 60°를 초과합니다.");
  return [...new Set(warnings)];
};

export const generateDrawingSet = (input: Partial<BuildingSpec>, generatedAt = new Date().toISOString()): DrawingSet => {
  const spec = normalizeSpec(input);
  const outline = normalizeOutline(spec.outline?.length ? spec.outline : DEFAULT_OUTLINE(spec.width, spec.depth));
  const openings = spec.openings?.length ? spec.openings : defaultOpenings(spec.width, spec.depth);
  const views: DrawingView[] = [
    planView({ ...spec, outline, openings }),
    elevationView({ ...spec, outline, openings }, "front", "FRONT ELEVATION"),
    elevationView({ ...spec, outline, openings }, "rear", "REAR ELEVATION"),
    elevationView({ ...spec, outline, openings }, "left", "LEFT ELEVATION"),
    elevationView({ ...spec, outline, openings }, "right", "RIGHT ELEVATION"),
    sectionA(spec),
    sectionB(spec),
  ];
  return {
    spec: { ...spec, outline, openings },
    views,
    warnings: validateSpec({ ...spec, outline, openings }),
    metrics: calculateMetrics(spec, outline, openings),
    openingSchedule: openingSchedule(openings),
    generatedAt,
    engineVersion: ENGINE_VERSION,
  };
};
