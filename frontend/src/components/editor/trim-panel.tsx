"use client";

import { Loader2, Pause, Play, Save } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatTimePrecise, parseTime } from "@/lib/captions";

const NUDGES = [-1, -0.1, 0.1, 1];

function TimeField({
  label,
  text,
  setText,
  value,
  onCommit,
  onUseCurrent,
}: {
  label: string;
  text: string;
  setText: (t: string) => void;
  value: number;
  onCommit: (v: number) => void;
  onUseCurrent: () => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <Label>{label}</Label>
      <div className="flex gap-1.5">
        <Input
          value={text}
          onChange={(ev) => setText(ev.target.value)}
          onBlur={() => {
            const parsed = parseTime(text);
            if (parsed === null) setText(formatTimePrecise(value));
            else onCommit(parsed);
          }}
          className="font-mono"
          aria-label={`${label} time`}
        />
        <Button variant="outline" size="sm" className="h-8 shrink-0" onClick={onUseCurrent} title="Use the player's current time">
          Set
        </Button>
      </div>
      <div className="flex gap-1">
        {NUDGES.map((n) => (
          <Button key={n} variant="ghost" size="xs" onClick={() => onCommit(value + n)}>
            {n > 0 ? `+${n}` : n}s
          </Button>
        ))}
      </div>
    </div>
  );
}

/** Adjust the clip's start/end against the full source video. */
export function TrimPanel({
  sourceUrl,
  start,
  end,
  maxDuration,
  saving,
  onSave,
}: {
  sourceUrl: string | null;
  start: number;
  end: number;
  maxDuration: number | null;
  saving: boolean;
  onSave: (start: number, end: number) => void;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const [s, setS] = useState(start);
  const [e, setE] = useState(end);
  const [sText, setSText] = useState(formatTimePrecise(start));
  const [eText, setEText] = useState(formatTimePrecise(end));
  const [playing, setPlaying] = useState(false);
  const limit = maxDuration ?? Number.POSITIVE_INFINITY;
  const length = e - s;
  const valid = length >= 3 && length <= 180 && s >= 0 && e <= limit + 0.5;
  const dirty = Math.abs(s - start) > 0.01 || Math.abs(e - end) > 0.01;

  const setStart = (v: number) => {
    const val = Math.max(0, Math.round(v * 10) / 10);
    setS(val);
    setSText(formatTimePrecise(val));
    if (video.current) video.current.currentTime = val;
  };
  const setEnd = (v: number) => {
    const val = Math.min(limit, Math.round(v * 10) / 10);
    setE(val);
    setEText(formatTimePrecise(val));
    if (video.current) video.current.currentTime = Math.max(0, val - 2);
  };

  // Stop preview playback at the end point.
  useEffect(() => {
    const v = video.current;
    if (!v) return;
    const onTime = () => {
      if (v.currentTime >= e) {
        v.pause();
        setPlaying(false);
      }
    };
    v.addEventListener("timeupdate", onTime);
    return () => v.removeEventListener("timeupdate", onTime);
  }, [e]);

  const preview = () => {
    const v = video.current;
    if (!v) return;
    if (playing) {
      v.pause();
      setPlaying(false);
      return;
    }
    v.currentTime = s;
    void v.play();
    setPlaying(true);
  };

  return (
    <div className="flex flex-col gap-4">
      {sourceUrl ? (
        <video
          ref={video}
          src={`${sourceUrl}#t=${start}`}
          controls
          preload="metadata"
          className="aspect-video w-full rounded-lg bg-black"
          onPause={() => setPlaying(false)}
        />
      ) : (
        <p className="text-sm text-muted-foreground">Source video unavailable.</p>
      )}

      <div className="grid grid-cols-2 gap-4">
        <TimeField
          label="Start"
          text={sText}
          setText={setSText}
          value={s}
          onCommit={setStart}
          onUseCurrent={() => video.current && setStart(video.current.currentTime)}
        />
        <TimeField
          label="End"
          text={eText}
          setText={setEText}
          value={e}
          onCommit={setEnd}
          onUseCurrent={() => video.current && setEnd(video.current.currentTime)}
        />
      </div>

      <p className={`text-sm ${valid ? "text-muted-foreground" : "text-destructive"}`}>
        Length {length.toFixed(1)}s {valid ? "" : " (must be 3-180s and inside the video)"}
      </p>

      <div className="flex gap-2">
        <Button variant="outline" onClick={preview} disabled={!sourceUrl}>
          {playing ? <Pause /> : <Play />} Preview selection
        </Button>
        <Button onClick={() => onSave(s, e)} disabled={!dirty || !valid || saving}>
          {saving ? <Loader2 className="animate-spin" /> : <Save />} Save trim
        </Button>
      </div>
    </div>
  );
}
