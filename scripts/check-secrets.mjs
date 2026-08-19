/**
 * Quality gate enforcing Definition of Done #4: no secret, key or credential
 * may appear in the tree.
 *
 * Patterns are assembled from fragments so this file cannot match itself, and
 * the scanner skips its own path as a second guard. A gate that trips on its
 * own source teaches the team to add --no-verify, which defeats the gate.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, relative, resolve } from "node:path";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const SELF = resolve(root, "scripts/check-secrets.mjs");

const SKIP_DIRS = new Set([
  ".git", "node_modules", ".next", "dist", "build", "out",
  "__pycache__", ".venv", "venv", ".pytest_cache", "coverage", "_work",
]);
const SCAN_EXT = /\.(mjs|cjs|js|jsx|ts|tsx|py|json|ya?ml|md|txt|env|sh|toml|html|css)$/i;
const MAX_BYTES = 2 * 1024 * 1024;

// Assembled from fragments: the literal prefixes never appear in this source.
const P = (...parts) => parts.join("");
const RULES = [
  ["OpenAI key",        new RegExp(P("sk", "-") + "[A-Za-z0-9_-]{20,}")],
  ["Groq key",          new RegExp(P("gsk", "_") + "[A-Za-z0-9]{20,}")],
  ["Google/Gemini key", new RegExp(P("AIza") + "[A-Za-z0-9_-]{30,}")],
  ["GitHub token",      new RegExp(P("gh", "[pousr]", "_") + "[A-Za-z0-9]{30,}")],
  ["Slack token",       new RegExp(P("xox", "[baprs]", "-") + "[A-Za-z0-9-]{10,}")],
  ["AWS access key",    new RegExp(P("AKIA") + "[0-9A-Z]{16}")],
  ["Anthropic key",     new RegExp(P("sk", "-ant-") + "[A-Za-z0-9_-]{20,}")],
  ["Private key block", new RegExp(P("-----BEGIN ") + "[A-Z ]*" + P("PRIVATE KEY", "-----"))],
];

// A .env.example is documentation; placeholders there are the point.
const PLACEHOLDER = /(your[_-]?key|xxx+|placeholder|example|changeme|<[^>]+>|\.\.\.)/i;

const findings = [];

function walk(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (!SKIP_DIRS.has(entry.name)) walk(full);
      continue;
    }
    if (full === SELF) continue;
    if (!SCAN_EXT.test(entry.name) && entry.name !== ".env.example") continue;
    if (statSync(full).size > MAX_BYTES) continue;

    const text = readFileSync(full, "utf8");
    const lines = text.split("\n");
    for (const [label, re] of RULES) {
      lines.forEach((line, i) => {
        const m = line.match(re);
        if (m && !PLACEHOLDER.test(line)) {
          findings.push({ file: relative(root, full), line: i + 1, label, snippet: m[0].slice(0, 12) + "…" });
        }
      });
    }
  }
}

walk(root);

if (findings.length) {
  console.error("✗ secret scan FAILED — Definition of Done #4 violated:");
  for (const f of findings) console.error(`   · ${f.file}:${f.line}  ${f.label}  (${f.snippet})`);
  process.exit(1);
}
console.log("✓ secret scan clean");
