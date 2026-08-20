"""Router state and the clock it reads.

Two things the original this is derived from got wrong, both of which made its
most important behaviour impossible to test:

  * disabled-provider state lived in a module-level dict, so tests leaked into
    each other and order mattered
  * expiry was computed against `time.time()` directly, so the only way to
    observe a time-boxed disable expiring was to sleep for the TTL

Both are fixed here by construction: state is an object you hold, and time is a
dependency you pass in.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol


class Clock(Protocol):
    def now(self) -> float: ...
    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def now(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


class ManualClock:
    """A clock tests advance explicitly.

    This exists so that `test_disabled_provider_is_reenabled_after_ttl` runs in
    microseconds and asserts the real boundary, instead of sleeping for ten
    minutes and asserting nothing.
    """

    def __init__(self, start: float = 1_000_000.0) -> None:
        self._now = start

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds

    def sleep(self, seconds: float) -> None:
        """Sleeping advances the clock instead of blocking.

        This is what lets inter-call pacing be exercised in tests at full speed
        while still asserting the real elapsed-time arithmetic.
        """
        self.advance(max(0.0, seconds))


class DisableReason(str):
    """Why a provider is unavailable. Subclasses str so it logs readably."""


RATE_LIMITED = DisableReason("rate_limited")
QUOTA_EXHAUSTED = DisableReason("quota_exhausted")
TRANSPORT_ERROR = DisableReason("transport_error")
INJECTED = DisableReason("injected_failure")
UNAVAILABLE_IN_ENVIRONMENT = DisableReason("unavailable_in_environment")


@dataclass(frozen=True, slots=True)
class Disablement:
    reason: DisableReason
    #: None means permanent for the life of the process. Quota exhaustion is
    #: permanent; a 429 is not, and conflating them strands the pipeline on its
    #: slowest fallback for the rest of the run.
    expires_at: float | None
    detail: str = ""

    def is_active(self, now: float) -> bool:
        return self.expires_at is None or now < self.expires_at


@dataclass(slots=True)
class RouterState:
    """Per-process router state. Constructed, not imported."""

    disabled: dict[str, Disablement] = field(default_factory=dict)
    consecutive_429: dict[str, int] = field(default_factory=dict)
    last_call_at: dict[str, float] = field(default_factory=dict)

    def disable(
        self,
        provider: str,
        reason: DisableReason,
        *,
        now: float,
        ttl_seconds: float | None,
        detail: str = "",
    ) -> None:
        self.disabled[provider] = Disablement(
            reason=reason,
            expires_at=None if ttl_seconds is None else now + ttl_seconds,
            detail=detail,
        )

    def is_disabled(self, provider: str, now: float) -> bool:
        disablement = self.disabled.get(provider)
        if disablement is None:
            return False
        if disablement.is_active(now):
            return True
        # Expired: clear it so re-enablement is observable in state, not just
        # inferred by every caller recomputing the same comparison.
        del self.disabled[provider]
        self.consecutive_429.pop(provider, None)
        return False

    def record_success(self, provider: str, now: float) -> None:
        self.consecutive_429.pop(provider, None)
        self.last_call_at[provider] = now

    def record_rate_limit(self, provider: str, now: float) -> int:
        self.consecutive_429[provider] = self.consecutive_429.get(provider, 0) + 1
        self.last_call_at[provider] = now
        return self.consecutive_429[provider]
