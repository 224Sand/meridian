#!/usr/bin/env node
/**
 * Guards every `run:` block in .github/workflows against two failure modes
 * that CI reports only as an opaque exit code:
 *
 *   1. A comment line inside a backslash-continued command. Bash ends the
 *      continuation at the comment, then executes the following flag as a
 *      command. This surfaces as "not found" + exit 127, long after the real
 *      tool has already run and printed plausible output -- which is exactly
 *      how it cost a full CI round trip (D-011).
 *
 *   2. Shell syntax errors, caught with `bash -n` before a runner sees them.
 *
 * Runs offline in milliseconds. No network, no tooling beyond bash.
 */
import { readFileSync, readdirSync, writeFileSync, mkdtempSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { execFileSync } from "node:child_process";

const dir = ".github/workflows";
const failures = [];

for (const file of readdirSync(dir).filter((f) => /\.ya?ml$/.test(f))) {
  const path = join(dir, file);
  const lines = readFileSync(path, "utf8").split("\n");

  // Locate `run: |` blocks by indentation rather than parsing YAML, so the
  // reported line numbers match the file the author will open.
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/^(\s*)-?\s*run:\s*\|/);
    if (!m) continue;
    const indent = m[1].length;
    const body = [];
    let j = i + 1;
    for (; j < lines.length; j++) {
      const line = lines[j];
      if (line.trim() !== "" && line.search(/\S/) <= indent) break;
      body.push({ n: j + 1, text: line });
    }

    // 1. comment inside a continuation
    for (let k = 0; k < body.length - 1; k++) {
      if (!body[k].text.trimEnd().endsWith("\\")) continue;
      const next = body[k + 1].text.trim();
      if (next.startsWith("#")) {
        failures.push(
          `${path}:${body[k + 1].n}  comment inside a backslash continuation — ` +
            `bash ends the command here and runs the next line as a program`,
        );
      }
    }

    // 2. shell syntax
    const script = body.map((b) => b.text.slice(indent + 2)).join("\n");
    const tmp = join(mkdtempSync(join(tmpdir(), "wf-")), "s.sh");
    writeFileSync(tmp, script);
    try {
      execFileSync("bash", ["-n", tmp], { stdio: "pipe" });
    } catch (e) {
      const msg = String(e.stderr || e).split("\n")[0].replace(tmp, `${path} (run block at line ${i + 1})`);
      failures.push(`${path}:${i + 1}  shell syntax: ${msg}`);
    }
    i = j - 1;
  }
}

if (failures.length) {
  console.error("workflow shell check FAILED\n");
  for (const f of failures) console.error("  " + f);
  process.exit(1);
}
console.log("workflow shell check passed");
