/**
 * FR-001 / ADR-0002 — rename the product without a refactor.
 *
 * The product name is authored in exactly one file (product.config.json).
 * Everything else reads it at build time, so a rename is a data edit, not a
 * find-and-replace across the tree.
 *
 *   npm run rename -- VANTAGE                 # local config only (default)
 *   npm run rename -- VANTAGE --apply-remote  # also renames the GitHub repo
 *
 * The remote rename is opt-in on purpose: renaming a public repo changes a URL
 * other people may already hold, which is not something a build script should
 * do as a side effect.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const applyRemote = args.includes("--apply-remote");
const newName = args.find((a) => !a.startsWith("--"));

if (!newName) {
  console.error("usage: npm run rename -- <NEW_NAME> [--apply-remote]");
  process.exit(1);
}

const NAME_RE = /^[A-Za-z][A-Za-z0-9 ._-]{1,31}$/;
if (!NAME_RE.test(newName)) {
  console.error(`✗ "${newName}" is not a valid product name (2-32 chars, must start with a letter)`);
  process.exit(1);
}

const slugify = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const newSlug = slugify(newName);

const configPath = resolve(root, "product.config.json");
const config = JSON.parse(readFileSync(configPath, "utf8"));
const oldName = config.name;
const oldSlug = config.slug;

if (oldName === newName) {
  console.log(`· already named "${newName}" — nothing to do`);
  process.exit(0);
}

const owner = config.repo.split("/")[0];
const updated = {
  ...config,
  name: newName,
  slug: newSlug,
  wordmark: newName.toUpperCase(),
  repo: `${owner}/${newSlug}`,
  primaryDomain: config.primaryDomain.replace(oldSlug, newSlug),
  agentServiceUrl: config.agentServiceUrl.replace(oldSlug, newSlug),
  provisional: false,
};

writeFileSync(configPath, JSON.stringify(updated, null, 2) + "\n");

console.log(`✓ renamed "${oldName}" → "${newName}"`);
console.log(`    slug             ${oldSlug} → ${newSlug}`);
console.log(`    repo             ${config.repo} → ${updated.repo}`);
console.log(`    primaryDomain    ${config.primaryDomain} → ${updated.primaryDomain}`);
console.log(`    agentServiceUrl  ${config.agentServiceUrl} → ${updated.agentServiceUrl}`);
console.log(`    provisional      ${config.provisional} → false`);

if (applyRemote) {
  try {
    execFileSync("gh", ["repo", "rename", newSlug, "--repo", config.repo, "--yes"], { stdio: "inherit" });
    console.log(`✓ GitHub repository renamed to ${updated.repo}`);
    console.log(`  note: GitHub redirects the old URL, but update any git remote with:`);
    console.log(`        git remote set-url origin https://github.com/${updated.repo}.git`);
  } catch {
    console.error("✗ GitHub rename failed — local config was still updated.");
    console.error(`  Run manually: gh repo rename ${newSlug} --repo ${config.repo}`);
    process.exit(1);
  }
} else {
  console.log(`\n  Local config only. To also rename the GitHub repo and Space:`);
  console.log(`    npm run rename -- ${newName} --apply-remote`);
}

console.log(`\n  Remaining manual steps:`);
console.log(`    · Python package: apps/agent/<slug>_agent is an IMPORT PATH, not`);
console.log(`      the product name, and this tool does not touch it. Renaming it`);
console.log(`      is a refactor across every import (ADR-0002 addendum).`);
console.log(`    · Hugging Face Space: rename in Space settings to ${newSlug}-agent`);
console.log(`    · Vercel project: rename in project settings to ${newSlug}`);
console.log(`    · Local directory: mv ${root} ${resolve(root, "..", newSlug)}`);
