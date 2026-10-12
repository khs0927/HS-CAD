import type { DrawingSet, DrawingView, Entity, Point } from "./types";

const EPS = 1e-6;
const esc = (value: string): string => value.replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]!);
const finite = (value: number, label: string): number => {
  if (!Number.isFinite(value)) throw new TypeError(`SVG ${label} must be finite`);
  return Object.is(value, -0) ? 0 : value;
};
const fmt = (value: number): string => {
  const numeric = finite(value, "number");
  return Number(numeric.toFixed(6)).toString();
};
const safeClass = (value: string): string => {
  let safe = value.normalize("NFKD").toUpperCase().replace(/[^A-Z0-9_-]+/g, "_").replace(/^_+|_+$/g, "");
  if (!safe) safe = "A-ANNO";
  if (!safe.startsWith("A-")) safe = `A-${safe}`;
  return safe.slice(0, 31);
};
const normalizeAngle = (value: number): number => ((finite(value, "angle") % 360) + 360) % 360;
const samePoint = (first: Point, second: Point): boolean => Math.abs(first.x - second.x) <= EPS && Math.abs(first.y - second.y) <= EPS;

type Bounds = { minX: number; minY: number; maxX: number; maxY: number };
const emptyBounds = (): Bounds => ({ minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity });
const includePoint = (box: Bounds, point: Point): void => {
  box.minX = Math.min(box.minX, finite(point.x, "x"));
  box.minY = Math.min(box.minY, finite(point.y, "y"));
  box.maxX = Math.max(box.maxX, finite(point.x, "x"));
  box.maxY = Math.max(box.maxY, finite(point.y, "y"));
};

const includeEntity = (box: Bounds, entity: Entity): void => {
  if (entity.type === "line") {
    if (samePoint(entity.start, entity.end)) throw new TypeError("SVG zero-length LINE is not allowed");
    includePoint(box, entity.start);
    includePoint(box, entity.end);
  } else if (entity.type === "polyline") {
    if (entity.points.length < (entity.closed ? 3 : 2)) throw new TypeError("SVG degenerate POLYLINE is not allowed");
    for (const point of entity.points) includePoint(box, point);
  } else if (entity.type === "arc" || entity.type === "circle") {
    const radius = finite(entity.radius, "radius");
    if (radius <= EPS) throw new TypeError("SVG radius must be positive");
    includePoint(box, { x: entity.center.x - radius, y: entity.center.y - radius });
    includePoint(box, { x: entity.center.x + radius, y: entity.center.y + radius });
  } else {
    const height = finite(entity.height, "text height");
    if (height <= EPS) throw new TypeError("SVG text height must be positive");
    includePoint(box, entity.at);
    includePoint(box, { x: entity.at.x + Math.max(height, entity.text.length * height * 0.7), y: entity.at.y + height });
  }
};

const originalBounds = (view: DrawingView): Bounds => {
  const box = emptyBounds();
  for (const entity of view.entities) includeEntity(box, entity);
  if (![box.minX, box.minY, box.maxX, box.maxY].every(Number.isFinite)) {
    includePoint(box, { x: 0, y: 0 });
    includePoint(box, { x: Math.max(view.width, 1), y: Math.max(view.height, 1) });
  }
  return box;
};

const transformedBounds = (view: DrawingView): Bounds => {
  const box = originalBounds(view);
  return { minX: box.minX, minY: view.height - box.maxY, maxX: box.maxX, maxY: view.height - box.minY };
};

const entitySvg = (entity: Entity, height: number): string => {
  const y = (value: number) => finite(height - value, "y");
  const className = safeClass(entity.layer);
  if (entity.type === "line") {
    if (samePoint(entity.start, entity.end)) throw new TypeError("SVG zero-length LINE is not allowed");
    return `<line x1="${fmt(entity.start.x)}" y1="${fmt(y(entity.start.y))}" x2="${fmt(entity.end.x)}" y2="${fmt(y(entity.end.y))}" class="${className}" />`;
  }
  if (entity.type === "polyline") {
    if (entity.points.length < (entity.closed ? 3 : 2)) throw new TypeError("SVG degenerate POLYLINE is not allowed");
    const points = entity.points.map((point) => `${fmt(point.x)},${fmt(y(point.y))}`).join(" ");
    return entity.closed ? `<polygon points="${points}" class="${className}" />` : `<polyline points="${points}" class="${className}" />`;
  }
  if (entity.type === "arc") {
    const radius = finite(entity.radius, "arc radius");
    if (radius <= EPS) throw new TypeError("SVG arc radius must be positive");
    const startAngle = normalizeAngle(entity.startAngle);
    const endAngle = normalizeAngle(entity.endAngle);
    const a1 = startAngle * Math.PI / 180;
    const a2 = endAngle * Math.PI / 180;
    const p1 = { x: entity.center.x + radius * Math.cos(a1), y: entity.center.y + radius * Math.sin(a1) };
    const p2 = { x: entity.center.x + radius * Math.cos(a2), y: entity.center.y + radius * Math.sin(a2) };
    const delta = normalizeAngle(endAngle - startAngle);
    if (delta <= EPS) throw new TypeError("SVG degenerate ARC is not allowed");
    const largeArc = delta > 180 ? 1 : 0;
    return `<path d="M ${fmt(p1.x)} ${fmt(y(p1.y))} A ${fmt(radius)} ${fmt(radius)} 0 ${largeArc} 0 ${fmt(p2.x)} ${fmt(y(p2.y))}" class="${className}" />`;
  }
  if (entity.type === "circle") {
    const radius = finite(entity.radius, "circle radius");
    if (radius <= EPS) throw new TypeError("SVG circle radius must be positive");
    return `<circle cx="${fmt(entity.center.x)}" cy="${fmt(y(entity.center.y))}" r="${fmt(radius)}" class="${className}" />`;
  }
  const textY = y(entity.at.y);
  return `<text x="${fmt(entity.at.x)}" y="${fmt(textY)}" font-size="${fmt(entity.height)}" class="${className}" transform="rotate(${fmt(-normalizeAngle(entity.rotation ?? 0))} ${fmt(entity.at.x)} ${fmt(textY)})">${esc(entity.text)}</text>`;
};

const baseStyle = `
line,polyline,polygon,path,circle{fill:none;stroke:#111827;stroke-width:28;vector-effect:non-scaling-stroke;stroke-linecap:round;stroke-linejoin:round}
.A-WALL,.A-CUT{stroke-width:64}.A-CUT{fill:rgba(17,24,39,.08)}.A-WIND,.A-GLAZ,.A-VENT{stroke:#0369a1}.A-DOOR{stroke:#b45309}.A-HIDD,.A-GRID,.A-SECT,.A-CEIL{stroke:#64748b;stroke-dasharray:160 100}.A-DIMS,.A-LEVEL{stroke:#7c3aed}.A-ROOF{stroke:#be123c}.A-FURN,.A-FIXT{stroke:#64748b}.A-COLS{stroke:#991b1b}.A-MATL,.A-PLIN,.A-HATCH{stroke:#94a3b8;stroke-width:12}.A-DRAIN{stroke:#0891b2}.A-STRS{stroke:#475569}text{fill:#111827;font-family:Arial,'Noto Sans KR',sans-serif}.A-NOTE{fill:#334155}`;

export const viewToSvg = (view: DrawingView): string => {
  const margin = 850;
  const box = transformedBounds(view);
  const width = Math.max(1, box.maxX - box.minX + margin * 2);
  const height = Math.max(1, box.maxY - box.minY + margin * 2);
  return `<svg xmlns="http://www.w3.org/2000/svg" data-view-id="${esc(view.id)}" viewBox="${fmt(box.minX - margin)} ${fmt(box.minY - margin)} ${fmt(width)} ${fmt(height)}" role="img" aria-label="${esc(view.title)}">
<style>${baseStyle}</style>${view.entities.map((entity) => entitySvg(entity, view.height)).join("")}</svg>`;
};

export const drawingSetToSvgSheet = (set: DrawingSet): string => {
  const cardW = 1600;
  const cardH = 1120;
  const cols = 2;
  const rows = Math.ceil(set.views.length / cols);
  const body = set.views.map((view, index) => {
    const cardX = index % cols * cardW;
    const cardY = Math.floor(index / cols) * cardH;
    const box = transformedBounds(view);
    const geometryWidth = Math.max(box.maxX - box.minX, 1);
    const geometryHeight = Math.max(box.maxY - box.minY, 1);
    const scale = Math.min((cardW - 160) / geometryWidth, (cardH - 250) / geometryHeight);
    const tx = cardX + 80 - box.minX * scale;
    const ty = cardY + 190 - box.minY * scale;
    return `<g data-view-id="${esc(view.id)}"><text x="${fmt(cardX + 80)}" y="${fmt(cardY + 105)}" font-size="30" class="A-TEXT">${esc(view.title)}</text><g transform="translate(${fmt(tx)} ${fmt(ty)}) scale(${fmt(scale)})">${view.entities.map((entity) => entitySvg(entity, view.height)).join("")}</g></g>`;
  }).join("");
  const header = `<text x="80" y="80" font-size="34" font-weight="700" class="A-TEXT">${esc(set.spec.projectName)}</text><text x="80" y="125" font-size="20" class="A-TEXT">HS-CAD Mobile ${esc(set.engineVersion)} · ${set.views.length} views · units mm</text>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" data-drawing-set="${esc(set.spec.schemaVersion ?? "legacy")}" viewBox="0 0 ${fmt(cardW * cols)} ${fmt(cardH * rows + 160)}"><rect width="100%" height="100%" fill="white"/><style>${baseStyle}</style>${header}<g transform="translate(0 160)">${body}</g></svg>`;
};
