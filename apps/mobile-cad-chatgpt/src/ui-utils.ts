import type {
  BuildingSpec,
  DrawingMetrics,
  DrawingSet,
  DrawingView,
  Entity,
  Opening,
  OpeningScheduleRow,
  Point,
  Segment,
  StairSpec,
  ValidationIssue,
  ViewKind,
} from "./types";
import { BUILDING_SCHEMA_VERSION } from "./types";

export const VIEW_KINDS: ViewKind[] = ["plan", "front", "rear", "left", "right", "section-a", "section-b"];
export const SAFE_LAYER_PATTERN = /^A-[A-Z0-9_-]{1,32}$/;

export type ArtifactBundle = {
  dxf?: string;
  sheetSvg?: string;
  viewSvgs: Partial<Record<ViewKind, string>>;
  projectJson?: string;
};

export type HydratedResult = {
  drawing?: DrawingSet;
  artifacts: ArtifactBundle;
  summarySpec?: BuildingSpec;
  summaryWarnings: string[];
  valid?: boolean;
  issues: ValidationIssue[];
  errors: string[];
};

export type SpecValidation = {
  spec?: BuildingSpec;
  errors: string[];
};

export type JsonEditorMode = "basic" | "advanced";

const BASIC_KEYS = [
  "schemaVersion",
  "projectName",
  "unit",
  "width",
  "depth",
  "wallThickness",
  "eaveHeight",
  "ridgeHeight",
  "atticFloorHeight",
  "ceilingHeight",
  "roofDirection",
  "roofOverhang",
  "roofThickness",
  "floorSlabThickness",
  "foundationDepth",
  "roofFinish",
  "wallFinish",
  "plinthFinish",
  "drawingScale",
  "atticMinimumClearHeight",
  "frameFinish",
  "gutterDownspoutSpec",
] as const;

const ADVANCED_KEYS = [
  "outline", "wallIds", "interiorWalls", "openings", "stair", "stairEnabled",
  "roomLabels", "gridAxes", "sectionCuts", "symbols", "facadeFeatures",
] as const;

const SPEC_KEYS = new Set<string>([...BASIC_KEYS, ...ADVANCED_KEYS]);

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value);

const boundedNumber = (
  record: Record<string, unknown>,
  key: string,
  min: number,
  max: number,
  errors: string[],
): number | undefined => {
  const value = record[key];
  if (!isFiniteNumber(value) || value < min || value > max) {
    errors.push(`${key} 값은 ${min}~${max} 범위의 숫자여야 합니다.`);
    return undefined;
  }
  return value;
};

const boundedString = (
  record: Record<string, unknown>,
  key: string,
  max: number,
  errors: string[],
): string | undefined => {
  const value = record[key];
  if (typeof value !== "string" || !value.trim() || value.length > max) {
    errors.push(`${key} 값은 비어 있지 않은 ${max}자 이하 문자열이어야 합니다.`);
    return undefined;
  }
  return value.trim();
};

const pointFrom = (value: unknown, path: string, errors: string[]): Point | undefined => {
  if (!isRecord(value) || !isFiniteNumber(value.x) || !isFiniteNumber(value.y)) {
    errors.push(`${path}에는 유효한 x, y 좌표가 필요합니다.`);
    return undefined;
  }
  if (Math.abs(value.x) > 1_000_000 || Math.abs(value.y) > 1_000_000) {
    errors.push(`${path} 좌표가 허용 범위를 벗어났습니다.`);
    return undefined;
  }
  return { x: value.x, y: value.y };
};

const orientation = (a: Point, b: Point, c: Point): number =>
  (b.y - a.y) * (c.x - b.x) - (b.x - a.x) * (c.y - b.y);

const onSegment = (a: Point, b: Point, c: Point): boolean =>
  b.x <= Math.max(a.x, c.x) && b.x >= Math.min(a.x, c.x) &&
  b.y <= Math.max(a.y, c.y) && b.y >= Math.min(a.y, c.y);

const segmentsIntersect = (a: Point, b: Point, c: Point, d: Point): boolean => {
  const o1 = orientation(a, b, c);
  const o2 = orientation(a, b, d);
  const o3 = orientation(c, d, a);
  const o4 = orientation(c, d, b);
  if (o1 === 0 && onSegment(a, c, b)) return true;
  if (o2 === 0 && onSegment(a, d, b)) return true;
  if (o3 === 0 && onSegment(c, a, d)) return true;
  if (o4 === 0 && onSegment(c, b, d)) return true;
  return (o1 > 0) !== (o2 > 0) && (o3 > 0) !== (o4 > 0);
};

const outlineIsSelfIntersecting = (points: Point[]): boolean => {
  for (let index = 0; index < points.length; index += 1) {
    const next = (index + 1) % points.length;
    for (let other = index + 1; other < points.length; other += 1) {
      const otherNext = (other + 1) % points.length;
      if (index === other || next === other || otherNext === index) continue;
      if (segmentsIntersect(points[index], points[next], points[other], points[otherNext])) return true;
    }
  }
  return false;
};

const polygonArea = (points: Point[]): number => Math.abs(points.reduce((sum, point, index) => {
  const next = points[(index + 1) % points.length];
  return sum + point.x * next.y - next.x * point.y;
}, 0) / 2);

const outlineFrom = (value: unknown, errors: string[]): Point[] | undefined => {
  if (value === undefined) return undefined;
  if (!Array.isArray(value) || value.length < 3 || value.length > 64) {
    errors.push("outline은 3~64개 좌표의 배열이어야 합니다.");
    return undefined;
  }
  const points = value.map((point, index) => pointFrom(point, `outline[${index}]`, errors));
  if (points.some((point) => !point)) return undefined;
  const result = points as Point[];
  if (polygonArea(result) < 1_000_000) errors.push("outline 면적은 최소 1㎡ 이상이어야 합니다.");
  if (outlineIsSelfIntersecting(result)) errors.push("outline은 자기 교차할 수 없습니다.");
  return result;
};

const segmentFrom = (value: unknown, path: string, errors: string[]): Segment | undefined => {
  if (!isRecord(value)) {
    errors.push(`${path}는 선분 객체여야 합니다.`);
    return undefined;
  }
  const start = pointFrom(value.start, `${path}.start`, errors);
  const end = pointFrom(value.end, `${path}.end`, errors);
  const thickness = value.thickness;
  if (thickness !== undefined && (!isFiniteNumber(thickness) || thickness < 20 || thickness > 2_000)) {
    errors.push(`${path}.thickness는 20~2000 범위여야 합니다.`);
  }
  const layer = value.layer;
  if (layer !== undefined && (typeof layer !== "string" || !SAFE_LAYER_PATTERN.test(layer))) {
    errors.push(`${path}.layer는 A-로 시작하는 안전한 CAD 레이어 이름이어야 합니다.`);
  }
  if (!start || !end || errors.some((error) => error.startsWith(path))) return undefined;
  return {
    ...(typeof value.id === "string" && value.id.length <= 64 ? { id: value.id } : {}),
    start,
    end,
    ...(isFiniteNumber(thickness) ? { thickness } : {}),
    ...(typeof layer === "string" ? { layer } : {}),
  };
};

const openingFrom = (value: unknown, path: string, errors: string[]): Opening | undefined => {
  if (!isRecord(value)) {
    errors.push(`${path}는 개구부 객체여야 합니다.`);
    return undefined;
  }
  const kind = value.kind;
  const wallIndex = value.wallIndex;
  const wallId = value.wallId;
  const offset = value.offset;
  const width = value.width;
  const height = value.height;
  const sill = value.sill;
  const swing = value.swing;
  const openingDirection = value.openingDirection;
  const panelType = value.panelType;
  const placement = value.placement;
  const label = value.label;
  if (kind !== "door" && kind !== "window") errors.push(`${path}.kind는 door 또는 window여야 합니다.`);
  if ((wallIndex === undefined || !Number.isInteger(wallIndex) || (wallIndex as number) < 0) &&
    (typeof wallId !== "string" || !/^[A-Za-z0-9_-]{1,64}$/.test(wallId))) {
    errors.push(`${path} requires a valid wallId or wallIndex.`);
  }
  if (!isFiniteNumber(offset) || offset < 0) errors.push(`${path}.offset은 0 이상이어야 합니다.`);
  if (!isFiniteNumber(width) || width <= 0 || width > 20_000) errors.push(`${path}.width가 올바르지 않습니다.`);
  if (!isFiniteNumber(height) || height <= 0 || height > 20_000) errors.push(`${path}.height가 올바르지 않습니다.`);
  if (sill !== undefined && (!isFiniteNumber(sill) || sill < 0 || sill > 20_000)) errors.push(`${path}.sill이 올바르지 않습니다.`);
  if (swing !== undefined && swing !== "left" && swing !== "right" && swing !== "double") errors.push(`${path}.swing이 올바르지 않습니다.`);
  if (openingDirection !== undefined && openingDirection !== "in" && openingDirection !== "out") errors.push(`${path}.openingDirection is invalid.`);
  if (panelType !== undefined && !["fixed", "single", "double", "sliding", "louvered"].includes(String(panelType))) errors.push(`${path}.panelType is invalid.`);
  if (placement !== undefined && placement !== "main" && placement !== "attic") errors.push(`${path}.placement is invalid.`);
  if (label !== undefined && (typeof label !== "string" || label.length > 24)) errors.push(`${path}.label은 24자 이하여야 합니다.`);
  if (errors.some((error) => error.startsWith(path))) return undefined;
  return {
    kind: kind as Opening["kind"],
    ...(Number.isInteger(wallIndex) ? { wallIndex: wallIndex as number } : {}),
    ...(typeof wallId === "string" ? { wallId } : {}),
    offset: offset as number,
    width: width as number,
    height: height as number,
    ...(isFiniteNumber(sill) ? { sill } : {}),
    ...(typeof swing === "string" ? { swing: swing as Opening["swing"] } : {}),
    ...(typeof openingDirection === "string" ? { openingDirection: openingDirection as Opening["openingDirection"] } : {}),
    ...(typeof panelType === "string" ? { panelType: panelType as Opening["panelType"] } : {}),
    ...(typeof placement === "string" ? { placement: placement as Opening["placement"] } : {}),
    ...(typeof label === "string" ? { label } : {}),
  };
};

const stairFrom = (value: unknown, errors: string[]): StairSpec | undefined => {
  if (value === undefined) return undefined;
  const errorStart = errors.length;
  if (!isRecord(value)) {
    errors.push("stair는 계단 객체여야 합니다.");
    return undefined;
  }
  const direction = value.direction;
  const allowedDirections = ["up-north", "up-south", "up-east", "up-west"];
  const x = boundedNumber(value, "x", -1_000_000, 1_000_000, errors);
  const y = boundedNumber(value, "y", -1_000_000, 1_000_000, errors);
  const width = boundedNumber(value, "width", 100, 20_000, errors);
  const length = boundedNumber(value, "length", 100, 50_000, errors);
  const risers = boundedNumber(value, "risers", 3, 40, errors);
  if (!Number.isInteger(risers)) errors.push("stair.risers는 정수여야 합니다.");
  if (typeof direction !== "string" || !allowedDirections.includes(direction)) errors.push("stair.direction이 올바르지 않습니다.");
  if (x === undefined || y === undefined || width === undefined || length === undefined || risers === undefined || typeof direction !== "string") return undefined;
  const treadDepth = value.treadDepth;
  const landingDepth = value.landingDepth;
  const railing = value.railing;
  const showDownArrow = value.showDownArrow;
  if (treadDepth !== undefined && (!isFiniteNumber(treadDepth) || treadDepth < 100 || treadDepth > 1_000)) errors.push("stair.treadDepth is invalid.");
  if (landingDepth !== undefined && (!isFiniteNumber(landingDepth) || landingDepth < 100 || landingDepth > 5_000)) errors.push("stair.landingDepth is invalid.");
  if (railing !== undefined && !["none", "left", "right", "both"].includes(String(railing))) errors.push("stair.railing is invalid.");
  if (showDownArrow !== undefined && typeof showDownArrow !== "boolean") errors.push("stair.showDownArrow is invalid.");
  if (errors.length > errorStart) return undefined;
  return {
    x, y, width, length, risers, direction: direction as StairSpec["direction"],
    ...(isFiniteNumber(treadDepth) ? { treadDepth } : {}),
    ...(isFiniteNumber(landingDepth) ? { landingDepth } : {}),
    ...(typeof railing === "string" ? { railing: railing as StairSpec["railing"] } : {}),
    ...(typeof showDownArrow === "boolean" ? { showDownArrow } : {}),
  };
};

const optionalString = (value: unknown, path: string, max: number, errors: string[]): string | undefined => {
  if (value === undefined) return undefined;
  if (typeof value !== "string" || value.length > max) {
    errors.push(`${path} must be a string no longer than ${max} characters.`);
    return undefined;
  }
  return value;
};

const optionalNumber = (value: unknown, path: string, min: number, max: number, errors: string[]): number | undefined => {
  if (value === undefined) return undefined;
  if (!isFiniteNumber(value) || value < min || value > max) {
    errors.push(`${path} must be between ${min} and ${max}.`);
    return undefined;
  }
  return value;
};

const pointArrayFrom = (value: unknown, path: string, min: number, max: number, errors: string[]): Point[] | undefined => {
  if (!Array.isArray(value) || value.length < min || value.length > max) {
    errors.push(`${path} must contain ${min}-${max} points.`);
    return undefined;
  }
  const points = value.map((point, index) => pointFrom(point, `${path}[${index}]`, errors));
  return points.some((point) => !point) ? undefined : points as Point[];
};

const extensionFieldsFrom = (value: Record<string, unknown>, errors: string[]): Partial<BuildingSpec> => {
  const extensions: Partial<BuildingSpec> = {};
  const drawingScale = optionalString(value.drawingScale, "drawingScale", 24, errors);
  const atticMinimumClearHeight = optionalNumber(value.atticMinimumClearHeight, "atticMinimumClearHeight", 600, 5_000, errors);
  const frameFinish = optionalString(value.frameFinish, "frameFinish", 120, errors);
  const gutterDownspoutSpec = optionalString(value.gutterDownspoutSpec, "gutterDownspoutSpec", 120, errors);
  if (drawingScale !== undefined) extensions.drawingScale = drawingScale;
  if (atticMinimumClearHeight !== undefined) extensions.atticMinimumClearHeight = atticMinimumClearHeight;
  if (frameFinish !== undefined) extensions.frameFinish = frameFinish;
  if (gutterDownspoutSpec !== undefined) extensions.gutterDownspoutSpec = gutterDownspoutSpec;

  if (value.wallIds !== undefined) {
    if (!Array.isArray(value.wallIds) || value.wallIds.length > 64 || value.wallIds.some((id) => typeof id !== "string" || !/^[A-Za-z0-9_-]{1,64}$/.test(id))) {
      errors.push("wallIds must be an array of safe identifiers.");
    } else {
      extensions.wallIds = [...value.wallIds] as string[];
    }
  }
  if (value.stairEnabled !== undefined) {
    if (typeof value.stairEnabled !== "boolean") errors.push("stairEnabled must be a boolean.");
    else extensions.stairEnabled = value.stairEnabled;
  }

  if (value.roomLabels !== undefined) {
    if (!Array.isArray(value.roomLabels) || value.roomLabels.length > 256) errors.push("roomLabels must contain at most 256 items.");
    else {
      const items: NonNullable<BuildingSpec["roomLabels"]> = [];
      for (const [index, item] of value.roomLabels.entries()) {
        const path = `roomLabels[${index}]`;
        if (!isRecord(item) || typeof item.name !== "string" || !item.name.trim() || item.name.length > 80) {
          errors.push(`${path}.name is invalid.`);
          continue;
        }
        const at = pointFrom(item.at, `${path}.at`, errors);
        const polygon = item.polygon === undefined ? undefined : pointArrayFrom(item.polygon, `${path}.polygon`, 3, 64, errors);
        if (at) items.push({ ...(typeof item.id === "string" ? { id: item.id.slice(0, 64) } : {}), name: item.name, at, ...(polygon ? { polygon } : {}) });
      }
      extensions.roomLabels = items;
    }
  }

  const parseAxes = (source: unknown, path: "gridAxes" | "sectionCuts", max: number): void => {
    if (source === undefined) return;
    if (!Array.isArray(source) || source.length > max) {
      errors.push(`${path} must contain at most ${max} items.`);
      return;
    }
    const items: Array<{ id: string; start: Point; end: Point }> = [];
    for (const [index, item] of source.entries()) {
      if (!isRecord(item) || typeof item.id !== "string" || !item.id.trim() || item.id.length > 64) {
        errors.push(`${path}[${index}].id is invalid.`);
        continue;
      }
      const start = pointFrom(item.start, `${path}[${index}].start`, errors);
      const end = pointFrom(item.end, `${path}[${index}].end`, errors);
      if (start && end) items.push({ id: item.id, start, end });
    }
    if (path === "gridAxes") extensions.gridAxes = items;
    else extensions.sectionCuts = items;
  };
  parseAxes(value.gridAxes, "gridAxes", 128);
  parseAxes(value.sectionCuts, "sectionCuts", 32);

  if (value.symbols !== undefined) {
    const allowedKinds = ["column", "sink", "toilet", "tub", "table", "chair", "cabinet", "label"];
    if (!Array.isArray(value.symbols) || value.symbols.length > 512) errors.push("symbols must contain at most 512 items.");
    else {
      const items: NonNullable<BuildingSpec["symbols"]> = [];
      for (const [index, item] of value.symbols.entries()) {
        const path = `symbols[${index}]`;
        if (!isRecord(item) || typeof item.kind !== "string" || !allowedKinds.includes(item.kind)) {
          errors.push(`${path}.kind is invalid.`);
          continue;
        }
        const at = pointFrom(item.at, `${path}.at`, errors);
        const width = optionalNumber(item.width, `${path}.width`, 0, 100_000, errors);
        const depth = optionalNumber(item.depth, `${path}.depth`, 0, 100_000, errors);
        const rotation = optionalNumber(item.rotation, `${path}.rotation`, -360_000, 360_000, errors);
        const label = optionalString(item.label, `${path}.label`, 120, errors);
        if (at) items.push({
          ...(typeof item.id === "string" ? { id: item.id.slice(0, 64) } : {}),
          kind: item.kind as NonNullable<BuildingSpec["symbols"]>[number]["kind"], at,
          ...(width !== undefined ? { width } : {}), ...(depth !== undefined ? { depth } : {}),
          ...(rotation !== undefined ? { rotation } : {}), ...(label !== undefined ? { label } : {}),
        });
      }
      extensions.symbols = items;
    }
  }

  if (value.facadeFeatures !== undefined) {
    const kinds = ["attic-window", "vent", "louver", "downspout"];
    const facades = ["front", "right", "rear", "left"];
    if (!Array.isArray(value.facadeFeatures) || value.facadeFeatures.length > 256) errors.push("facadeFeatures must contain at most 256 items.");
    else {
      const items: NonNullable<BuildingSpec["facadeFeatures"]> = [];
      for (const [index, item] of value.facadeFeatures.entries()) {
        const path = `facadeFeatures[${index}]`;
        if (!isRecord(item) || typeof item.kind !== "string" || !kinds.includes(item.kind) || typeof item.facade !== "string" || !facades.includes(item.facade)) {
          errors.push(`${path}.kind/facade is invalid.`);
          continue;
        }
        const offset = optionalNumber(item.offset, `${path}.offset`, 0, 100_000, errors);
        const width = optionalNumber(item.width, `${path}.width`, 0, 100_000, errors);
        const height = optionalNumber(item.height, `${path}.height`, 0, 100_000, errors);
        const sill = optionalNumber(item.sill, `${path}.sill`, 0, 100_000, errors);
        const label = optionalString(item.label, `${path}.label`, 120, errors);
        if (offset !== undefined) items.push({
          ...(typeof item.id === "string" ? { id: item.id.slice(0, 64) } : {}),
          kind: item.kind as NonNullable<BuildingSpec["facadeFeatures"]>[number]["kind"],
          facade: item.facade as NonNullable<BuildingSpec["facadeFeatures"]>[number]["facade"], offset,
          ...(width !== undefined ? { width } : {}), ...(height !== undefined ? { height } : {}),
          ...(sill !== undefined ? { sill } : {}), ...(label !== undefined ? { label } : {}),
        });
      }
      extensions.facadeFeatures = items;
    }
  }
  return extensions;
};

export const validateBuildingSpec = (value: unknown): SpecValidation => {
  if (!isRecord(value)) return { errors: ["설계 사양은 JSON 객체여야 합니다."] };
  const errors: string[] = [];
  const unknownKeys = Object.keys(value).filter((key) => !SPEC_KEYS.has(key));
  if (unknownKeys.length) errors.push(`Unknown BuildingSpec fields: ${unknownKeys.join(", ")}.`);
  if (value.schemaVersion !== undefined && value.schemaVersion !== BUILDING_SCHEMA_VERSION) {
    errors.push(`schemaVersion must be ${BUILDING_SCHEMA_VERSION}.`);
  }
  const projectName = boundedString(value, "projectName", 120, errors);
  if (value.unit !== "mm") errors.push("unit은 mm여야 합니다.");
  const width = boundedNumber(value, "width", 3_000, 50_000, errors);
  const depth = boundedNumber(value, "depth", 3_000, 50_000, errors);
  const wallThickness = boundedNumber(value, "wallThickness", 80, 600, errors);
  const eaveHeight = boundedNumber(value, "eaveHeight", 2_400, 15_000, errors);
  const ridgeHeight = boundedNumber(value, "ridgeHeight", 2_600, 20_000, errors);
  const atticFloorHeight = boundedNumber(value, "atticFloorHeight", 1_800, 12_000, errors);
  const ceilingHeight = boundedNumber(value, "ceilingHeight", 2_100, 10_000, errors);
  const roofOverhang = boundedNumber(value, "roofOverhang", 0, 2_000, errors);
  const roofThickness = boundedNumber(value, "roofThickness", 80, 800, errors);
  const floorSlabThickness = boundedNumber(value, "floorSlabThickness", 80, 800, errors);
  const foundationDepth = boundedNumber(value, "foundationDepth", 250, 4_000, errors);
  const roofFinish = boundedString(value, "roofFinish", 120, errors);
  const wallFinish = boundedString(value, "wallFinish", 120, errors);
  const plinthFinish = boundedString(value, "plinthFinish", 120, errors);
  const roofDirection = value.roofDirection;
  if (roofDirection !== "ridge-along-width" && roofDirection !== "ridge-along-depth") {
    errors.push("roofDirection 값이 올바르지 않습니다.");
  }
  if (isFiniteNumber(ridgeHeight) && isFiniteNumber(eaveHeight) && ridgeHeight <= eaveHeight) {
    errors.push("용마루 높이는 처마 높이보다 높아야 합니다.");
  }
  if (isFiniteNumber(atticFloorHeight) && isFiniteNumber(eaveHeight) && atticFloorHeight >= eaveHeight) {
    errors.push("다락 바닥 높이는 처마 높이보다 낮아야 합니다.");
  }
  if (isFiniteNumber(ceilingHeight) && isFiniteNumber(atticFloorHeight) && ceilingHeight > atticFloorHeight) {
    errors.push("실내 천장 높이는 다락 바닥 높이보다 높을 수 없습니다.");
  }

  const outline = outlineFrom(value.outline, errors);
  const extensions = extensionFieldsFrom(value, errors);
  if (outline && extensions.wallIds && outline.length !== extensions.wallIds.length) {
    errors.push("wallIds length must match outline length.");
  }
  let interiorWalls: Segment[] | undefined;
  if (value.interiorWalls !== undefined) {
    if (!Array.isArray(value.interiorWalls) || value.interiorWalls.length > 128) {
      errors.push("interiorWalls는 최대 128개 선분의 배열이어야 합니다.");
    } else {
      const parsed = value.interiorWalls.map((item, index) => segmentFrom(item, `interiorWalls[${index}]`, errors));
      if (!parsed.some((item) => !item)) interiorWalls = parsed as Segment[];
    }
  }
  let openings: Opening[] | undefined;
  if (value.openings !== undefined) {
    if (!Array.isArray(value.openings) || value.openings.length > 128) {
      errors.push("openings는 최대 128개 개구부의 배열이어야 합니다.");
    } else {
      const parsed = value.openings.map((item, index) => openingFrom(item, `openings[${index}]`, errors));
      if (!parsed.some((item) => !item)) openings = parsed as Opening[];
    }
  }
  const stairErrorsStart = errors.length;
  const stair = stairFrom(value.stair, errors);

  if (errors.length > 0) return { errors: [...new Set(errors)] };
  return {
    errors: [],
    spec: {
      schemaVersion: BUILDING_SCHEMA_VERSION,
      ...extensions,
      projectName: projectName!,
      unit: "mm",
      width: width!,
      depth: depth!,
      wallThickness: wallThickness!,
      eaveHeight: eaveHeight!,
      ridgeHeight: ridgeHeight!,
      atticFloorHeight: atticFloorHeight!,
      ceilingHeight: ceilingHeight!,
      roofDirection: roofDirection as BuildingSpec["roofDirection"],
      roofOverhang: roofOverhang!,
      roofThickness: roofThickness!,
      floorSlabThickness: floorSlabThickness!,
      foundationDepth: foundationDepth!,
      roofFinish: roofFinish!,
      wallFinish: wallFinish!,
      plinthFinish: plinthFinish!,
      ...(outline ? { outline } : {}),
      ...(interiorWalls ? { interiorWalls } : {}),
      ...(openings ? { openings } : {}),
      ...(stair && errors.length === stairErrorsStart ? { stair } : {}),
    },
  };
};

const entityFrom = (value: unknown, path: string, errors: string[]): Entity | undefined => {
  if (!isRecord(value) || typeof value.type !== "string" || typeof value.layer !== "string" || !SAFE_LAYER_PATTERN.test(value.layer)) {
    errors.push(`${path}에 안전한 type/layer가 필요합니다.`);
    return undefined;
  }
  const layer = value.layer;
  if (value.type === "line") {
    const start = pointFrom(value.start, `${path}.start`, errors);
    const end = pointFrom(value.end, `${path}.end`, errors);
    return start && end ? { type: "line", layer, start, end } : undefined;
  }
  if (value.type === "polyline") {
    if (!Array.isArray(value.points) || value.points.length < 2 || value.points.length > 1_024 || typeof value.closed !== "boolean") {
      errors.push(`${path}.points/closed가 올바르지 않습니다.`);
      return undefined;
    }
    const points = value.points.map((point, index) => pointFrom(point, `${path}.points[${index}]`, errors));
    return points.some((point) => !point) ? undefined : { type: "polyline", layer, points: points as Point[], closed: value.closed };
  }
  if (value.type === "arc") {
    const center = pointFrom(value.center, `${path}.center`, errors);
    if (!center || !isFiniteNumber(value.radius) || value.radius <= 0 || !isFiniteNumber(value.startAngle) || !isFiniteNumber(value.endAngle)) {
      errors.push(`${path}의 호 데이터가 올바르지 않습니다.`);
      return undefined;
    }
    return { type: "arc", layer, center, radius: value.radius, startAngle: value.startAngle, endAngle: value.endAngle };
  }
  if (value.type === "circle") {
    const center = pointFrom(value.center, `${path}.center`, errors);
    if (!center || !isFiniteNumber(value.radius) || value.radius <= 0) {
      errors.push(`${path}의 원 데이터가 올바르지 않습니다.`);
      return undefined;
    }
    return { type: "circle", layer, center, radius: value.radius };
  }
  if (value.type === "text") {
    const at = pointFrom(value.at, `${path}.at`, errors);
    if (!at || typeof value.text !== "string" || value.text.length > 500 || !isFiniteNumber(value.height) || value.height <= 0) {
      errors.push(`${path}의 문자 데이터가 올바르지 않습니다.`);
      return undefined;
    }
    if (value.rotation !== undefined && !isFiniteNumber(value.rotation)) {
      errors.push(`${path}.rotation이 올바르지 않습니다.`);
      return undefined;
    }
    return { type: "text", layer, at, text: value.text, height: value.height, ...(isFiniteNumber(value.rotation) ? { rotation: value.rotation } : {}) };
  }
  errors.push(`${path}.type을 지원하지 않습니다.`);
  return undefined;
};

const viewFrom = (value: unknown, path: string, errors: string[]): DrawingView | undefined => {
  if (!isRecord(value) || !VIEW_KINDS.includes(value.id as ViewKind) || typeof value.title !== "string" || value.title.length > 120 ||
    !isFiniteNumber(value.width) || value.width <= 0 || value.width > 100_000 ||
    !isFiniteNumber(value.height) || value.height <= 0 || value.height > 100_000 ||
    !Array.isArray(value.entities) || value.entities.length > 20_000) {
    errors.push(`${path} 도면 데이터가 올바르지 않습니다.`);
    return undefined;
  }
  const entities = value.entities.map((entity, index) => entityFrom(entity, `${path}.entities[${index}]`, errors));
  if (entities.some((entity) => !entity)) return undefined;
  return { id: value.id as ViewKind, title: value.title, width: value.width, height: value.height, entities: entities as Entity[] };
};

const metricsFrom = (value: unknown, errors: string[]): DrawingMetrics | undefined => {
  if (!isRecord(value)) {
    errors.push("metrics가 올바르지 않습니다.");
    return undefined;
  }
  const keys: Array<keyof DrawingMetrics> = [
    "footprintAreaM2", "perimeterM", "roofPitchDegrees", "atticPeakHeight",
    "atticUsableWidthAt1800", "exteriorWallCount", "openingCount",
  ];
  if (keys.some((key) => !isFiniteNumber(value[key]))) {
    errors.push("metrics에 유효한 숫자 값이 필요합니다.");
    return undefined;
  }
  const metrics = Object.fromEntries(keys.map((key) => [key, value[key]])) as DrawingMetrics;
  if (value.roofPitchRatio !== undefined) {
    if (typeof value.roofPitchRatio !== "string" || value.roofPitchRatio.length > 40) errors.push("metrics.roofPitchRatio is invalid.");
    else metrics.roofPitchRatio = value.roofPitchRatio;
  }
  for (const key of ["atticMinimumClearHeight", "atticUsableWidthAtMinimum"] as const) {
    if (value[key] !== undefined) {
      if (!isFiniteNumber(value[key])) errors.push(`metrics.${key} is invalid.`);
      else metrics[key] = value[key];
    }
  }
  return metrics;
};

const scheduleFrom = (value: unknown, path: string, errors: string[]): OpeningScheduleRow | undefined => {
  if (!isRecord(value) || typeof value.mark !== "string" || value.mark.length > 80 ||
    (value.kind !== "door" && value.kind !== "window") ||
    !isFiniteNumber(value.count) || !isFiniteNumber(value.width) || !isFiniteNumber(value.height) || !isFiniteNumber(value.sill)) {
    errors.push(`${path} 창호 일람 데이터가 올바르지 않습니다.`);
    return undefined;
  }
  return {
    mark: value.mark,
    kind: value.kind,
    count: value.count,
    width: value.width,
    height: value.height,
    sill: value.sill,
  };
};

export const validateDrawingSet = (value: unknown): { drawing?: DrawingSet; errors: string[] } => {
  if (!isRecord(value)) return { errors: ["도면 결과가 객체가 아닙니다."] };
  const errors: string[] = [];
  const specResult = validateBuildingSpec(value.spec);
  errors.push(...specResult.errors.map((error) => `spec: ${error}`));
  if (!Array.isArray(value.views) || value.views.length < 1 || value.views.length > VIEW_KINDS.length) {
    errors.push("views는 1~7개 도면 배열이어야 합니다.");
  }
  const views = Array.isArray(value.views)
    ? value.views.map((view, index) => viewFrom(view, `views[${index}]`, errors))
    : [];
  const validViews = views.filter(Boolean) as DrawingView[];
  if (new Set(validViews.map((view) => view.id)).size !== validViews.length) errors.push("도면 view id가 중복되었습니다.");
  const metrics = metricsFrom(value.metrics, errors);
  if (!Array.isArray(value.openingSchedule) || value.openingSchedule.length > 256) {
    errors.push("openingSchedule이 올바르지 않습니다.");
  }
  const openingSchedule = Array.isArray(value.openingSchedule)
    ? value.openingSchedule.map((row, index) => scheduleFrom(row, `openingSchedule[${index}]`, errors))
    : [];
  if (!Array.isArray(value.warnings) || value.warnings.length > 256 || value.warnings.some((item) => typeof item !== "string" || item.length > 500)) {
    errors.push("warnings가 올바르지 않습니다.");
  }
  if (typeof value.generatedAt !== "string" || value.generatedAt.length > 100) errors.push("generatedAt이 올바르지 않습니다.");
  if (typeof value.engineVersion !== "string" || value.engineVersion.length > 80) errors.push("engineVersion이 올바르지 않습니다.");
  const validationIssues = issuesFrom(value.validationIssues);
  if (value.validationIssues !== undefined && (!Array.isArray(value.validationIssues) || validationIssues.length !== value.validationIssues.length)) {
    errors.push("validationIssues is invalid.");
  }
  const optionalSchedule = (source: unknown, name: string): OpeningScheduleRow[] | undefined => {
    if (source === undefined) return undefined;
    if (!Array.isArray(source) || source.length > 256) {
      errors.push(`${name} is invalid.`);
      return undefined;
    }
    const rows = source.map((row, index) => scheduleFrom(row, `${name}[${index}]`, errors));
    return rows.some((row) => !row) ? undefined : rows as OpeningScheduleRow[];
  };
  const doorSchedule = optionalSchedule(value.doorSchedule, "doorSchedule");
  const windowSchedule = optionalSchedule(value.windowSchedule, "windowSchedule");
  let drawingViewList: DrawingSet["drawingViewList"];
  if (value.drawingViewList !== undefined) {
    if (!Array.isArray(value.drawingViewList) || value.drawingViewList.length > 16 || value.drawingViewList.some((item) =>
      !isRecord(item) || !VIEW_KINDS.includes(item.id as ViewKind) || typeof item.title !== "string" || item.title.length > 120)) {
      errors.push("drawingViewList is invalid.");
    } else drawingViewList = value.drawingViewList as NonNullable<DrawingSet["drawingViewList"]>;
  }
  let layerList: string[] | undefined;
  if (value.layerList !== undefined) {
    if (!Array.isArray(value.layerList) || value.layerList.length > 128 || value.layerList.some((layer) => typeof layer !== "string" || !SAFE_LAYER_PATTERN.test(layer))) {
      errors.push("layerList is invalid.");
    } else layerList = [...value.layerList] as string[];
  }
  if (errors.length || !specResult.spec || !metrics || validViews.length !== views.length || openingSchedule.some((row) => !row)) {
    return { errors: [...new Set(errors)] };
  }
  return {
    errors: [],
    drawing: {
      spec: specResult.spec,
      views: validViews,
      warnings: value.warnings as string[],
      metrics,
      openingSchedule: openingSchedule as OpeningScheduleRow[],
      generatedAt: value.generatedAt as string,
      engineVersion: value.engineVersion as string,
      ...(validationIssues.length ? { validationIssues } : {}),
      ...(doorSchedule ? { doorSchedule } : {}),
      ...(windowSchedule ? { windowSchedule } : {}),
      ...(drawingViewList ? { drawingViewList } : {}),
      ...(layerList ? { layerList } : {}),
    },
  };
};

const readArtifactText = (value: unknown): string | undefined => {
  if (typeof value === "string" && value.length <= 12_000_000) return value;
  if (!isRecord(value)) return undefined;
  for (const key of ["content", "text", "data"]) {
    if (typeof value[key] === "string" && value[key].length <= 12_000_000) return value[key];
  }
  return undefined;
};

const artifactsFrom = (value: unknown): ArtifactBundle => {
  const bundle: ArtifactBundle = { viewSvgs: {} };
  if (!isRecord(value)) return bundle;
  bundle.dxf = readArtifactText(value.dxf ?? value.drawingDxf);
  bundle.sheetSvg = readArtifactText(value.sheetSvg ?? value.svgSheet ?? value.combinedSvg ?? value.svg);
  bundle.projectJson = readArtifactText(value.projectJson ?? value.json ?? value.drawingJson);
  const views = value.viewSvgs ?? value.views ?? value.individualSvgs;
  if (Array.isArray(views)) {
    for (const item of views) {
      if (!isRecord(item) || typeof item.id !== "string") continue;
      const kind = item.id.startsWith("viewSvg:") ? item.id.slice("viewSvg:".length) : item.id;
      if (!VIEW_KINDS.includes(kind as ViewKind)) continue;
      const content = readArtifactText(item);
      if (content) bundle.viewSvgs[kind as ViewKind] = content;
    }
  } else if (isRecord(views)) {
    for (const kind of VIEW_KINDS) {
      const content = readArtifactText(views[kind]);
      if (content) bundle.viewSvgs[kind] = content;
    }
  }
  return bundle;
};

const mergeArtifacts = (base: ArtifactBundle, next: ArtifactBundle): ArtifactBundle => ({
  dxf: next.dxf ?? base.dxf,
  sheetSvg: next.sheetSvg ?? base.sheetSvg,
  projectJson: next.projectJson ?? base.projectJson,
  viewSvgs: { ...base.viewSvgs, ...next.viewSvgs },
});

const issuesFrom = (value: unknown): ValidationIssue[] => {
  if (!Array.isArray(value)) return [];
  const issues: ValidationIssue[] = [];
  for (const item of value) {
    if (!isRecord(item) || typeof item.code !== "string" || typeof item.path !== "string" ||
      (item.severity !== "error" && item.severity !== "warning") || typeof item.message !== "string" ||
      item.code.length > 120 || item.path.length > 240 || item.message.length > 1_000) continue;
    issues.push({ code: item.code, path: item.path, severity: item.severity, message: item.message });
  }
  return issues;
};

const collectPayloadRecords = (value: unknown): Record<string, unknown>[] => {
  if (!isRecord(value)) return [];
  const records = [value];
  for (const key of ["_meta", "structuredContent", "toolResponseMetadata", "result", "prepared", "error"]) {
    if (isRecord(value[key])) records.push(value[key] as Record<string, unknown>);
  }
  return records;
};

export const extractHydratedResult = (...values: unknown[]): HydratedResult => {
  let drawing: DrawingSet | undefined;
  let summarySpec: BuildingSpec | undefined;
  let artifacts: ArtifactBundle = { viewSvgs: {} };
  const summaryWarnings: string[] = [];
  const issues: ValidationIssue[] = [];
  let valid: boolean | undefined;
  const errors: string[] = [];

  for (const value of values) {
    for (const record of collectPayloadRecords(value)) {
      if (record.artifacts !== undefined) artifacts = mergeArtifacts(artifacts, artifactsFrom(record.artifacts));
      if (typeof record.valid === "boolean") valid = valid === false ? false : record.valid;
      issues.push(...issuesFrom(record.issues), ...issuesFrom(record.validationIssues));
      const drawingCandidate = record.drawing ?? (record.spec && record.views ? record : undefined);
      if (!drawing && drawingCandidate !== undefined) {
        const result = validateDrawingSet(drawingCandidate);
        if (result.drawing) drawing = result.drawing;
        else errors.push(...result.errors.map((error) => `수신 도면: ${error}`));
      }
      if (!summarySpec && record.spec !== undefined) {
        const result = validateBuildingSpec(record.spec);
        if (result.spec) summarySpec = result.spec;
      }
      if (Array.isArray(record.warnings)) {
        summaryWarnings.push(...record.warnings.filter((item): item is string => typeof item === "string" && item.length <= 500));
      }
    }
  }

  if (drawing?.validationIssues) issues.push(...drawing.validationIssues);
  if (issues.some((issue) => issue.severity === "error")) valid = false;

  return {
    drawing,
    artifacts,
    summarySpec,
    summaryWarnings: [...new Set(summaryWarnings)],
    valid,
    issues: issues.filter((issue, index, list) => list.findIndex((candidate) =>
      candidate.code === issue.code && candidate.path === issue.path && candidate.message === issue.message,
    ) === index),
    errors: [...new Set(errors)],
  };
};

export const editorJsonFor = (spec: BuildingSpec, mode: JsonEditorMode): string => {
  const keys = mode === "basic" ? BASIC_KEYS : ADVANCED_KEYS;
  const object = Object.fromEntries(keys.filter((key) => spec[key] !== undefined).map((key) => [key, spec[key]]));
  return JSON.stringify(object, null, 2);
};

export const parseEditorJson = (text: string, mode: JsonEditorMode, current: BuildingSpec): SpecValidation => {
  try {
    const parsed: unknown = JSON.parse(text);
    if (!isRecord(parsed)) return { errors: ["JSON 최상위 값은 객체여야 합니다."] };
    const allowed = new Set<string>(mode === "basic" ? BASIC_KEYS : ADVANCED_KEYS);
    const disallowed = Object.keys(parsed).filter((key) => !allowed.has(key));
    if (disallowed.length) return { errors: [`${mode === "basic" ? "기본" : "고급"} JSON에서 지원하지 않는 키: ${disallowed.join(", ")}`] };
    return validateBuildingSpec({ ...current, ...parsed });
  } catch (error) {
    return { errors: [error instanceof Error ? error.message : "JSON을 읽을 수 없습니다."] };
  }
};

export const parseProjectJson = (text: string): { drawing?: DrawingSet; spec?: BuildingSpec; errors: string[] } => {
  try {
    const parsed: unknown = JSON.parse(text);
    const records = collectPayloadRecords(parsed);
    for (const record of records) {
      const drawingCandidate = record.drawing ?? (record.views && record.spec ? record : undefined);
      if (drawingCandidate !== undefined) {
        const result = validateDrawingSet(drawingCandidate);
        if (result.drawing) return { drawing: result.drawing, spec: result.drawing.spec, errors: [] };
      }
    }
    const candidate = isRecord(parsed) && isRecord(parsed.spec) ? parsed.spec : parsed;
    const result = validateBuildingSpec(candidate);
    return result.spec ? { spec: result.spec, errors: [] } : { errors: result.errors };
  } catch (error) {
    return { errors: [error instanceof Error ? error.message : "프로젝트 JSON을 읽을 수 없습니다."] };
  }
};

export const projectJsonFor = (drawing: DrawingSet): string => JSON.stringify({
  format: "hscad-mobile-project",
  version: 1,
  drawing,
}, null, 2);

export const safeFilename = (value: string): string =>
  value.trim().replace(/[\\/:*?"<>|\u0000-\u001f]+/g, "-").replace(/\s+/g, "_").slice(0, 96) || "hscad-drawing";

export const downloadText = (name: string, content: string, type: string): Blob => {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.rel = "noopener";
  link.hidden = true;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
  return blob;
};

export const copyTextWithFallback = async (
  text: string,
  fallbackFilename: string,
): Promise<"clipboard" | "legacy" | "download"> => {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return "clipboard";
    }
  } catch {
    // Sandboxed widgets may deny the async clipboard permission.
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.readOnly = true;
  textarea.setAttribute("aria-hidden", "true");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  try {
    if (typeof document.execCommand === "function" && document.execCommand("copy")) {
      textarea.remove();
      return "legacy";
    }
  } catch {
    // Fall through to a deterministic file download.
  }
  textarea.remove();
  downloadText(fallbackFilename, text, "application/json;charset=utf-8");
  return "download";
};

export const collectLayers = (view: DrawingView): string[] =>
  [...new Set(view.entities.map((entity) => entity.layer))].sort((a, b) => a.localeCompare(b));

export const filterViewLayers = (view: DrawingView, hiddenLayers: ReadonlySet<string>): DrawingView => ({
  ...view,
  entities: view.entities.filter((entity) => !hiddenLayers.has(entity.layer)),
});

export const svgDataUrl = (svg: string): string => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
