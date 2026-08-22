# role-council

A Claude Code / Claude Agent skill that runs a cross-functional SDLC/PDLC review over a git
repository's real history. Given a repo, it works out which delivery and stakeholder roles
actually apply to *that* project — not a fixed list — mines its real artifacts (defect logs,
ADRs, sprint retros, PR reviews, or plain commit history if nothing more formal exists), and
produces independent, citation-grounded commentary from each relevant role on the same real
decisions and defects.

It exists because a retrospective where every role agrees on everything isn't a review — it's a
rubber stamp with labels on it. The point is to surface real, sourced disagreement the way a
real cross-functional team would generate it: a developer calling something clean, QA approving
it on visual grounds, a BA flagging it against the actual requirement, a TPM asking whether the
numbers on the page even make sense — four lenses on one artifact, each grounded in what that
role is actually responsible for.

## Origin

Built inside [SandScope](https://github.com/224Sand/sandscope), an agent-reliability platform
whose entire development process is run under a named-role charter
(`docs/00-governance/WAYS_OF_WORKING.md`). Partway through that project it became clear the
review discipline the charter described — a defect reaching a QA reaction, a BA reaction, a TPM
reaction, on the record — was worth extracting into something reusable on any repository, not
just this one. `docs/00-governance/COUNCIL_RETROSPECTIVE.md` in that repo is this skill's first
real output, run against SandScope's own history.

## Using it elsewhere

This directory is the whole skill — copy it into `.claude/skills/role-council/` (or wherever
your tooling looks for skills) in any other repository, or point a Claude Code session at this
path directly. It has no dependency on SandScope; `SKILL.md` and
`references/role-archetypes.md` are self-contained.

It works best on a repo with *some* real history to mine — a defect log, ADRs, closed PRs with
review comments, or at minimum a commit history with real fixes in it. A brand-new repo with one
commit has nothing for the council to react to yet.

## License

MIT. Fork it, change the role library, point it at your own project.
