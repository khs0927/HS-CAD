import { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { generateDrawingSet, validateSpec } from "./cad-model";
import { drawingSetToDxf } from "./dxf";
import { drawingSetToSvgSheet, viewToSvg } from "./svg";
import type { BuildingSpec, DrawingSet, ViewKind } from "./types";
import "./styles.css";

type OpenAiGlobals = {
  toolOutput?: unknown;
  toolInput?: unknown;
  widgetState?: unknown;
  theme?: "light" | "dark";
  displayMode?: string;
};

declare global {
  interface Window {
    openai?: OpenAiGlobals & {
      callTool?: (name: string, args: Record<string, unknown>) => Promise<unknown>;
      sendFollowUpMessage?: (message: { prompt: string; scrollToBottom?: boolean }) => Promise<void>;
      requestDisplayMode?: (request: { mode: "inline" | "pip" | "fullscreen" }) => Promise<unknown>;
      setWidgetState?: (state: unknown) => void;
      notifyIntrinsicHeight?: (height?: number) => void;
      requestClose?: () => Promise<void>;
    };
  }
  interface WindowEventMap {
    "openai:set_globals": CustomEvent<{ globals: OpenAiGlobals }>;
  }
}

const defaults: BuildingSpec = {
  projectName: "박공지붕 건축도면",
  unit: "mm",
  width: 12000,
  depth: 11300,
  wallThickness: 200,
  eaveHeight: 3200,
  ridgeHeight: 5000,
  atticFloorHeight: 2600,
  ceilingHeight: 2500,
  roofDirection: "ridge-along-depth",
  roofOverhang: 450,
  roofThickness: 220,
  floorSlabThickness: 180,
  foundationDepth: 700,
  roofFinish: "Standing seam metal",
  wallFinish: "Exterior render / panel",
  plinthFinish: "Exposed concrete / stone",
};

const extractDrawing = (value: unknown): DrawingSet | null => {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  const drawing = record.drawing;
  return drawing && typeof drawing === "object" ? drawing as DrawingSet : null;
};

const extractWidgetState = (value: unknown): { spec?: BuildingSpec; active?: ViewKind } => {
  if (!value || typeof value !== "object") return {};
  const state = value as Record<string, unknown>;
  return {
    spec: state.spec && typeof state.spec === "object" ? state.spec as BuildingSpec : undefined,
    active: typeof state.active === "string" ? state.active as ViewKind : undefined,
  };
};

const safeFilename = (value: string): string => value.trim().replace(/[\\/:*?"<>|]+/g, "-").replace(/\s+/g, "_") || "hscad-drawing";

const saveText = (name: string, content: string, type: string): void => {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};

const Field = ({ label, children }: { label: string; children: React.ReactNode }) => <label className="field"><span>{label}</span>{children}</label>;

function App() {
  const initialDrawing = extractDrawing(window.openai?.toolOutput) ?? generateDrawingSet(defaults);
  const initialState = extractWidgetState(window.openai?.widgetState);
  const [spec, setSpec] = useState<BuildingSpec>(initialState.spec ?? initialDrawing.spec);
  const [drawing, setDrawing] = useState<DrawingSet>(initialDrawing);
  const [active, setActive] = useState<ViewKind>(initialState.active ?? "plan");
  const [busy, setBusy] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [advancedJson, setAdvancedJson] = useState(() => JSON.stringify({
    outline: initialDrawing.spec.outline,
    interiorWalls: initialDrawing.spec.interiorWalls,
    openings: initialDrawing.spec.openings,
    stair: initialDrawing.spec.stair,
  }, null, 2));
  const [advancedError, setAdvancedError] = useState("");

  const view = useMemo(() => drawing.views.find((item) => item.id === active) ?? drawing.views[0], [drawing, active]);
  const svg = useMemo(() => viewToSvg(view), [view]);
  const liveWarnings = useMemo(() => validateSpec(spec), [spec]);

  useEffect(() => {
    const handleGlobals = (event: WindowEventMap["openai:set_globals"]) => {
      const next = extractDrawing(event.detail?.globals?.toolOutput);
      if (next) {
        setDrawing(next);
        setSpec(next.spec);
        setAdvancedJson(JSON.stringify({ outline: next.spec.outline, interiorWalls: next.spec.interiorWalls, openings: next.spec.openings, stair: next.spec.stair }, null, 2));
      }
    };
    window.addEventListener("openai:set_globals", handleGlobals, { passive: true });
    return () => window.removeEventListener("openai:set_globals", handleGlobals);
  }, []);

  useEffect(() => {
    window.openai?.setWidgetState?.({ spec, active });
  }, [spec, active]);

  useEffect(() => {
    const reportHeight = () => window.openai?.notifyIntrinsicHeight?.(document.documentElement.scrollHeight);
    reportHeight();
    const observer = new ResizeObserver(reportHeight);
    observer.observe(document.body);
    return () => observer.disconnect();
  }, []);

  const updateNumber = (key: keyof BuildingSpec, value: string) => setSpec((current) => ({ ...current, [key]: Number(value) }));
  const updateText = (key: keyof BuildingSpec, value: string) => setSpec((current) => ({ ...current, [key]: value }));

  const applyAdvancedJson = () => {
    try {
      const parsed = JSON.parse(advancedJson) as Partial<BuildingSpec>;
      setSpec((current) => ({ ...current, ...parsed }));
      setAdvancedError("");
    } catch (error) {
      setAdvancedError(error instanceof Error ? error.message : "JSON 형식을 확인하세요.");
    }
  };

  const generate = async () => {
    setBusy(true);
    try {
      if (window.openai?.callTool) {
        const result = await window.openai.callTool("generate_architectural_set", spec as unknown as Record<string, unknown>);
        const resultRecord = result && typeof result === "object" ? result as Record<string, unknown> : {};
        const next = extractDrawing(resultRecord.structuredContent ?? result);
        if (next) {
          setDrawing(next);
          setSpec(next.spec);
          return;
        }
      }
      setDrawing(generateDrawingSet(spec));
    } finally {
      setBusy(false);
    }
  };

  const downloadBase = safeFilename(spec.projectName);

  return <main className="app-shell">
    <header className="hero">
      <div>
        <p className="eyebrow">MOBILE-ONLY ARCHITECTURAL CAD</p>
        <h1>HS-CAD Mobile</h1>
        <p>평면도 · 입면도 4면 · 단면도 2면 · 상세 DXF/SVG</p>
      </div>
      <div className="hero-actions">
        <button className="ghost" onClick={() => window.openai?.requestDisplayMode?.({ mode: "fullscreen" })}>전체화면</button>
        <button className="primary" onClick={generate} disabled={busy}>{busy ? "생성 중…" : "도면 생성"}</button>
      </div>
    </header>

    <section className="panel">
      <div className="panel-heading"><div><p className="step">01</p><h2>기본 치수와 지붕</h2></div><span className="badge">단위 mm</span></div>
      <div className="controls">
        <Field label="프로젝트"><input value={spec.projectName} onChange={(event) => updateText("projectName", event.target.value)} /></Field>
        <Field label="가로"><input inputMode="decimal" value={spec.width} onChange={(event) => updateNumber("width", event.target.value)} /></Field>
        <Field label="세로"><input inputMode="decimal" value={spec.depth} onChange={(event) => updateNumber("depth", event.target.value)} /></Field>
        <Field label="외벽 두께"><input inputMode="decimal" value={spec.wallThickness} onChange={(event) => updateNumber("wallThickness", event.target.value)} /></Field>
        <Field label="처마 높이"><input inputMode="decimal" value={spec.eaveHeight} onChange={(event) => updateNumber("eaveHeight", event.target.value)} /></Field>
        <Field label="용마루 높이"><input inputMode="decimal" value={spec.ridgeHeight} onChange={(event) => updateNumber("ridgeHeight", event.target.value)} /></Field>
        <Field label="다락 바닥"><input inputMode="decimal" value={spec.atticFloorHeight} onChange={(event) => updateNumber("atticFloorHeight", event.target.value)} /></Field>
        <Field label="실내 천장"><input inputMode="decimal" value={spec.ceilingHeight} onChange={(event) => updateNumber("ceilingHeight", event.target.value)} /></Field>
        <Field label="처마 돌출"><input inputMode="decimal" value={spec.roofOverhang} onChange={(event) => updateNumber("roofOverhang", event.target.value)} /></Field>
        <Field label="지붕 두께"><input inputMode="decimal" value={spec.roofThickness} onChange={(event) => updateNumber("roofThickness", event.target.value)} /></Field>
        <Field label="바닥 슬래브"><input inputMode="decimal" value={spec.floorSlabThickness} onChange={(event) => updateNumber("floorSlabThickness", event.target.value)} /></Field>
        <Field label="기초 깊이"><input inputMode="decimal" value={spec.foundationDepth} onChange={(event) => updateNumber("foundationDepth", event.target.value)} /></Field>
        <Field label="용마루 방향"><select value={spec.roofDirection} onChange={(event) => setSpec({ ...spec, roofDirection: event.target.value as BuildingSpec["roofDirection"] })}><option value="ridge-along-depth">세로 방향</option><option value="ridge-along-width">가로 방향</option></select></Field>
      </div>
    </section>

    <section className="panel">
      <div className="panel-heading"><div><p className="step">02</p><h2>마감 사양</h2></div></div>
      <div className="controls finish-controls">
        <Field label="지붕 마감"><input value={spec.roofFinish} onChange={(event) => updateText("roofFinish", event.target.value)} /></Field>
        <Field label="외벽 마감"><input value={spec.wallFinish} onChange={(event) => updateText("wallFinish", event.target.value)} /></Field>
        <Field label="기단부 마감"><input value={spec.plinthFinish} onChange={(event) => updateText("plinthFinish", event.target.value)} /></Field>
      </div>
    </section>

    <section className="metrics" aria-label="도면 주요 수치">
      <article><span>건축면적</span><strong>{drawing.metrics.footprintAreaM2}㎡</strong></article>
      <article><span>외벽 둘레</span><strong>{drawing.metrics.perimeterM}m</strong></article>
      <article><span>지붕 경사</span><strong>{drawing.metrics.roofPitchDegrees}°</strong></article>
      <article><span>다락 최고높이</span><strong>{drawing.metrics.atticPeakHeight}mm</strong></article>
      <article><span>1.8m 유효폭</span><strong>{drawing.metrics.atticUsableWidthAt1800}mm</strong></article>
      <article><span>창호 수</span><strong>{drawing.metrics.openingCount}</strong></article>
    </section>

    {(liveWarnings.length > 0 || drawing.warnings.length > 0) && <aside className="warnings">
      <h3>설계 검토 항목</h3>
      {[...new Set([...liveWarnings, ...drawing.warnings])].map((warning) => <p key={warning}>⚠ {warning}</p>)}
    </aside>}

    <section className="panel advanced-panel">
      <button className="advanced-toggle" onClick={() => setAdvancedOpen((value) => !value)} aria-expanded={advancedOpen}>
        <span><b>고급 형상 편집</b><small>외곽 폴리라인·내부벽·문·창·계단 JSON</small></span><span>{advancedOpen ? "접기" : "열기"}</span>
      </button>
      {advancedOpen && <div className="advanced-body">
        <textarea value={advancedJson} onChange={(event) => setAdvancedJson(event.target.value)} spellCheck={false} aria-label="고급 형상 JSON" />
        {advancedError && <p className="error">{advancedError}</p>}
        <div className="inline-actions"><button onClick={applyAdvancedJson}>JSON 적용</button><button onClick={() => setAdvancedJson(JSON.stringify({ outline: spec.outline, interiorWalls: spec.interiorWalls, openings: spec.openings, stair: spec.stair }, null, 2))}>현재값 다시 불러오기</button></div>
      </div>}
    </section>

    <section className="drawing-section">
      <div className="panel-heading"><div><p className="step">03</p><h2>도면 미리보기</h2></div><span className="badge">ENGINE {drawing.engineVersion}</span></div>
      <nav className="tabs">{drawing.views.map((item) => <button key={item.id} className={item.id === active ? "active" : ""} onClick={() => setActive(item.id)}>{item.title}</button>)}</nav>
      <div className="canvas-card"><div className="drawing" dangerouslySetInnerHTML={{ __html: svg }} /></div>
    </section>

    <section className="panel schedule-panel">
      <div className="panel-heading"><div><p className="step">04</p><h2>창호 일람표</h2></div></div>
      <div className="table-scroll"><table><thead><tr><th>기호</th><th>종류</th><th>수량</th><th>폭</th><th>높이</th><th>창대</th></tr></thead><tbody>{drawing.openingSchedule.map((row) => <tr key={`${row.mark}-${row.kind}-${row.width}`}><td>{row.mark}</td><td>{row.kind === "door" ? "문" : "창"}</td><td>{row.count}</td><td>{row.width}</td><td>{row.height}</td><td>{row.sill}</td></tr>)}</tbody></table></div>
    </section>

    <section className="actions">
      <button onClick={() => saveText(`${downloadBase}.dxf`, drawingSetToDxf(drawing), "application/dxf")}>DXF 다운로드</button>
      <button onClick={() => saveText(`${downloadBase}.svg`, drawingSetToSvgSheet(drawing), "image/svg+xml")}>전체 SVG 다운로드</button>
      <button onClick={() => saveText(`${downloadBase}.json`, JSON.stringify(drawing, null, 2), "application/json")}>도면 JSON 저장</button>
      <button onClick={() => window.openai?.sendFollowUpMessage?.({ prompt: `현재 ${spec.projectName}의 ${view.title}을 검토하고, 창호·치수·재료·구조 디테일 중 누락된 항목을 보완해줘. 기존 높이와 외곽선은 유지해줘.`, scrollToBottom: true })}>GPT 상세 검토</button>
    </section>

    <footer>
      <b>HS-CAD Mobile</b><span>모바일에서 신규 DXF/SVG 도면을 생성합니다. 실시설계·구조·법규 확정 전 전문 검토가 필요합니다.</span>
    </footer>
  </main>;
}

createRoot(document.getElementById("root")!).render(<App />);
