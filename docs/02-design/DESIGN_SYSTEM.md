# Design System

**Author:** UX/UI Designer · **Date:** 2026-08-20 · **Satisfies:** DR-001

> The UX/UI Designer role produced nothing for five sprints while DR-001 —
> *"visual quality must meet the standard of apple.com product pages"* — sat in
> the requirements unexamined. That is the gap this document closes, and it
> should have been opened in Sprint 0 alongside the tech spec.

---

## 1. What the reference standard actually is

DR-001 names apple.com product pages. The instinct is to copy the *look*: black
background, large type, full-bleed imagery. That is the least transferable part.

What actually makes those pages work:

**Motion is scroll-driven, not autoplay.** The reader controls the pace. Nothing
happens on a timer, so nothing is missed by looking away.

**One idea per viewport.** Each pinned section makes exactly one claim, and the
next does not begin until the first has landed.

**Type carries the hierarchy, not colour.** Weight, size and spacing do the work.
Colour is reserved for meaning — which, for this product, means status.

**The technique is video and CSS, not a framework.** Scroll-scrubbed `<video>`,
`position: sticky`, `IntersectionObserver`. Near-zero JavaScript on the hot path,
which is also what NFR-003 requires.

**The honest divergence:** Apple is selling an object and can show it. This
product's subject is a *process* — evidence, refusal, governance. Photography of
a data centre would be decoration standing in for substance. So the hero of each
scene is **the system's own output**: a real trace, a real citation, a real
refusal. Stock footage is atmosphere at the edges, never the subject.

## 2. Colour

Black canvas, as specified. The palette is deliberately small: a product with
seven accent colours is a product where colour means nothing.

| Token | Value | Meaning |
|---|---|---|
| `--ground` | `#000000` | Page. True black, not near-black — the reference standard is specific about this and screens differ. |
| `--surface` | `#0B0B0D` | Raised panels |
| `--surface-2` | `#141417` | Nested panels, table rows |
| `--line` | `#26262B` | Hairlines. Never a border heavier than 1px. |
| `--text` | `#F5F5F7` | Primary |
| `--text-2` | `#A1A1A8` | Secondary |
| `--text-3` | `#6E6E76` | Tertiary, metadata |
| `--grounded` | `#3FB950` | A cited claim, a passing check |
| `--refused` | `#D29922` | A refusal, a warning, the probe suite |
| `--blocked` | `#F85149` | Awaiting approval, a failure |
| `--accent` | `#4C8DFF` | Interactive only. Never decorative. |

**Status colour is the only colour with meaning**, and the three states map
exactly to the product's three outcomes: grounded, refused, blocked. A reader who
learns those three colours can read any screen.

Contrast: every text token meets WCAG AA on its intended ground. `--text-3` on
`--surface-2` is 4.6:1 and is used only for metadata that is never the sole
carrier of information.

## 3. Type

One family. `ui-sans-serif, -apple-system, "SF Pro Text", "Inter", system-ui` —
the system stack renders natively on the reader's platform and costs zero bytes.
A webfont for a page this type-heavy would cost more than it returns.

Monospace for anything the system produced: `ui-monospace, "SF Mono", "JetBrains
Mono", monospace`. **Machine output is always monospace.** A reader should be
able to tell prose from evidence without reading either.

| Role | Size | Weight | Tracking | Leading |
|---|---|---|---|---|
| Display | `clamp(2.75rem, 7vw, 6.5rem)` | 600 | `-0.045em` | 0.95 |
| Headline | `clamp(1.75rem, 3.5vw, 3rem)` | 600 | `-0.03em` | 1.1 |
| Title | `1.25rem` | 590 | `-0.01em` | 1.3 |
| Body | `1.0625rem` | 400 | `0` | 1.55 |
| Caption | `0.8125rem` | 450 | `0.01em` | 1.4 |
| Mono | `0.875rem` | 400 | `0` | 1.6 |

Negative tracking on large sizes and none on body. Display type set at default
tracking is the single most common tell of a page that was not designed.

## 4. Space

A 4px base, used as `4 · 8 · 12 · 16 · 24 · 32 · 48 · 64 · 96 · 128`. Nothing
between. Arbitrary values are how a layout stops having rhythm.

Section rhythm: `96px` on mobile, `128px` above 768px. Panels: `24px` internal.
Measure capped at `68ch` for body prose.

## 5. Motion

### Principles

**Motion explains or it does not happen.** Every animation in this product either
shows causality (a signal propagating from one service to its dependents), state
change (a claim gaining a citation), or progress (a node completing). Decorative
motion is rejected at review.

**The reader sets the pace.** Scroll-driven, never timed. A visitor who stops
scrolling stops the animation.

**Nothing is reachable only by animating.** AC-C10. Content is present in the DOM
and legible with animation removed; motion changes emphasis, never availability.

### Tokens

| Token | Duration | Curve | Used for |
|---|---|---|---|
| `--t-instant` | 100ms | `linear` | Hover, focus |
| `--t-quick` | 200ms | `cubic-bezier(0.4, 0, 0.2, 1)` | State change, toggles |
| `--t-considered` | 420ms | `cubic-bezier(0.16, 1, 0.3, 1)` | Panel entry, scene transitions |
| `--t-scrub` | — | scroll-linked | Video scrub, pinned scenes |

The `considered` curve decelerates hard — it settles rather than arrives, which
is what makes the reference standard feel unhurried.

### Scroll-scrubbed video

Encoded as H.264, 1920×1080, 30fps, **under 4 seconds per scene, under 2.5 MB**.
A budget, enforced in CI: a scene that exceeds it does not merge.

Requirements that are not negotiable:
- `preload="auto"`, `muted`, `playsInline`, no `autoplay`
- Keyframe every 6 frames, or seeking stutters
- A poster frame that is meaningful on its own
- **Below 768px, or under reduced motion, the poster frame replaces the video
  entirely.** Scrubbing a video on a phone spends the user's data to produce a
  worse experience than the still.

### Reduced motion

`@media (prefers-reduced-motion: reduce)` is not an afterthought path. Under it:
scrubbed video becomes its poster, pinned sections become ordinary stacked
sections, transitions collapse to `--t-instant`, and **nothing is hidden**.

## 6. Components

**Evidence panel.** Monospace, `--surface-2`, hairline left border in
`--grounded`. Each citation is a button, not a link — it reveals the passage
in place rather than navigating away, because a reader checking a citation has
not finished reading the claim.

**Verdict chip.** The three states, in their colours, with the score. Always
carries a text label as well as a colour: colour alone fails for the ~8% of men
with a colour-vision deficiency, and this is status information.

**Trace waterfall.** Rows are spans, width is duration, indentation is
parentage. Provider hops and cache outcomes are annotations on the row, not a
separate view — the question "why did that take 900ms" is answered in one place
or it is not answered.

**Approval block.** `--blocked`, full-width, the proposed action verbatim, and
two buttons of equal visual weight. **Approve is not the primary action.** A
gate where one choice is styled as the obvious one is not a gate.

## 7. What this system deliberately does not have

No shadow scale — hairlines and surface levels carry elevation. No border radius
above 12px. No gradient except the single page-edge vignette. No icon set beyond
what status requires. No dark/light toggle: the product is one thing.

Every omission is one fewer decision per screen, and the reference standard's
real lesson is restraint rather than polish.
