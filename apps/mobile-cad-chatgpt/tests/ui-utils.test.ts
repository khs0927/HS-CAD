// @vitest-environment happy-dom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { generateDrawingSet } from "../src/cad-model";
import { BUILDING_SCHEMA_VERSION, type BuildingSpec } from "../src/types";
import {
  copyTextWithFallback,
  downloadText,
  extractHydratedResult,
  parseProjectJson,
  validateBuildingSpec,
  validateDrawingSet,
} from "../src/ui-utils";

const validSpec: BuildingSpec = {
  schemaVersion: BUILDING_SCHEMA_VERSION,
  projectName: "UI test house",
  unit: "mm",
  width: 12_000,
  depth: 10_000,
  wallThickness: 200,
  eaveHeight: 3_200,
  ridgeHeight: 5_000,
  atticFloorHeight: 2_600,
  ceilingHeight: 2_400,
  roofDirection: "ridge-along-depth",
  roofOverhang: 450,
  roofThickness: 220,
  floorSlabThickness: 180,
  foundationDepth: 700,
  roofFinish: "Metal",
  wallFinish: "Render",
  plinthFinish: "Concrete",
};

describe("UI input and host-result guards", () => {
  it("accepts the current 1.0 BuildingSpec and rejects unknown top-level keys", () => {
    expect(validateBuildingSpec(validSpec).spec?.schemaVersion).toBe("1.0");
    const invalid = validateBuildingSpec({ ...validSpec, silentlyDropped: true });
    expect(invalid.spec).toBeUndefined();
    expect(invalid.errors.join(" ")).toContain("silentlyDropped");
  });

  it("does not silently drop unknown fields during project JSON import", () => {
    const imported = parseProjectJson(JSON.stringify({ ...validSpec, injectedField: "no" }));
    expect(imported.spec).toBeUndefined();
    expect(imported.errors.join(" ")).toContain("injectedField");
  });

  it("rejects an unsafe entity layer before SVG rendering", () => {
    const drawing = generateDrawingSet(validSpec);
    const malicious = structuredClone(drawing);
    malicious.views[0].entities[0].layer = 'A-WALL" onload="alert(1)';
    const result = validateDrawingSet(malicious);
    expect(result.drawing).toBeUndefined();
    expect(result.errors.join(" ")).toContain("type/layer");
  });

  it("hydrates private drawing and text artifacts from tool-result _meta", () => {
    const drawing = generateDrawingSet(validSpec);
    const hydrated = extractHydratedResult({
      structuredContent: { spec: drawing.spec, valid: true, warnings: [] },
      _meta: {
        drawing,
        artifacts: {
          dxf: { id: "dxf", text: "0\nEOF\n" },
          sheetSvg: { id: "sheetSvg", text: "<svg/>" },
          viewSvgs: [{ id: "viewSvg:plan", title: "PLAN", text: "<svg/>" }],
          projectJson: { id: "projectJson", text: "{}" },
        },
      },
    });
    expect(hydrated.drawing?.spec.projectName).toBe("UI test house");
    expect(hydrated.artifacts.dxf).toBe("0\nEOF\n");
    expect(hydrated.artifacts.viewSvgs.plan).toBe("<svg/>");
    expect(hydrated.valid).toBe(true);
  });

  it("marks semantic error results invalid without fabricating a drawing", () => {
    const hydrated = extractHydratedResult({
      isError: true,
      structuredContent: {
        valid: false,
        issues: [{ code: "ROOF_HEIGHT", path: "ridgeHeight", severity: "error", message: "Ridge must exceed eave." }],
        warnings: [],
      },
    });
    expect(hydrated.valid).toBe(false);
    expect(hydrated.drawing).toBeUndefined();
    expect(hydrated.issues).toEqual([expect.objectContaining({ severity: "error", path: "ridgeHeight" })]);
  });
});

describe("sandbox-safe file helpers", () => {
  const createObjectURL = vi.fn(() => "blob:hscad-test");
  const revokeObjectURL = vi.fn();
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);

  beforeEach(() => {
    vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL });
    createObjectURL.mockClear();
    revokeObjectURL.mockClear();
    click.mockClear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("creates a typed Blob and activates a download link", async () => {
    const blob = downloadText("drawing.dxf", "0\nEOF\n", "application/dxf;charset=utf-8");
    expect(blob.type).toBe("application/dxf;charset=utf-8");
    expect(await blob.text()).toBe("0\nEOF\n");
    expect(createObjectURL).toHaveBeenCalledWith(blob);
    expect(click).toHaveBeenCalledOnce();
  });

  it("falls back to a download when clipboard and execCommand are unavailable", async () => {
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: undefined });
    Object.defineProperty(document, "execCommand", { configurable: true, value: undefined });
    await expect(copyTextWithFallback("{}", "project.json")).resolves.toBe("download");
    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
  });
});
