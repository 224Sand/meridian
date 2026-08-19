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
