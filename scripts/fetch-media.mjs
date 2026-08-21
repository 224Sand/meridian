/**
 * Fetch and transcode the hero footage.
 *
 * Reproducible and committed as a script rather than a one-time download, so
 * the encode settings are reviewable and the budget is enforced rather than
 * remembered.
 *
 * The Designer's spec is explicit that footage is atmosphere and never the
 * subject: this product's subject is a process - evidence, refusal, governance -
 * and a data-centre stock shot standing in for that would be decoration in
 * place of substance. One establishing clip, scrubbed by scroll. Everything
 * else on the page is the system's own output.
 *
 *   PEXELS_API_KEY=... node scripts/fetch-media.mjs
 */

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const outDir = resolve(root, "apps/web/public/media");

/** DESIGN_SYSTEM.md section 5. Enforced here, not remembered. */
const BUDGET = { seconds: 4, bytes: 2.5 * 1024 * 1024, width: 1920 };
/** Scrubbing needs frequent keyframes or seeking stutters visibly. */
const KEYFRAME_INTERVAL = 6;

/** Pinned by id so a re-run produces the same footage. A search that returns
 *  whatever is trending today is not a reproducible build. */
const CLIPS = [
  { id: 7140928, name: "hero", startSeconds: 1 },
];

function key() {
  const value = process.env.PEXELS_API_KEY?.trim();
  if (!value) throw new Error("PEXELS_API_KEY is not set");
  return value;
}

async function sourceUrl(id) {
  const response = await fetch(`https://api.pexels.com/videos/videos/${id}`, {
    headers: { Authorization: key() },
  });
  if (!response.ok) throw new Error(`pexels ${id}: HTTP ${response.status}`);
  const video = await response.json();
  const candidates = video.video_files
    .filter((f) => (f.width ?? 0) <= BUDGET.width && f.file_type === "video/mp4")
    .sort((a, b) => (b.width ?? 0) - (a.width ?? 0));
  if (candidates.length === 0) throw new Error(`pexels ${id}: no usable mp4`);
  return { url: candidates[0].link, credit: video.user?.name ?? "Pexels", link: video.url };
}

function transcode(input, output, startSeconds) {
  execFileSync("ffmpeg", [
    "-y", "-ss", String(startSeconds), "-i", input,
    "-t", String(BUDGET.seconds),
    "-vf", `scale=${BUDGET.width}:-2,format=yuv420p`,
    // CRF 26 with a slow preset: the page is dark and near-black gradients band
    // badly at higher CRF, which is exactly where a cheap encode shows.
    "-c:v", "libx264", "-preset", "slow", "-crf", "26",
    "-g", String(KEYFRAME_INTERVAL), "-keyint_min", String(KEYFRAME_INTERVAL),
    "-sc_threshold", "0",
    // No audio at all. The clip is muted by design and the track would be bytes
    // spent on silence.
    "-an",
    // Moves the index to the front so playback can begin before the whole file
    // has arrived. Without it a scrubbed video is unusable until fully loaded.
    "-movflags", "+faststart",
    output,
  ], { stdio: "inherit" });
}

function poster(input, output) {
  // A poster frame that is meaningful on its own: it replaces the video
  // entirely on mobile and under reduced motion.
  execFileSync("ffmpeg", ["-y", "-i", input, "-vframes", "1", "-q:v", "3", output], {
    stdio: "inherit",
  });
}

async function main() {
  mkdirSync(outDir, { recursive: true });
  const manifest = [];

  for (const clip of CLIPS) {
    const { url, credit, link } = await sourceUrl(clip.id);
    const raw = resolve(outDir, `.${clip.name}.source.mp4`);
    const mp4 = resolve(outDir, `${clip.name}.mp4`);
    const jpg = resolve(outDir, `${clip.name}.jpg`);

    if (!existsSync(raw)) {
      process.stdout.write(`fetching ${clip.name} (pexels ${clip.id})…\n`);
      const response = await fetch(url);
      writeFileSync(raw, Buffer.from(await response.arrayBuffer()));
    }

    transcode(raw, mp4, clip.startSeconds);
    poster(mp4, jpg);

    const bytes = statSync(mp4).size;
    if (bytes > BUDGET.bytes) {
      throw new Error(
        `${clip.name}.mp4 is ${(bytes / 1024 / 1024).toFixed(2)}MB, over the ` +
        `${(BUDGET.bytes / 1024 / 1024).toFixed(1)}MB budget. Shorten it or raise CRF ` +
        `deliberately — do not raise the budget to fit the file.`,
      );
    }

    manifest.push({
      name: clip.name,
      pexelsId: clip.id,
      credit,
      source: link,
      bytes,
      posterBytes: statSync(jpg).size,
    });
    process.stdout.write(
      `  ${clip.name}.mp4  ${(bytes / 1024 / 1024).toFixed(2)}MB  ` +
      `poster ${(statSync(jpg).size / 1024).toFixed(0)}KB\n`,
    );
  }

  writeFileSync(resolve(outDir, "CREDITS.json"), JSON.stringify(manifest, null, 2) + "\n");
  process.stdout.write("wrote CREDITS.json\n");
}

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exit(1);
});
