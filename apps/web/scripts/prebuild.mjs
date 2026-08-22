/**
 * Pre-build hook that tolerates being run outside the monorepo.
 *
 * The derive scripts live at the repository root (../../scripts) and regenerate
 * the JSON that /delivery, /reliability and /architecture read. When the whole
 * repo is present -- local dev, CI, a Vercel build rooted at the repo -- they
 * run, so those pages are always derived from the current tree.
 *
 * A deploy of the apps/web subtree alone does not carry them. That is not a
 * reason to fail the build: the generated JSON is committed, so the pages still
 * render real derived numbers, just as of the last commit that ran the scripts.
 * Failing here would block a deploy over data that is already present.
 */
import { existsSync } from "node:fs";
import { execFileSync } from "node:child_process";

const scripts = [
  "../../scripts/derive-delivery.mjs",
  "../../scripts/derive-surfaces.mjs",
];

if (scripts.every((s) => existsSync(s))) {
  for (const script of scripts) {
    execFileSync("node", [script], { stdio: "inherit" });
  }
} else {
  console.log(
    "prebuild: derive scripts not present (deploying the apps/web subtree) — " +
      "using the committed generated JSON, which was derived at commit time.",
  );
}
