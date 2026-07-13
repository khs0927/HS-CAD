import type { DrawingSet, DrawingView, Entity } from "./types";

const esc = (value: string): string => value.replace(/[&<>\"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[character]!);

const entitySvg = (entity: Entity, height: number): string => {
  const y = (value: number) => height - value;
  if (entity.type === "line") return `<line x1="${entity.start.x}" y1="${y(entity.start.y)}" x2="${entity.end.x}" y2="${y(entity.end.y)}" class="${entity.layer}" />`;
  if (entity.type === "polyline") {
    const points = entity.points.map((point) => `${point.x},${y(point.y)}`).join(" ");
    return entity.closed ? `<polygon points="${points}" class="${entity.layer}" />` : `<polyline points="${points}" class="${entity.layer}" />`;
  }
  if (entity.type === "arc") {
    const a1 = (entity.startAngle * Math.PI) / 180;
    const a2 = (entity.endAngle * Math.PI) / 180;
    const p1 = { x: entity.center.x + entity.radius * Math.cos(a1), y: entity.center.y + entity.radius * Math.sin(a1) };
    const p2 = { x: entity.center.x + entity.radius * Math.cos(a2), y: entity.center.y + entity.radius * Math.sin(a2) };
    let delta = ((entity.endAngle - entity.startAngle) % 360 + 360) % 360;
    if (delta === 0) delta = 360;
    const largeArc = delta > 180 ? 1 : 0;
    return `<path d="M ${p1.x} ${y(p1.y)} A ${entity.radius} ${entity.radius} 0 ${largeArc} 0 ${p2.x} ${y(p2.y)}" class="${entity.layer}" />`;
  }
  if (entity.type === "circle") return `<circle cx="${entity.center.x}" cy="${y(entity.center.y)}" r="${entity.radius}" class="${entity.layer}" />`;
  return `<text x="${entity.at.x}" y="${y(entity.at.y)}" font-size="${entity.height}" transform="rotate(${-1 * (entity.rotation ?? 0)} ${entity.at.x} ${y(entity.at.y)})">${esc(entity.text)}</text>`;
};

const baseStyle = `
line,polyline,polygon,path,circle{fill:none;stroke:#111827;stroke-width:28;vector-effect:non-scaling-stroke;stroke-linecap:round;stroke-linejoin:round}
.A-WALL,.A-CUT{stroke-width:64}.A-CUT{fill:rgba(17,24,39,.08)}.A-WIND,.A-GLAZ,.A-VENT{stroke:#0369a1}.A-DOOR{stroke:#b45309}.A-HIDD,.A-GRID,.A-SECT,.A-CEIL{stroke:#64748b;stroke-dasharray:160 100}.A-DIMS,.A-LEVEL{stroke:#7c3aed}.A-ROOF{stroke:#be123c}.A-FURN{stroke:#64748b}.A-MATL,.A-PLIN,.A-HATCH{stroke:#94a3b8;stroke-width:12}.A-DRAIN{stroke:#0891b2}.A-STRS{stroke:#475569}text{fill:#111827;font-family:Arial,'Noto Sans KR',sans-serif}.A-NOTE{fill:#334155}`;

export const viewToSvg = (view: DrawingView): string => {
  const margin = 850;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${-margin} ${-margin} ${view.width + margin * 2} ${view.height + margin * 2}" role="img" aria-label="${esc(view.title)}">
<style>${baseStyle}</style>${view.entities.map((entity) => entitySvg(entity, view.height)).join("")}</svg>`;
};

export const drawingSetToSvgSheet = (set: DrawingSet): string => {
  const cardW = 1600;
  const cardH = 1120;
  const cols = 2;
  const rows = Math.ceil(set.views.length / cols);
  const body = set.views.map((view, index) => {
    const x = (index % cols) * cardW;
    const y = Math.floor(index / cols) * cardH;
    const scale = Math.min((cardW - 160) / Math.max(view.width, 1), (cardH - 240) / Math.max(view.height, 1));
    const tx = x + 80;
    const ty = y + 180;
    return `<g transform="translate(${tx} ${ty}) scale(${scale})"><text x="0" y="-130" font-size="190">${esc(view.title)}</text>${view.entities.map((entity) => entitySvg(entity, view.height)).join("")}</g>`;
  }).join("");
  const header = `<text x="80" y="80" font-size="34" font-weight="700">${esc(set.spec.projectName)}</text><text x="80" y="125" font-size="20">HS-CAD Mobile ${esc(set.engineVersion)} · ${set.views.length} views · units mm</text>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${cardW * cols} ${cardH * rows + 160}"><rect width="100%" height="100%" fill="white"/><style>${baseStyle}</style>${header}<g transform="translate(0 160)">${body}</g></svg>`;
};
