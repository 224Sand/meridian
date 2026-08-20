---
id: pm-2026-04-pricing-config-rollout
kind: postmortem
title: "Pricing rounding change applied to all regions at once"
date: 2026-04-08
severity: 2
---

## Summary

A rounding-behaviour change in pricing-engine was classified Low because it
touched no service boundary and changed nine lines. It was applied to all
regions simultaneously and produced incorrect totals on multi-item baskets for
41 minutes.

## Impact

Incorrect displayed totals on baskets of four or more items. 2,300 affected
sessions. No incorrect charges were taken: checkout recomputes at capture, and
the discrepancy surfaced as a mismatch that blocked capture rather than as a
wrong charge.

## Timeline

- **11:02** Change deployed to all regions.
- **11:09** Capture mismatch rate rises. Alert fires on the mismatch metric, not
  on anything in pricing-engine.
- **11:23** Correlated to the pricing deploy by change marker.
- **11:31** Rolled back.
- **11:43** Mismatch rate returns to baseline.

## Root cause

The change altered rounding from per-line to per-basket. On a single-item
basket the two are identical, which is what every test fixture used.

## Why the classification was wrong

The change was classified on its diff size. Nine lines, one file, no interface
change. Blast radius was never assessed: pricing-engine is on the synchronous
checkout path and every basket in every region flows through it.

`pol-change-risk-classification` now classifies on blast radius and
reversibility rather than on size or author confidence, and this incident is the
reason.

## Corrective actions

1. Risk classification rewritten to use blast radius, not diff size. **Done.**
2. Regional staged rollout mandatory for Tier 0 and Tier 1 path changes. **Done.**
3. Pricing test fixtures extended to multi-item baskets. **Done.**

## What we deliberately did not change

We did not add an approval requirement for all pricing changes. The failure was
a wrong classification, not a missing approver, and adding approvers to
correctly-classified low-risk changes buys nothing but latency.
