# Sprint 6 — Experience

**Sprint goal:** Make the front door earn the engineering behind it. A first-time
visitor should read the landing surface as a product, not a portfolio page, and
should reach the console without being told to.

**Opened:** 2026-08-21 · **Release target:** 0.6.0 · **Gate:** Design Review + UAT

> **Backfilled.** This plan was written after the sprint's work had already
> shipped, and says so rather than being dated to look otherwise. The charter
> names Sprint Planning as the ceremony that opens a sprint; it did not happen
> here. The work went out under a sprint number that existed only in the defect
> log — a claim with no artifact behind it, which is the same failure the
> traceability gate was built to stop, committed against the process rather than
> the requirements. Recorded as D-016.

## Why this sprint exists

Sprints 0–5 produced a runtime that refuses well and a console that streams. Both
are invisible. Every judgement a first-time visitor makes happens before either
runs, and a landing page that looks like a template invites the reader to assume
the rest is one too.

The constraint that shapes the whole sprint: **no paid asset, no CDN, no
motion library.** Zero infrastructure cost (NFR-002) is not suspended for
aesthetics.

## Sprint backlog

| ID | Story | Pts | Acceptance |
|---|---|---|---|
| S6-HERO | Scroll-scrubbed hero from stock footage | 8 | ≤2.5MB and ≤4s of video; one seek per animation frame |
| S6-MOTION | Motion system in design tokens, not ad-hoc transitions | 5 | Three durations, one easing family, all in `globals.css` |
| S6-MEDIA | Reproducible media pipeline | 5 | `fetch-media.mjs` re-derives every asset from a Pexels id; credits committed |
| S6-A11Y | Reduced motion and small screens lose nothing | 5 | Poster REPLACES video; no content reachable only by animating |
| S6-COPY | Landing copy states the product, not the author | 3 | No first person; no "portfolio"; the refusal claim is the lede |
| S6-NAV | Every surface reachable from every surface | 2 | Sticky nav, keyboard reachable, visible focus |

**Committed: 28 points.** Demonstrated velocity: 41, 36, 40, 36, 39.
Deliberately below trend — this sprint is judgement-heavy and its work does not
decompose into parallel tasks the way the runtime sprints did.

## Definition of Done additions

7. A visual claim is demonstrated at two viewport widths and under
   `prefers-reduced-motion`, not asserted.
8. Any third-party asset carries its licence and attribution in the repository.

## Explicitly out of scope

The proof surfaces. `/delivery` exists from Sprint 5 and `/reliability` and
`/architecture` belong to Sprint 7. Building them here would mean building them
before the evidence they present is stable.

## Impediments

### IMP-07 — the video budget and the visual are in direct tension

A scroll-scrubbed hero wants a long, high-bitrate clip; the budget wants neither.
Resolved by treating the budget as the requirement and the clip as the variable:
4 seconds at CRF 26, scaled to 1920, transcoded locally. Result 0.90MB against a
2.5MB ceiling.
