import type { Keyframe } from "./types";

/** Crop centre at time t, linearly interpolated between keyframes (held before/after). */
export function xAt(keyframes: Keyframe[] | undefined, t: number): number {
  if (!keyframes || keyframes.length === 0) return 0.5;
  if (t <= keyframes[0].t) return keyframes[0].x;
  for (let i = 1; i < keyframes.length; i++) {
    const a = keyframes[i - 1];
    const b = keyframes[i];
    if (t <= b.t) {
      const span = b.t - a.t;
      return span <= 0 ? b.x : a.x + ((t - a.t) / span) * (b.x - a.x);
    }
  }
  return keyframes[keyframes.length - 1].x;
}

export type Placement = { width: number; height: number; left: number; top: number };

/**
 * Where to draw a srcW x srcH video so it covers a boxW x boxH area with the point at
 * horizontal fraction `cx` of the source as close to the box centre as the edges allow.
 */
export function coverPlacement(srcW: number, srcH: number, boxW: number, boxH: number, cx: number): Placement {
  const scale = Math.max(boxH / srcH, boxW / srcW);
  const width = srcW * scale;
  const height = srcH * scale;
  const left = Math.min(0, Math.max(boxW - width, boxW / 2 - cx * width));
  const top = (boxH - height) / 2;
  return { width, height, left, top };
}
