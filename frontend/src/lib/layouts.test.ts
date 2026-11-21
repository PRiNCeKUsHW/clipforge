import { describe, expect, it } from "vitest";

import { captionsOn, LAYOUTS, layoutLabel } from "./layouts";

describe("layouts", () => {
  it("matches the backend's layout ids", () => {
    // backend/app/services/editing.py LAYOUTS
    expect(LAYOUTS.map((l) => l.id)).toEqual(["auto", "podcast_split", "single", "centered_title", "blur_fit"]);
    expect(LAYOUTS.every((l) => l.label && l.hint && l.bestFor)).toBe(true);
  });

  it("labels and caption toggle", () => {
    expect(layoutLabel("podcast_split")).toBe("Podcast split");
    expect(layoutLabel("unknown")).toBe("Smart");
    expect(captionsOn("none")).toBe(false);
    expect(captionsOn("karaoke")).toBe(true);
  });
});
