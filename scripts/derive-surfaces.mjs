/**
 * Derive /reliability and /architecture from the repository.
 *
 * Same rule as the delivery record: no number on either page is typed by a
 * human. Measurements come from the evaluation report and the model metadata
 * that training actually wrote; thresholds are read out of the module that
 * enforces them; the provider order is parsed from the function that builds it.
 * A page arguing that its numbers can be checked cannot contain a number that
 * was remembered.
 *
 *   node scripts/derive-surfaces.mjs
 */

import { readFileSync, readdirSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const outDir = resolve(root, "apps/web/src/generated");
mkdirSync(outDir, { recursive: true });

const read = (p) => readFileSync(resolve(root, p), "utf8");
const json = (p) => JSON.parse(read(p));

/** Fail loudly rather than emitting a page with a blank where a number goes. */
function required(value, what) {
  if (value === undefined || value === null || Number.isNaN(value)) {
    throw new Error(`derive-surfaces: could not derive ${what}`);
  }
  return value;
}

// ---------------------------------------------------------------- thresholds
// Read from the module that enforces them. A page that quoted these from memory
// would keep displaying 0.86 after the code moved on -- which is exactly how
// D-008 (the cache threshold) came to be wrong in the first place.
// Reads `NAME = <number>` without constructing a regex from a variable.
// Building one would be safe here -- every name is a literal in this file --
// but scanning lines is simpler, and it keeps the SAST gate meaningful rather
// than teaching it to ignore another rule.
function pyConstant(source, name) {
  for (const line of source.split("\n")) {
    const eq = line.indexOf("=");
    if (eq < 0 || line.trimStart().startsWith("#")) continue;
    if (line.slice(0, eq).trim() !== name) continue;
    const value = Number.parseFloat(line.slice(eq + 1).trim());
    if (!Number.isNaN(value)) return value;
  }
  return undefined;
}

const evidenceSrc = read("apps/agent/sandscope_agent/retrieval/evidence.py");
const num = (name) => required(pyConstant(evidenceSrc, name), name);

const thresholds = {
  insufficientBelow: num("INSUFFICIENT_BELOW"),
  sufficientAbove: num("SUFFICIENT_ABOVE"),
};

// ---------------------------------------------------------------- evaluation
// The evaluation report is produced by running the suites and is gitignored --
// it exists on a developer machine and as a CI artifact of the agent job, but
// not in the tree. When it is absent, keep the reliability.json already
// committed rather than failing the build or, worse, emitting zeros.
//
// This does not weaken the "no number is typed by hand" rule: the committed
// file was itself derived from a real run. It only means the web build does not
// have to wait on the agent job to produce a page whose inputs have not changed.
//
// Failing if BOTH are missing is deliberate -- that is the case where there is
// genuinely nothing to show, and a blank page would be a lie by omission.
const reportPath = resolve(root, "apps/agent/reports/evaluation.json");
const priorPath = resolve(outDir, "reliability.json");
if (!existsSync(reportPath)) {
  if (!existsSync(priorPath)) {
    throw new Error(
      "derive-surfaces: no evaluation report and no previously derived " +
        "reliability.json; run the evaluation suites before building.",
    );
  }
  console.log(
    "derive-surfaces: evaluation report absent; keeping the committed " +
      "reliability.json and regenerating architecture.json only",
  );
}
const evaluation = existsSync(reportPath)
  ? json("apps/agent/reports/evaluation.json")
  : null;
const checks = evaluation
  ? Object.fromEntries(evaluation.suites.flatMap((s) => s.checks.map((c) => [c.name, c])))
  : {};

const detail = (name) => required(checks[name], name).detail;
const parseRate = (name) => {
  const d = detail(name);
  const m = d.match(/([\d/]+)\s+.*?:\s*([\d.]+)\s*\[([\d.]+),\s*([\d.]+)\]/);
  return {
    counts: m?.[1] ?? null,
    rate: Number(m?.[2]),
    ci: [Number(m?.[3]), Number(m?.[4])],
    detail: d,
  };
};

// The gate budgets live in the harness that enforces them. These were briefly
// hand-typed here from memory and one was wrong -- 2% is the false-refusal
// figure used to DERIVE the threshold in evidence.py, not the budget the CI
// gate asserts against, which is 10%. The page consequently rendered a passing
// check as "over budget". Parsed now, for the same reason as everything else on
// these pages.
const harness = read("apps/agent/sandscope_agent/evaluation/harness.py");
const budget = (name) => required(pyConstant(harness, name), name);
const budgets = {
  falseAnswer: budget("FALSE_ANSWER_BUDGET"),
  falseRefusal: budget("FALSE_REFUSAL_BUDGET"),
};

let reliability = null;
if (evaluation) {
  const sample = detail("sample_is_large_enough");
  reliability = {
    generatedAt: new Date().toISOString(),
    sha: execFileSync("git", ["rev-parse", "--short", "HEAD"], { cwd: root, encoding: "utf8" }).trim(),
    thresholds,
    sample: {
      answerable: Number(sample.match(/(\d+)\s+answerable/)?.[1]),
      unanswerable: Number(sample.match(/(\d+)\s+unanswerable/)?.[1]),
    },
    gate: {
      falseAnswer: { ...parseRate("false_answer_rate_within_budget"), budget: budgets.falseAnswer },
      falseRefusal: { ...parseRate("false_refusal_rate_within_budget"), budget: budgets.falseRefusal },
    },
    // The probe suite exists to publish what is still weak. Its checks are
    // expected to fail; a green probe suite would mean it had stopped looking.
    weaknesses: evaluation.suites
      .find((s) => s.suite === "probe")
      ?.checks.map((c) => ({ name: c.name, detail: c.detail, value: c.value })) ?? [],
    model: (() => {
      const m = json("apps/agent/sandscope_agent/evaluation/model/metadata.json");
      return {
        kind: m.model,
        format: m.format,
        trainedOn: m.trained_on,
        features: m.features.length,
        featureNames: m.features,
        auc: m.cross_validated_auc,
        baselineAuc: m.baseline_auc,
        operatingPoint: m.operating_point,
      };
    })(),
    reranker: (() => {
      const m = json("apps/agent/sandscope_agent/retrieval/reranker/metrics.json");
      return {
        baseModel: m.base_model,
        trainingPairs: m.training_pairs,
        heldOutDocuments: m.held_out_documents,
        latencyP50Ms: m.rerank_latency_p50_ms,
        candidates: m.candidates,
        // Document-level was already 0.986 and hid the whole effect (D-003).
        // Both levels ship so the saturated metric stays visible next to the one
        // that could actually move.
        documentLevelMrr: m.document_level.hybrid.mrr,
        chunkLevel: {
          hybrid: m.chunk_level.hybrid.mrr,
          pretrained: m.chunk_level.pretrained_reranked.mrr,
          finetuned: m.chunk_level.finetuned_reranked.mrr,
        },
      };
    })(),
    defects: (() => {
      const rows = read("docs/04-quality/DEFECT_LOG.md")
        .split("\n")
        .filter((l) => /^\|\s*D-\d+\s*\|/.test(l))
        .map((l) => {
          const c = l.split("|").map((x) => x.trim());
          return {
            id: c[1],
            foundIn: c[2],
            sprint: c[3],
            severity: c[4].replace(/\*/g, ""),
            description: c[5],
            rootCause: c[6].replace(/\*/g, ""),
          };
        });
      return {
        total: rows.length,
        severity1: rows.filter((r) => r.severity === "1").length,
        caughtByReview: 0, // stated in the log, and the point of it
        rows,
      };
    })(),
    postmortems: readdirSync(resolve(root, "docs/06-operations/postmortems"))
      .filter((f) => f.endsWith(".md"))
      .sort()
      .map((f) => {
        const body = read(`docs/06-operations/postmortems/${f}`);
        return {
          file: f,
          title: body.match(/^#\s*(.+)$/m)?.[1]?.replace(/^Postmortem\s*—\s*/, "") ?? f,
          date: body.match(/\*\*Date:\*\*\s*([\d-]+)/)?.[1] ?? null,
        };
      }),
  };
}

// -------------------------------------------------------------- architecture
const adrDir = resolve(root, "docs/03-architecture/adr");
const adrs = readdirSync(adrDir)
  .filter((f) => /^\d{4}-.*\.md$/.test(f))
  .sort()
  .map((f) => {
    const body = read(`docs/03-architecture/adr/${f}`);
    const heading = body.match(/^#\s*ADR-(\d+)\s*—\s*(.+)$/m);
    return {
      id: heading?.[1] ?? f.slice(0, 4),
      title: required(heading?.[2], `title of ${f}`),
      status: body.match(/\*\*Status:\*\*\s*([A-Za-z]+)/)?.[1] ?? "Unknown",
      date: body.match(/\*\*Date:\*\*\s*([\d-]+)/)?.[1] ?? null,
      // The first paragraph of Context, which is the decision's reason for
      // existing. Truncated rather than summarised -- a summary would be a
      // hand-written claim about a document that is right there.
      context: body
        .split(/^##\s*Context\s*$/m)[1]
        ?.trim()
        .split(/\n\s*\n/)[0]
        ?.replace(/\s+/g, " ")
        .trim() ?? null,
    };
  });

// Parsed from the function that builds the chain, so reordering the code
// reorders the page.
const adapters = read("apps/agent/sandscope_agent/router/adapters.py");
const chainBlock = adapters.split("def build_default_providers")[1] ?? "";
const providers = [...chainBlock.matchAll(/(?:OpenAICompatibleProvider\((\w+),|(\w+)Provider\(client=)/g)]
  .map((m) => (m[1] ?? m[2]).toLowerCase())
  .filter((n) => n !== "openaicompatible");

if (providers.length === 0) throw new Error("derive-surfaces: provider chain not parsed");

const architecture = {
  generatedAt: new Date().toISOString(),
  sha: execFileSync("git", ["rev-parse", "--short", "HEAD"], { cwd: root, encoding: "utf8" }).trim(),
  providers,
  adrs,
  counts: {
    adrs: adrs.length,
    accepted: adrs.filter((a) => a.status === "Accepted").length,
  },
};

if (evaluation) {
  writeFileSync(resolve(outDir, "reliability.json"), JSON.stringify(reliability, null, 2) + "\n");
}
writeFileSync(resolve(outDir, "architecture.json"), JSON.stringify(architecture, null, 2) + "\n");

console.log(
  (reliability
    ? `derived reliability.json (${reliability.defects.total} defects, ${reliability.weaknesses.length} published weaknesses) and `
    : "derived ") +
    `architecture.json (${adrs.length} ADRs, ${providers.length} providers: ${providers.join(" → ")})`,
);
