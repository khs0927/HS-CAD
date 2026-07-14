import type { DrawingSet, DrawingView, Entity, Point } from "./types";

const EPS = 1e-6;
const finite = (value: number, label: string): number => {
  if (!Number.isFinite(value)) throw new TypeError(`DXF ${label} must be finite`);
  return Object.is(value, -0) ? 0 : value;
};
const ascii = (value: string): string => value.normalize("NFKD").replace(/[^\x20-\x7E]/g, "?").replace(/[\r\n]+/g, " ");
const pair = (code: number, value: string | number): string => `${code}\n${typeof value === "number" ? finite(value, `group ${code}`) : ascii(value)}\n`;
const pt = (point: Point, ox: number, oy: number): Point => ({ x: finite(point.x + ox, "x"), y: finite(point.y + oy, "y") });
const samePoint = (first: Point, second: Point): boolean => Math.abs(first.x - second.x) <= EPS && Math.abs(first.y - second.y) <= EPS;
const normalizeAngle = (value: number): number => {
  const angle = finite(value, "arc angle") % 360;
  return angle < 0 ? angle + 360 : angle;
};

export const sanitizeLayerName = (value: string): string => {
  let safe = ascii(value).toUpperCase().replace(/[^A-Z0-9_-]+/g, "_").replace(/^_+|_+$/g, "");
  if (!safe) safe = "A-ANNO";
  if (!safe.startsWith("A-")) safe = `A-${safe}`;
  return safe.slice(0, 31);
};

const layerConfig: Record<string, { color: number; linetype: "CONTINUOUS" | "DASHED" }> = {
  "A-WALL": { color: 7, linetype: "CONTINUOUS" },
  "A-CUT": { color: 1, linetype: "CONTINUOUS" },
  "A-ELEV": { color: 7, linetype: "CONTINUOUS" },
  "A-ROOF": { color: 5, linetype: "CONTINUOUS" },
  "A-DOOR": { color: 30, linetype: "CONTINUOUS" },
  "A-WIND": { color: 4, linetype: "CONTINUOUS" },
  "A-GLAZ": { color: 151, linetype: "CONTINUOUS" },
  "A-OPEN": { color: 3, linetype: "CONTINUOUS" },
  "A-STRS": { color: 6, linetype: "CONTINUOUS" },
  "A-FURN": { color: 8, linetype: "CONTINUOUS" },
  "A-FIXT": { color: 140, linetype: "CONTINUOUS" },
  "A-COLS": { color: 1, linetype: "CONTINUOUS" },
  "A-DIMS": { color: 2, linetype: "CONTINUOUS" },
  "A-TEXT": { color: 7, linetype: "CONTINUOUS" },
  "A-NOTE": { color: 7, linetype: "CONTINUOUS" },
  "A-ANNO": { color: 6, linetype: "CONTINUOUS" },
  "A-SECT": { color: 1, linetype: "DASHED" },
  "A-HIDD": { color: 8, linetype: "DASHED" },
  "A-HATCH": { color: 8, linetype: "CONTINUOUS" },
  "A-MATL": { color: 9, linetype: "CONTINUOUS" },
  "A-PLIN": { color: 9, linetype: "CONTINUOUS" },
  "A-VENT": { color: 4, linetype: "CONTINUOUS" },
  "A-DRAIN": { color: 3, linetype: "CONTINUOUS" },
  "A-GRID": { color: 8, linetype: "DASHED" },
  "A-LEVEL": { color: 2, linetype: "CONTINUOUS" },
  "A-CEIL": { color: 6, linetype: "DASHED" },
  "A-BORDER": { color: 7, linetype: "CONTINUOUS" },
};

const normalizeEntity = (entity: Entity): Entity => {
  const layer = sanitizeLayerName(entity.layer);
  if (entity.type === "line") {
    const start = { x: finite(entity.start.x, "line start x"), y: finite(entity.start.y, "line start y") };
    const end = { x: finite(entity.end.x, "line end x"), y: finite(entity.end.y, "line end y") };
    if (samePoint(start, end)) throw new TypeError("DXF zero-length LINE is not allowed");
    return { ...entity, layer, start, end };
  }
  if (entity.type === "polyline") {
    const points: Point[] = [];
    for (const source of entity.points) {
      const point = { x: finite(source.x, "polyline x"), y: finite(source.y, "polyline y") };
      if (!points.length || !samePoint(points.at(-1)!, point)) points.push(point);
    }
    if (entity.closed && points.length > 1 && samePoint(points[0], points.at(-1)!)) points.pop();
    if (points.length < (entity.closed ? 3 : 2)) throw new TypeError("DXF degenerate POLYLINE is not allowed");
    return { ...entity, layer, points };
  }
  if (entity.type === "arc") {
    const center = { x: finite(entity.center.x, "arc center x"), y: finite(entity.center.y, "arc center y") };
    const radius = finite(entity.radius, "arc radius");
    if (radius <= EPS) throw new TypeError("DXF ARC radius must be positive");
    const startAngle = normalizeAngle(entity.startAngle);
    const endAngle = normalizeAngle(entity.endAngle);
    if (Math.abs(normalizeAngle(endAngle - startAngle)) <= EPS) throw new TypeError("DXF degenerate ARC is not allowed");
    return { ...entity, layer, center, radius, startAngle, endAngle };
  }
  if (entity.type === "circle") {
    const center = { x: finite(entity.center.x, "circle center x"), y: finite(entity.center.y, "circle center y") };
    const radius = finite(entity.radius, "circle radius");
    if (radius <= EPS) throw new TypeError("DXF CIRCLE radius must be positive");
    return { ...entity, layer, center, radius };
  }
  const at = { x: finite(entity.at.x, "text x"), y: finite(entity.at.y, "text y") };
  const height = finite(entity.height, "text height");
  if (height <= EPS) throw new TypeError("DXF TEXT height must be positive");
  return { ...entity, layer, at, height, rotation: normalizeAngle(entity.rotation ?? 0), text: ascii(entity.text) };
};

const entityKey = (entity: Entity): string => {
  if (entity.type === "line") {
    const first = `${entity.start.x},${entity.start.y}`;
    const second = `${entity.end.x},${entity.end.y}`;
    return `${entity.type}|${entity.layer}|${first < second ? `${first}|${second}` : `${second}|${first}`}`;
  }
  return JSON.stringify(entity);
};

const prepareEntities = (entities: Entity[]): Entity[] => {
  const seen = new Set<string>();
  const result: Entity[] = [];
  for (const source of entities) {
    const entity = normalizeEntity(source);
    const key = entityKey(entity);
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(entity);
  }
  return result;
};

const entityToDxf = (entity: Entity, ox: number, oy: number): string => {
  if (entity.type === "line") {
    const start = pt(entity.start, ox, oy);
    const end = pt(entity.end, ox, oy);
    return pair(0, "LINE") + pair(8, entity.layer) + pair(10, start.x) + pair(20, start.y) + pair(30, 0) + pair(11, end.x) + pair(21, end.y) + pair(31, 0);
  }
  if (entity.type === "polyline") {
    let out = pair(0, "POLYLINE") + pair(8, entity.layer) + pair(66, 1) + pair(10, 0) + pair(20, 0) + pair(30, 0) + pair(70, entity.closed ? 1 : 0);
    for (const point of entity.points) {
      const p = pt(point, ox, oy);
      out += pair(0, "VERTEX") + pair(8, entity.layer) + pair(10, p.x) + pair(20, p.y) + pair(30, 0) + pair(70, 0);
    }
    return out + pair(0, "SEQEND") + pair(8, entity.layer);
  }
  if (entity.type === "arc") {
    const center = pt(entity.center, ox, oy);
    return pair(0, "ARC") + pair(8, entity.layer) + pair(10, center.x) + pair(20, center.y) + pair(30, 0) + pair(40, entity.radius) + pair(50, entity.startAngle) + pair(51, entity.endAngle);
  }
  if (entity.type === "circle") {
    const center = pt(entity.center, ox, oy);
    return pair(0, "CIRCLE") + pair(8, entity.layer) + pair(10, center.x) + pair(20, center.y) + pair(30, 0) + pair(40, entity.radius);
  }
  const at = pt(entity.at, ox, oy);
  return pair(0, "TEXT") + pair(8, entity.layer) + pair(10, at.x) + pair(20, at.y) + pair(30, 0) + pair(40, entity.height) + pair(1, entity.text) + pair(50, entity.rotation ?? 0) + pair(7, "STANDARD");
};

export const layoutViews = (views: DrawingView[]): Array<{ view: DrawingView; x: number; y: number }> => {
  const gapX = 3200;
  const gapY = 3600;
  const rows: DrawingView[][] = [views.slice(0, 3), views.slice(3, 5), views.slice(5, 7)];
  const result: Array<{ view: DrawingView; x: number; y: number }> = [];
  let y = 0;
  for (const row of rows) {
    let x = 0;
    const rowHeight = Math.max(...row.map((view) => view.height), 0);
    for (const view of row) {
      result.push({ view, x, y });
      x += view.width + gapX;
    }
    y -= rowHeight + gapY;
  }
  return result;
};

type Extents = { minX: number; minY: number; maxX: number; maxY: number };
const includePoint = (box: Extents, point: Point): void => {
  box.minX = Math.min(box.minX, point.x);
  box.minY = Math.min(box.minY, point.y);
  box.maxX = Math.max(box.maxX, point.x);
  box.maxY = Math.max(box.maxY, point.y);
};
const includeEntity = (box: Extents, entity: Entity, ox: number, oy: number): void => {
  if (entity.type === "line") {
    includePoint(box, pt(entity.start, ox, oy));
    includePoint(box, pt(entity.end, ox, oy));
  } else if (entity.type === "polyline") {
    for (const point of entity.points) includePoint(box, pt(point, ox, oy));
  } else if (entity.type === "arc" || entity.type === "circle") {
    includePoint(box, { x: entity.center.x + ox - entity.radius, y: entity.center.y + oy - entity.radius });
    includePoint(box, { x: entity.center.x + ox + entity.radius, y: entity.center.y + oy + entity.radius });
  } else {
    includePoint(box, pt(entity.at, ox, oy));
    includePoint(box, { x: entity.at.x + ox + Math.max(entity.height, entity.text.length * entity.height * 0.7), y: entity.at.y + oy + entity.height });
  }
};

export const drawingSetToDxf = (set: DrawingSet): string => {
  const placements = layoutViews(set.views).map((placement) => ({ ...placement, entities: prepareEntities(placement.view.entities) }));
  if (!placements.length) throw new TypeError("DXF requires at least one drawing view");
  const rawBox: Extents = { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity };
  for (const placement of placements) {
    for (const entity of placement.entities) includeEntity(rawBox, entity, placement.x, placement.y);
    includePoint(rawBox, { x: placement.x, y: placement.y + placement.view.height + 750 });
  }
  if (![rawBox.minX, rawBox.minY, rawBox.maxX, rawBox.maxY].every(Number.isFinite)) throw new TypeError("DXF extents are invalid");
  const margin = 1800;
  const box = { minX: rawBox.minX - margin, minY: rawBox.minY - margin, maxX: rawBox.maxX + margin, maxY: rawBox.maxY + margin };
  const allLayers = new Set(placements.flatMap((placement) => placement.entities.map((entity) => entity.layer)));
  allLayers.add("A-TEXT");
  allLayers.add("A-BORDER");
  const layers = [...allLayers].sort();

  let tables = pair(0, "SECTION") + pair(2, "TABLES");
  tables += pair(0, "TABLE") + pair(2, "LTYPE") + pair(70, 2);
  tables += pair(0, "LTYPE") + pair(2, "CONTINUOUS") + pair(70, 0) + pair(3, "Solid line") + pair(72, 65) + pair(73, 0) + pair(40, 0);
  tables += pair(0, "LTYPE") + pair(2, "DASHED") + pair(70, 0) + pair(3, "Dashed") + pair(72, 65) + pair(73, 2) + pair(40, 240) + pair(49, 160) + pair(74, 0) + pair(49, -80) + pair(74, 0);
  tables += pair(0, "ENDTAB");
  tables += pair(0, "TABLE") + pair(2, "LAYER") + pair(70, layers.length);
  for (const layer of layers) {
    const config = layerConfig[layer] ?? { color: 7, linetype: "CONTINUOUS" as const };
    tables += pair(0, "LAYER") + pair(2, layer) + pair(70, 0) + pair(62, config.color) + pair(6, config.linetype);
  }
  tables += pair(0, "ENDTAB");
  tables += pair(0, "TABLE") + pair(2, "STYLE") + pair(70, 1);
  tables += pair(0, "STYLE") + pair(2, "STANDARD") + pair(70, 0) + pair(40, 0) + pair(41, 1) + pair(50, 0) + pair(71, 0) + pair(42, 2.5) + pair(3, "txt") + pair(4, "");
  tables += pair(0, "ENDTAB") + pair(0, "ENDSEC");

  let entities = pair(0, "SECTION") + pair(2, "ENTITIES");
  entities += entityToDxf({ type: "polyline", layer: "A-BORDER", closed: true, points: [
    { x: box.minX, y: box.minY }, { x: box.maxX, y: box.minY }, { x: box.maxX, y: box.maxY }, { x: box.minX, y: box.maxY },
  ] }, 0, 0);
  entities += entityToDxf({ type: "text", layer: "A-TEXT", at: { x: box.minX + 600, y: box.maxY - 600 }, height: 320, text: set.spec.projectName }, 0, 0);
  entities += entityToDxf({ type: "text", layer: "A-TEXT", at: { x: box.minX + 600, y: box.maxY - 1050 }, height: 150, text: `HS-CAD MOBILE ${set.engineVersion} | UNITS mm | ${set.views.length} VIEWS` }, 0, 0);
  for (const placement of placements) {
    entities += entityToDxf({ type: "text", layer: "A-TEXT", at: { x: 0, y: placement.view.height + 750 }, height: 260, text: placement.view.title }, placement.x, placement.y);
    for (const entity of placement.entities) entities += entityToDxf(entity, placement.x, placement.y);
  }
  entities += pair(0, "ENDSEC");

  const header = pair(0, "SECTION") + pair(2, "HEADER") +
    pair(9, "$ACADVER") + pair(1, "AC1009") +
    pair(9, "$INSUNITS") + pair(70, 4) +
    pair(9, "$MEASUREMENT") + pair(70, 1) +
    pair(9, "$EXTMIN") + pair(10, box.minX) + pair(20, box.minY) + pair(30, 0) +
    pair(9, "$EXTMAX") + pair(10, box.maxX) + pair(20, box.maxY) + pair(30, 0) +
    pair(0, "ENDSEC");
  const blocks = pair(0, "SECTION") + pair(2, "BLOCKS") + pair(0, "ENDSEC");
  return header + tables + blocks + entities + pair(0, "EOF");
};
