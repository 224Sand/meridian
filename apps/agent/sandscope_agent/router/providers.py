"""Provider contract, failure taxonomy, and test doubles.

The failure taxonomy is the important part. A router that cannot distinguish a
transient 429 from an exhausted quota will either strand itself on its slowest
fallback for the rest of the run, or keep hammering a provider that will never
answer again. Those are opposite mistakes with the same symptom, so the
distinction has to exist at the type level rather than in a log message.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol

ModelTier = Literal["fast", "large"]


@dataclass(frozen=True, slots=True)
class Message:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class Completion:
    text: str
    tokens_in: int
    tokens_out: int
    model: str


class ProviderError(Exception):
    """Base class. Never raised directly; the subclass carries the decision."""


class RateLimitError(ProviderError):
    """Transient. The provider is disabled for a bounded TTL, not permanently."""

    def __init__(self, message: str = "", retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class QuotaExhaustedError(ProviderError):
    """Terminal for this process. Billing or quota is spent; waiting will not help."""


class TransportError(ProviderError):
    """Network or protocol failure. Transient, but not the provider's rate limit."""


class ProviderUnavailableError(ProviderError):
    """The provider cannot run in this environment at all.

    Raised by `claude_cli`, which authenticates through a local interactive
    session that does not exist inside a deployed container (R-06). Surfaced
    honestly in the provider panel rather than hidden by omitting it from the
    list.
    """


class Provider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def min_call_gap_seconds(self) -> float:
        """Minimum spacing between calls, to stay inside a published rate limit."""

    def is_available(self, environment: str) -> bool: ...

    def complete(
        self,
        messages: Sequence[Message],
        *,
        tier: ModelTier,
        max_tokens: int,
        temperature: float,
    ) -> Completion: ...


@dataclass(slots=True)
class StubProvider:
    """A provider whose behaviour is scripted.

    Used everywhere in the test suite: no test in this project makes a live
    model call, so failover, disabling and re-enablement are asserted against
    scripted failures rather than hoped for against a real one.
    """

    name: str
    responses: list[str | ProviderError] = field(default_factory=list)
    min_call_gap_seconds: float = 0.0
    available_in: tuple[str, ...] = ("local", "test", "production")
    calls: int = 0
    default: str | ProviderError | None = None

    def is_available(self, environment: str) -> bool:
        return environment in self.available_in

    #: The last user message received. Lets a test assert what a node actually
    #: SENT, not merely that it called something.
    last_user_message: str = ""

    def complete(
        self,
        messages: Sequence[Message],
        *,
        tier: ModelTier,
        max_tokens: int,
        temperature: float,
    ) -> Completion:
        self.calls += 1
        self.last_user_message = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        )
        if self.responses:
            outcome = self.responses.pop(0)
        elif self.default is not None:
            outcome = self.default
        else:
            outcome = f"{self.name} response"

        if isinstance(outcome, ProviderError):
            raise outcome
        return Completion(
            text=outcome,
            tokens_in=sum(len(m.content.split()) for m in messages),
            tokens_out=len(outcome.split()),
            model=f"{self.name}-{tier}",
        )


ProviderFactory = Callable[[], Provider]
