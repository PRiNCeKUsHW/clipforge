"use client";

import { Scissors } from "lucide-react";

import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

/** Matches CLIP_LENGTHS in backend/app/services/editing.py */
export const CLIP_LENGTHS = [
  { id: "auto", label: "Auto", hint: "AI picks" },
  { id: "1m", label: "0–1 min", hint: "15–60 s" },
  { id: "2m", label: "0–2 min", hint: "30–120 s" },
] as const;
export type ClipLengthId = (typeof CLIP_LENGTHS)[number]["id"];

const COUNTS = [null, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as const;

const pill = (active: boolean) =>
  cn(
    "rounded-xl border text-sm transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
    active
      ? "border-primary bg-primary text-primary-foreground"
      : "border-transparent bg-card/70 text-muted-foreground hover:text-foreground",
  );

export function ClipOptions({
  length,
  onLengthChange,
  count,
  onCountChange,
}: {
  length: ClipLengthId;
  onLengthChange: (v: ClipLengthId) => void;
  count: number | null;
  onCountChange: (v: number | null) => void;
}) {
  return (
    <div className="flex flex-col gap-4 rounded-2xl bg-secondary/60 p-4">
      <Label className="flex items-center gap-1.5">
        <Scissors className="size-3.5 text-primary" /> Clips
      </Label>

      <div className="flex flex-col gap-2">
        <span id="clip-length-label" className="text-xs text-muted-foreground">
          Length of each clip
        </span>
        <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-labelledby="clip-length-label">
          {CLIP_LENGTHS.map((o) => (
            <button
              key={o.id}
              type="button"
              role="radio"
              aria-checked={length === o.id}
              onClick={() => onLengthChange(o.id)}
              className={cn(pill(length === o.id), "flex flex-col items-center px-2 py-2")}
            >
              <span className="font-medium">{o.label}</span>
              <span className={cn("text-xs", length === o.id ? "text-primary-foreground/80" : "text-muted-foreground")}>
                {o.hint}
              </span>
            </button>
          ))}
        </div>
        {length === "2m" && (
          <p className="text-xs text-muted-foreground">
            YouTube blocks Shorts over 1 minute that get a copyright claim, so keep movie or TV clips under 1 min.
          </p>
        )}
      </div>

      <div className="flex flex-col gap-2">
        <span id="clip-count-label" className="text-xs text-muted-foreground">
          How many clips
        </span>
        <div className="grid grid-cols-6 gap-2 sm:grid-cols-11" role="radiogroup" aria-labelledby="clip-count-label">
          {COUNTS.map((n) => (
            <button
              key={n ?? "auto"}
              type="button"
              role="radio"
              aria-checked={count === n}
              aria-label={n === null ? "Auto, AI decides" : `${n} clip${n > 1 ? "s" : ""}`}
              onClick={() => onCountChange(n)}
              className={cn(pill(count === n), "h-10 tabular-nums", n === null && "col-span-2 sm:col-span-1")}
            >
              {n ?? "Auto"}
            </button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          {count === null
            ? "Auto: the AI finds 5–10 clips, fewer if the video is short."
            : `Up to ${count} clip${count > 1 ? "s" : ""}, the best ones first. A short video may give fewer.`}
        </p>
      </div>
    </div>
  );
}
