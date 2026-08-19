---
id: arch-estate-overview
kind: architecture
title: Estate overview and dependency topology
owner: Platform Edge
---

## Shape

Traffic enters through `edge-gateway`, which fans out to `identity-service`,
`checkout-api` and `catalog-api`. Checkout depends synchronously on
`order-orchestrator`, `pricing-engine` and `payments-gateway`. Everything
transactional terminates at `orders-db`; everything session-scoped terminates at
`sessions-cache`.

Asynchronous work flows through `events-bus`. `notification-service`,
`search-indexer`, `recommendation-service` and `analytics-etl` all consume from
it and none of them are on the synchronous request path.

## Tiering

Tier 0 covers `edge-gateway`, `checkout-api`, `payments-gateway`,
`identity-service`, `catalog-api`, `orders-db` and `sessions-cache`. Tier 1
covers `order-orchestrator`, `inventory-service`, `pricing-engine`,
`fraud-scoring`, `notification-service` and `events-bus`. Tier 2 covers
`search-indexer`, `recommendation-service`, `config-service` and
`catalog-search`. Tier 3 covers `analytics-etl` and `reporting-batch`.

Tier is blast radius, not importance. A Tier 3 service can be more valuable to
the business and still be Tier 3, because nobody outside its owning team notices
within the hour.

## Why the graph is acyclic

The dependency graph is maintained without cycles so that "the upstream cause"
of an incident is always well defined. A cycle makes causality ambiguous exactly
when it matters most, which is during triage. Introducing one requires
architecture review.

## Failure propagation

Synchronous edges propagate failure in seconds. Asynchronous edges propagate
staleness over minutes and rarely propagate failure at all — a consumer falling
behind does not error, which is why lag needs its own alerting rather than
relying on error rate.

Datastore edges propagate saturation. A datastore at its connection ceiling fails
every caller at once, which is why simultaneous onset across unrelated services
points at a shared datastore rather than at a cascade.
