import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("v1656 mobile Home layout contract", () => {
  it("keeps a bounded mobile map with accessible offers below it", () => {
    const css = readFileSync("src/legacy/public/legacy-public.css", "utf8");
    const normalized = css.replace(/\s+/g, " ");

    expect(normalized).toContain(
      ".app-shell.home-active { height: 100dvh; max-height: 100dvh; overflow: hidden; }",
    );
    expect(normalized).toContain(
      "grid-template-rows: repeat(5, auto)",
    );
    expect(normalized).toContain(
      ".screen[data-screen=\"home\"] > #followedProfileStrip { height: 88px",
    );
    expect(normalized).toContain(
      "grid-template-rows: auto clamp(160px, 30dvh, 240px)",
    );
    expect(normalized).toContain(
      ".screen[data-screen=\"home\"] .home-map-pane .map-wrap { height: 100%",
    );
    expect(normalized).toContain("overflow-x: hidden; overflow-y: auto; padding-bottom: env(safe-area-inset-bottom, 0px)");
    expect(normalized).toContain("grid-template-rows: repeat(5, auto); gap: 4px; align-content: start");
    expect(normalized).toContain(".pin .dot.has-photo");
    expect(normalized).toContain(".pin .pin-fallback");
  });

  it("keeps discovery in its own row when guest follows or advertisements are absent", () => {
    const css = readFileSync("src/legacy/public/legacy-public.css", "utf8");
    const normalized = css.replace(/\s+/g, " ");
    for (const [selector, row] of [
      ["#followedProfileStrip", 1],
      [".home-discovery", 2],
      ["#adBox", 3],
      ["#adDots", 4],
      ["#districtOffersMount", 5],
    ]) {
      expect(normalized).toContain(`.screen[data-screen="home"] > ${selector} { grid-row: ${row}; }`);
    }
    expect(normalized).toContain("grid-template-rows: repeat(5, auto)");
  });

  it("keeps the exact v1656 dark palette available to the Home shell", () => {
    const css = readFileSync("src/legacy/public/legacy-public.css", "utf8");
    const normalized = css.replace(/\s+/g, " ");

    expect(normalized).toContain("[data-theme=\"dark\"] .app-shell");
    expect(normalized).toContain("--bg: #0e1413");
    expect(normalized).toContain("--map-land: #161f1c");
    expect(normalized).toContain("--shadow-lg:");
  });
});
