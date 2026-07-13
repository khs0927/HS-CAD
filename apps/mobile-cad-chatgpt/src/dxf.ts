import type { DrawingSet, DrawingView, Entity, Point } from "./types";

const pair = (code: number, value: string | number): string => `${code}\n${value}\n`;
const pt = (p: Point, ox: number, oy: number): Point => ({ x: p.x + ox, y: p.y + oy });
const ascii = (value: string): string => value.normalize("NFKD").replace(/[^\x20-\x7E]/g, "?");

const layerConfig: Record<string, { color: number; linetype: "CONTINUOUS" | "DASHED"; lineweight: number }> = {
  "A-WALL": { color: 7, linetype: "CONTINUOUS", lineweight: 50 },
  "A-CUT": { color: 1, linetype: "CONTINUOUS", lineweight: 70 },
  "A-ELEV": { color: 7, linetype: "CONTINUOUS", lineweight: 35 },
  "A-ROOF": { color: 5, linetype: "CONTINUOUS", lineweight: 35 },
  "A-DOOR": { color: 30, linetype: "CONTINUOUS", lineweight: 25 },
  "A-WIND": { color: 4, linetype: "CONTINUOUS", lineweight: 25 },
  "A-GLAZ": { color: 151, linetype: "CONTINUOUS", lineweight: 15 },
  "A-OPEN": { color: 3, linetype: "CONTINUOUS", lineweight: 20 },
  "A-STRS": { color: 6, linetype: "CONTINUOUS", lineweight: 25 },
  "A-FURN": { color: 8, linetype: "CONTINUOUS", lineweight: 15 },
  "A-DIMS": { color: 2, linetype: "CONTINUOUS", lineweight: 15 },
  "A-TEXT": { color: 7, linetype: "CONTINUOUS", lineweight: 15 },
  "A-NOTE": { color: 7, linetype: "CONTINUOUS", lineweight: 15 },
  "A-ANNO": { color: 6, linetype: "CONTINUOUS", lineweight: 15 },
  "A-SECT": { color: 1, linetype: "DASHED", lineweight: 25 },
  "A-HIDD": { color: 8, linetype: "DASHED", lineweight: 15 },
  "A-HATCH": { color: 8, linetype: "CONTINUOUS", lineweight: 9 },
  "A-MATL": { color: 9, linetype: "CONTINUOUS", lineweight: 9 },
  "A-PLIN": { color: 9, linetype: "CONTINUOUS", lineweight: 15 },
  "A-VENT": { color: 4, linetype: "CONTINUOUS", lineweight: 15 },
  "A-DRAIN": { color: 3, linetype: "CONTINUOUS", lineweight: 20 },
  "A-GRID": { color: 8, linetype: "DASHED", lineweight: 9 },
  "A-LEVEL": { color: 2, linetype: "CONTINUOUS", lineweight: 15 },
  "A-CEIL": { color: 6, linetype: "DASHED", lineweight: 15 },
  "A-BORDER": { color: 7, linetype: "CONTINUOUS", lineweight: 50 },
};

const entityToDxf = (entity: Entity, ox: number, oy: number): string => {
  if (entity.type === "line") {
    const a = pt(entity.start, ox, oy);
    const b = pt(entity.end, ox, oy);
    return pair(0, "LINE") + pair(8, entity.layer) + pair(10, a.x) + pair(20, a.y) + pair(30, 0) + pair(11, b.x) + pair(21, b.y) + pair(31, 0);
  }
  if (entity.type === "polyline") {
    let out = pair(0, "POLYLINE") + pair(8, entity.layer) + pair(66, 1) + pair(70, entity.closed ? 1 : 0);
    for (const point of entity.points) {
      const p = pt(point, ox, oy);
      out += pair(0, "VERTEX") + pair(8, entity.layer) + pair(10, p.x) + pair(20, p.y) + pair(30, 0);
    }
    return out + pair(0, "SEQEND") + pair(8, entity.layer);
  }
  if (entity.type === "arc") {
    const c = pt(entity.center, ox, oy);
    return pair(0, "ARC") + pair(8, entity.layer) + pair(10, c.x) + pair(20, c.y) + pair(30, 0) + pair(40, entity.radius) + pair(50, entity.startAngle) + pair(51, entity.endAngle);
  }
  if (entity.type === "circle") {
    const c = pt(entity.center, ox, oy);
    return pair(0, "CIRCLE") + pair(8, entity.layer) + pair(10, c.x) + pair(20, c.y) + pair(30, 0) + pair(40, entity.radius);
  }
  const p = pt(entity.at, ox, oy);
  return pair(0, "TEXT") + pair(8, entity.layer) + pair(10, p.x) + pair(20, p.y) + pair(30, 0) + pair(40, entity.height) + pair(1, ascii(entity.text)) + pair(50, entity.rotation ?? 0) + pair(7, "STANDARD");
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

const extents = (placements: Array<{ view: DrawingView; x: number; y: number }>): { minX: number; minY: number; maxX: number; maxY: number } => ({
  minX: Math.min(...placements.map((item) => item.x)) - 1800,
  minY: Math.min(...placements.map((item) => item.y - 1800)),
  maxX: Math.max(...placements.map((item) => item.x + item.view.width)) + 1800,
  maxY: Math.max(...placements.map((item) => item.y + item.view.height)) + 1800,
});

export const drawingSetToDxf = (set: DrawingSet): string => {
  const placements = layoutViews(set.views);
  const allLayers = new Set(set.views.flatMap((view) => view.entities.map((entity) => entity.layer)));
  allLayers.add("A-TEXT");
  allLayers.add("A-BORDER");
  const layers = [...allLayers].sort();
  const box = extents(placements);

  let tables = pair(0, "SECTION") + pair(2, "TABLES");
  tables += pair(0, "TABLE") + pair(2, "LTYPE") + pair(70, 2);
  tables += pair(0, "LTYPE") + pair(2, "CONTINUOUS") + pair(70, 0) + pair(3, "Solid line") + pair(72, 65) + pair(73, 0) + pair(40, 0);
  tables += pair(0, "LTYPE") + pair(2, "DASHED") + pair(70, 0) + pair(3, "Dashed") + pair(72, 65) + pair(73, 2) + pair(40, 240) + pair(49, 160) + pair(74, 0) + pair(49, -80) + pair(74, 0);
  tables += pair(0, "ENDTAB");
  tables += pair(0, "TABLE") + pair(2, "LAYER") + pair(70, layers.length);
  for (const layer of layers) {
    const config = layerConfig[layer] ?? { color: 7, linetype: "CONTINUOUS" as const, lineweight: 15 };
    tables += pair(0, "LAYER") + pair(2, layer) + pair(70, 0) + pair(62, config.color) + pair(6, config.linetype);
  }
  tables += pair(0, "ENDTAB");
  tables += pair(0, "TABLE") + pair(2, "STYLE") + pair(70, 1);
  tables += pair(0, "STYLE") + pair(2, "STANDARD") + pair(70, 0) + pair(40, 0) + pair(41, 1) + pair(50, 0) + pair(71, 0) + pair(42, 2.5) + pair(3, "txt") + pair(4, "");
  tables += pair(0, "ENDTAB") + pair(0, "ENDSEC");

  let entities = pair(0, "SECTION") + pair(2, "ENTITIES");
  entities += pair(0, "POLYLINE") + pair(8, "A-BORDER") + pair(66, 1) + pair(70, 1);
  for (const p of [{ x: box.minX, y: box.minY }, { x: box.maxX, y: box.minY }, { x: box.maxX, y: box.maxY }, { x: box.minX, y: box.maxY }]) {
    entities += pair(0, "VERTEX") + pair(8, "A-BORDER") + pair(10, p.x) + pair(20, p.y) + pair(30, 0);
  }
  entities += pair(0, "SEQEND") + pair(8, "A-BORDER");
  entities += pair(0, "TEXT") + pair(8, "A-TEXT") + pair(10, box.minX + 600) + pair(20, box.maxY - 600) + pair(30, 0) + pair(40, 320) + pair(1, ascii(set.spec.projectName)) + pair(7, "STANDARD");
  entities += pair(0, "TEXT") + pair(8, "A-TEXT") + pair(10, box.minX + 600) + pair(20, box.maxY - 1050) + pair(30, 0) + pair(40, 150) + pair(1, `HS-CAD MOBILE ${set.engineVersion} | UNITS mm | ${set.views.length} VIEWS`) + pair(7, "STANDARD");
  for (const placement of placements) {
    entities += pair(0, "TEXT") + pair(8, "A-TEXT") + pair(10, placement.x) + pair(20, placement.y + placement.view.height + 750) + pair(30, 0) + pair(40, 260) + pair(1, ascii(placement.view.title)) + pair(7, "STANDARD");
    for (const entity of placement.view.entities) entities += entityToDxf(entity, placement.x, placement.y);
  }
  entities += pair(0, "ENDSEC");

  const header = pair(0, "SECTION") + pair(2, "HEADER") +
    pair(9, "$ACADVER") + pair(1, "AC1009") +
    pair(9, "$INSUNITS") + pair(70, 4) +
    pair(9, "$EXTMIN") + pair(10, box.minX) + pair(20, box.minY) + pair(30, 0) +
    pair(9, "$EXTMAX") + pair(10, box.maxX) + pair(20, box.maxY) + pair(30, 0) +
    pair(0, "ENDSEC");
  return header + tables + entities + pair(0, "EOF");
};
