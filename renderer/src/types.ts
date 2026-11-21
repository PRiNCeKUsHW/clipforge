export type Keyframe = { t: number; x: number };

export type CropPath = {
  layout: "single" | "split" | "fit";
  source: { w: number; h: number };
  /** crop width as a fraction of the source width */
  crop_w?: number;
  keyframes?: Keyframe[];
  /** split layout: [top panel keyframes, bottom panel keyframes] */
  panels?: Keyframe[][];
};

/** A caption word, times in seconds from the start of the clip. */
export type CaptionWord = { text: string; start: number; end: number };

export type CaptionStyleId = "bold" | "karaoke" | "minimal" | "beast";

export type ClipProps = {
  /** URL of the pre-cut clip segment (the renderer serves it from the shared work volume) */
  videoSrc: string;
  durationInSeconds: number;
  fps: number;
  crop: CropPath;
  words: CaptionWord[];
  /** "none" renders the clip without captions */
  style: CaptionStyleId | "none";
  /** Chosen layout; framing for auto/podcast_split/single comes from `crop` (the reframe stage). */
  layout?: ClipLayout;
  /** Shown above the video in the centered_title layout */
  title?: string;
};

export type ClipLayout = "auto" | "podcast_split" | "single" | "centered_title" | "blur_fit";
