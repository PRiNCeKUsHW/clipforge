// Mirrors renderer/src/captions.ts so the editor groups words into the same caption lines
// the renderer will draw.
import type { TranscriptWord } from "./types";

export type CaptionLine = { start: number; indices: number[] };

const SENTENCE_END = /[.!?…।]["'”’)\]]*$/;

/** Group word indices into 2-4 word lines (hidden/empty words are skipped but keep their slot). */
export function captionLines(words: TranscriptWord[], maxWords = 4, maxChars = 18, maxGap = 0.7): CaptionLine[] {
  const lines: CaptionLine[] = [];
  let current: number[] = [];
  let chars = 0;
  let prev: TranscriptWord | null = null;
  const flush = () => {
    if (current.length) lines.push({ start: words[current[0]].start, indices: current });
    current = [];
    chars = 0;
  };
  words.forEach((w, i) => {
    const text = w.word.trim();
    if (!text) return;
    const overflow = current.length > 0 && chars + 1 + text.length > maxChars;
    const pause = prev !== null && w.start - prev.end > maxGap;
    const sentence = prev !== null && SENTENCE_END.test(prev.word.trim());
    if (current.length >= maxWords || overflow || pause || sentence) flush();
    current.push(i);
    chars += (current.length > 1 ? 1 : 0) + text.length;
    prev = w;
  });
  flush();
  return lines;
}

/** "1:23.4" | "83.4" | "1:02:03" -> seconds; null if unparseable. */
export function parseTime(input: string): number | null {
  const parts = input.trim().split(":");
  if (parts.length === 0 || parts.length > 3 || parts.some((p) => p.trim() === "" || isNaN(Number(p)))) return null;
  return parts.reduce((acc, p) => acc * 60 + Number(p), 0);
}

/** 83.44 -> "1:23.4" */
export function formatTimePrecise(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds - m * 60;
  return `${m}:${s.toFixed(1).padStart(4, "0")}`;
}
