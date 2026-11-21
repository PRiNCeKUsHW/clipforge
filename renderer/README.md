# renderer

Remotion project (React components rendered to video) plus a tiny HTTP render service.

* `src/ClipVideo.tsx`: the 1080x1920 composition: applies the reframe crop path (single, split
  screen, fit) and draws word-by-word animated captions.
* `src/captions.ts`: groups words into 2-4 word lines, finds the active word, keyword emoji.
* `src/styles.ts`: caption style presets (`bold`, `karaoke`, `minimal`, `beast`).
* `server.mjs`: `POST /render {input, output, props}` → `{id}`, `GET /jobs/:id` → progress.
  Inputs/outputs live on the shared `/data/work` volume; the Python worker cuts the segment,
  calls this service, then uploads the result. The renderer never needs storage credentials.

```bash
npm install
npm run studio     # preview the composition and styles in the browser
npm test           # caption grouping + crop math
```

**License:** Remotion is free for individuals and companies of up to 3 people; larger companies
need a company license (set `REMOTION_LICENSE_KEY`). See https://remotion.dev/license.
