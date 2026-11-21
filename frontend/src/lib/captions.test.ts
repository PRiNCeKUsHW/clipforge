import { describe, expect, it } from "vitest";

import { captionLines, formatTimePrecise, parseTime } from "./captions";

const words = (text: string, step = 0.4) =>
  text.split(" ").map((word, i) => ({ word, start: i * step, end: i * step + 0.3 }));

describe("captionLines (same rules as the renderer)", () => {
  it("makes 2-4 word lines and breaks after sentences", () => {
    const ws = words("one two three four five. six seven");
    expect(captionLines(ws).map((l) => l.indices)).toEqual([[0, 1, 2, 3], [4], [5, 6]]);
  });

  it("skips hidden words but keeps original indices", () => {
    const ws = words("um this is it");
    ws[0].word = "";
    expect(captionLines(ws)[0].indices).toEqual([1, 2, 3]);
  });
});

describe("parseTime / formatTimePrecise", () => {
  it.each([
    ["83.4", 83.4],
    ["1:23.4", 83.4],
    ["1:02:03", 3723],
    ["0:05", 5],
  ])("%s -> %s", (s, n) => expect(parseTime(s)).toBeCloseTo(n));

  it.each(["", "abc", "1::2", "1:2:3:4"])("rejects %s", (s) => expect(parseTime(s)).toBeNull());

  it("formats", () => {
    expect(formatTimePrecise(83.44)).toBe("1:23.4");
    expect(formatTimePrecise(5)).toBe("0:05.0");
  });
});
