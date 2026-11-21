// ClipForge render service.
//
// The Python worker cuts each clip segment into the shared work volume, then calls:
//   POST /render {input, output, props}  -> {id}
//   GET  /jobs/:id                       -> {status, progress, error}
// Inputs/outputs must live under WORK_ROOT; the renderer never touches object storage.

import { createReadStream, existsSync, statSync, renameSync } from "node:fs";
import http from "node:http";
import path from "node:path";
import { randomUUID } from "node:crypto";

import { bundle } from "@remotion/bundler";
import { ensureBrowser, renderMedia, selectComposition } from "@remotion/renderer";

const PORT = Number(process.env.PORT || 3100);
const WORK_ROOT = path.resolve(process.env.WORK_ROOT || "/data/work");
const CONCURRENCY = process.env.RENDER_CONCURRENCY ? Number(process.env.RENDER_CONCURRENCY) : 2;
const LICENSE_KEY = process.env.REMOTION_LICENSE_KEY || null;

const jobs = new Map(); // id -> {status, progress, error, input, output, props, finishedAt}
const queue = [];
let serveUrl = null;
let busy = false;

const log = (...args) => console.log(new Date().toISOString(), ...args);

function insideWorkRoot(p) {
  const resolved = path.resolve(p);
  return resolved === WORK_ROOT || resolved.startsWith(WORK_ROOT + path.sep);
}

function sendJson(res, status, body) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(body));
}

async function readJson(req) {
  let raw = "";
  for await (const chunk of req) {
    raw += chunk;
    if (raw.length > 5_000_000) throw new Error("request too large");
  }
  return JSON.parse(raw || "{}");
}

// Serves clip segments to the headless browser, with Range support for seeking.
function serveFile(req, res, rel) {
  const file = path.resolve(WORK_ROOT, decodeURIComponent(rel));
  if (!insideWorkRoot(file) || !existsSync(file)) return sendJson(res, 404, { error: "not found" });
  const size = statSync(file).size;
  const range = req.headers.range;
  if (range) {
    const [s, e] = range.replace("bytes=", "").split("-");
    const start = Number(s);
    const end = e ? Number(e) : size - 1;
    res.writeHead(206, {
      "Content-Type": "video/mp4",
      "Content-Range": `bytes ${start}-${end}/${size}`,
      "Accept-Ranges": "bytes",
      "Content-Length": end - start + 1,
    });
    createReadStream(file, { start, end }).pipe(res);
  } else {
    res.writeHead(200, { "Content-Type": "video/mp4", "Content-Length": size, "Accept-Ranges": "bytes" });
    createReadStream(file).pipe(res);
  }
}

async function runJob(id) {
  const job = jobs.get(id);
  job.status = "rendering";
  const rel = path.relative(WORK_ROOT, path.resolve(job.input)).split(path.sep).map(encodeURIComponent).join("/");
  const inputProps = { ...job.props, videoSrc: `http://127.0.0.1:${PORT}/files/${rel}` };
  const tmp = `${job.output}.part.mp4`;
  const started = Date.now();
  try {
    const composition = await selectComposition({ serveUrl, id: "Clip", inputProps, licenseKey: LICENSE_KEY });
    await renderMedia({
      composition,
      serveUrl,
      codec: "h264",
      audioCodec: "aac",
      crf: 20,
      inputProps,
      outputLocation: tmp,
      concurrency: CONCURRENCY,
      timeoutInMilliseconds: 120_000,
      licenseKey: LICENSE_KEY,
      onProgress: ({ progress }) => {
        job.progress = progress;
      },
    });
    renameSync(tmp, job.output);
    job.status = "done";
    job.progress = 1;
    log(`job ${id} done in ${((Date.now() - started) / 1000).toFixed(1)}s`);
  } catch (err) {
    job.status = "failed";
    job.error = String(err?.message || err).slice(0, 2000);
    log(`job ${id} failed: ${job.error}`);
  } finally {
    job.finishedAt = Date.now();
  }
}

async function pump() {
  if (busy || !serveUrl) return;
  busy = true;
  try {
    while (queue.length) await runJob(queue.shift());
  } finally {
    busy = false;
  }
}

// Forget finished jobs after an hour.
setInterval(() => {
  const cutoff = Date.now() - 3600_000;
  for (const [id, job] of jobs) if (job.finishedAt && job.finishedAt < cutoff) jobs.delete(id);
}, 600_000).unref();

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://${req.headers.host}`);
    if (req.method === "GET" && url.pathname === "/health") {
      return sendJson(res, 200, { ok: true, ready: Boolean(serveUrl), queued: queue.length, busy });
    }
    if (req.method === "GET" && url.pathname.startsWith("/files/")) {
      return serveFile(req, res, url.pathname.slice("/files/".length));
    }
    if (req.method === "POST" && url.pathname === "/render") {
      const body = await readJson(req);
      const { input, output, props } = body;
      if (!input || !output || !props) return sendJson(res, 400, { error: "input, output and props are required" });
      if (!insideWorkRoot(input) || !insideWorkRoot(output)) return sendJson(res, 400, { error: "paths must be inside WORK_ROOT" });
      if (!existsSync(input)) return sendJson(res, 400, { error: `input not found: ${input}` });
      const id = randomUUID();
      jobs.set(id, { status: "queued", progress: 0, error: null, input, output, props, finishedAt: null });
      queue.push(id);
      pump();
      return sendJson(res, 202, { id });
    }
    const m = url.pathname.match(/^\/jobs\/([\w-]+)$/);
    if (req.method === "GET" && m) {
      const job = jobs.get(m[1]);
      if (!job) return sendJson(res, 404, { error: "unknown job" });
      return sendJson(res, 200, { status: job.status, progress: job.progress, error: job.error, ready: Boolean(serveUrl) });
    }
    sendJson(res, 404, { error: "not found" });
  } catch (err) {
    sendJson(res, 500, { error: String(err?.message || err) });
  }
});

server.listen(PORT, () => log(`renderer listening on :${PORT}, work root ${WORK_ROOT}`));

// Prepare the headless browser and the webpack bundle once at startup.
(async () => {
  await ensureBrowser();
  serveUrl = await bundle({ entryPoint: path.resolve("src/index.ts") });
  log("bundle ready");
  pump();
})().catch((err) => {
  log("startup failed", err);
  process.exit(1);
});
