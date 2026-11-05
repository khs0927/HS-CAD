export const BUILDING_SCHEMA_VERSION = "1.0" as const;

export const CAD_LAYERS = [
  "A-WALL", "A-CUT", "A-ELEV", "A-ROOF", "A-DOOR", "A-WIND", "A-GLAZ", "A-OPEN",
  "A-STRS", "A-FURN", "A-FIXT", "A-COLS", "A-DIMS", "A-TEXT", "A-NOTE", "A-ANNO",
  "A-SECT", "A-HIDD", "A-HATCH", "A-MATL", "A-PLIN", "A-VENT", "A-DRAIN", "A-GRID",
  "A-LEVEL", "A-CEIL", "A-BORDER",
] as const;

export type CadLayer = typeof CAD_LAYERS[number];
export type Point = { x: number; y: number };
export type Segment = { id?: string; start: Point; end: Point; thickness?: number; layer?: string };
export type OpeningKind = "door" | "window";
export type RoofDirection = "ridge-along-width" | "ridge-along-depth";
export type Facade = "front" | "right" | "rear" | "left";

export type Opening = {
  kind: OpeningKind;
  /** Stable wall reference. Preferred over wallIndex when supplied. */
  wallId?: string;
  /** Backwards-compatible zero-based wall reference. */
  wallIndex?: number;
  offset: number;
  width: number;
  height: number;
  sill?: number;
  swing?: "left" | "right" | "double";
  openingDirection?: "in" | "out";
  panelType?: "fixed" | "single" | "double" | "sliding" | "louvered";
  placement?: "main" | "attic";
  label?: string;
};

export type StairSpec = {
  x: number;
  y: number;
  width: number;
  length: number;
  risers: number;
  direction: "up-north" | "up-south" | "up-east" | "up-west";
  treadDepth?: number;
  landingDepth?: number;
  railing?: "none" | "left" | "right" | "both";
  showDownArrow?: boolean;
};

export type GridAxis = {
  id: string;
  start: Point;
  end: Point;
};

export type SectionCut = {
  id: "A" | "B" | string;
  start: Point;
  end: Point;
};

export type RoomLabel = {
  id?: string;
  name: string;
  at: Point;
  polygon?: Point[];
};

export type SymbolItem = {
  id?: string;
  kind: "column" | "sink" | "toilet" | "tub" | "table" | "chair" | "cabinet" | "label";
  at: Point;
  width?: number;
  depth?: number;
  rotation?: number;
  label?: string;
};

export type FacadeFeature = {
  id?: string;
  kind: "attic-window" | "vent" | "louver" | "downspout";
  facade: Facade;
  offset: number;
  width?: number;
  height?: number;
  sill?: number;
  label?: string;
};

export type BuildingSpec = {
  /** Optional on legacy input; normalizeSpec always emits the current literal. */
  schemaVersion?: typeof BUILDING_SCHEMA_VERSION;
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
  drawingScale?: string;
  atticMinimumClearHeight?: number;
  roofFinish: string;
  wallFinish: string;
  plinthFinish: string;
  frameFinish?: string;
  gutterDownspoutSpec?: string;
  outline?: Point[];
  wallIds?: string[];
  interiorWalls?: Segment[];
  openings?: Opening[];
  stair?: StairSpec;
  stairEnabled?: boolean;
  roomLabels?: RoomLabel[];
  gridAxes?: GridAxis[];
  sectionCuts?: SectionCut[];
  symbols?: SymbolItem[];
  facadeFeatures?: FacadeFeature[];
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
  roofPitchRatio?: string;
  atticMinimumClearHeight?: number;
  atticUsableWidthAtMinimum?: number;
};

export type ValidationIssue = {
  code: string;
  path: string;
  severity: "error" | "warning";
  message: string;
};

export type DrawingSet = {
  spec: BuildingSpec;
  views: DrawingView[];
  warnings: string[];
  metrics: DrawingMetrics;
  openingSchedule: OpeningScheduleRow[];
  generatedAt: string;
  engineVersion: string;
  validationIssues?: ValidationIssue[];
  doorSchedule?: OpeningScheduleRow[];
  windowSchedule?: OpeningScheduleRow[];
  drawingViewList?: Array<{ id: ViewKind; title: string }>;
  layerList?: string[];
};
