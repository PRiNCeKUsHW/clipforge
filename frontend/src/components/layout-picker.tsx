"use client";

import { Sparkles } from "lucide-react";

import { LAYOUTS, type LayoutId } from "@/lib/layouts";
import { cn } from "@/lib/utils";

// Small 9:16 preview drawings of each layout (viewBox 90 x 160).
const Face = ({ cx, cy, r = 11, tone = "#f4b98a" }: { cx: number; cy: number; r?: number; tone?: string }) => (
  <g>
    <circle cx={cx} cy={cy} r={r} fill={tone} />
    <path d={`M${cx - r * 1.6} ${cy + r * 3.2} Q${cx} ${cy + r * 0.9} ${cx + r * 1.6} ${cy + r * 3.2} Z`} fill="#b4567a" />
  </g>
);
const Caption = ({ y, w = 54 }: { y: number; w?: number }) => (
  <g>
    <rect x={45 - w / 2} y={y - 5} width={w} height={10} rx={2} fill="#000" opacity={0.35} />
    <rect x={45 - w / 2 + 4} y={y - 2.5} width={w * 0.38} height={5} rx={1.5} fill="#fff" />
    <rect x={45 - w / 2 + 6 + w * 0.38} y={y - 2.5} width={w * 0.42} height={5} rx={1.5} fill="#FFE600" />
  </g>
);
const Band = ({ y, h = 50 }: { y: number; h?: number }) => (
  <g>
    <rect x={0} y={y} width={90} height={h} fill="#4a2b4f" />
    <rect x={0} y={y + h * 0.62} width={90} height={h * 0.38} fill="#5e3a5f" />
    <Face cx={34} cy={y + h * 0.42} r={7} />
    <Face cx={58} cy={y + h * 0.45} r={6} tone="#d99a6c" />
  </g>
);

function Preview({ id }: { id: LayoutId }) {
  return (
    <svg viewBox="0 0 90 160" className="h-full w-full" aria-hidden>
      <defs>
        <linearGradient id={`bg-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#6a3358" />
          <stop offset="1" stopColor="#2a1530" />
        </linearGradient>
      </defs>
      {id === "auto" && (
        <>
          <rect width={90} height={160} fill="#3d2442" />
          <Face cx={45} cy={62} r={16} />
          <Caption y={118} />
        </>
      )}
      {id === "single" && (
        <>
          <rect width={90} height={160} fill="#3d2442" />
          <Face cx={45} cy={58} r={18} />
          <Caption y={118} />
        </>
      )}
      {id === "podcast_split" && (
        <>
          <rect width={90} height={80} fill="#3d2442" />
          <rect y={80} width={90} height={80} fill="#4d2e50" />
          <Face cx={45} cy={30} r={12} />
          <Face cx={45} cy={110} r={12} tone="#d99a6c" />
          <rect y={79} width={90} height={2} fill="#000" />
          <Caption y={80} />
        </>
      )}
      {id === "centered_title" && (
        <>
          <rect width={90} height={160} fill={`url(#bg-${id})`} />
          <rect x={14} y={28} width={62} height={6} rx={2} fill="#fff" />
          <rect x={22} y={38} width={46} height={6} rx={2} fill="#fff" />
          <Band y={56} />
          <Caption y={124} />
        </>
      )}
      {id === "blur_fit" && (
        <>
          <rect width={90} height={160} fill={`url(#bg-${id})`} />
          <Band y={55} />
          <Caption y={122} />
        </>
      )}
    </svg>
  );
}

export function LayoutPicker({ value, onChange, compact = false }: { value: string; onChange: (id: LayoutId) => void; compact?: boolean }) {
  return (
    <div className={cn("grid gap-3", compact ? "grid-cols-3 sm:grid-cols-5" : "grid-cols-2 sm:grid-cols-3")}>
      {LAYOUTS.map((l) => (
        <button
          key={l.id}
          type="button"
          onClick={() => onChange(l.id)}
          aria-pressed={value === l.id}
          title={l.hint}
          className={cn(
            "flex flex-col gap-2 rounded-2xl border-2 p-2 text-left transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
            value === l.id ? "border-primary bg-primary/10" : "border-transparent bg-card/60 hover:border-primary/40",
          )}
        >
          <div className="relative mx-auto aspect-[9/16] w-full max-w-[96px] overflow-hidden rounded-xl ring-1 ring-white/10">
            <Preview id={l.id} />
            {l.id === "auto" && (
              <span className="absolute top-1 right-1 rounded-full bg-primary px-1.5 text-[9px] font-semibold text-primary-foreground">
                <Sparkles className="inline size-2.5" /> AI
              </span>
            )}
          </div>
          <div className="px-0.5">
            <p className="text-sm leading-tight font-medium">{l.label}</p>
            {!compact && <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground">{l.hint}</p>}
            {compact && <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground">{l.bestFor}</p>}
          </div>
        </button>
      ))}
    </div>
  );
}

export function CaptionsToggle({ on, onChange }: { on: boolean; onChange: (on: boolean) => void }) {
  return (
    <div className="inline-flex rounded-full bg-card/70 p-1" role="radiogroup" aria-label="Captions">
      {[
        { v: true, label: "Captions on" },
        { v: false, label: "No captions" },
      ].map((o) => (
        <button
          key={o.label}
          type="button"
          role="radio"
          aria-checked={on === o.v}
          onClick={() => onChange(o.v)}
          className={cn(
            "rounded-full px-3.5 py-1 text-sm transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
            on === o.v ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
