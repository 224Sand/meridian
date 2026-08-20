"""The deterministic router.

Providers are attempted in a fixed order. The order is a configuration value,
not an emergent property of latency or luck: two identical requests take the
same path, which is what makes a trace worth reading and a failure worth
reproducing.

Everything that decides routing is explicit - the order, the clock, the state,
the environment. Nothing here reads a module global or the wall clock.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from sandscope_agent.router.providers import (
    Completion,
    Message,
    ModelTier,
    Provider,
    ProviderUnavailableError,
    QuotaExhaustedError,
    RateLimitError,
    TransportError,
)
from sandscope_agent.router.state import (
    INJECTED,
    QUOTA_EXHAUSTED,
    RATE_LIMITED,
    TRANSPORT_ERROR,
    UNAVAILABLE_IN_ENVIRONMENT,
    Clock,
    RouterState,
    SystemClock,
)

#: A 429 is transient, so the disable expires. Ten minutes is long enough that a
#: burst does not immediately re-trigger, and short enough that a provider is not
#: written off for the rest of a run.
RATE_LIMIT_TTL_SECONDS = 600.0
#: A transport failure is more likely to be brief than a rate limit.
TRANSPORT_TTL_SECONDS = 60.0
#: Consecutive 429s tolerated before the provider is disabled rather than retried.
MAX_CONSECUTIVE_RATE_LIMITS = 8


@dataclass(frozen=True, slots=True)
class RouterEvent:
    provider: str
    event: str
    detail: str = ""
    latency_ms: int | None = None


@dataclass(frozen=True, slots=True)
class RouterResult:
    completion: Completion
    provider: str
    attempts: tuple[str, ...]

    @property
    def failed_over(self) -> bool:
        return len(self.attempts) > 1


class AllProvidersUnavailableError(RuntimeError):
    """Every provider was skipped or failed.

    The run fails closed. There is no path here that returns fabricated output
    when no model answered (TECH_SPEC failure mode F-2).
    """

    def __init__(self, attempts: Sequence[str]) -> None:
        super().__init__(
            "no provider could serve the request; attempted: "
            + (", ".join(attempts) if attempts else "none")
        )
        self.attempts = tuple(attempts)


@dataclass(slots=True)
class ProviderStatus:
    name: str
    available: bool
    disabled_reason: str | None
    disabled_until: float | None
    detail: str


@dataclass(slots=True)
class Router:
    providers: list[Provider]
    state: RouterState = field(default_factory=RouterState)
    clock: Clock = field(default_factory=SystemClock)
    environment: str = "production"
    on_event: Callable[[RouterEvent], None] | None = None

    def _emit(self, event: RouterEvent) -> None:
        if self.on_event is not None:
            self.on_event(event)

    def _respect_pacing(self, provider: Provider) -> None:
        """Wait out the provider's minimum inter-call gap.

        Under a manual clock this advances time rather than blocking, so the
        arithmetic is exercised in tests without any test taking longer than a
        millisecond.
        """
        gap = provider.min_call_gap_seconds
        if gap <= 0:
            return
        last = self.state.last_call_at.get(provider.name)
        if last is None:
            return
        remaining = gap - (self.clock.now() - last)
        if remaining > 0:
            self.clock.sleep(remaining)

    def inject_failure(self, provider_name: str, *, ttl_seconds: float = 120.0) -> None:
        """Force a provider to be treated as failed (FR-011).

        Session scoping is enforced by the caller holding a per-session Router,
        not here: a visitor must never be able to degrade the demonstration for
        anyone else (THREAT_MODEL T-6).
        """
        self.state.disable(
            provider_name,
            INJECTED,
            now=self.clock.now(),
            ttl_seconds=ttl_seconds,
            detail="failure injected by request",
        )
        self._emit(RouterEvent(provider_name, "injected_failure"))

    def status(self) -> list[ProviderStatus]:
        """Live provider health, in routing order."""
        now = self.clock.now()
        statuses: list[ProviderStatus] = []
        for provider in self.providers:
            if not provider.is_available(self.environment):
                statuses.append(
                    ProviderStatus(
                        provider.name,
                        False,
                        str(UNAVAILABLE_IN_ENVIRONMENT),
                        None,
                        f"not available in environment '{self.environment}'",
                    )
                )
                continue
            disablement = self.state.disabled.get(provider.name)
            if disablement is not None and disablement.is_active(now):
                statuses.append(
                    ProviderStatus(
                        provider.name,
                        False,
                        str(disablement.reason),
                        disablement.expires_at,
                        disablement.detail,
                    )
                )
                continue
            statuses.append(ProviderStatus(provider.name, True, None, None, ""))
        return statuses

    def complete(
        self,
        messages: Sequence[Message],
        *,
        tier: ModelTier = "fast",
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> RouterResult:
        attempts: list[str] = []

        for provider in self.providers:
            now = self.clock.now()

            if not provider.is_available(self.environment):
                # Not an attempt: it was never a candidate in this environment.
                continue
            if self.state.is_disabled(provider.name, now):
                continue

            attempts.append(provider.name)
            self._respect_pacing(provider)

            started = self.clock.now()
            try:
                completion = provider.complete(
                    messages, tier=tier, max_tokens=max_tokens, temperature=temperature
                )
            except RateLimitError as error:
                consecutive = self.state.record_rate_limit(provider.name, self.clock.now())
                self._emit(RouterEvent(provider.name, "rate_limit", f"consecutive={consecutive}"))
                if consecutive >= MAX_CONSECUTIVE_RATE_LIMITS:
                    ttl = error.retry_after or RATE_LIMIT_TTL_SECONDS
                    self.state.disable(
                        provider.name,
                        RATE_LIMITED,
                        now=self.clock.now(),
                        ttl_seconds=ttl,
                        detail=f"{consecutive} consecutive rate limits",
                    )
                    self._emit(
                        RouterEvent(provider.name, "disabled", f"rate limited for {ttl:.0f}s")
                    )
                continue
            except QuotaExhaustedError as error:
                # Permanent for this process. Retrying spends latency to learn
                # something already known.
                self.state.disable(
                    provider.name,
                    QUOTA_EXHAUSTED,
                    now=self.clock.now(),
                    ttl_seconds=None,
                    detail=str(error),
                )
                self._emit(RouterEvent(provider.name, "disabled", "quota exhausted"))
                continue
            except (TransportError, ProviderUnavailableError) as error:
                reason = (
                    UNAVAILABLE_IN_ENVIRONMENT
                    if isinstance(error, ProviderUnavailableError)
                    else TRANSPORT_ERROR
                )
                self.state.disable(
                    provider.name,
                    reason,
                    now=self.clock.now(),
                    ttl_seconds=None
                    if isinstance(error, ProviderUnavailableError)
                    else TRANSPORT_TTL_SECONDS,
                    detail=str(error),
                )
                self._emit(RouterEvent(provider.name, "error", str(error)))
                continue

            latency_ms = int((self.clock.now() - started) * 1000)
            self.state.record_success(provider.name, self.clock.now())
            self._emit(RouterEvent(provider.name, "success", latency_ms=latency_ms))
            return RouterResult(completion, provider.name, tuple(attempts))

        raise AllProvidersUnavailableError(attempts)
