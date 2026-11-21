import { describe, expect, it } from "vitest";

import { coverPlacement, xAt } from "./crop";

describe("xAt", () => {
  const kf = [
    { t: 0, x: 0.3 },
    { t: 2, x: 0.7 },
    { t: 2, x: 0.2 }, // instant cut
    { t: 4, x: 0.2 },
  ];
  it("interpolates and holds at the ends", () => {
    expect(xAt(kf, -1)).toBe(0.3);
    expect(xAt(kf, 1)).toBeCloseTo(0.5);
    expect(xAt(kf, 3)).toBeCloseTo(0.2);
    expect(xAt(kf, 10)).toBe(0.2);
    expect(xAt([], 1)).toBe(0.5);
  });
});

describe("coverPlacement", () => {
  it("fills a 9:16 frame from 16:9 and centres the requested point", () => {
    const p = coverPlacement(1920, 1080, 1080, 1920, 0.5);
    expect(p.height).toBe(1920);
    expect(p.width).toBeCloseTo(3413.33, 1);
    expect(p.left).toBeCloseTo(540 - 0.5 * p.width, 1);
    expect(p.top).toBe(0);
  });

  it("clamps so the frame is always covered", () => {
    expect(coverPlacement(1920, 1080, 1080, 1920, 0).left).toBe(0);
    const right = coverPlacement(1920, 1080, 1080, 1920, 1);
    expect(right.left + right.width).toBeCloseTo(1080);
  });

  it("covers a split panel", () => {
    const p = coverPlacement(1920, 1080, 1080, 960, 0.25);
    expect(p.height).toBeCloseTo(960);
    expect(p.width).toBeGreaterThanOrEqual(1080);
  });
});
