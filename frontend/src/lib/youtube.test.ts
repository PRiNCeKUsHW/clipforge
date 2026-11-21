import { describe, expect, it } from "vitest";

import { youtubeVideoId } from "./youtube";

// Keep in sync with backend/tests/test_services.py::test_youtube_video_id
describe("youtubeVideoId", () => {
  it.each([
    ["https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"],
    ["https://youtube.com/watch?v=dQw4w9WgXcQ&t=42s", "dQw4w9WgXcQ"],
    ["https://m.youtube.com/watch?feature=share&v=dQw4w9WgXcQ", "dQw4w9WgXcQ"],
    ["https://youtu.be/dQw4w9WgXcQ?si=abc", "dQw4w9WgXcQ"],
    ["https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"],
    ["https://www.youtube.com/live/dQw4w9WgXcQ", "dQw4w9WgXcQ"],
    ["  https://www.youtube.com/watch?v=dQw4w9WgXcQ  ", "dQw4w9WgXcQ"],
    ["https://www.youtube.com/playlist?list=PL123", null],
    ["https://www.youtube.com/@channel", null],
    ["https://evil.com/watch?v=dQw4w9WgXcQ", null],
    ["https://youtube.com.evil.com/watch?v=dQw4w9WgXcQ", null],
    ["javascript:alert(1)", null],
    ["ftp://youtube.com/watch?v=dQw4w9WgXcQ", null],
    ["not a url", null],
  ])("%s -> %s", (url, id) => expect(youtubeVideoId(url)).toBe(id));
});
