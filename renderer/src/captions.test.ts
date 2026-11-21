import { describe, expect, it } from "vitest";

import { activeWordIndex, emojiForPage, groupWords, pageAt } from "./captions";
import type { CaptionWord } from "./types";

const words = (text: string, start = 0, step = 0.4): CaptionWord[] =>
  text.split(" ").map((t, i) => ({ text: t, start: start + i * step, end: start + i * step + 0.3 }));

describe("groupWords", () => {
  it("makes lines of at most 4 words", () => {
    const pages = groupWords(words("one two three four five six seven"));
    expect(pages.map((p) => p.words.length)).toEqual([4, 3]);
  });

  it("breaks after sentence ends", () => {
    const pages = groupWords(words("Hello there. How are you"));
    expect(pages.map((p) => p.words.map((w) => w.text).join(" "))).toEqual(["Hello there.", "How are you"]);
  });

  it("breaks on long pauses", () => {
    const pages = groupWords([...words("first bit", 0), ...words("after pause", 3)]);
    expect(pages).toHaveLength(2);
  });

  it("respects the character budget", () => {
    const pages = groupWords(words("extraordinarily complicated words"), { maxChars: 18 });
    expect(pages.every((p) => p.words.map((w) => w.text).join(" ").length <= 18 || p.words.length === 1)).toBe(true);
  });

  it("hides words edited to empty text without shifting timings", () => {
    const ws = words("um this is great");
    ws[0].text = "";
    const [page] = groupWords(ws);
    expect(page.words.map((w) => w.text)).toEqual(["this", "is", "great"]);
    expect(page.start).toBe(ws[1].start);
  });

  it("keeps a line visible until the next one when the gap is short", () => {
    const pages = groupWords(words("a b c d e f"));
    expect(pages[0].end).toBe(pages[1].start);
    expect(pages[1].end).toBeCloseTo(words("a b c d e f")[5].end + 0.3);
  });
});

describe("pageAt / activeWordIndex", () => {
  const pages = groupWords(words("one two three four five"));
  it("finds the page and active word", () => {
    const p = pageAt(pages, 0.85)!;
    expect(p.words[0].text).toBe("one");
    expect(activeWordIndex(p, 0.85)).toBe(2);
    expect(activeWordIndex(p, -1)).toBe(-1);
    expect(pageAt(pages, 100)).toBeNull();
  });
});

describe("emojiForPage", () => {
  it("matches keywords, including plurals and punctuation", () => {
    expect(emojiForPage(groupWords(words("Making MONEY!"))[0])).toBe("💰");
    expect(emojiForPage(groupWords(words("big dollars"))[0])).toBe("💵");
    expect(emojiForPage(groupWords(words("nothing here"))[0])).toBeNull();
  });
});
