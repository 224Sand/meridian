/**
 * Quality gate enforcing Definition of Done #4: no secret, key or credential
 * may appear in the tree.
 *
 * Patterns are assembled from fragments so this file cannot match itself, and
 * the scanner skips its own path as a second guard. A gate that trips on its
 * own source teaches the team to add --no-verify, which defeats the gate.
 *
 * For the same reason it scans the set of files that CAN be committed - git's
 * tracked and untracked-but-not-ignored files - rather than walking the
 * filesystem. The first version walked the tree and failed on .env, which is
 * gitignored and therefore uncommittable by construction. A gate that fails on
 * every machine with a working local environment is a gate everyone learns to
 * skip, which is precisely the failure this comment block was written to warn
 * about and did not prevent.
 */
import { execFileSync } from "node:child_process";
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

/**
 * Files that could actually reach a commit. `-c` cached (tracked), `-o` other
 * (untracked), `--exclude-standard` applies .gitignore. Outside a git repo the
 * directory walk below is the fallback.
 */
function committableFiles() {
  try {
    return execFileSync("git", ["ls-files", "-co", "--exclude-standard", "-z"], {
      cwd: root,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    })
      .split("\0")
      .filter(Boolean)
      .map((relPath) => resolve(root, relPath));
  } catch {
    return null;
  }
}

function scanFile(full) {
  if (full === SELF) return;
  const name = full.split("/").pop();
  if (!SCAN_EXT.test(name) && name !== ".env.example") return;
  try {
    if (statSync(full).size > MAX_BYTES) return;
  } catch {
    return;
  }

  const text = readFileSync(full, "utf8");
  const lines = text.split("\n");
  for (const [label, re] of RULES) {
    lines.forEach((line, i) => {
      const m = line.match(re);
      if (m && !PLACEHOLDER.test(line)) {
        findings.push({
          file: relative(root, full),
          line: i + 1,
          label,
          snippet: m[0].slice(0, 12) + "…",
        });
      }
    });
  }
}

function walk(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (!SKIP_DIRS.has(entry.name)) walk(full);
      continue;
    }
    scanFile(full);
  }
}

const tracked = committableFiles();
if (tracked) {
  for (const file of tracked) scanFile(file);
} else {
  walk(root);
}

if (findings.length) {
  console.error("✗ secret scan FAILED — Definition of Done #4 violated:");
  for (const f of findings) console.error(`   · ${f.file}:${f.line}  ${f.label}  (${f.snippet})`);
  process.exit(1);
}
console.log(`✓ secret scan clean (${tracked ? tracked.length + " committable files" : "directory walk"})`);
