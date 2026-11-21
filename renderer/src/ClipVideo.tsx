import React, { useMemo } from "react";
import { AbsoluteFill, OffthreadVideo, spring, useCurrentFrame, useVideoConfig } from "remotion";

import { activeWordIndex, emojiForPage, groupWords, pageAt, type CaptionPage } from "./captions";
import { coverPlacement, xAt } from "./crop";
import { getStyle, type CaptionStyle } from "./styles";
import { captionPosition, fitGeometry, isFramedLayout } from "./layout";
import type { ClipLayout, ClipProps, CropPath, Keyframe } from "./types";

const VideoPanel: React.FC<{
  src: string;
  crop: CropPath;
  keyframes?: Keyframe[];
  top: number;
  height: number;
  muted?: boolean;
}> = ({ src, crop, keyframes, top, height, muted }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const cx = crop.layout === "fit" ? 0.5 : xAt(keyframes, frame / fps);
  const p = coverPlacement(crop.source.w, crop.source.h, width, height, cx);
  return (
    <div style={{ position: "absolute", left: 0, top, width, height, overflow: "hidden" }}>
      <OffthreadVideo
        src={src}
        muted={muted}
        style={{ position: "absolute", width: p.width, height: p.height, left: p.left, top: p.top, maxWidth: "none" }}
      />
    </div>
  );
};

const Word: React.FC<{ text: string; style: CaptionStyle; state: "spoken" | "active" | "upcoming"; startFrame: number }> = ({
  text,
  style,
  state,
  startFrame,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = state === "active" ? spring({ frame: frame - startFrame, fps, config: { damping: 12, stiffness: 220 }, durationInFrames: 8 }) : 0;
  const scale = state === "active" ? 1 + (style.activeScale - 1) * pop : 1;
  const color =
    state === "active" ? style.activeColor : state === "upcoming" ? (style.upcomingColor ?? style.color) : style.color;
  const pill = state === "active" && style.activeBackground;
  return (
    <span
      style={{
        display: "inline-block",
        transformOrigin: "center 60%",
        padding: pill ? "0.02em 0.22em" : 0,
        borderRadius: pill ? "0.18em" : 0,
        backgroundColor: pill ? style.activeBackground! : "transparent",
        color,
        transform: `scale(${scale})`,
        WebkitTextStroke: style.strokeColor ? `${style.strokeWidth}px ${style.strokeColor}` : undefined,
        paintOrder: "stroke fill",
        textShadow: style.strokeColor ? "0 6px 18px rgba(0,0,0,0.45)" : undefined,
      }}
    >
      {style.uppercase ? text.toUpperCase() : text}
    </span>
  );
};

const Captions: React.FC<{ pages: CaptionPage[]; style: CaptionStyle; positionY: number }> = ({ pages, style, positionY }) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const t = frame / fps;
  const page = pageAt(pages, t);
  if (!page) return null;

  const active = activeWordIndex(page, t);
  const enter = spring({ frame: frame - Math.round(page.start * fps), fps, config: { damping: 14, stiffness: 180 }, durationInFrames: 10 });
  const emoji = style.emoji ? emojiForPage(page) : null;

  return (
    <AbsoluteFill style={{ alignItems: "center", pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          top: height * positionY,
          transform: `translateY(-50%) scale(${0.85 + 0.15 * enter}) rotate(${style.tilt}deg)`,
          width: 940,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 12,
        }}
      >
        {emoji && <div style={{ fontSize: 120, lineHeight: 1, transform: `scale(${enter})` }}>{emoji}</div>}
        <div
          style={{
            fontFamily: style.fontFamily,
            fontWeight: style.fontWeight,
            fontSize: style.fontSize,
            lineHeight: 1.15,
            textAlign: "center",
            // flex gap (not spaces) so the scaled-up active word never collides with its neighbours
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            columnGap: `${0.22 + (style.activeScale - 1) * 1.6}em`,
            rowGap: "0.08em",
            letterSpacing: style.uppercase ? "0.01em" : 0,
            backgroundColor: style.lineBackground ?? "transparent",
            padding: style.lineBackground ? "0.25em 0.5em" : 0,
            borderRadius: style.lineBackground ? "0.35em" : 0,
          }}
        >
          {page.words.map((w, i) => (
            <Word
              key={`${w.start}-${i}`}
              text={w.text.trim()}
              style={style}
              state={i < active ? "spoken" : i === active ? "active" : "upcoming"}
              startFrame={Math.round(w.start * fps)}
            />
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** Whole frame in a band across the middle, a blurred zoomed copy behind it, optional title above. */
const FramedLayout: React.FC<{ src: string; crop: CropPath; layout: ClipLayout; title?: string }> = ({ src, crop, layout, title }) => {
  const { width, height } = useVideoConfig();
  const g = fitGeometry(layout, crop, width, height, Boolean(title));
  const bg = coverPlacement(crop.source.w, crop.source.h, width, height, 0.5);
  return (
    <>
      <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
        <OffthreadVideo
          src={src}
          muted
          style={{
            position: "absolute", width: bg.width, height: bg.height, left: bg.left, top: bg.top, maxWidth: "none",
            filter: "blur(36px) brightness(0.45) saturate(1.2)", transform: "scale(1.12)",
          }}
        />
      </div>
      <OffthreadVideo src={src} style={{ position: "absolute", left: 0, top: g.videoTop, width, height: g.videoHeight }} />
      {title && g.titleBottom !== null && (
        <div
          style={{
            position: "absolute", left: 70, right: 70, bottom: height - g.titleBottom,
            display: "flex", justifyContent: "center", textAlign: "center",
            fontFamily: "Montserrat, 'Noto Sans Devanagari', 'Noto Color Emoji', sans-serif", fontWeight: 900,
            fontSize: 68, lineHeight: 1.18, color: "#fff", textShadow: "0 6px 24px rgba(0,0,0,0.6)",
          }}
        >
          {title}
        </div>
      )}
    </>
  );
};

export const ClipVideo: React.FC<ClipProps> = ({ videoSrc, crop, words, style, layout = "auto", title }) => {
  const { width, height } = useVideoConfig();
  const pages = useMemo(() => groupWords(words), [words]);
  const captionStyle = getStyle(style);
  const framed = isFramedLayout(layout);
  const split = !framed && crop.layout === "split" && crop.panels?.length === 2;
  const cleanTitle = title?.replace(/#\S+/g, "").trim();

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {framed ? (
        <FramedLayout src={videoSrc} crop={crop} layout={layout} title={layout === "centered_title" ? cleanTitle : undefined} />
      ) : split ? (
        <>
          <VideoPanel src={videoSrc} crop={crop} keyframes={crop.panels![0]} top={0} height={height / 2} />
          <VideoPanel src={videoSrc} crop={crop} keyframes={crop.panels![1]} top={height / 2} height={height / 2} muted />
          <div style={{ position: "absolute", top: height / 2 - 2, left: 0, width, height: 4, backgroundColor: "#000" }} />
        </>
      ) : (
        <VideoPanel src={videoSrc} crop={crop} keyframes={crop.keyframes} top={0} height={height} />
      )}
      {style !== "none" && (
        <Captions
          pages={pages}
          style={captionStyle}
          positionY={captionPosition(layout, crop, captionStyle.positionY, width, height, Boolean(cleanTitle))}
        />
      )}
    </AbsoluteFill>
  );
};
