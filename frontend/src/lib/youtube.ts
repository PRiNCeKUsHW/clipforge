// Mirrors backend/app/services/youtube.py so the form can validate instantly.
const YT_HOSTS = new Set(["youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"]);
const ID_RE = /^[A-Za-z0-9_-]{11}$/;

export function youtubeVideoId(raw: string): string | null {
  let url: URL;
  try {
    url = new URL(raw.trim());
  } catch {
    return null;
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") return null;
  const host = url.hostname.toLowerCase();
  const parts = url.pathname.split("/").filter(Boolean);
  let candidate: string | null = null;
  if (host === "youtu.be") candidate = parts[0] ?? null;
  else if (YT_HOSTS.has(host)) {
    if (url.pathname === "/watch") candidate = url.searchParams.get("v");
    else if (parts.length >= 2 && ["shorts", "live", "embed", "v"].includes(parts[0])) candidate = parts[1];
  }
  return candidate && ID_RE.test(candidate) ? candidate : null;
}

export const isYouTubeUrl = (raw: string) => youtubeVideoId(raw) !== null;
