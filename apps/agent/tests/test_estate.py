"""The authored estate must satisfy its own invariants.

These run offline and are fast, which matters: the estate is edited by hand, and
a hand-edited topology is exactly the thing that acquires a typo'd service id or
an accidental cycle during a later sprint.
"""

from __future__ import annotations

import pytest

from meridian_agent.seed import estate
from meridian_agent.seed.estate import EstateError, Tier


class TestInvariants:
    def test_authored_estate_is_valid(self) -> None:
        estate.validate()

    def test_every_service_has_a_unique_id_and_name(self) -> None:
        services = estate.services()
        assert len({s.id for s in services}) == len(services)
        assert len({s.name for s in services}) == len(services)

    def test_every_dependency_resolves_to_a_real_service(self) -> None:
        known = {s.id for s in estate.services()}
        for dep in estate.dependencies():
            assert dep.upstream_id in known
            assert dep.downstream_id in known

    def test_dependency_graph_is_acyclic(self) -> None:
        # validate() raises on a cycle; this names the property explicitly so a
        # failure reads as "you introduced a cycle" rather than "estate invalid".
        estate.validate()

    def test_estate_has_services_at_every_tier(self) -> None:
        tiers = {s.tier for s in estate.services()}
        assert tiers == set(Tier)

    def test_cycle_is_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The acyclicity check must actually be capable of failing."""
        from meridian_agent.seed.estate import Dependency

        cyclic = (
            *estate.dependencies(),
            Dependency("svc-orders-db", "svc-edge-gateway", "sync"),
        )
        monkeypatch.setattr(estate, "_DEPENDENCIES", cyclic)
        with pytest.raises(EstateError, match="cycle"):
            estate.validate()

    def test_dangling_dependency_is_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from meridian_agent.seed.estate import Dependency

        broken = (*estate.dependencies(), Dependency("svc-edge-gateway", "svc-nope", "sync"))
        monkeypatch.setattr(estate, "_DEPENDENCIES", broken)
        with pytest.raises(EstateError, match="unknown downstream"):
            estate.validate()


class TestTopologyQueries:
    def test_downstream_of_checkout(self) -> None:
        assert set(estate.downstream_of("svc-checkout-api")) == {
            "svc-order-orchestrator",
            "svc-pricing",
            "svc-payments-gateway",
            "svc-sessions-cache",
        }

    def test_upstream_of_orders_db_includes_every_direct_consumer(self) -> None:
        assert set(estate.upstream_of("svc-orders-db")) == {
            "svc-payments-gateway",
            "svc-order-orchestrator",
            "svc-inventory",
            "svc-fraud-scoring",
            "svc-analytics-etl",
        }

    def test_blast_radius_is_transitive(self) -> None:
        """A datastore failure must reach the edge, not stop at its neighbours."""
        radius = estate.blast_radius("svc-orders-db")
        assert "svc-checkout-api" in radius, "transitive path through order-orchestrator missing"
        assert "svc-edge-gateway" in radius, "failure must reach the customer-facing edge"

    def test_blast_radius_of_a_leaf_consumer_is_empty(self) -> None:
        assert estate.blast_radius("svc-reporting-batch") == ()

    def test_blast_radius_is_deterministic(self) -> None:
        assert estate.blast_radius("svc-events-bus") == estate.blast_radius("svc-events-bus")

    def test_blast_radius_is_sorted(self) -> None:
        radius = estate.blast_radius("svc-orders-db")
        assert list(radius) == sorted(radius)

    def test_unknown_service_raises(self) -> None:
        with pytest.raises(KeyError):
            estate.blast_radius("svc-does-not-exist")

    def test_service_lookup(self) -> None:
        assert estate.service_by_id("svc-payments-gateway").owner_team == "Payments"
        with pytest.raises(KeyError):
            estate.service_by_id("svc-missing")
