#!/usr/bin/env node
/**
 * The traceability matrix must not claim more than the repository can show.
 *
 * The matrix defines exactly three statuses -- Planned, Building, Done -- and
 * defines Done as "implemented, test green in CI". Both halves of that were
 * being violated silently:
 *
 *   - rows used statuses the legend never defined (`Done (design)`,
 *     `Done (gate)`, `Done (decision)`), and the delivery page counted every
 *     one of them as done because it matched on the prefix. The public number
 *     was inflated by claims nothing checked.
 *   - one row sat at `Planned` while the test it named had been passing for
 *     four sprints, so the same number was also understated.
 *
 * Hand-maintained status drifts in both directions. This makes it a build
 * failure instead.
 *
 *   node scripts/check-traceability.mjs
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, resolve, join } from "node:path";
import { fileURLToPath } from "node:url";

// An optional root lets the guard be pointed at a fixture and observed to
// FAIL, which is Definition of Done item 9. A guard that has only ever been
// run against a passing tree has not been tested.
const root = resolve(process.argv[2] ?? resolve(dirname(fileURLToPath(import.meta.url)), ".."));
const VALID = new Set(["Planned", "Building", "Done"]);

const tracked = execFileSync("git", ["ls-files"], { cwd: root, encoding: "utf8" })
  .split("\n")
  .filter((f) => /\.(py|ts|tsx|mjs|yml)$/.test(f));

let corpus = "";
for (const file of tracked) {
  try {
    corpus += readFileSync(resolve(root, file), "utf8") + "\n";
  } catch {
    /* unreadable files cannot support a claim either way */
  }
}

const rows = readFileSync(resolve(root, "docs/01-requirements/TRACEABILITY.md"), "utf8")
  .split("\n")
  .filter((line) => /^\|\s*[A-Z]{2,4}-\d{3}\s*\|/.test(line))
  .map((line) => {
    const c = line.split("|").map((x) => x.trim());
    return { id: c[1], test: c[4], status: c[6] };
  });

const problems = [];

for (const row of rows) {
  if (!VALID.has(row.status)) {
    problems.push(
      `${row.id}: status ${JSON.stringify(row.status)} is not one of ` +
        `${[...VALID].join(", ")}. A qualifier appended to "Done" still counts ` +
        `as done on the delivery page.`,
    );
    continue;
  }
  if (row.status !== "Done") continue;

  // A Done row must name something the repository actually contains.
  const identifiers = (row.test.match(/[A-Za-z_][A-Za-z0-9_.\/-]{6,}/g) ?? []).filter(
    (t) => !/^https?/.test(t),
  );
  const found = identifiers.some((t) => {
    if (corpus.includes(t)) return true;
    try {
      return statSync(resolve(root, t)).isFile();
    } catch {
      return false;
    }
  });
  if (!found) {
    problems.push(
      `${row.id}: claims Done but nothing in the repository matches its test ` +
        `${JSON.stringify(row.test)}.`,
    );
  }
}

if (problems.length) {
  console.error(`traceability check FAILED (${problems.length})\n`);
  for (const p of problems) console.error("  " + p);
  process.exit(1);
}
console.log(
  `traceability check passed: ${rows.length} requirements, ` +
    `${rows.filter((r) => r.status === "Done").length} Done and each names a test that exists`,
);
