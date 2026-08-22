---
name: role-council
description: Runs a dynamic, cross-functional SDLC/PDLC review over a git repository's real history — infers which roles (BA, PM, TPM, Developer, QA, DevOps/SRE, AppSec, UX, Data/ML Engineer, Architect, Scrum Master, Stakeholder, Executive Sponsor, etc.) actually apply to THIS project, then produces grounded, citation-backed commentary from each relevant role on real defects, decisions, commits, or PRs — never invented opinions. Use whenever the user wants a project retrospective from multiple perspectives, a "council" or panel review of a PR/feature/decision, to see how different roles (dev/QA/PM/etc.) would react to something, a cross-functional post-mortem, or a role-based audit of a repository's history. Works on any git repository — not tied to one codebase or a fixed role list.
---

# Role Council

A council of role-grounded reviewers — Business Analyst, PM, TPM, Developer, QA, DevOps,
Security, whichever roles the *project itself* calls for — independently reacting to the same
real artifact, the way a real cross-functional team would. The value is in **genuine
disagreement**: a report where every role agrees about everything is not a review, it's a
rubber stamp with extra labels.

## When this earns its keep

- "how would QA and the BA react to this PR"
- "give me a retrospective of this project from every role's point of view"
- "run a council review on this decision / design / page"
- "what would each stakeholder say about this defect"
- "review the current state of the repo like a cross-functional team would"

Skip it for a single, narrow question with one obvious answer — the council is for artifacts
where different roles would reasonably see different things. Reviewing a typo fix through five
roles produces five copies of "looks fine," which is exactly the manufactured-consensus failure
mode this skill exists to avoid.

## The four steps

### 1. Determine the roster — don't assume it

Read the repository before picking roles. A CLI tool has no UX Designer. A pure infra repo has
no BA. An ML pipeline needs a role none of the others do. A roster that's the same eleven names
for a Python data-cleaning script and a consumer mobile app means this step was skipped.

Look at:

- Manifests (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`) — what kind of software
  this actually is
- Directory shape — `models/` or `notebooks/` → ML roles matter; `infra/` or
  `.github/workflows/` → DevOps/SRE matters; a `docs/` folder full of PRDs and BRDs → BA/PM
  already exist here as a practice, not a hypothetical
- Existing docs — if the repo already names roles (a `WAYS_OF_WORKING.md`, a CONTRIBUTING.md
  with a review process, `CODEOWNERS`), start from what it already declares rather than
  inventing a parallel roster that ignores the project's own governance

See `references/role-archetypes.md` for the library of role lenses and what each one
instinctively looks for. Pick the subset that's actually load-bearing for this project — five
relevant roles beat twelve where seven have nothing real to say about anything in the repo.

### 2. Mine real artifacts — never invent the disagreement

In priority order, look for:

1. A defect/issue log (`DEFECT_LOG.md`, `CHANGELOG.md`, an issue tracker export)
2. Decision records (ADRs, `docs/decisions/`, RFCs)
3. Sprint or retro documents, postmortems
4. Pull request review threads (`gh pr view --json reviews,comments` if `gh` is available and
   the repo has a GitHub remote)
5. If none of the above exist: `git log --stat` for commits with unusually large diffs, revert
   commits, or messages containing "fix" / "bug" / "broke" — these are where real friction
   happened even without a formal record of it

Every artifact reviewed needs a citation a reader can actually go check: a defect ID, a commit
SHA, a file path and line, a PR number. If a claim can't be cited, it isn't council material —
skip it rather than inventing texture to fill the section.

### 3. Get independent reactions, not a committee memo

The failure mode is one pass that writes "the BA would probably think X, and QA would probably
agree" — that's groupthink with role labels stapled on afterward. Instead:

**If subagents are available**, dispatch one per applicable role against the SAME artifact, with
no visibility into what the other roles produced. Give each one: the artifact, its citation, and
that role's one-paragraph brief from `references/role-archetypes.md`. Collect independently,
then assemble. This is the same blind-review discipline the `llm-council` skill uses to fight
sycophancy between models — applied here to SDLC roles reviewing a real project instead of
models answering a question.

**If running inline** (no subagent budget, or a lighter request), still write each role's
reaction as a genuinely separate pass — finish and commit one role's paragraph before starting
the next. Drafting all of them together is exactly where they start agreeing with each other by
osmosis.

A role is allowed to have nothing to say about a given artifact. Not every issue touches every
discipline, and "not something I'd weigh in on" from QA about a database-region decision is more
honest than a manufactured opinion stretched to fill a row.

### 4. Assemble the retrospective

Group by artifact, not by role — a reader wants to see one decision and every reaction to it
side by side, which is where real disagreement becomes visible.

```markdown
## [Artifact title] — [citation: D-004 / commit a1b2c3d / PR #42]

**What happened:** [one factual sentence, no role's opinion yet]

- **[Role]:** [reaction, grounded in what that role cares about, referencing the artifact]
- **[Role]:** [reaction]
- **[Role]:** [reaction — say explicitly whether it agrees with or diverges from the above]

**Where they diverged:** [one line — if they genuinely didn't diverge, say so rather than
inventing daylight between them]
```

Close with a short synthesis: which roles agreed most often (worth asking why — is one role just
deferring to another?), which artifact produced the sharpest disagreement, and what that
disagreement reveals about the project that a single-voice retrospective would have missed.

## What makes this fail

- **Inventing an opinion with no basis.** If the repo has no record of how QA felt about a
  decision, don't write one — cite what exists, or skip that role for that artifact.
- **Manufactured consensus.** If every role says "looks good," check whether the passes were
  actually independent, or whether they were drafted together and converged.
- **Manufactured conflict.** The opposite failure is just as fake — don't invent disagreement
  for drama. Real projects have real friction; find it in the artifacts rather than staging it.
- **A fixed role list.** Re-check step 1 if the roster looks identical across two very
  different repositories.
