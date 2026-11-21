import type { ProgressEvent, ProjectStatus } from "./types";

/** 75.4 -> "1:15", 3725 -> "1:02:05" */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return "–";
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

export type ScoreTone = "great" | "good" | "ok" | "low";

export function scoreTone(score: number): ScoreTone {
  if (score >= 85) return "great";
  if (score >= 70) return "good";
  if (score >= 50) return "ok";
  return "low";
}

export const STATUS_LABELS: Record<ProjectStatus, string> = {
  queued: "Queued",
  downloading: "Downloading",
  transcribing: "Transcribing",
  finding_highlights: "Finding highlights",
  reframing: "Reframing",
  rendering: "Rendering clips",
  ready: "Ready",
  failed: "Failed",
};

/** The steps shown in the progress stepper, in order. */
export const PIPELINE_STEPS: ProjectStatus[] = ["downloading", "transcribing", "finding_highlights", "rendering", "ready"];

export type StepState = "done" | "active" | "pending" | "failed";

export function stepState(step: ProjectStatus, current: ProjectStatus, progress: number): StepState {
  if (current === "ready") return "done";
  const idx = PIPELINE_STEPS.indexOf(step);
  if (current === "failed") {
    // Which step failed is inferred from where the progress bar stopped.
    const failedIdx = progress < 15 ? 0 : progress < 70 ? 1 : progress < 80 ? 2 : 3;
    return idx < failedIdx ? "done" : idx === failedIdx ? "failed" : "pending";
  }
  if (current === "queued") return "pending";
  const curIdx = PIPELINE_STEPS.indexOf(current === "reframing" ? "rendering" : current);
  return idx < curIdx ? "done" : idx === curIdx ? "active" : "pending";
}

/** Parse an SSE `data:` payload; returns null for anything malformed. */
export function parseProgressEvent(data: string): ProgressEvent | null {
  try {
    const parsed = JSON.parse(data) as Partial<ProgressEvent>;
    if (typeof parsed.id !== "string" || typeof parsed.status !== "string" || typeof parsed.progress !== "number") {
      return null;
    }
    if (!(parsed.status in STATUS_LABELS)) return null;
    return {
      id: parsed.id,
      status: parsed.status as ProjectStatus,
      progress: Math.max(0, Math.min(100, parsed.progress)),
      status_message: parsed.status_message ?? null,
      error: parsed.error ?? null,
    };
  } catch {
    return null;
  }
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let v = bytes / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(v >= 10 ? 0 : 1)} ${units[i]}`;
}
