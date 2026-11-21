import { cancelRender, continueRender, delayRender } from "remotion";
import bangers400 from "@fontsource/bangers/files/bangers-latin-400-normal.woff2";
import inter700 from "@fontsource/inter/files/inter-latin-700-normal.woff2";
import montserrat800 from "@fontsource/montserrat/files/montserrat-latin-800-normal.woff2";
import montserrat900 from "@fontsource/montserrat/files/montserrat-latin-900-normal.woff2";

// Fonts are bundled (no network needed at render time). delayRender makes Remotion wait for them
// before capturing the first frame, so captions never render in a fallback font.
const FONTS = [
  { family: "Montserrat", weight: "800", url: montserrat800 },
  { family: "Montserrat", weight: "900", url: montserrat900 },
  { family: "Inter", weight: "700", url: inter700 },
  { family: "Bangers", weight: "400", url: bangers400 },
];

const handle = delayRender("Loading caption fonts");
Promise.all(
  FONTS.map((f) =>
    new FontFace(f.family, `url(${f.url})`, { weight: f.weight }).load().then((face) => {
      document.fonts.add(face);
    }),
  ),
)
  .then(() => continueRender(handle))
  .catch((err) => cancelRender(err));
