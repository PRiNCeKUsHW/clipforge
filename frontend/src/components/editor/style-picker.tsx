"use client";

import type { CSSProperties } from "react";

import { cn } from "@/lib/utils";

// Visual approximations of renderer/src/styles.ts presets.
export const CAPTION_STYLES: { id: string; label: string; hint: string; base: CSSProperties; active: CSSProperties; box?: CSSProperties; upper: boolean }[] = [
  {
    id: "bold",
    label: "Bold pop",
    hint: "Yellow active word, thick outline, emoji",
    upper: true,
    base: { fontFamily: "var(--font-montserrat)", fontWeight: 900, color: "#fff", WebkitTextStroke: "1.5px #000", paintOrder: "stroke fill" },
    active: { color: "#FFE600", transform: "scale(1.12)" },
  },
  {
    id: "karaoke",
    label: "Karaoke",
    hint: "Green highlight pill behind the spoken word",
    upper: true,
    base: { fontFamily: "var(--font-montserrat)", fontWeight: 800, color: "#fff", WebkitTextStroke: "1px #000", paintOrder: "stroke fill" },
    active: { backgroundColor: "#16A34A", borderRadius: 4, padding: "0 4px" },
  },
  {
    id: "minimal",
    label: "Clean",
    hint: "Sentence case in a dark box",
    upper: false,
    base: { fontFamily: "var(--font-inter)", fontWeight: 700, color: "rgba(255,255,255,0.5)" },
    active: { color: "#fff" },
    box: { backgroundColor: "rgba(0,0,0,0.6)", borderRadius: 8, padding: "2px 8px" },
  },
  {
    id: "beast",
    label: "Hype",
    hint: "Big comic font, red pop, emoji",
    upper: true,
    base: { fontFamily: "var(--font-bangers)", fontWeight: 400, color: "#fff", WebkitTextStroke: "1.5px #000", paintOrder: "stroke fill", fontSize: "1.25em" },
    active: { color: "#FF3B30", transform: "scale(1.18) rotate(-3deg)" },
  },
  {
    id: "none",
    label: "No captions",
    hint: "Clean video, no text on screen",
    upper: false,
    base: { color: "transparent" },
    active: {},
  },
];

export function StylePicker({
  value,
  onChange,
  hideNone = false,
}: {
  value: string;
  onChange: (id: string) => void;
  /** hide the "No captions" card when a separate captions on/off toggle is shown */
  hideNone?: boolean;
}) {
  return (
    <div className="grid grid-cols-2 gap-3">
      {CAPTION_STYLES.filter((s) => !(hideNone && s.id === "none")).map((s) => {
        const words = ["This", "is", "huge"];
        return (
          <button
            key={s.id}
            type="button"
            onClick={() => onChange(s.id)}
            aria-pressed={value === s.id}
            className={cn(
              "flex flex-col gap-2 rounded-lg border p-3 text-left transition-colors",
              value === s.id ? "border-primary bg-primary/10" : "border-border hover:border-primary/50",
            )}
          >
            <div className="grid h-16 place-items-center rounded-md bg-gradient-to-br from-zinc-700 to-zinc-900 text-lg">
              <span style={s.box} className="flex gap-1.5">
                {s.id === "none" && <span className="text-xs text-muted-foreground">no text</span>}
                {s.id !== "none" && words.map((w, i) => (
                  <span key={w} style={{ ...s.base, ...(i === 1 ? s.active : {}), display: "inline-block" }}>
                    {s.upper ? w.toUpperCase() : w}
                  </span>
                ))}
              </span>
            </div>
            <div>
              <p className="text-sm font-medium">{s.label}</p>
              <p className="text-xs text-muted-foreground">{s.hint}</p>
            </div>
          </button>
        );
      })}
    </div>
  );
}
