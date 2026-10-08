// @vitest-environment happy-dom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { App } from "../src/app";

const styles = readFileSync(join(process.cwd(), "src", "styles.css"), "utf8");

beforeAll(() => {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
  });
  if (!globalThis.ResizeObserver) {
    vi.stubGlobal("ResizeObserver", class {
      observe() {}
      disconnect() {}
    });
  }
});

afterEach(() => cleanup());

describe("mobile editor smoke behavior", () => {
  it("keeps viewport overflow contained and touch controls at least 44px", () => {
    expect(styles).toContain("overflow-x: hidden");
    expect(styles).toMatch(/button,\s*input,\s*select\s*\{[\s\S]*?min-height:\s*44px/);
    expect(styles).toContain("width: 100%");
    expect(styles).not.toContain("min-width: 520px");
  });

  it("renders a standalone editor, then blocks invalid semantic results and downloads", async () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "HS-CAD Mobile" })).toBeTruthy();
    expect((screen.getByRole("button", { name: /도면 다시 생성|변경사항으로 생성/ }) as HTMLButtonElement).disabled).toBe(false);

    window.dispatchEvent(new CustomEvent("openai:set_globals", {
      detail: {
        globals: {
          toolOutput: {
            valid: false,
            issues: [{ code: "SELF_INTERSECTION", path: "outline", severity: "error", message: "Outline self-intersects." }],
            warnings: [],
          },
        },
      },
    }));

    expect(await screen.findByRole("heading", { name: "산출물 생성이 중지되었습니다" })).toBeTruthy();
    expect(screen.getAllByText("Outline self-intersects.").length).toBeGreaterThan(0);
    await waitFor(() => expect((screen.getByRole("button", { name: /전체 DXF/ }) as HTMLButtonElement).disabled).toBe(true));
    expect(screen.getByText("산출물 없음")).toBeTruthy();
  });
});
