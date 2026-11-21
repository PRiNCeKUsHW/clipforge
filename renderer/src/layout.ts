import type { ClipLayout, CropPath } from "./types";

export type FitGeometry = {
  /** top edge and height of the full-width 16:9 video band */
  videoTop: number;
  videoHeight: number;
  /** vertical centre of the captions, 0..1 of frame height */
  captionY: number;
  /** bottom edge (px) of the title area, or null when there's no title */
  titleBottom: number | null;
};

export const isFramedLayout = (layout: ClipLayout | undefined) => layout === "centered_title" || layout === "blur_fit";

/** Geometry for the "framed" layouts: the whole video in a band across the middle of a blurred background. */
export function fitGeometry(layout: ClipLayout, crop: CropPath, width: number, height: number, hasTitle: boolean): FitGeometry {
  const aspect = crop.source.h / crop.source.w;
  const videoHeight = Math.min(height, width * aspect);
  const withTitle = layout === "centered_title" && hasTitle;
  // nudge the band down a little when a title sits above it
  const centre = withTitle ? height * 0.53 : height * 0.5;
  const videoTop = Math.max(0, centre - videoHeight / 2);
  const below = videoTop + videoHeight;
  return {
    videoTop,
    videoHeight,
    captionY: Math.min(0.9, (below + height * 0.09) / height),
    titleBottom: withTitle ? videoTop - height * 0.03 : null,
  };
}

/** Where captions sit for each layout (0 = top, 1 = bottom). */
export function captionPosition(layout: ClipLayout, crop: CropPath, styleY: number, width: number, height: number, hasTitle: boolean): number {
  if (isFramedLayout(layout)) return fitGeometry(layout, crop, width, height, hasTitle).captionY;
  if (crop.layout === "split") return 0.5; // the seam between the two speakers covers no one
  return styleY;
}
