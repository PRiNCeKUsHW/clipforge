"use client";

import { Loader2, Save } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { captionLines, formatTimePrecise } from "@/lib/captions";
import type { TranscriptWord } from "@/lib/types";

/**
 * Edit caption text word by word. Timings never change: fix transcription mistakes in place,
 * or clear a word to hide it (e.g. "um").
 */
export function WordEditor({
  words,
  clipStart,
  saving,
  onSave,
}: {
  words: TranscriptWord[];
  clipStart: number;
  saving: boolean;
  onSave: (texts: string[]) => void;
}) {
  const [texts, setTexts] = useState(() => words.map((w) => w.word));
  const dirty = texts.some((t, i) => t !== words[i]?.word);
  // Lines are computed from the original words so hidden words keep a visible (empty) slot.
  const lines = useMemo(() => captionLines(words.map((w) => ({ ...w, word: w.word || "·" }))), [words]);

  if (words.length === 0) return <p className="text-sm text-muted-foreground">No speech in this clip.</p>;

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-muted-foreground">
        Fix any word the local transcription got wrong. Clear a word to hide it. Timing stays the same.
      </p>
      <div className="flex max-h-[420px] flex-col gap-2 overflow-y-auto pr-1">
        {lines.map((line) => (
          <div key={line.indices[0]} className="flex flex-wrap items-center gap-1.5">
            <span className="w-12 shrink-0 text-[11px] tabular-nums text-muted-foreground">
              {formatTimePrecise(Math.max(0, line.start - clipStart))}
            </span>
            {line.indices.map((i) => (
              <input
                key={i}
                value={texts[i]}
                onChange={(e) => setTexts((prev) => prev.map((t, j) => (j === i ? e.target.value : t)))}
                aria-label={`Word ${i + 1}`}
                size={Math.max(2, texts[i].length || 2)}
                className={`rounded border bg-background px-1.5 py-0.5 text-sm outline-none focus:border-primary ${
                  texts[i] !== words[i].word ? "border-primary/70 bg-primary/10" : "border-border"
                } ${texts[i] === "" ? "line-through opacity-50" : ""}`}
              />
            ))}
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <Button onClick={() => onSave(texts)} disabled={!dirty || saving}>
          {saving ? <Loader2 className="animate-spin" /> : <Save />} Save captions
        </Button>
        {dirty && (
          <Button variant="ghost" onClick={() => setTexts(words.map((w) => w.word))}>
            Discard
          </Button>
        )}
      </div>
    </div>
  );
}
