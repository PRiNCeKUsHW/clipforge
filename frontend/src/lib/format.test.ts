import { describe, expect, it } from "vitest";

import { formatBytes, formatDuration, parseProgressEvent, scoreTone, stepState } from "./format";

describe("formatDuration", () => {
  it.each([
    [0, "0:00"],
    [5.4, "0:05"],
    [75.4, "1:15"],
    [599.6, "10:00"],
    [3725, "1:02:05"],
  ])("%s -> %s", (input, expected) => expect(formatDuration(input)).toBe(expected));

  it("handles missing values", () => {
    expect(formatDuration(null)).toBe("–");
    expect(formatDuration(NaN)).toBe("–");
    expect(formatDuration(-1)).toBe("–");
  });
});

describe("scoreTone", () => {
  it("buckets scores", () => {
    expect([95, 85, 84, 70, 69, 50, 49, 0].map(scoreTone)).toEqual(["great", "great", "good", "good", "ok", "ok", "low", "low"]);
  });
});

describe("stepState", () => {
  it("marks earlier steps done and the current one active", () => {
    expect(stepState("downloading", "transcribing", 40)).toBe("done");
    expect(stepState("transcribing", "transcribing", 40)).toBe("active");
    expect(stepState("rendering", "transcribing", 40)).toBe("pending");
  });

  it("treats everything as done when ready and pending when queued", () => {
    expect(stepState("rendering", "ready", 100)).toBe("done");
    expect(stepState("downloading", "queued", 0)).toBe("pending");
  });

  it("infers the failed step from progress", () => {
    expect(stepState("downloading", "failed", 5)).toBe("failed");
    expect(stepState("downloading", "failed", 50)).toBe("done");
    expect(stepState("transcribing", "failed", 50)).toBe("failed");
    expect(stepState("finding_highlights", "failed", 75)).toBe("failed");
    expect(stepState("rendering", "failed", 75)).toBe("pending");
  });
});

describe("parseProgressEvent", () => {
  it("parses a valid payload and clamps progress", () => {
    expect(parseProgressEvent('{"id":"p1","status":"transcribing","progress":140,"status_message":"x"}')).toEqual({
      id: "p1",
      status: "transcribing",
      progress: 100,
      status_message: "x",
      error: null,
    });
  });

  it.each(["", "not json", '{"id":"p1"}', '{"id":"p1","status":"exploded","progress":1}', '{"id":1,"status":"ready","progress":1}'])(
    "rejects %s",
    (raw) => expect(parseProgressEvent(raw)).toBeNull(),
  );
});

describe("formatBytes", () => {
  it.each([
    [500, "500 B"],
    [2048, "2.0 KB"],
    [15 * 1024 * 1024, "15 MB"],
    [3.5 * 1024 ** 3, "3.5 GB"],
  ])("%s -> %s", (n, s) => expect(formatBytes(n)).toBe(s));
});
