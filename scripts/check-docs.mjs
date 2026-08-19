/**
 * Quality gate for the PDLC artifacts.
 *
 * Enforces AC-002 ("genuinely real") mechanically rather than on trust:
 *   1. every artifact the charter promises actually exists and is non-trivial
 *   2. every requirement classified in the charter appears in the traceability
 *      matrix, with a story AND a test against it
 *   3. no artifact still contains an unresolved placeholder
 *
 * A requirement with no test is a process defect (charter §11), so this gate
 * fails the build rather than warning.
 */
import { existsSync, readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const errors = [];
const warnings = [];

const REQUIRED = [
  ["docs/00-governance/WAYS_OF_WORKING.md", 2000],
  ["docs/00-governance/SPRINT_00_PLAN.md", 500],
  ["docs/01-requirements/BRD.md", 2000],
  ["docs/01-requirements/PRD.md", 2000],
  ["docs/01-requirements/TRACEABILITY.md", 500],
  ["docs/03-architecture/TECH_SPEC.md", 3000],
  ["docs/04-quality/TEST_STRATEGY.md", 1000],
  ["docs/05-security/THREAT_MODEL.md", 1000],
];

for (const [rel, minBytes] of REQUIRED) {
  const full = resolve(root, rel);
  if (!existsSync(full)) { errors.push(`missing required artifact: ${rel}`); continue; }
  const size = statSync(full).size;
  if (size < minBytes) errors.push(`${rel}: ${size} bytes — below the ${minBytes}-byte floor (stub, not an artifact)`);
}

const REQ_ID = /\b([A-Z]{2,4}-\d{3})\b/g;
const read = (rel) => (existsSync(resolve(root, rel)) ? readFileSync(resolve(root, rel), "utf8") : "");

// 1. Requirements are DECLARED in the charter, the BRD and the PRD. Other
//    documents reference requirements but do not create them; treating a
//    reference as a declaration would force TECH_SPEC prose to be traced.
const DECLARING_DOCS = [
  "docs/00-governance/WAYS_OF_WORKING.md",
  "docs/01-requirements/BRD.md",
  "docs/01-requirements/PRD.md",
];
const declared = new Set();
for (const rel of DECLARING_DOCS) {
  for (const id of read(rel).match(REQ_ID) ?? []) declared.add(id);
}

// 2. Requirements the traceability matrix covers, with story + test populated.
const trace = read("docs/01-requirements/TRACEABILITY.md");
const covered = new Set();
for (const raw of trace.split("\n")) {
  const line = raw.trim();
  if (!line.startsWith("|") || line.includes("---")) continue;
  const cells = line.split("|").map((c) => c.trim()).filter((c, i, a) => i > 0 && i < a.length - 1);
  if (cells.length < 4) continue;
  const id = cells[0].match(/^([A-Z]{2,4}-\d{3})$/)?.[1];
  if (!id) continue;
  const [, , story, test] = cells;
  const empty = (v) => !v || v === "-" || v === "—" || /^tbd$/i.test(v);
  if (empty(story)) { errors.push(`TRACEABILITY: ${id} has no story`); continue; }
  if (empty(test))  { errors.push(`TRACEABILITY: ${id} has no test — charter §11 forbids this`); continue; }
  covered.add(id);
}

for (const id of declared) {
  if (!covered.has(id)) errors.push(`requirement ${id} is declared in the charter but not traced`);
}
for (const id of covered) {
  if (!declared.has(id)) warnings.push(`${id} is traced but never declared in the charter`);
}

// 3. Unresolved placeholders anywhere in docs.
const PLACEHOLDER = /\b(TBD|TODO|FIXME|XXX|\?\?\?|LOREM IPSUM)\b/i;
for (const [rel] of REQUIRED) {
  const text = read(rel);
  text.split("\n").forEach((line, i) => {
    // A gate may name the tokens it forbids; prose may not contain them.
    if (PLACEHOLDER.test(line) && !/forbid|placeholder|gate|scanner/i.test(line)) {
      errors.push(`${rel}:${i + 1} unresolved placeholder — "${line.trim().slice(0, 70)}"`);
    }
  });
}

for (const w of warnings) console.warn(`  ! ${w}`);
if (errors.length) {
  console.error(`✗ PDLC artifact check FAILED (${errors.length} error${errors.length > 1 ? "s" : ""}):`);
  for (const e of errors) console.error(`   · ${e}`);
  process.exit(1);
}
console.log(`✓ PDLC artifacts complete — ${declared.size} requirements, all traced to a story and a test`);
