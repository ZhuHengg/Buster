import { describe, expect, it } from "vitest";

import { bestGrid } from "./layout";

describe("bestGrid", () => {
  it("returns a single cell for one camera", () => {
    expect(bestGrid(1, 1200, 700, 16 / 9)).toEqual({ cols: 1, rows: 1 });
  });
  it("puts landscape footage in a near-square grid", () => {
    const g = bestGrid(6, 1200, 700, 16 / 9);
    expect(g.cols * g.rows).toBeGreaterThanOrEqual(6);
    expect(g.cols).toBeLessThanOrEqual(3);
  });
  it("uses more, narrower columns for portrait footage in a wide container", () => {
    const portrait = bestGrid(6, 1400, 700, 9 / 16);
    const landscape = bestGrid(6, 1400, 700, 16 / 9);
    expect(portrait.cols).toBeGreaterThan(landscape.cols);
  });
});
