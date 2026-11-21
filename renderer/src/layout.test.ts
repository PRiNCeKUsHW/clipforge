import { describe, expect, it } from "vitest";

import { captionPosition, fitGeometry, isFramedLayout } from "./layout";
import type { CropPath } from "./types";

const crop16x9: CropPath = { layout: "single", source: { w: 1920, h: 1080 }, keyframes: [{ t: 0, x: 0.5 }] };
const split: CropPath = { layout: "split", source: { w: 1920, h: 1080 }, panels: [[], []] };

describe("fitGeometry", () => {
  it("puts the full-width 16:9 band in the middle for blur_fit", () => {
    const g = fitGeometry("blur_fit", crop16x9, 1080, 1920, false);
    expect(g.videoHeight).toBeCloseTo(607.5);
    expect(g.videoTop + g.videoHeight / 2).toBeCloseTo(960);
    expect(g.titleBottom).toBeNull();
  });

  it("leaves room for a title above the band in centered_title", () => {
    const g = fitGeometry("centered_title", crop16x9, 1080, 1920, true);
    expect(g.titleBottom).not.toBeNull();
    expect(g.titleBottom!).toBeLessThan(g.videoTop);
    expect(g.titleBottom!).toBeGreaterThan(300); // enough space for 2-3 lines of title
  });

  it("captions go below the video band", () => {
    const g = fitGeometry("centered_title", crop16x9, 1080, 1920, true);
    expect(g.captionY * 1920).toBeGreaterThan(g.videoTop + g.videoHeight);
    expect(g.captionY).toBeLessThanOrEqual(0.9);
  });
});

describe("captionPosition", () => {
  it("depends on the layout", () => {
    expect(captionPosition("auto", split, 0.7, 1080, 1920, false)).toBe(0.5);
    expect(captionPosition("podcast_split", split, 0.7, 1080, 1920, false)).toBe(0.5);
    expect(captionPosition("single", crop16x9, 0.7, 1080, 1920, false)).toBe(0.7);
    expect(captionPosition("blur_fit", crop16x9, 0.7, 1080, 1920, false)).toBeGreaterThan(0.66);
  });

  it("knows which layouts are framed", () => {
    expect(["centered_title", "blur_fit"].every((l) => isFramedLayout(l as never))).toBe(true);
    expect(isFramedLayout("auto")).toBe(false);
  });
});
