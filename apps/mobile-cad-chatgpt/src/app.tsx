import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import { createRoot } from "react-dom/client";
import { generateDrawingSet, validateSpec } from "./cad-model";
import { drawingSetToDxf } from "./dxf";
import { mcpBridge, readOpenAi, type BridgeSnapshot, type HostContext } from "./mcp-bridge";
import { drawingSetToSvgSheet, viewToSvg } from "./svg";
import { BUILDING_SCHEMA_VERSION, type BuildingSpec, type DrawingSet, type ValidationIssue, type ViewKind } from "./types";
import {
  collectLayers,
  copyTextWithFallback,
  downloadText,
  editorJsonFor,
  extractHydratedResult,
  filterViewLayers,
  parseEditorJson,
  parseProjectJson,
  projectJsonFor,
  safeFilename,
  svgDataUrl,
  validateBuildingSpec,
  validateDrawingSet,
  type ArtifactBundle,
  type HydratedResult,
  type JsonEditorMode,
} from "./ui-utils";
import "./styles.css";

const DEFAULT_SPEC: BuildingSpec = {
  schemaVersion: BUILDING_SCHEMA_VERSION,
  projectName: "HS-CAD 주택 계획",
  unit: "mm",
  width: 12_000,
  depth: 11_300,
  wallThickness: 200,
  eaveHeight: 3_200,
  ridgeHeight: 5_000,
  atticFloorHeight: 2_600,
  ceilingHeight: 2_500,
  roofDirection: "ridge-along-depth",
  roofOverhang: 450,
  roofThickness: 220,
  floorSlabThickness: 180,
  foundationDepth: 700,
  drawingScale: "1:100",
  atticMinimumClearHeight: 1_800,
  roofFinish: "Standing seam metal",
  wallFinish: "Exterior render / panel",
  plinthFinish: "Exposed concrete / stone",
};

type PersistedWidgetState = {
  spec?: BuildingSpec;
  active?: ViewKind;
  hiddenLayers?: string[];
};

type Viewport = { zoom: number; x: number; y: number };
type Notice = { tone: "success" | "error" | "info"; text: string } | null;

const EMPTY_ARTIFACTS: ArtifactBundle = { viewSvgs: {} };

const blockingIssuesFor = (drawing: DrawingSet): ValidationIssue[] =>
  (drawing.validationIssues ?? []).filter((issue) => issue.severity === "error");

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const parseWidgetState = (value: unknown): PersistedWidgetState => {
  if (!isRecord(value)) return {};
  const specResult = validateBuildingSpec(value.spec);
  const active = typeof value.active === "string" ? value.active as ViewKind : undefined;
  const hiddenLayers = Array.isArray(value.hiddenLayers)
    ? value.hiddenLayers.filter((item): item is string => typeof item === "string")
    : undefined;
  return {
    spec: specResult.spec,
    active: ["plan", "front", "rear", "left", "right", "section-a", "section-b"].includes(active ?? "") ? active : undefined,
    hiddenLayers,
  };
};

const safeLocalDrawing = (spec: BuildingSpec): DrawingSet => {
  const generated = generateDrawingSet(spec);
  return validateDrawingSet(generated).drawing ?? generated;
};

const createInitialState = (): {
  drawing: DrawingSet;
  spec: BuildingSpec;
  active: ViewKind;
  hiddenLayers: Set<string>;
  artifacts: ArtifactBundle;
  blockedIssues: ValidationIssue[];
  errors: string[];
} => {
  const compatibility = mcpBridge.readCompatibilityPayload();
  const hydration = extractHydratedResult(compatibility.toolResponseMetadata, compatibility.toolOutput);
  const persisted = parseWidgetState(compatibility.widgetState);
  const blockedIssues = hydration.issues.filter((issue) => issue.severity === "error");
  const invalidResult = hydration.valid === false || blockedIssues.length > 0;
  const baseSpec = persisted.spec ?? hydration.drawing?.spec ?? hydration.summarySpec ?? DEFAULT_SPEC;
  const drawing = !invalidResult && hydration.drawing ? hydration.drawing : safeLocalDrawing(invalidResult ? DEFAULT_SPEC : baseSpec);
  const active = persisted.active && drawing.views.some((view) => view.id === persisted.active)
    ? persisted.active
    : drawing.views[0]?.id ?? "plan";
  return {
    drawing,
    spec: persisted.spec ?? drawing.spec,
    active,
    hiddenLayers: new Set(persisted.hiddenLayers ?? []),
    artifacts: hydration.artifacts,
    blockedIssues,
    errors: invalidResult ? blockedIssues.map((issue) => issue.message) : hydration.drawing ? [] : hydration.errors,
  };
};

const clamp = (value: number, min: number, max: number): number => Math.min(max, Math.max(min, value));

const errorMessage = (error: unknown, fallback: string): string =>
  error instanceof Error && error.message ? error.message : fallback;

const mergeArtifacts = (previous: ArtifactBundle, next: ArtifactBundle): ArtifactBundle => ({
  dxf: next.dxf ?? previous.dxf,
  sheetSvg: next.sheetSvg ?? previous.sheetSvg,
  projectJson: next.projectJson ?? previous.projectJson,
  viewSvgs: { ...previous.viewSvgs, ...next.viewSvgs },
});

const Field = ({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) => (
  <label className="field">
    <span>{label}</span>
    {children}
    {hint ? <small>{hint}</small> : null}
  </label>
);

const Icon = ({ children }: { children: ReactNode }) => <span aria-hidden="true" className="button-icon">{children}</span>;

const MetricCard = ({ label, value, unit }: { label: string; value: string | number; unit?: string }) => (
  <article className="metric-card">
    <span>{label}</span>
    <strong>{value}<small>{unit}</small></strong>
  </article>
);

const applyHostContext = (context: HostContext): (() => void) => {
  const root = document.documentElement;
  const theme = context.theme ?? (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  root.dataset.theme = theme;
  root.style.colorScheme = theme;
  root.dataset.displayMode = context.displayMode ?? "standalone";
  if (context.locale) root.lang = context.locale;
  const safeArea = context.safeAreaInsets ?? { top: 0, right: 0, bottom: 0, left: 0 };
  const properties: Record<string, string> = {
    "--safe-top": `${safeArea.top}px`,
    "--safe-right": `${safeArea.right}px`,
    "--safe-bottom": `${safeArea.bottom}px`,
    "--safe-left": `${safeArea.left}px`,
    "--host-max-height": context.maxHeight ? `${context.maxHeight}px` : "100dvh",
  };
  for (const [key, value] of Object.entries(properties)) root.style.setProperty(key, value);
  for (const [key, value] of Object.entries(context.styles?.variables ?? {})) {
    if (/^--(?:color|font|border|shadow)-[a-z0-9-]+$/.test(key) && typeof value === "string" && value.length < 200) {
      root.style.setProperty(key, value);
    }
  }
  return () => {
    for (const key of Object.keys(properties)) root.style.removeProperty(key);
  };
};

export function App() {
  const [initial] = useState(createInitialState);
  const [drawing, setDrawing] = useState(initial.drawing);
  const [spec, setSpec] = useState(initial.spec);
  const [active, setActive] = useState<ViewKind>(initial.active);
  const [hiddenLayers, setHiddenLayers] = useState<Set<string>>(initial.hiddenLayers);
  const [artifacts, setArtifacts] = useState<ArtifactBundle>(initial.artifacts);
  const [blockedIssues, setBlockedIssues] = useState<ValidationIssue[]>(initial.blockedIssues);
  const [dirty, setDirty] = useState(() => JSON.stringify(initial.spec) !== JSON.stringify(initial.drawing.spec));
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice>(initial.errors.length ? { tone: "error", text: initial.errors[0] } : null);
  const [jsonMode, setJsonMode] = useState<JsonEditorMode>("basic");
  const [jsonText, setJsonText] = useState(() => editorJsonFor(initial.spec, "basic"));
  const [jsonError, setJsonError] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [viewport, setViewport] = useState<Viewport>({ zoom: 1, x: 0, y: 0 });
  const [panEnabled, setPanEnabled] = useState(true);
  const [inlineOverride, setInlineOverride] = useState(false);
  const [bridgeSnapshot, setBridgeSnapshot] = useState<BridgeSnapshot>(() => mcpBridge.getSnapshot());
  const [compatibilityRevision, setCompatibilityRevision] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pointerRef = useRef<{ id: number; clientX: number; clientY: number; x: number; y: number } | null>(null);
  const toolRevisionRef = useRef(0);

  const validation = useMemo(() => validateBuildingSpec(spec), [spec]);
  const liveWarnings = useMemo(() => {
    if (!validation.spec) return [];
    try {
      return validateSpec(validation.spec);
    } catch {
      return ["고급 형상 조건을 다시 확인해 주세요."];
    }
  }, [validation.spec]);
  const warnings = useMemo(
    () => [...new Set([...liveWarnings, ...drawing.warnings])],
    [drawing.warnings, liveWarnings],
  );
  const view = useMemo(
    () => drawing.views.find((item) => item.id === active) ?? drawing.views[0],
    [active, drawing.views],
  );
  const layers = useMemo(() => view ? collectLayers(view) : [], [view]);
  const filteredView = useMemo(
    () => view ? filterViewLayers(view, hiddenLayers) : undefined,
    [hiddenLayers, view],
  );
  const renderedSvg = useMemo(() => filteredView ? viewToSvg(filteredView) : "", [filteredView]);
  const renderedSvgUrl = useMemo(() => svgDataUrl(renderedSvg), [renderedSvg]);
  const downloadBase = safeFilename(spec.projectName);
  const outputsReady = Boolean(validation.spec) && !dirty && blockedIssues.length === 0;

  const hosted = bridgeSnapshot.status === "connected" || Boolean(readOpenAi()) || window.parent !== window;
  const displayMode = bridgeSnapshot.hostContext.displayMode ?? readOpenAi()?.displayMode ?? (hosted ? "inline" : "fullscreen");
  const compactInline = hosted && displayMode === "inline" && !inlineOverride;

  const applyHydration = useCallback((hydration: HydratedResult): boolean => {
    const blockers = hydration.issues.filter((issue) => issue.severity === "error");
    if (hydration.valid === false || blockers.length > 0) {
      const nextBlockers = blockers.length ? blockers : [{
        code: "INVALID_DRAWING",
        path: "spec",
        severity: "error" as const,
        message: "설계 조건에 차단 오류가 있어 도면 산출물을 만들지 않았습니다.",
      }];
      setBlockedIssues(nextBlockers);
      setArtifacts(EMPTY_ARTIFACTS);
      setNotice({ tone: "error", text: nextBlockers[0].message });
      return false;
    }
    setArtifacts((previous) => mergeArtifacts(previous, hydration.artifacts));
    let nextDrawing = hydration.drawing;
    if (!nextDrawing && hydration.summarySpec) nextDrawing = safeLocalDrawing(hydration.summarySpec);
    if (!nextDrawing) {
      if (hydration.errors.length) setNotice({ tone: "error", text: hydration.errors[0] });
      return false;
    }
    setDrawing(nextDrawing);
    setBlockedIssues([]);
    setSpec(nextDrawing.spec);
    setDirty(false);
    setHiddenLayers(new Set());
    setViewport({ zoom: 1, x: 0, y: 0 });
    setActive((current) => nextDrawing!.views.some((item) => item.id === current) ? current : nextDrawing!.views[0]?.id ?? "plan");
    setJsonText(editorJsonFor(nextDrawing.spec, jsonMode));
    setJsonError("");
    setNotice({ tone: "success", text: `도면 ${nextDrawing.views.length}개를 업데이트했습니다.` });
    return true;
  }, [jsonMode]);

  useEffect(() => {
    const unsubscribe = mcpBridge.subscribe((snapshot) => {
      setBridgeSnapshot(snapshot);
      if (snapshot.toolResult && snapshot.toolRevision > toolRevisionRef.current) {
        toolRevisionRef.current = snapshot.toolRevision;
        applyHydration(extractHydratedResult(snapshot.toolResult));
        setBusy(false);
      }
    });
    void mcpBridge.connect();
    return unsubscribe;
  }, [applyHydration]);

  useEffect(() => {
    const handleGlobals = (event: Event) => {
      const detail = (event as CustomEvent<{ globals?: unknown }>).detail;
      const globals = isRecord(detail?.globals) ? detail.globals : readOpenAi();
      mcpBridge.refreshCompatibilityContext();
      setCompatibilityRevision((revision) => revision + 1);
      if (isRecord(globals)) {
        applyHydration(extractHydratedResult(globals.toolResponseMetadata, globals.toolOutput));
      }
    };
    window.addEventListener("openai:set_globals", handleGlobals);
    return () => window.removeEventListener("openai:set_globals", handleGlobals);
  }, [applyHydration]);

  useEffect(() => applyHostContext(bridgeSnapshot.hostContext), [bridgeSnapshot.hostContext, compatibilityRevision]);

  useEffect(() => {
    mcpBridge.persistWidgetState({
      schemaVersion: BUILDING_SCHEMA_VERSION,
      spec,
      active,
      hiddenLayers: [...hiddenLayers],
    });
  }, [active, hiddenLayers, spec]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void mcpBridge.updateModelContext({
        content: [{
          type: "text",
          text: `${spec.projectName}: ${view?.title ?? active}, ${dirty ? "edited but not regenerated" : "generated"}, ${warnings.length} review notes.`,
        }],
        structuredContent: {
          projectName: spec.projectName,
          schemaVersion: BUILDING_SCHEMA_VERSION,
          activeView: active,
          dirty,
          visibleLayers: layers.filter((layer) => !hiddenLayers.has(layer)),
          warningCount: warnings.length,
        },
      }).catch(() => undefined);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [active, dirty, hiddenLayers, layers, spec.projectName, view?.title, warnings.length]);

  useEffect(() => {
    let frame = 0;
    const report = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => {
        mcpBridge.reportSize(Math.ceil(document.documentElement.clientWidth), Math.ceil(document.documentElement.scrollHeight));
      });
    };
    report();
    if (typeof ResizeObserver === "undefined") return () => window.cancelAnimationFrame(frame);
    const observer = new ResizeObserver(report);
    observer.observe(document.body);
    return () => {
      observer.disconnect();
      window.cancelAnimationFrame(frame);
    };
  }, [compactInline]);

  useEffect(() => {
    setHiddenLayers((previous) => new Set([...previous].filter((layer) => layers.includes(layer))));
    setViewport({ zoom: 1, x: 0, y: 0 });
  }, [active, layers]);

  const updateSpec = useCallback((patch: Partial<BuildingSpec>) => {
    setSpec((current) => ({ ...current, ...patch, schemaVersion: BUILDING_SCHEMA_VERSION }));
    setDirty(true);
    setNotice(null);
  }, []);

  const updateNumber = (key: keyof BuildingSpec, event: ChangeEvent<HTMLInputElement>) => {
    updateSpec({ [key]: event.currentTarget.valueAsNumber } as Partial<BuildingSpec>);
  };

  const generate = async () => {
    if (!validation.spec) {
      setNotice({ tone: "error", text: validation.errors[0] ?? "입력값을 확인해 주세요." });
      return;
    }
    setBusy(true);
    setNotice({ tone: "info", text: "도면을 생성하고 있습니다…" });
    try {
      const result = await mcpBridge.callTool("generate_architectural_set", validation.spec as unknown as Record<string, unknown>);
      if (result === undefined) {
        applyHydration(extractHydratedResult({ drawing: safeLocalDrawing(validation.spec) }));
      } else {
        const hydration = extractHydratedResult(result);
        const applied = applyHydration(hydration);
        if (!applied && hydration.valid !== false && !hydration.issues.some((issue) => issue.severity === "error")) {
          throw new Error("도구 결과에 검증 가능한 도면 데이터가 없습니다.");
        }
      }
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error, "도면 생성에 실패했습니다.") });
    } finally {
      setBusy(false);
    }
  };

  const requestFullscreen = async () => {
    try {
      const supported = await mcpBridge.requestFullscreen();
      if (!supported) {
        setInlineOverride(true);
        setNotice({ tone: "info", text: "호스트 전체 화면 API가 없어 현재 카드에서 편집기를 열었습니다." });
      }
    } catch (error) {
      setInlineOverride(true);
      setNotice({ tone: "error", text: errorMessage(error, "전체 화면을 열 수 없습니다.") });
    }
  };

  const saveDxf = () => {
    if (!outputsReady) {
      setNotice({ tone: "error", text: "오류를 수정하고 도면을 다시 생성한 뒤 다운로드하세요." });
      return;
    }
    const content = artifacts.dxf ?? drawingSetToDxf(drawing);
    downloadText(`${downloadBase}.dxf`, content, "application/dxf;charset=utf-8");
    setNotice({ tone: "success", text: "DXF 파일을 저장했습니다." });
  };

  const saveCurrentSvg = () => {
    if (!outputsReady) {
      setNotice({ tone: "error", text: "오류를 수정하고 도면을 다시 생성한 뒤 다운로드하세요." });
      return;
    }
    if (!filteredView) return;
    downloadText(`${downloadBase}-${filteredView.id}.svg`, viewToSvg(filteredView), "image/svg+xml;charset=utf-8");
    setNotice({ tone: "success", text: `${filteredView.title} SVG를 저장했습니다.` });
  };

  const saveSheetSvg = () => {
    if (!outputsReady) {
      setNotice({ tone: "error", text: "오류를 수정하고 도면을 다시 생성한 뒤 다운로드하세요." });
      return;
    }
    downloadText(`${downloadBase}-sheet.svg`, drawingSetToSvgSheet(drawing), "image/svg+xml;charset=utf-8");
    setNotice({ tone: "success", text: "전체 도면 시트 SVG를 저장했습니다." });
  };

  const saveProject = () => {
    if (!outputsReady) {
      setNotice({ tone: "error", text: "오류를 수정하고 도면을 다시 생성한 뒤 프로젝트를 저장하세요." });
      return;
    }
    downloadText(`${downloadBase}.hscad.json`, projectJsonFor(drawing), "application/json;charset=utf-8");
    setNotice({ tone: "success", text: "프로젝트 JSON을 저장했습니다." });
  };

  const copyProject = async () => {
    if (!outputsReady) {
      setNotice({ tone: "error", text: "오류를 수정하고 도면을 다시 생성한 뒤 프로젝트를 복사하세요." });
      return;
    }
    const result = await copyTextWithFallback(projectJsonFor(drawing), `${downloadBase}.hscad.json`);
    setNotice({
      tone: "success",
      text: result === "download" ? "클립보드 권한이 없어 프로젝트 JSON을 파일로 저장했습니다." : "프로젝트 JSON을 복사했습니다.",
    });
  };

  const askChatGpt = async () => {
    try {
      const sent = await mcpBridge.sendUserMessage(
        `${spec.projectName}의 ${view?.title ?? "현재 도면"}을 검토해 주세요. 치수, 개구부, 재료, 구조·법규 검토가 필요한 항목을 구분하고 기존 치수는 임의로 바꾸지 마세요.`,
      );
      setNotice(sent
        ? { tone: "success", text: "ChatGPT에 검토 요청을 보냈습니다." }
        : { tone: "info", text: "현재 실행 환경은 후속 메시지 기능을 제공하지 않습니다." });
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error, "검토 요청을 보낼 수 없습니다.") });
    }
  };

  const switchJsonMode = (mode: JsonEditorMode) => {
    setJsonMode(mode);
    setJsonText(editorJsonFor(spec, mode));
    setJsonError("");
  };

  const applyJson = () => {
    const result = parseEditorJson(jsonText, jsonMode, spec);
    if (!result.spec) {
      setJsonError(result.errors[0] ?? "JSON을 적용할 수 없습니다.");
      return;
    }
    setSpec(result.spec);
    setDirty(true);
    setJsonError("");
    setNotice({ tone: "success", text: `${jsonMode === "basic" ? "기본" : "고급"} JSON을 적용했습니다. 도면 생성을 눌러 반영하세요.` });
  };

  const copyEditorJson = async () => {
    const result = await copyTextWithFallback(jsonText, `${downloadBase}-${jsonMode}.json`);
    setNotice({ tone: "success", text: result === "download" ? "JSON을 파일로 저장했습니다." : "JSON을 복사했습니다." });
  };

  const importProject = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = "";
    if (!file) return;
    if (file.size > 8_000_000) {
      setNotice({ tone: "error", text: "프로젝트 파일은 8MB 이하여야 합니다." });
      return;
    }
    try {
      const result = parseProjectJson(await file.text());
      if (result.drawing) {
        applyHydration({ drawing: result.drawing, artifacts: EMPTY_ARTIFACTS, summaryWarnings: [], valid: true, issues: [], errors: [] });
      } else if (result.spec) {
        setSpec(result.spec);
        setDirty(true);
        setJsonText(editorJsonFor(result.spec, jsonMode));
        setNotice({ tone: "success", text: "설계 사양을 가져왔습니다. 도면 생성을 눌러 반영하세요." });
      } else {
        setNotice({ tone: "error", text: result.errors[0] ?? "프로젝트 파일을 읽을 수 없습니다." });
      }
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error, "프로젝트 파일을 읽을 수 없습니다.") });
    }
  };

  const toggleLayer = (layer: string) => {
    setHiddenLayers((current) => {
      const next = new Set(current);
      if (next.has(layer)) next.delete(layer);
      else next.add(layer);
      return next;
    });
  };

  const zoomBy = (factor: number) => setViewport((current) => ({ ...current, zoom: clamp(current.zoom * factor, 0.5, 4) }));
  const fitView = () => setViewport({ zoom: 1, x: 0, y: 0 });
  const resetView = () => {
    fitView();
    setHiddenLayers(new Set());
  };

  const pointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!panEnabled || event.button !== 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    pointerRef.current = { id: event.pointerId, clientX: event.clientX, clientY: event.clientY, x: viewport.x, y: viewport.y };
  };
  const pointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const pointer = pointerRef.current;
    if (!pointer || pointer.id !== event.pointerId) return;
    setViewport((current) => ({ ...current, x: pointer.x + event.clientX - pointer.clientX, y: pointer.y + event.clientY - pointer.clientY }));
  };
  const pointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (pointerRef.current?.id === event.pointerId) pointerRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  };

  if (compactInline) {
    return (
      <main className="compact-card" aria-busy={busy}>
        <header className="compact-header">
          <div className="brand-mark" aria-hidden="true">HS</div>
          <div>
            <p className="eyebrow">HS-CAD MOBILE</p>
            <h1>{drawing.spec.projectName}</h1>
            <p>{drawing.views.length}개 도면 · {drawing.metrics.footprintAreaM2}㎡ · 검토 {warnings.length}건</p>
          </div>
          <span className={`status-dot ${dirty ? "dirty" : "ready"}`}>{dirty ? "편집됨" : "최신"}</span>
        </header>
        <div className="compact-preview">
          <img src={renderedSvgUrl} alt={`${view?.title ?? "도면"} 미리보기`} />
        </div>
        {notice ? <p className={`notice ${notice.tone}`} role={notice.tone === "error" ? "alert" : "status"}>{notice.text}</p> : null}
        <div className="compact-actions" aria-label="주요 작업">
          <button className="primary" type="button" onClick={requestFullscreen}><Icon>↗</Icon>전체 화면에서 편집</button>
          <button className="secondary" type="button" onClick={saveDxf} disabled={!outputsReady}><Icon>↓</Icon>DXF</button>
        </div>
      </main>
    );
  }

  return (
    <main className="app-shell" aria-busy={busy}>
      <header className="app-header">
        <div className="brand-block">
          <div className="brand-mark" aria-hidden="true">HS</div>
          <div>
            <p className="eyebrow">MOBILE ARCHITECTURAL CAD</p>
            <h1>HS-CAD Mobile</h1>
            <p>평면 · 입면 4면 · 단면 2면 · DXF/SVG</p>
          </div>
        </div>
        <div className="header-actions">
          {hosted && displayMode !== "fullscreen" ? <button className="secondary" type="button" onClick={requestFullscreen}>전체 화면</button> : null}
          <button className="primary" type="button" onClick={generate} disabled={busy || !validation.spec}>
            {busy ? "생성 중…" : dirty ? "변경사항으로 생성" : "도면 다시 생성"}
          </button>
        </div>
      </header>

      <section className="status-strip" aria-label="프로젝트 상태">
        <span className={`status-pill ${dirty ? "dirty" : "ready"}`}>{dirty ? "● 변경사항 미생성" : "✓ 도면 최신 상태"}</span>
        <span className="status-pill">스키마 {BUILDING_SCHEMA_VERSION}</span>
        <span className="status-pill">{bridgeSnapshot.status === "connected" ? "MCP Apps 연결" : hosted ? "ChatGPT 호환 모드" : "독립 PWA 모드"}</span>
        <span className="status-pill">ENGINE {drawing.engineVersion}</span>
      </section>

      {notice ? <div className={`notice ${notice.tone}`} role={notice.tone === "error" ? "alert" : "status"}>
        <span>{notice.text}</span><button type="button" aria-label="알림 닫기" onClick={() => setNotice(null)}>×</button>
      </div> : null}

      {validation.errors.length ? <section className="validation-card" role="alert">
        <h2>생성 전에 수정할 항목</h2>
        <ul>{validation.errors.slice(0, 8).map((error) => <li key={error}>{error}</li>)}</ul>
      </section> : null}

      {blockedIssues.length ? <section className="validation-card blocking" role="alert">
        <h2>산출물 생성이 중지되었습니다</h2>
        <p>아래 오류를 교정한 뒤 도면을 다시 생성하세요. 현재 미리보기는 이전 또는 예시 도면이며 다운로드할 수 없습니다.</p>
        <ul>{blockedIssues.slice(0, 12).map((issue) => <li key={`${issue.code}-${issue.path}`}>{issue.message}<small>{issue.path}</small></li>)}</ul>
      </section> : null}

      <section className="workspace-grid">
        <aside className="settings-column" aria-label="설계 설정">
          <details className="panel" open>
            <summary><span><b>01</b> 기본 치수</span><small>단위 mm</small></summary>
            <div className="form-grid">
              <Field label="프로젝트명"><input value={spec.projectName} maxLength={120} onChange={(event) => updateSpec({ projectName: event.currentTarget.value })} /></Field>
              <Field label="도면 축척"><input value={spec.drawingScale ?? ""} maxLength={24} onChange={(event) => updateSpec({ drawingScale: event.currentTarget.value })} /></Field>
              <Field label="가로"><input type="number" inputMode="decimal" min="3000" max="50000" value={Number.isFinite(spec.width) ? spec.width : ""} onChange={(event) => updateNumber("width", event)} /></Field>
              <Field label="세로"><input type="number" inputMode="decimal" min="3000" max="50000" value={Number.isFinite(spec.depth) ? spec.depth : ""} onChange={(event) => updateNumber("depth", event)} /></Field>
              <Field label="외벽 두께"><input type="number" inputMode="decimal" min="80" max="600" value={Number.isFinite(spec.wallThickness) ? spec.wallThickness : ""} onChange={(event) => updateNumber("wallThickness", event)} /></Field>
              <Field label="처마 높이"><input type="number" inputMode="decimal" min="2400" max="15000" value={Number.isFinite(spec.eaveHeight) ? spec.eaveHeight : ""} onChange={(event) => updateNumber("eaveHeight", event)} /></Field>
              <Field label="용마루 높이"><input type="number" inputMode="decimal" min="2600" max="20000" value={Number.isFinite(spec.ridgeHeight) ? spec.ridgeHeight : ""} onChange={(event) => updateNumber("ridgeHeight", event)} /></Field>
              <Field label="다락 바닥"><input type="number" inputMode="decimal" min="1800" max="12000" value={Number.isFinite(spec.atticFloorHeight) ? spec.atticFloorHeight : ""} onChange={(event) => updateNumber("atticFloorHeight", event)} /></Field>
              <Field label="실내 천장"><input type="number" inputMode="decimal" min="2100" max="10000" value={Number.isFinite(spec.ceilingHeight) ? spec.ceilingHeight : ""} onChange={(event) => updateNumber("ceilingHeight", event)} /></Field>
              <Field label="다락 최소 유효높이"><input type="number" inputMode="decimal" min="600" max="5000" value={spec.atticMinimumClearHeight ?? 1800} onChange={(event) => updateNumber("atticMinimumClearHeight", event)} /></Field>
              <Field label="지붕 돌출"><input type="number" inputMode="decimal" min="0" max="2000" value={Number.isFinite(spec.roofOverhang) ? spec.roofOverhang : ""} onChange={(event) => updateNumber("roofOverhang", event)} /></Field>
              <Field label="지붕 두께"><input type="number" inputMode="decimal" min="80" max="800" value={Number.isFinite(spec.roofThickness) ? spec.roofThickness : ""} onChange={(event) => updateNumber("roofThickness", event)} /></Field>
              <Field label="바닥 슬래브"><input type="number" inputMode="decimal" min="80" max="800" value={Number.isFinite(spec.floorSlabThickness) ? spec.floorSlabThickness : ""} onChange={(event) => updateNumber("floorSlabThickness", event)} /></Field>
              <Field label="기초 깊이"><input type="number" inputMode="decimal" min="250" max="4000" value={Number.isFinite(spec.foundationDepth) ? spec.foundationDepth : ""} onChange={(event) => updateNumber("foundationDepth", event)} /></Field>
              <Field label="용마루 방향"><select value={spec.roofDirection} onChange={(event) => updateSpec({ roofDirection: event.currentTarget.value as BuildingSpec["roofDirection"] })}><option value="ridge-along-depth">세로 방향</option><option value="ridge-along-width">가로 방향</option></select></Field>
            </div>
          </details>

          <details className="panel">
            <summary><span><b>02</b> 마감 사양</span><small>텍스트</small></summary>
            <div className="form-stack">
              <Field label="지붕 마감"><input value={spec.roofFinish} maxLength={120} onChange={(event) => updateSpec({ roofFinish: event.currentTarget.value })} /></Field>
              <Field label="외벽 마감"><input value={spec.wallFinish} maxLength={120} onChange={(event) => updateSpec({ wallFinish: event.currentTarget.value })} /></Field>
              <Field label="기단부 마감"><input value={spec.plinthFinish} maxLength={120} onChange={(event) => updateSpec({ plinthFinish: event.currentTarget.value })} /></Field>
              <Field label="창호 프레임"><input value={spec.frameFinish ?? ""} maxLength={120} onChange={(event) => updateSpec({ frameFinish: event.currentTarget.value })} /></Field>
              <Field label="홈통·선홈통"><input value={spec.gutterDownspoutSpec ?? ""} maxLength={120} onChange={(event) => updateSpec({ gutterDownspoutSpec: event.currentTarget.value })} /></Field>
            </div>
          </details>

          <details className="panel json-panel" open={advancedOpen} onToggle={(event) => setAdvancedOpen(event.currentTarget.open)}>
            <summary><span><b>03</b> JSON 편집·가져오기</span><small>검증 후 적용</small></summary>
            <div className="json-toolbar" role="tablist" aria-label="JSON 범위">
              <button type="button" role="tab" aria-selected={jsonMode === "basic"} className={jsonMode === "basic" ? "active" : ""} onClick={() => switchJsonMode("basic")}>기본 사양</button>
              <button type="button" role="tab" aria-selected={jsonMode === "advanced"} className={jsonMode === "advanced" ? "active" : ""} onClick={() => switchJsonMode("advanced")}>고급 형상</button>
            </div>
            <textarea value={jsonText} onChange={(event) => setJsonText(event.currentTarget.value)} spellCheck={false} aria-label={`${jsonMode === "basic" ? "기본 사양" : "고급 형상"} JSON`} />
            {jsonError ? <p className="field-error" role="alert">{jsonError}</p> : null}
            <div className="button-grid">
              <button type="button" className="secondary" onClick={applyJson}>JSON 적용</button>
              <button type="button" className="secondary" onClick={() => setJsonText(editorJsonFor(spec, jsonMode))}>현재값 불러오기</button>
              <button type="button" className="secondary" onClick={copyEditorJson}>JSON 복사</button>
              <button type="button" className="secondary" onClick={() => fileInputRef.current?.click()}>프로젝트 가져오기</button>
            </div>
            <input ref={fileInputRef} className="visually-hidden" type="file" accept="application/json,.json,.hscad.json" onChange={importProject} />
          </details>
        </aside>

        <section className="drawing-column" aria-label="도면 작업 영역">
          <div className="metrics-grid">
            <MetricCard label="건축면적" value={drawing.metrics.footprintAreaM2} unit="㎡" />
            <MetricCard label="외벽 둘레" value={drawing.metrics.perimeterM} unit="m" />
            <MetricCard label="지붕 경사" value={drawing.metrics.roofPitchDegrees} unit="°" />
            <MetricCard label="다락 유효폭" value={drawing.metrics.atticUsableWidthAtMinimum ?? drawing.metrics.atticUsableWidthAt1800} unit="mm" />
          </div>

          <section className="drawing-panel">
            <header className="drawing-heading">
              <div><p className="eyebrow">DRAWING VIEW</p><h2>{view?.title ?? "도면"}</h2></div>
              <label className="view-select-label"><span>도면 선택</span><select value={active} onChange={(event) => setActive(event.currentTarget.value as ViewKind)}>{drawing.views.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
            </header>
            <nav className="view-tabs" aria-label="도면 보기">{drawing.views.map((item) => <button type="button" key={item.id} className={item.id === active ? "active" : ""} aria-current={item.id === active ? "page" : undefined} onClick={() => setActive(item.id)}>{item.title}</button>)}</nav>

            <div className="view-toolbar" aria-label="도면 확대 및 이동">
              <button type="button" onClick={() => zoomBy(0.8)} aria-label="축소">−</button>
              <output aria-label="확대 비율">{Math.round(viewport.zoom * 100)}%</output>
              <button type="button" onClick={() => zoomBy(1.25)} aria-label="확대">＋</button>
              <button type="button" className={panEnabled ? "active" : ""} aria-pressed={panEnabled} onClick={() => setPanEnabled((value) => !value)}>이동</button>
              <button type="button" onClick={fitView}>맞춤</button>
              <button type="button" onClick={resetView}>초기화</button>
            </div>

            <div
              className={`canvas-viewport ${panEnabled ? "can-pan" : ""} ${blockedIssues.length ? "blocked" : ""}`}
              onPointerDown={pointerDown}
              onPointerMove={pointerMove}
              onPointerUp={pointerUp}
              onPointerCancel={pointerUp}
            >
              <div className="drawing-image" style={{ transform: `translate3d(${viewport.x}px, ${viewport.y}px, 0) scale(${viewport.zoom})` }}>
                <img src={renderedSvgUrl} alt={`${view?.title ?? "건축 도면"} — 선택한 레이어만 표시`} draggable={false} />
              </div>
              {blockedIssues.length ? <div className="canvas-blocker"><strong>산출물 없음</strong><span>차단 오류를 수정하고 다시 생성하세요.</span></div> : null}
            </div>

            <details className="layer-panel">
              <summary>레이어 표시 <small>{layers.length - hiddenLayers.size}/{layers.length}</small></summary>
              <div className="layer-grid">{layers.map((layer) => <label key={layer}><input type="checkbox" checked={!hiddenLayers.has(layer)} onChange={() => toggleLayer(layer)} /><span>{layer}</span></label>)}</div>
            </details>
          </section>

          <section className="review-grid">
            <details className="review-panel" open={warnings.length > 0}>
              <summary><span>검토 항목</span><b>{warnings.length}</b></summary>
              {warnings.length ? <ul>{warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul> : <p className="empty-state">자동 검토 경고가 없습니다. 전문 검토는 별도로 진행하세요.</p>}
            </details>
            <details className="review-panel">
              <summary><span>창호 일람표</span><b>{drawing.openingSchedule.length}</b></summary>
              <div className="schedule-grid">{drawing.openingSchedule.map((row, index) => <article key={`${row.mark}-${row.kind}-${index}`}><header><strong>{row.mark}</strong><span>{row.kind === "door" ? "문" : "창"} × {row.count}</span></header><dl><div><dt>폭</dt><dd>{row.width}</dd></div><div><dt>높이</dt><dd>{row.height}</dd></div><div><dt>창대</dt><dd>{row.sill}</dd></div></dl></article>)}</div>
            </details>
          </section>
        </section>
      </section>

      <section className="export-panel" aria-label="내보내기">
        <div><p className="eyebrow">EXPORT</p><h2>도면 파일</h2><p>검증된 현재 도면으로 파일을 만듭니다.</p></div>
        <div className="export-actions">
          <button type="button" onClick={saveDxf} disabled={!outputsReady}><Icon>DXF</Icon><span>전체 DXF<small>CAD 교환 파일</small></span></button>
          <button type="button" onClick={saveCurrentSvg} disabled={!outputsReady}><Icon>SVG</Icon><span>현재 도면 SVG<small>{view?.title}</small></span></button>
          <button type="button" onClick={saveSheetSvg} disabled={!outputsReady}><Icon>7</Icon><span>전체 시트 SVG<small>7개 도면 한 장</small></span></button>
          <button type="button" onClick={saveProject} disabled={!outputsReady}><Icon>{"{}"}</Icon><span>프로젝트 JSON<small>다시 가져오기 가능</small></span></button>
        </div>
        <div className="export-secondary">
          <button type="button" className="secondary" onClick={copyProject} disabled={!outputsReady}>프로젝트 JSON 복사</button>
          <button type="button" className="secondary" onClick={askChatGpt}>ChatGPT에 검토 요청</button>
        </div>
      </section>

      <footer className="app-footer">
        <strong>HS-CAD Mobile</strong>
        <p>생성 도면은 개념 설계용입니다. 시공 전 구조·법규·현장 조건을 자격 있는 전문가가 검토해야 합니다.</p>
      </footer>
    </main>
  );
}

const rootElement = document.getElementById("root");
if (rootElement) createRoot(rootElement).render(<App />);
