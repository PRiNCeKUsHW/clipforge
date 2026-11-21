export type LayoutId = "auto" | "podcast_split" | "single" | "centered_title" | "blur_fit";

export type LayoutOption = { id: LayoutId; label: string; hint: string; bestFor: string };

// Keep in sync with backend/app/services/editing.py LAYOUTS and renderer/src/layout.ts
export const LAYOUTS: LayoutOption[] = [
  { id: "auto", label: "Smart", hint: "Follows the speaker; splits automatically when two people sit side by side", bestFor: "Anything" },
  { id: "podcast_split", label: "Podcast split", hint: "Two speakers stacked top and bottom, captions on the seam", bestFor: "Podcasts, interviews" },
  { id: "single", label: "Full face", hint: "One full-screen crop that follows whoever is talking", bestFor: "Solo talking head" },
  { id: "centered_title", label: "Title + video", hint: "Whole video in the middle, topic above, captions below", bestFor: "Tech, gameplay, tutorials" },
  { id: "blur_fit", label: "Blur fit", hint: "Whole video in the middle on a blurred background", bestFor: "Screen recordings, wide shots" },
];

export const layoutLabel = (id: string) => LAYOUTS.find((l) => l.id === id)?.label ?? "Smart";

/** "none" = captions off; any other caption style = captions on. */
export const captionsOn = (style: string) => style !== "none";
