export type ProjectStatus =
  | "queued"
  | "downloading"
  | "transcribing"
  | "finding_highlights"
  | "reframing"
  | "rendering"
  | "ready"
  | "failed";

export type SourceType = "youtube" | "upload";

export interface User {
  id: string;
  email: string;
  is_active: boolean;
  is_verified: boolean;
}

export interface Project {
  id: string;
  source_type: SourceType;
  source_url: string | null;
  title: string | null;
  duration: number | null;
  instruction: string | null;
  layout: string;
  caption_style: string;
  status: ProjectStatus;
  progress: number;
  status_message: string | null;
  error: string | null;
  language: string | null;
  created_at: string;
  updated_at: string;
  clip_count: number;
  /** unfinished but no progress for 20+ minutes (worker probably died); can be retried */
  stalled: boolean;
}

export interface ProgressEvent {
  id: string;
  status: ProjectStatus;
  progress: number;
  status_message: string | null;
  error: string | null;
}

export interface ScoreBreakdown {
  hook: number;
  payoff: number;
  emotion: number;
  standalone: number;
}

export type CaptionStyleId = "bold" | "karaoke" | "minimal" | "beast";

export interface Clip {
  id: string;
  project_id: string;
  start: number;
  end: number;
  duration: number;
  hook_title: string;
  virality_score: number;
  score_breakdown: Partial<ScoreBreakdown>;
  reason: string;
  description: string | null;
  hashtags: string[];
  caption_style: CaptionStyleId | string;
  /** chosen layout (see lib/layouts.ts) */
  layout: string;
  /** framing the reframe stage produced: single | split | fit (null until reframed) */
  framing: "single" | "split" | "fit" | null;
  status: "pending" | "rendering" | "ready" | "failed";
  progress: number;
  error: string | null;
  transcript_text: string;
  video_url: string | null;
  thumbnail_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface TranscriptWord {
  word: string;
  start: number;
  end: number;
  speaker?: string;
}

export interface ClipDetail extends Clip {
  transcript_words: TranscriptWord[];
  project_title: string | null;
  project_duration: number | null;
  source_url: string | null;
}

export interface ClipUpdate {
  start?: number;
  end?: number;
  hook_title?: string;
  caption_style?: string;
  layout?: string;
  word_texts?: string[];
  description?: string;
  hashtags?: string[];
}

export type PlatformId = "youtube" | "instagram";

export interface SocialAccount {
  id: string;
  platform: PlatformId;
  external_account_id: string;
  display_name: string | null;
  expires_at: string | null;
  created_at: string;
}

export interface PublishJob {
  id: string;
  clip_id: string;
  social_account_id: string | null;
  platform: PlatformId;
  status: "queued" | "uploading" | "published" | "failed";
  title: string | null;
  privacy_status: string | null;
  external_id: string | null;
  external_url: string | null;
  error: string | null;
  published_at: string | null;
  created_at: string;
}

export interface PresignResponse {
  storage_key: string;
  upload_url: string;
  content_type: string;
  expires_in: number;
}

export const TERMINAL_STATUSES: ReadonlySet<ProjectStatus> = new Set(["ready", "failed"]);
