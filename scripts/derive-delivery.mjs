/**
 * Derive the delivery record from the repository (AC-C12, FR-020..FR-024).
 *
 * Every number on /delivery comes from here. Not one is typed by a human,
 * because a hand-written test count is a claim that drifts the moment someone
 * adds a test and forgets, and the whole argument of that page is that its
 * numbers can be checked.
 *
 *   node scripts/derive-delivery.mjs
 */

import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const out = resolve(root, "apps/web/src/generated/delivery.json");

const git = (...args) =>
  execFileSync("git", args, { cwd: root, encoding: "utf8" }).trim();

const read = (relative) => readFileSync(resolve(root, relative), "utf8");

function countTests() {
  /** Counted by parsing test files rather than by running pytest: this script
   *  runs at build time on a machine that may have no Python environment, and a
   *  number that only exists when the suite runs is a number the page cannot
   *  show. CI asserts the suite passes; this asserts how many there are. */
  const dir = resolve(root, "apps/agent/tests");
  let total = 0;
  let files = 0;
  for (const name of readdirSync(dir)) {
    if (!name.startsWith("test_") || !name.endsWith(".py")) continue;
    files += 1;
    total += (read(`apps/agent/tests/${name}`).match(/^\s*def test_/gm) ?? []).length;
  }
  return { total, files };
}

function countLines(globs) {
  let total = 0;
  for (const path of globs) {
    try {
      const output = execFileSync(
        "bash",
        ["-c", `find ${path} -type f \\( -name '*.py' -o -name '*.ts' -o -name '*.tsx' -o -name '*.mjs' -o -name '*.sql' \\) ! -path '*/.venv*' ! -path '*/node_modules/*' ! -path '*/.next/*' ! -path '*/reranker/*' -print0 | xargs -0 cat | grep -cve '^\\s*$'`],
        { cwd: root, encoding: "utf8" },
      );
      total += Number.parseInt(output.trim(), 10) || 0;
    } catch {
      /* a path that does not exist contributes nothing */
    }
  }
  return total;
}

function requirements() {
  const matrix = read("docs/01-requirements/TRACEABILITY.md");
  const rows = matrix
    .split("\n")
    .filter((line) => /^\|\s*[A-Z]{2,4}-\d{3}\s*\|/.test(line))
    .map((line) => line.split("|").map((cell) => cell.trim()).filter(Boolean));
  return {
    total: rows.length,
    done: rows.filter((r) => (r[5] ?? "").toLowerCase().startsWith("done")).length,
    planned: rows.filter((r) => (r[5] ?? "").toLowerCase().startsWith("planned")).length,
  };
}

function defects() {
  const log = read("docs/04-quality/DEFECT_LOG.md");
  const rows = log.split("\n").filter((line) => /^\|\s*D-\d{3}\s*\|/.test(line));
  return {
    total: rows.length,
    severityOne: rows.filter((line) => line.includes("**1**")).length,
    entries: rows.map((line) => {
      const cells = line.split("|").map((c) => c.trim()).filter(Boolean);
      return {
        id: cells[0], found: cells[1], sprint: cells[2],
        severity: (cells[3] ?? "").replace(/\*/g, ""),
        description: cells[4], cause: cells[5], status: cells[6],
      };
    }),
  };
}

function adrs() {
  const dir = resolve(root, "docs/03-architecture/adr");
  return readdirSync(dir)
    .filter((name) => name.endsWith(".md"))
    .sort()
    .map((name) => {
      const body = read(`docs/03-architecture/adr/${name}`);
      const title = body.match(/^#\s*(.+)$/m)?.[1] ?? name;
      const status = body.match(/\*\*Status:\*\*\s*([A-Za-z]+)/)?.[1] ?? "unknown";
      return { file: name, title, status };
    });
}

function sprints() {
  const dir = resolve(root, "docs/00-governance");
  return readdirSync(dir)
    .filter((name) => /^SPRINT_\d+_REVIEW\.md$/.test(name))
    .sort()
    .map((name) => {
      const body = read(`docs/00-governance/${name}`);
      return {
        number: Number.parseInt(name.match(/\d+/)?.[0] ?? "0", 10),
        name: body.match(/^\*\*Sprint:\*\*\s*\d+\s*—\s*(.+?)\s*·/m)?.[1] ?? "",
        release: body.match(/\*\*Release:\*\*\s*([\d.]+)/)?.[1] ?? "",
        velocity: body.match(/\*\*Velocity:\s*([^*]+)\*\*/)?.[1]?.trim() ?? "",
      };
    });
}

const commits = git("rev-list", "--count", "HEAD");
const firstCommit = git("log", "--reverse", "--format=%aI", "--max-count=1");
const lastCommit = git("log", "-1", "--format=%aI");
const sha = git("rev-parse", "--short", "HEAD");

const record = {
  generatedAt: new Date().toISOString(),
  repo: JSON.parse(read("product.config.json")).repo,
  sha,
  commits: Number.parseInt(commits, 10),
  firstCommit,
  lastCommit,
  tests: countTests(),
  lines: {
    agent: countLines(["apps/agent/sandscope_agent", "apps/agent/migrations"]),
    tests: countLines(["apps/agent/tests"]),
    web: countLines(["apps/web/src"]),
    tooling: countLines(["scripts", "apps/agent/training", "apps/agent/scripts"]),
  },
  docs: {
    files: execFileSync("bash", ["-c", "find docs -name '*.md' | wc -l"], { cwd: root, encoding: "utf8" }).trim(),
    lines: Number.parseInt(
      execFileSync("bash", ["-c", "find docs -name '*.md' -exec cat {} + | grep -cve '^\\s*$'"], { cwd: root, encoding: "utf8" }).trim(),
      10,
    ),
  },
  requirements: requirements(),
  defects: defects(),
  adrs: adrs(),
  sprints: sprints(),
};

writeFileSync(out, JSON.stringify(record, null, 2) + "\n");
process.stdout.write(
  `derived ${record.commits} commits · ${record.tests.total} tests · ` +
  `${record.requirements.total} requirements · ${record.defects.total} defects · ` +
  `${record.adrs.length} ADRs · ${record.sprints.length} sprint reviews\n`,
);
