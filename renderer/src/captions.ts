import type { CaptionWord } from "./types";

export type CaptionPage = { start: number; end: number; words: CaptionWord[] };

export type GroupOptions = {
  maxWords: number;
  maxChars: number;
  /** a pause longer than this starts a new line */
  maxGap: number;
};

const DEFAULTS: GroupOptions = { maxWords: 4, maxChars: 18, maxGap: 0.7 };
const SENTENCE_END = /[.!?…।]["'”’)\]]*$/;

/**
 * Split words into short caption "pages" of 2-4 words, breaking at sentence ends, long pauses
 * and a character budget so lines fit the vertical frame. Words edited to empty text are hidden.
 */
export function groupWords(words: CaptionWord[], options: Partial<GroupOptions> = {}): CaptionPage[] {
  const opts = { ...DEFAULTS, ...options };
  const visible = words.filter((w) => w.text.trim() !== "").sort((a, b) => a.start - b.start);
  const pages: CaptionPage[] = [];
  let current: CaptionWord[] = [];
  let chars = 0;

  const flush = () => {
    if (current.length) {
      pages.push({ start: current[0].start, end: current[current.length - 1].end, words: current });
    }
    current = [];
    chars = 0;
  };

  for (const word of visible) {
    const prev = current[current.length - 1];
    const len = word.text.trim().length;
    const wouldOverflow = current.length > 0 && chars + 1 + len > opts.maxChars;
    const longPause = prev !== undefined && word.start - prev.end > opts.maxGap;
    const afterSentence = prev !== undefined && SENTENCE_END.test(prev.text.trim());
    if (current.length >= opts.maxWords || wouldOverflow || longPause || afterSentence) flush();
    current.push(word);
    chars += (current.length > 1 ? 1 : 0) + len;
  }
  flush();

  // Keep a line on screen until the next one starts (if the gap is short), so captions don't flicker.
  for (let i = 0; i < pages.length; i++) {
    const next = pages[i + 1];
    if (next && next.start - pages[i].end < 0.5) pages[i].end = next.start;
    else pages[i].end += 0.3;
  }
  return pages;
}

export function pageAt(pages: CaptionPage[], t: number): CaptionPage | null {
  for (const page of pages) {
    if (t >= page.start && t < page.end) return page;
  }
  return null;
}

/** Index of the word being spoken (the last one that has started), or -1 before the first. */
export function activeWordIndex(page: CaptionPage, t: number): number {
  let idx = -1;
  page.words.forEach((w, i) => {
    if (t >= w.start) idx = i;
  });
  return idx;
}

const EMOJI: Record<string, string> = {
  money: "💰", cash: "💸", rich: "🤑", million: "💰", billion: "💰", dollars: "💵",
  fire: "🔥", hot: "🔥", insane: "🤯", crazy: "🤯", mind: "🤯", shocking: "😱", scary: "😱",
  love: "❤️", heart: "❤️", happy: "😄", laugh: "😂", funny: "😂", lol: "😂", joke: "😂",
  sad: "😢", cry: "😭", angry: "😡", mad: "😡", secret: "🤫", truth: "💯", facts: "💯",
  win: "🏆", winner: "🏆", best: "🏆", goal: "🎯", target: "🎯", idea: "💡", think: "🤔",
  why: "🤔", question: "❓", work: "💼", business: "💼", growth: "📈", success: "🚀", rocket: "🚀",
  fast: "⚡", speed: "⚡", power: "💪", strong: "💪", gym: "💪", food: "🍔", eat: "🍔",
  game: "🎮", gaming: "🎮", music: "🎵", phone: "📱", time: "⏰", danger: "⚠️", warning: "⚠️",
  wow: "😮", omg: "😱", kill: "💀", dead: "💀", world: "🌍", car: "🚗", python: "🐍", code: "💻",
};

const normalise = (w: string) => w.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");

/** An emoji for the first keyword on the line (plural "s" tolerated), or null. */
export function emojiForPage(page: CaptionPage): string | null {
  for (const w of page.words) {
    const n = normalise(w.text);
    const hit = EMOJI[n] ?? (n.endsWith("s") ? EMOJI[n.slice(0, -1)] : undefined);
    if (hit) return hit;
  }
  return null;
}
