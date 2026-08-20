# ADR-0002 — The product name is build-time configuration, not source

**Status:** Accepted · **Date:** 2026-08-20 · **Deciders:** Solutions Architect, Product Owner (FR-001)

## Context
The Product Owner requires the ability to change the product name late without a
refactor. A name hardcoded across components, metadata, manifests and asset
filenames turns a rename into a risky find-and-replace across the tree.

## Decision
`product.config.json` is the only file in which the product name is authored.
Every consumer reads it at build time. `scripts/rename.mjs` performs the rename
as a data edit and derives slug, wordmark, repository name and hostnames from it.
`scripts/check-config.mjs` fails the build if the derived slug ever drifts from
the name.

## Consequences
**Positive.** A rename is one command and a validated data change. The invariant
is enforced by a gate rather than by discipline.

**Negative.** No component may write the name as a literal, including in tests
and copy. This is a rule people forget, so the secret-scanning pass will be
extended to flag hardcoded occurrences once the name is final.

**Deliberately not automated.** The remote repository rename is opt-in
(`--apply-remote`). Changing a public URL as a side effect of a build script is
not acceptable behaviour for a build script.

---

## Addendum, 2026-08-20 — what the first real rename exposed

The Product Owner chose **SandScope**. `npm run rename -- SandScope` did exactly
what this ADR promised: one command updated the name, slug, wordmark, repository
name and both hostnames, and the schema gate verified the slug was still derived
from the name.

Then an audit found 188 further occurrences of the old name, and **173 of them
were `meridian_agent`** — the Python package.

**This ADR conflated two identities.** They are not the same thing and do not
change for the same reasons:

| | Product name | Package identifier |
|---|---|---|
| What it is | Wordmark, domain, repository, page titles | An import path |
| Who sees it | Everyone | Anyone reading the code |
| Changes when | Branding changes | Almost never |
| Cost to change | One data edit | Every import statement |

The rename tool correctly owned the first and silently ignored the second, so
"the name is authored in exactly one place" was true of the half the tool
covered and false of the half it did not.

### What was done

The package was renamed `meridian_agent` → `sandscope_agent` across 173 import
statements. It is a mechanical change and the full suite passed unchanged
afterwards, which is the only reason it was worth doing rather than living with
a package named after a discarded product.

Environment variables (`MERIDIAN_ENV`, `MERIDIAN_ALLOW_DESTRUCTIVE_TESTS`) and
the CI database credentials carried the same problem and were renamed with it.

### What was deliberately not renamed

`sandscope_agent/retrieval/reranker/vocab.txt` and `tokenizer.json` contain
"meridian" as an ordinary English word in a BERT vocabulary. A blind
find-and-replace would have corrupted a trained tokenizer to fix a false
positive.

### The correction to this ADR

The claim is narrowed to what is true: **the product name is authored in exactly
one place.** The package identifier is a separate decision with a separate cost,
it is expected to change approximately never, and renaming it is a refactor
rather than a configuration change.

`scripts/rename.mjs` now prints the package rename as a remaining manual step
rather than implying the job is done when it returns.
