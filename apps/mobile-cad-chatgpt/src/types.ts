export type Point = { x: number; y: number };
export type Segment = { start: Point; end: Point; thickness?: number; layer?: string };
export type OpeningKind = "door" | "window";
export type RoofDirection = "ridge-along-width" | "ridge-along-depth";
export type Facade = "front" | "right" | "rear" | "left";

export type Opening = {
  kind: OpeningKind;
  wallIndex: number;
  offset: number;
  width: number;
  height: number;
  sill?: number;
  swing?: "left" | "right" | "double";
  label?: string;
};

export type StairSpec = {
  x: number;
  y: number;
  width: number;
  length: number;
  risers: number;
  direction: "up-north" | "up-south" | "up-east" | "up-west";
};

export type BuildingSpec = {
  projectName: string;
  unit: "mm";
  width: number;
  depth: number;
  wallThickness: number;
  eaveHeight: number;
  ridgeHeight: number;
  atticFloorHeight: number;
  ceilingHeight: number;
  roofDirection: RoofDirection;
  roofOverhang: number;
  roofThickness: number;
  floorSlabThickness: number;
  foundationDepth: number;
  roofFinish: string;
  wallFinish: string;
  plinthFinish: string;
  outline?: Point[];
  interiorWalls?: Segment[];
  openings?: Opening[];
  stair?: StairSpec;
};

export type EntityBase = { layer: string };
export type LineEntity = EntityBase & { type: "line"; start: Point; end: Point };
export type PolylineEntity = EntityBase & { type: "polyline"; points: Point[]; closed: boolean };
export type ArcEntity = EntityBase & { type: "arc"; center: Point; radius: number; startAngle: number; endAngle: number };
export type CircleEntity = EntityBase & { type: "circle"; center: Point; radius: number };
export type TextEntity = EntityBase & { type: "text"; at: Point; text: string; height: number; rotation?: number };
export type Entity = LineEntity | PolylineEntity | ArcEntity | CircleEntity | TextEntity;

export type ViewKind = "plan" | "front" | "rear" | "left" | "right" | "section-a" | "section-b";
export type DrawingView = {
  id: ViewKind;
  title: string;
  width: number;
  height: number;
  entities: Entity[];
};

export type OpeningScheduleRow = {
  mark: string;
  kind: OpeningKind;
  count: number;
  width: number;
  height: number;
  sill: number;
};

export type DrawingMetrics = {
  footprintAreaM2: number;
  perimeterM: number;
  roofPitchDegrees: number;
  atticPeakHeight: number;
  atticUsableWidthAt1800: number;
  exteriorWallCount: number;
  openingCount: number;
};

export type DrawingSet = {
  spec: BuildingSpec;
  views: DrawingView[];
  warnings: string[];
  metrics: DrawingMetrics;
  openingSchedule: OpeningScheduleRow[];
  generatedAt: string;
  engineVersion: string;
};
