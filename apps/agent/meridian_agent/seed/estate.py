"""The simulated production estate.

Topology is authored, not generated. A randomly wired dependency graph produces
service names that read plausibly and a shape that does not: real estates have
meaning in their edges, and incident causality is only interesting when the
topology is. What *is* generated is the dynamic part - telemetry and incidents -
which is seeded and reproducible.

Everything here is synthetic (SD-002). No name, team or topology is taken from
any real organisation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Literal

DependencyKind = Literal["sync", "async", "datastore"]


class Tier(IntEnum):
    """Blast radius, not importance.

    Tier 0 is on the customer's critical path right now. Tier 3 can be down for
    an hour before anyone outside the owning team notices.
    """

    CUSTOMER_CRITICAL = 0
    CUSTOMER_DEGRADING = 1
    INTERNAL = 2
    BATCH = 3


@dataclass(frozen=True, slots=True)
class Service:
    id: str
    name: str
    tier: Tier
    owner_team: str
    runtime: str
    region: str


@dataclass(frozen=True, slots=True)
class Dependency:
    upstream_id: str
    downstream_id: str
    kind: DependencyKind


class EstateError(ValueError):
    """The authored estate violates one of its own invariants."""


_SERVICES: tuple[Service, ...] = (
    # Customer critical path
    Service(
        "svc-edge-gateway",
        "edge-gateway",
        Tier.CUSTOMER_CRITICAL,
        "Platform Edge",
        "go1.23",
        "eu-west-1",
    ),
    Service(
        "svc-checkout-api",
        "checkout-api",
        Tier.CUSTOMER_CRITICAL,
        "Commerce",
        "java21",
        "eu-west-1",
    ),
    Service(
        "svc-payments-gateway",
        "payments-gateway",
        Tier.CUSTOMER_CRITICAL,
        "Payments",
        "java21",
        "eu-west-1",
    ),
    Service(
        "svc-identity",
        "identity-service",
        Tier.CUSTOMER_CRITICAL,
        "Identity",
        "go1.23",
        "eu-west-1",
    ),
    Service(
        "svc-catalog-api", "catalog-api", Tier.CUSTOMER_CRITICAL, "Commerce", "node20", "eu-west-1"
    ),
    # Degrades the experience, does not stop it
    Service(
        "svc-order-orchestrator",
        "order-orchestrator",
        Tier.CUSTOMER_DEGRADING,
        "Commerce",
        "java21",
        "eu-west-1",
    ),
    Service(
        "svc-inventory",
        "inventory-service",
        Tier.CUSTOMER_DEGRADING,
        "Supply",
        "go1.23",
        "eu-west-1",
    ),
    Service(
        "svc-pricing",
        "pricing-engine",
        Tier.CUSTOMER_DEGRADING,
        "Commerce",
        "rust1.82",
        "eu-west-1",
    ),
    Service(
        "svc-fraud-scoring",
        "fraud-scoring",
        Tier.CUSTOMER_DEGRADING,
        "Risk",
        "python3.12",
        "eu-west-1",
    ),
    Service(
        "svc-notifications",
        "notification-service",
        Tier.CUSTOMER_DEGRADING,
        "Growth",
        "node20",
        "eu-west-1",
    ),
    # Internal
    Service(
        "svc-search-indexer", "search-indexer", Tier.INTERNAL, "Commerce", "python3.12", "eu-west-1"
    ),
    Service(
        "svc-recommendations",
        "recommendation-service",
        Tier.INTERNAL,
        "Growth",
        "python3.12",
        "eu-west-1",
    ),
    Service("svc-config", "config-service", Tier.INTERNAL, "Platform Edge", "go1.23", "eu-west-1"),
    # Stateful dependencies
    Service(
        "svc-orders-db",
        "orders-db",
        Tier.CUSTOMER_CRITICAL,
        "Data Platform",
        "postgres16",
        "eu-west-1",
    ),
    Service(
        "svc-sessions-cache",
        "sessions-cache",
        Tier.CUSTOMER_CRITICAL,
        "Data Platform",
        "redis7",
        "eu-west-1",
    ),
    Service(
        "svc-events-bus",
        "events-bus",
        Tier.CUSTOMER_DEGRADING,
        "Data Platform",
        "kafka3.8",
        "eu-west-1",
    ),
    Service(
        "svc-catalog-search",
        "catalog-search",
        Tier.INTERNAL,
        "Data Platform",
        "opensearch2",
        "eu-west-1",
    ),
    # Batch
    Service(
        "svc-analytics-etl", "analytics-etl", Tier.BATCH, "Data Platform", "python3.12", "eu-west-1"
    ),
    Service(
        "svc-reporting-batch",
        "reporting-batch",
        Tier.BATCH,
        "Data Platform",
        "python3.12",
        "eu-west-1",
    ),
)

# upstream depends on downstream. Edges point in the direction a failure
# propagates: if `downstream_id` degrades, `upstream_id` feels it.
_DEPENDENCIES: tuple[Dependency, ...] = (
    Dependency("svc-edge-gateway", "svc-identity", "sync"),
    Dependency("svc-edge-gateway", "svc-checkout-api", "sync"),
    Dependency("svc-edge-gateway", "svc-catalog-api", "sync"),
    Dependency("svc-edge-gateway", "svc-config", "sync"),
    Dependency("svc-identity", "svc-sessions-cache", "datastore"),
    Dependency("svc-checkout-api", "svc-order-orchestrator", "sync"),
    Dependency("svc-checkout-api", "svc-pricing", "sync"),
    Dependency("svc-checkout-api", "svc-payments-gateway", "sync"),
    Dependency("svc-checkout-api", "svc-sessions-cache", "datastore"),
    Dependency("svc-payments-gateway", "svc-fraud-scoring", "sync"),
    Dependency("svc-payments-gateway", "svc-orders-db", "datastore"),
    Dependency("svc-order-orchestrator", "svc-inventory", "sync"),
    Dependency("svc-order-orchestrator", "svc-orders-db", "datastore"),
    Dependency("svc-order-orchestrator", "svc-events-bus", "async"),
    Dependency("svc-inventory", "svc-orders-db", "datastore"),
    Dependency("svc-pricing", "svc-config", "sync"),
    Dependency("svc-catalog-api", "svc-catalog-search", "sync"),
    Dependency("svc-catalog-api", "svc-pricing", "sync"),
    Dependency("svc-notifications", "svc-events-bus", "async"),
    Dependency("svc-search-indexer", "svc-events-bus", "async"),
    Dependency("svc-search-indexer", "svc-catalog-search", "datastore"),
    Dependency("svc-recommendations", "svc-events-bus", "async"),
    Dependency("svc-recommendations", "svc-catalog-search", "datastore"),
    Dependency("svc-fraud-scoring", "svc-orders-db", "datastore"),
    Dependency("svc-analytics-etl", "svc-events-bus", "async"),
    Dependency("svc-analytics-etl", "svc-orders-db", "datastore"),
    Dependency("svc-reporting-batch", "svc-analytics-etl", "async"),
)


def services() -> tuple[Service, ...]:
    return _SERVICES


def dependencies() -> tuple[Dependency, ...]:
    return _DEPENDENCIES


def service_by_id(service_id: str) -> Service:
    for service in _SERVICES:
        if service.id == service_id:
            return service
    raise KeyError(service_id)


def downstream_of(service_id: str) -> tuple[str, ...]:
    """What this service depends on, directly."""
    return tuple(d.downstream_id for d in _DEPENDENCIES if d.upstream_id == service_id)


def upstream_of(service_id: str) -> tuple[str, ...]:
    """What directly depends on this service."""
    return tuple(d.upstream_id for d in _DEPENDENCIES if d.downstream_id == service_id)


def blast_radius(service_id: str) -> tuple[str, ...]:
    """Every service transitively affected if `service_id` degrades.

    Returned in deterministic order (breadth-first, then sorted) so a triage
    narrative reads the same way every time it is regenerated.
    """
    if service_id not in {s.id for s in _SERVICES}:
        raise KeyError(service_id)

    seen: set[str] = set()
    frontier = [service_id]
    while frontier:
        current = frontier.pop(0)
        for parent in sorted(upstream_of(current)):
            if parent not in seen:
                seen.add(parent)
                frontier.append(parent)
    return tuple(sorted(seen))


def validate() -> None:
    """Assert the authored estate's invariants.

    Called by a test rather than at import time: an invalid estate should fail
    the build loudly, not fail every import in a confusing place.
    """
    ids = [s.id for s in _SERVICES]
    if len(ids) != len(set(ids)):
        raise EstateError("duplicate service id")

    names = [s.name for s in _SERVICES]
    if len(names) != len(set(names)):
        raise EstateError("duplicate service name")

    known = set(ids)
    for dep in _DEPENDENCIES:
        if dep.upstream_id not in known:
            raise EstateError(f"dependency references unknown upstream {dep.upstream_id}")
        if dep.downstream_id not in known:
            raise EstateError(f"dependency references unknown downstream {dep.downstream_id}")
        if dep.upstream_id == dep.downstream_id:
            raise EstateError(f"self-dependency on {dep.upstream_id}")

    edges = {(d.upstream_id, d.downstream_id) for d in _DEPENDENCIES}
    if len(edges) != len(_DEPENDENCIES):
        raise EstateError("duplicate dependency edge")

    _assert_acyclic()


def _assert_acyclic() -> None:
    """A cycle would make 'the upstream cause' undefined.

    Real estates do contain cycles. This one is authored not to, because the
    triage narrative depends on causality having a direction, and a synthetic
    estate that makes its own reasoning ambiguous is a worse teaching object.
    """
    colour: dict[str, int] = {}  # 0 = visiting, 1 = done

    def visit(node: str, path: list[str]) -> None:
        state = colour.get(node)
        if state == 1:
            return
        if state == 0:
            cycle = " -> ".join([*path[path.index(node) :], node])
            raise EstateError(f"dependency cycle: {cycle}")
        colour[node] = 0
        for child in downstream_of(node):
            visit(child, [*path, node])
        colour[node] = 1

    for service in _SERVICES:
        visit(service.id, [])
