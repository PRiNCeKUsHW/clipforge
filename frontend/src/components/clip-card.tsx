"use client";

import { Download, Loader2, Pencil, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatDuration, scoreTone, type ScoreTone } from "@/lib/format";
import type { Clip, ScoreBreakdown } from "@/lib/types";
import { cn } from "@/lib/utils";

const TONE_CLASSES: Record<ScoreTone, string> = {
  great: "bg-rose text-white",
  good: "bg-marigold text-plum",
  ok: "bg-[color-mix(in_oklch,var(--marigold)_35%,transparent)] text-foreground",
  low: "bg-muted text-muted-foreground",
};

const BREAKDOWN: { key: keyof ScoreBreakdown; label: string }[] = [
  { key: "hook", label: "Hook" },
  { key: "payoff", label: "Payoff" },
  { key: "emotion", label: "Emotion" },
  { key: "standalone", label: "Standalone" },
];

export function ClipCard({ clip, rank }: { clip: Clip; rank: number }) {
  const [downloading, setDownloading] = useState(false);

  async function download() {
    setDownloading(true);
    try {
      const { url } = await api.downloadClip(clip.id);
      // The presigned URL sets Content-Disposition: attachment, so this downloads instead of navigating.
      window.location.assign(url);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Download failed");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <Card className="gap-0 overflow-hidden rounded-[1.6rem] border-border/60 py-0">
      <div className="relative m-2 mb-0 aspect-[9/16] overflow-hidden rounded-[1.2rem] bg-[#170b1a]">
        {clip.video_url && clip.status !== "rendering" ? (
          <video
            src={clip.video_url}
            poster={clip.thumbnail_url ?? undefined}
            controls
            preload="none"
            playsInline
            className="size-full object-contain"
          />
        ) : (
          <div className="grid size-full place-items-center text-sm text-muted-foreground">
            {clip.status === "failed" ? (
              <span className="flex items-center gap-2 px-4 text-center text-destructive">
                <TriangleAlert className="size-4 shrink-0" /> {clip.error || "Render failed"}
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <Loader2 className="size-4 animate-spin" /> Rendering{clip.progress ? ` ${clip.progress}%` : "…"}
              </span>
            )}
          </div>
        )}
        <span className="pointer-events-none absolute top-2.5 left-2.5 rounded-full bg-black/55 px-2 py-0.5 text-xs font-semibold text-white backdrop-blur">
          #{rank}
        </span>
        <span className="pointer-events-none absolute top-2.5 right-2.5 rounded-full bg-black/55 px-2 py-0.5 text-xs tabular-nums text-white backdrop-blur">
          {formatDuration(clip.duration)}
        </span>
      </div>

      <CardContent className="flex flex-1 flex-col gap-3 py-4">
        <div className="flex items-start gap-3">
          <div
            className={cn("grid size-12 shrink-0 place-items-center rounded-2xl font-heading text-xl font-extrabold tabular-nums", TONE_CLASSES[scoreTone(clip.virality_score)])}
            title="Virality score (0-100)"
          >
            {clip.virality_score}
          </div>
          <div className="min-w-0">
            <h3 className="text-[1.05rem] leading-snug font-semibold">{clip.hook_title}</h3>
            <p className="text-xs text-muted-foreground">
              {formatDuration(clip.start)} – {formatDuration(clip.end)} in source
            </p>
          </div>
        </div>

        <dl className="grid grid-cols-4 gap-2">
          {BREAKDOWN.map(({ key, label }) => {
            const value = clip.score_breakdown[key] ?? 0;
            return (
              <div key={key} className="flex flex-col gap-1">
                <dt className="text-[11px] text-muted-foreground">{label}</dt>
                <dd className="h-1.5 overflow-hidden rounded-full bg-muted" title={`${label}: ${value}`}>
                  <div className="h-full rounded-full bg-primary" style={{ width: `${value}%` }} />
                </dd>
              </div>
            );
          })}
        </dl>

        {clip.reason && <p className="text-sm text-muted-foreground">{clip.reason}</p>}
        {clip.transcript_text && (
          <p className="line-clamp-3 border-l-2 border-primary/60 pl-3 text-xs text-muted-foreground italic">
            “{clip.transcript_text}”
          </p>
        )}

        <div className="mt-auto flex gap-2 pt-1">
          <Link href={`/clips/${clip.id}`} className={cn(buttonVariants({ variant: "default" }), "flex-1 rounded-full font-semibold")}>
            <Pencil /> Edit
          </Link>
          <Button variant="outline" className="rounded-full" onClick={download} disabled={!clip.video_url || downloading} aria-label="Download MP4">
            {downloading ? <Loader2 className="animate-spin" /> : <Download />}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
