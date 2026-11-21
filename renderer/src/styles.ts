import type { CaptionStyleId } from "./types";

export type CaptionStyle = {
  id: CaptionStyleId;
  label: string;
  fontFamily: string;
  fontWeight: number;
  fontSize: number;
  uppercase: boolean;
  color: string;
  activeColor: string;
  /** colour of words not yet spoken (null = same as color) */
  upcomingColor: string | null;
  strokeColor: string | null;
  strokeWidth: number;
  /** pill drawn behind the active word */
  activeBackground: string | null;
  /** box drawn behind the whole line */
  lineBackground: string | null;
  activeScale: number;
  /** vertical centre of the caption block, 0 = top, 1 = bottom (kept clear of the Shorts/Reels UI) */
  positionY: number;
  emoji: boolean;
  tilt: number;
};

// Devanagari and emoji fall back to the Noto fonts installed in the renderer image.
const FALLBACK = "'Noto Sans Devanagari', 'Noto Sans', 'Noto Color Emoji', sans-serif";

export const CAPTION_STYLES: Record<CaptionStyleId, CaptionStyle> = {
  bold: {
    id: "bold",
    label: "Bold pop",
    fontFamily: `Montserrat, ${FALLBACK}`,
    fontWeight: 900,
    fontSize: 84,
    uppercase: true,
    color: "#FFFFFF",
    activeColor: "#FFE600",
    upcomingColor: null,
    strokeColor: "#000000",
    strokeWidth: 12,
    activeBackground: null,
    lineBackground: null,
    activeScale: 1.14,
    positionY: 0.7,
    emoji: true,
    tilt: 0,
  },
  karaoke: {
    id: "karaoke",
    label: "Karaoke",
    fontFamily: `Montserrat, ${FALLBACK}`,
    fontWeight: 800,
    fontSize: 76,
    uppercase: true,
    color: "#FFFFFF",
    activeColor: "#FFFFFF",
    upcomingColor: "rgba(255,255,255,0.85)",
    strokeColor: "#000000",
    strokeWidth: 8,
    activeBackground: "#16A34A",
    lineBackground: null,
    activeScale: 1.06,
    positionY: 0.7,
    emoji: false,
    tilt: 0,
  },
  minimal: {
    id: "minimal",
    label: "Clean",
    fontFamily: `Inter, ${FALLBACK}`,
    fontWeight: 700,
    fontSize: 62,
    uppercase: false,
    color: "#FFFFFF",
    activeColor: "#FFFFFF",
    upcomingColor: "rgba(255,255,255,0.5)",
    strokeColor: null,
    strokeWidth: 0,
    activeBackground: null,
    lineBackground: "rgba(0,0,0,0.6)",
    activeScale: 1,
    positionY: 0.78,
    emoji: false,
    tilt: 0,
  },
  beast: {
    id: "beast",
    label: "Hype",
    fontFamily: `Bangers, ${FALLBACK}`,
    fontWeight: 400,
    fontSize: 108,
    uppercase: true,
    color: "#FFFFFF",
    activeColor: "#FF3B30",
    upcomingColor: null,
    strokeColor: "#000000",
    strokeWidth: 14,
    activeBackground: null,
    lineBackground: null,
    activeScale: 1.22,
    positionY: 0.66,
    emoji: true,
    tilt: -3,
  },
};

export const getStyle = (id: string): CaptionStyle => CAPTION_STYLES[id as CaptionStyleId] ?? CAPTION_STYLES.bold;
