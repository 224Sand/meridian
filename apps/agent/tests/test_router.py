"""Router failover, disabling and re-enablement.

Every test uses a ManualClock. No test sleeps, and no test makes a live model
call. The behaviours asserted here - a rate limit expiring, a quota exhaustion
persisting, a cascade of failures ending in a closed failure rather than a
fabricated answer - are exactly the ones that are impossible to exercise against
a real provider on demand.
"""

from __future__ import annotations

import pytest

from sandscope_agent.router.providers import (
    Message,
    ProviderUnavailableError,
    QuotaExhaustedError,
    RateLimitError,
    StubProvider,
    TransportError,
)
from sandscope_agent.router.router import (
    MAX_CONSECUTIVE_RATE_LIMITS,
    RATE_LIMIT_TTL_SECONDS,
    AllProvidersUnavailableError,
    Router,
    RouterEvent,
)
from sandscope_agent.router.state import ManualClock, RouterState

PROMPT = [Message("user", "why is the pool exhausted")]


def build(*providers: StubProvider, environment: str = "production"):
    clock = ManualClock()
    events: list[RouterEvent] = []
    router = Router(
        providers=list(providers),
        state=RouterState(),
        clock=clock,
        environment=environment,
        on_event=events.append,
    )
    return router, clock, events


class TestOrdering:
    def test_first_available_provider_serves(self) -> None:
        a, b = StubProvider("a"), StubProvider("b")
        router, _, _ = build(a, b)
        result = router.complete(PROMPT)
        assert result.provider == "a"
        assert b.calls == 0
        assert not result.failed_over

    def test_order_is_fixed_not_emergent(self) -> None:
        """Two identical requests must take the same path."""
        router, _, _ = build(StubProvider("a"), StubProvider("b"))
        assert router.complete(PROMPT).provider == router.complete(PROMPT).provider

    def test_failover_reaches_the_next_provider(self) -> None:
        a = StubProvider("a", responses=[TransportError("connection reset")])
        b = StubProvider("b")
        router, _, _ = build(a, b)
        result = router.complete(PROMPT)
        assert result.provider == "b"
        assert result.attempts == ("a", "b")
        assert result.failed_over

    def test_workflow_completes_when_first_provider_fails(self) -> None:
        """BR-003 / FR-011: the headline resilience claim."""
        a = StubProvider("a", default=RateLimitError("429"))
        b = StubProvider("b", default="the pool is exhausted because hold time rose")
        router, _, _ = build(a, b)
        assert "hold time" in router.complete(PROMPT).completion.text


class TestRateLimiting:
    def test_a_single_rate_limit_does_not_disable(self) -> None:
        a = StubProvider("a", responses=[RateLimitError("429")])
        router, _, _ = build(a, StubProvider("b"))
        router.complete(PROMPT)
        assert router.state.disabled == {}, "one 429 must not write off a provider"

    def test_provider_is_disabled_after_the_consecutive_ceiling(self) -> None:
        a = StubProvider("a", default=RateLimitError("429"))
        router, _, _ = build(a, StubProvider("b"))
        for _ in range(MAX_CONSECUTIVE_RATE_LIMITS):
            router.complete(PROMPT)
        assert "a" in router.state.disabled
        assert router.state.disabled["a"].reason == "rate_limited"

    def test_a_success_resets_the_consecutive_count(self) -> None:
        # A fallback is required: with one provider the first call has nothing
        # to fail over to and raises before a second call can succeed.
        a = StubProvider("a", responses=[RateLimitError("429"), "recovered"])
        router, _, _ = build(a, StubProvider("b"))
        router.complete(PROMPT)
        assert router.state.consecutive_429["a"] == 1
        assert router.complete(PROMPT).provider == "a"
        assert router.state.consecutive_429.get("a") is None

    def test_disabled_provider_is_reenabled_after_the_ttl(self) -> None:
        """The behaviour the original could not test without sleeping 10 minutes."""
        a = StubProvider("a", default=RateLimitError("429"))
        router, clock, _ = build(a, StubProvider("b"))
        for _ in range(MAX_CONSECUTIVE_RATE_LIMITS):
            router.complete(PROMPT)
        assert router.state.is_disabled("a", clock.now())

        clock.advance(RATE_LIMIT_TTL_SECONDS - 1)
        assert router.state.is_disabled("a", clock.now()), "must still be disabled 1s early"

        clock.advance(2)
        assert not router.state.is_disabled("a", clock.now()), "must re-enable after the TTL"

    def test_retry_after_overrides_the_default_ttl(self) -> None:
        a = StubProvider("a", default=RateLimitError("429", retry_after=30.0))
        router, clock, _ = build(a, StubProvider("b"))
        for _ in range(MAX_CONSECUTIVE_RATE_LIMITS):
            router.complete(PROMPT)
        clock.advance(31)
        assert not router.state.is_disabled("a", clock.now())


class TestQuotaExhaustion:
    def test_quota_exhaustion_disables_permanently(self) -> None:
        """Distinguished from a 429: waiting will never help."""
        a = StubProvider("a", default=QuotaExhaustedError("credit balance is zero"))
        router, clock, _ = build(a, StubProvider("b"))
        router.complete(PROMPT)
        assert router.state.disabled["a"].expires_at is None

        clock.advance(86_400)
        assert router.state.is_disabled("a", clock.now()), "a day later it must still be disabled"

    def test_quota_exhaustion_is_not_retried(self) -> None:
        a = StubProvider("a", default=QuotaExhaustedError("zero balance"))
        router, _, _ = build(a, StubProvider("b"))
        router.complete(PROMPT)
        router.complete(PROMPT)
        assert a.calls == 1, "a provider with no quota must not be called again"


class TestEnvironmentAvailability:
    def test_local_only_provider_is_skipped_in_production(self) -> None:
        """R-06: claude_cli authenticates through a session a container lacks."""
        local_only = StubProvider("claude_cli", available_in=("local",))
        cloud = StubProvider("groq")
        router, _, _ = build(local_only, cloud, environment="production")
        result = router.complete(PROMPT)
        assert result.provider == "groq"
        assert local_only.calls == 0
        assert "claude_cli" not in result.attempts, "never a candidate, so never an attempt"

    def test_local_only_provider_serves_locally(self) -> None:
        local_only = StubProvider("claude_cli", available_in=("local",))
        router, _, _ = build(local_only, StubProvider("groq"), environment="local")
        assert router.complete(PROMPT).provider == "claude_cli"

    def test_status_reports_environment_unavailability_honestly(self) -> None:
        router, _, _ = build(
            StubProvider("claude_cli", available_in=("local",)), StubProvider("groq")
        )
        status = {s.name: s for s in router.status()}
        assert status["claude_cli"].available is False
        assert status["claude_cli"].disabled_reason == "unavailable_in_environment"
        assert "production" in status["claude_cli"].detail

    def test_provider_unavailable_error_disables_permanently(self) -> None:
        a = StubProvider("claude_cli", default=ProviderUnavailableError("no local session"))
        router, clock, _ = build(a, StubProvider("groq"))
        router.complete(PROMPT)
        clock.advance(86_400)
        assert router.state.is_disabled("claude_cli", clock.now())


class TestFailureInjection:
    def test_injection_forces_failover(self) -> None:
        router, _, _ = build(StubProvider("a"), StubProvider("b"))
        router.inject_failure("a")
        assert router.complete(PROMPT).provider == "b"

    def test_injection_expires(self) -> None:
        router, clock, _ = build(StubProvider("a"), StubProvider("b"))
        router.inject_failure("a", ttl_seconds=60)
        clock.advance(61)
        assert router.complete(PROMPT).provider == "a"

    def test_injection_is_scoped_to_this_router_instance(self) -> None:
        """T-6: one visitor must not be able to degrade the demo for another."""
        router_one, clock, _ = build(StubProvider("a"), StubProvider("b"))
        router_two = Router(
            providers=[StubProvider("a"), StubProvider("b")],
            state=RouterState(),
            clock=clock,
            environment="production",
        )
        router_one.inject_failure("a")
        assert router_one.complete(PROMPT).provider == "b"
        assert router_two.complete(PROMPT).provider == "a", "injection leaked across sessions"


class TestFailClosed:
    def test_all_providers_failing_raises_rather_than_fabricating(self) -> None:
        """F-2: there is no path that returns invented output when none answered."""
        router, _, _ = build(
            StubProvider("a", default=TransportError("down")),
            StubProvider("b", default=TransportError("down")),
        )
        with pytest.raises(AllProvidersUnavailableError) as caught:
            router.complete(PROMPT)
        assert caught.value.attempts == ("a", "b")

    def test_empty_provider_list_raises(self) -> None:
        router, _, _ = build()
        with pytest.raises(AllProvidersUnavailableError):
            router.complete(PROMPT)


class TestPacing:
    def test_minimum_gap_is_respected(self) -> None:
        a = StubProvider("a", min_call_gap_seconds=3.0)
        router, clock, _ = build(a)
        router.complete(PROMPT)
        before = clock.now()
        router.complete(PROMPT)
        assert clock.now() - before >= 3.0

    def test_no_wait_on_the_first_call(self) -> None:
        router, clock, _ = build(StubProvider("a", min_call_gap_seconds=30.0))
        before = clock.now()
        router.complete(PROMPT)
        assert clock.now() == before


class TestObservability:
    def test_success_emits_an_event_with_latency(self) -> None:
        router, _, events = build(StubProvider("a"))
        router.complete(PROMPT)
        assert [e.event for e in events] == ["success"]
        assert events[0].latency_ms is not None

    def test_failover_is_visible_in_the_event_stream(self) -> None:
        router, _, events = build(
            StubProvider("a", default=RateLimitError("429")), StubProvider("b")
        )
        router.complete(PROMPT)
        assert [e.event for e in events] == ["rate_limit", "success"]

    def test_status_lists_providers_in_routing_order(self) -> None:
        router, _, _ = build(StubProvider("a"), StubProvider("b"), StubProvider("c"))
        assert [s.name for s in router.status()] == ["a", "b", "c"]
