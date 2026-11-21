import React from "react";
import { Composition } from "remotion";

import { ClipVideo } from "./ClipVideo";
import "./fonts";
import type { ClipProps } from "./types";

// Used by `npm run studio` for previewing styles; real renders pass their own props.
const sampleProps: ClipProps = {
  videoSrc: "https://remotion.media/BigBuckBunny.mp4",
  durationInSeconds: 6,
  fps: 30,
  crop: { layout: "single", source: { w: 1920, h: 1080 }, crop_w: 0.316, keyframes: [{ t: 0, x: 0.3 }, { t: 6, x: 0.7 }] },
  words: "Here is the one trick nobody tells you about making money online".split(" ").map((text, i) => ({
    text,
    start: 0.3 + i * 0.42,
    end: 0.3 + i * 0.42 + 0.36,
  })),
  style: "bold",
};

export const RemotionRoot: React.FC = () => (
  <Composition
    id="Clip"
    component={ClipVideo}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={180}
    defaultProps={sampleProps}
    calculateMetadata={({ props }) => ({
      fps: props.fps,
      durationInFrames: Math.max(1, Math.ceil(props.durationInSeconds * props.fps)),
    })}
  />
);
