#!/usr/bin/env node
/**
 * A sprint number may not be used before the sprint is opened.
 *
 * Sprints 6 and 7 were worked and shipped without a planning ceremony or a plan
 * document. The number existed only in defect-log entries: a claim with no
 * artifact behind it, which is the same failure the traceability gate was built
 * to catch, committed against the process instead of the requirements (D-016).
 *
 * The Sprint 5 retrospective had already committed, in writing, to raising a
 * silent role as an impediment. It was not honoured, because it relied on
 * someone remembering. This is that commitment expressed as a build failure.
 *
 * Checks:
 *   1. every `Sprint N` referenced in docs/ has a SPRINT_0N_PLAN.md
 *   2. every review has a matching plan
 *   3. plans are contiguous from 0 — a gap means a sprint was skipped silently
 *
 * Accepts an optional root so the guard can be run against a fixture and
 * observed to fail (Definition of Done item 9).
 *
 *   node scripts/check-sprints.mjs [root]
 */
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { dirname, resolve, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(process.argv[2] ?? resolve(dirname(fileURLToPath(import.meta.url)), ".."));
const governance = join(root, "docs/00-governance");

const planned = new Set();
const reviewed = new Set();
for (const file of existsSync(governance) ? readdirSync(governance) : []) {
  const plan = file.match(/^SPRINT_(\d{2})_PLAN\.md$/);
  const review = file.match(/^SPRINT_(\d{2})_REVIEW\.md$/);
  if (plan) planned.add(Number(plan[1]));
  if (review) reviewed.add(Number(review[1]));
}

/** Every markdown file under docs/, recursively. */
function markdown(dir) {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...markdown(full));
    else if (entry.name.endsWith(".md")) out.push(full);
  }
  return out;
}

const problems = [];
const referenced = new Map();

for (const file of markdown(join(root, "docs"))) {
  const text = readFileSync(file, "utf8");
  for (const m of text.matchAll(/\bSprint (\d{1,2})\b/g)) {
    const n = Number(m[1]);
    if (!referenced.has(n)) referenced.set(n, file);
  }
}

for (const [n, file] of [...referenced].sort((a, b) => a[0] - b[0])) {
  if (!planned.has(n)) {
    problems.push(
      `Sprint ${n} is referenced in ${file.replace(root + "/", "")} but ` +
        `SPRINT_${String(n).padStart(2, "0")}_PLAN.md does not exist. ` +
        `A sprint number in an artifact is a claim that the sprint was opened.`,
    );
  }
}

for (const n of [...reviewed].sort((a, b) => a - b)) {
  if (!planned.has(n)) {
    problems.push(`Sprint ${n} has a review but no plan; it was closed without being opened.`);
  }
}

const highest = Math.max(-1, ...planned);
for (let n = 0; n <= highest; n += 1) {
  if (!planned.has(n)) {
    problems.push(`Sprint ${n} has no plan while Sprint ${highest} does; the sequence has a gap.`);
  }
}

if (problems.length) {
  console.error(`sprint check FAILED (${problems.length})\n`);
  for (const p of problems) console.error("  " + p);
  process.exit(1);
}
console.log(
  `sprint check passed: ${planned.size} planned (0-${highest}), ` +
    `${reviewed.size} reviewed, no number used before its plan`,
);
