#!/usr/bin/env node
/**
 * The README states figures. This asserts they match the derived record.
 *
 * The README is the most-read document here and the least likely to be updated
 * when a number moves. It claims its figures are derived; without this check
 * that claim would be the first thing to rot -- the same failure as the
 * traceability matrix (D-014), which was rendered publicly as fact while
 * drifting in both directions.
 *
 * The first version of this script searched for each value as a SUBSTRING of
 * the whole file. That cannot fail: change "| Commits | 54 |" to 99 and the
 * check still passes, because "54" also appears in "54% of questions". It was
 * caught by deliberately corrupting a number and watching it go green -- the
 * D-013 defect, written into the very script that exists to prevent this class.
 *
 * Each claim now anchors to the sentence or table cell that makes it, so the
 * check fails when the stated number changes and only then.
 *
 * Commit count is deliberately NOT checked, and not stated. It changes with
 * the very commit that would correct it, so any value in a checked file is
 * wrong the instant it is written -- an unwinnable check on the least
 * informative number available.
 *
 *   node scripts/check-readme.mjs
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const readme = readFileSync(resolve(root, "README.md"), "utf8");
const delivery = JSON.parse(readFileSync(resolve(root, "apps/web/src/generated/delivery.json"), "utf8"));
const reliability = JSON.parse(readFileSync(resolve(root, "apps/web/src/generated/reliability.json"), "utf8"));

const pct = (n) => `${(n * 100).toFixed(1)}%`;
const g = reliability.gate;
const m = reliability.model;
const rr = reliability.reranker;

/** [label, anchoring regex with ONE capture group, expected value, source] */
const claims = [
  ["tests", /\| Tests \| ([\d,]+) across/, delivery.tests.total, "delivery.tests.total"],
  ["test files", /across ([\d,]+) files \|/, delivery.tests.files, "delivery.tests.files"],
  ["requirements", /\| Requirements \| ([\d,]+), of which/, delivery.requirements.total, "delivery.requirements.total"],
  ["requirements Done", /of which ([\d,]+) `Done`/, delivery.requirements.done, "delivery.requirements.done"],
  ["requirements Planned", /[-*] ([\d,]+) of \d+ requirements are still `Planned`/, delivery.requirements.planned, "delivery.requirements.planned"],
  ["defects", /\| Defects logged \| ([\d,]+), of which/, delivery.defects.total, "delivery.defects.total"],
  ["severity 1", /of which ([\d,]+) severity 1 \|/, delivery.defects.severityOne, "delivery.defects.severityOne"],
  ["ADRs", /\| ADRs \| ([\d,]+) \|/, JSON.parse(readFileSync(resolve(root, "apps/web/src/generated/architecture.json"), "utf8")).counts.adrs, "architecture.counts.adrs"],
  ["labelled questions", /\*\*([\d,]+) labelled\s+questions\*\*/, reliability.sample.answerable + reliability.sample.unanswerable, "reliability.sample"],
  ["answerable", /\(([\d,]+) answerable/, reliability.sample.answerable, "reliability.sample.answerable"],
  ["unanswerable", /answerable, ([\d,]+) not\)/, reliability.sample.unanswerable, "reliability.sample.unanswerable"],
  ["false-answer rate", /\| False answers \| ([\d.]+%) \|/, pct(g.falseAnswer.rate), "gate.falseAnswer.rate"],
  ["false-refusal rate", /\| False refusals \| ([\d.]+%) \|/, pct(g.falseRefusal.rate), "gate.falseRefusal.rate"],
  ["classifier AUC", /\*\*AUC ([\d.]+)\*\*/, m.auc.toFixed(3), "model.auc"],
  ["baseline AUC", /vs ([\d.]+) baseline/, m.baselineAuc.toFixed(3), "model.baselineAuc"],
  ["training examples", /features, ([\d,]+) examples/, m.trainedOn, "model.trainedOn"],
  ["chunk MRR before", /MRR \*\*([\d.]+) →/, rr.chunkLevel.hybrid.toFixed(3), "reranker.chunkLevel.hybrid"],
  ["chunk MRR after", /→ ([\d.]+)\*\*/, rr.chunkLevel.finetuned.toFixed(3), "reranker.chunkLevel.finetuned"],
  ["re-rank latency", /p50 ([\d.]+)ms/, rr.latencyP50Ms, "reranker.latencyP50Ms"],
];

const problems = [];
for (const [label, pattern, expected, source] of claims) {
  const found = readme.match(pattern);
  if (!found) {
    problems.push(`${label}: the README no longer makes this claim in a recognisable form (${source}). Update the pattern or the text.`);
    continue;
  }
  const stated = found[1].replace(/,/g, "");
  if (stated !== String(expected)) {
    problems.push(`${label}: README says ${JSON.stringify(found[1])}, derived record says ${JSON.stringify(String(expected))} (${source}).`);
  }
}

if (problems.length) {
  console.error(`README check FAILED (${problems.length})\n`);
  for (const p of problems) console.error("  " + p);
  console.error("\n  Update README.md, or its claim that the figures are derived is false.");
  process.exit(1);
}
console.log(`README check passed: ${claims.length} stated figures match the derived record`);
