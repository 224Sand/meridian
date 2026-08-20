"""Spend guard at the single model-call chokepoint (ADR-0007).

Two properties, and the ordering of them is the whole point:

  1. A live call is REFUSED unless a budget is open. Not warned about, not
     logged - refused. The default state of this system is that it cannot spend.
  2. Every call is priced at WORST CASE before it fires, and actual cost is
     written to the ledger after. Pricing after the fact is accounting.
     Pricing before is control.

The distinction matters because an unattended run that drains a balance does so
in the gap between the call and the invoice. Reserving against the estimate
closes that gap.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: USD per million tokens, (input, output). Free tiers are priced at their PAID
#: rate on purpose: a guard calibrated to zero teaches nothing and silently
#: stops guarding the day a provider's free tier ends.
PRICES: dict[str, tuple[float, float]] = {
    "groq": (0.05, 0.08),
    "gemini": (0.10, 0.40),
    "cerebras": (0.10, 0.10),
    "openrouter": (0.20, 0.60),
    "mistral": (0.20, 0.60),
    "anthropic": (3.00, 15.00),
    "openai": (2.50, 10.00),
}
#: Applied to any provider not listed. Deliberately the most expensive rate
#: present: an unknown provider must not be cheap by default.
UNKNOWN_PRICE = (3.00, 15.00)


class BudgetError(RuntimeError):
    """Base for every refusal from this module."""


class NoBudgetOpenError(BudgetError):
    """A live call was attempted with no budget open.

    This is the default state. Code that wants to spend has to say so first.
    """


class BudgetExhaustedError(BudgetError):
    """The reservation would take the run past its ceiling."""


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    provider: str
    model: str
    estimated_usd: float
    actual_usd: float | None
    tokens_in: int
    tokens_out: int
    cache_hit: bool


def price(provider: str, tokens_in: int, tokens_out: int) -> float:
    rate_in, rate_out = PRICES.get(provider, UNKNOWN_PRICE)
    return (tokens_in * rate_in + tokens_out * rate_out) / 1_000_000


@dataclass(slots=True)
class SpendGuard:
    """Per-run spend control. Constructed, never imported as a global.

    A module-level guard would be shared between concurrent runs, and a ceiling
    shared between runs is not a ceiling for either of them.
    """

    ceiling_usd: float = 0.0
    reserved_usd: float = 0.0
    actual_usd: float = 0.0
    ledger: list[LedgerEntry] = field(default_factory=list)
    _open: bool = False

    @property
    def is_open(self) -> bool:
        return self._open

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.ceiling_usd - self.reserved_usd)

    def open(self, ceiling_usd: float) -> None:
        if ceiling_usd <= 0:
            raise BudgetError(f"a budget ceiling must be positive, got {ceiling_usd}")
        self.ceiling_usd = ceiling_usd
        self._open = True

    def close(self) -> None:
        self._open = False

    def reserve(
        self, provider: str, model: str, *, max_tokens_in: int, max_tokens_out: int
    ) -> float:
        """Price the worst case and hold it against the ceiling.

        `max_tokens_out` is the requested maximum rather than an expectation. A
        reservation against the expected length is a reservation that is wrong
        precisely when a response runs long, which is when it matters.
        """
        if not self._open:
            raise NoBudgetOpenError(
                "no budget is open; a live model call cannot be made. "
                "Open one explicitly with SpendGuard.open(ceiling_usd)."
            )
        estimate = price(provider, max_tokens_in, max_tokens_out)
        if self.reserved_usd + estimate > self.ceiling_usd:
            raise BudgetExhaustedError(
                f"reserving ${estimate:.6f} for {provider}/{model} would exceed the "
                f"${self.ceiling_usd:.6f} ceiling "
                f"(${self.reserved_usd:.6f} already reserved)"
            )
        self.reserved_usd += estimate
        return estimate

    def record(
        self,
        provider: str,
        model: str,
        *,
        estimated_usd: float,
        tokens_in: int,
        tokens_out: int,
        cache_hit: bool = False,
    ) -> float:
        """Write what the call actually cost, after the response."""
        actual = 0.0 if cache_hit else price(provider, tokens_in, tokens_out)
        self.actual_usd += actual
        self.ledger.append(
            LedgerEntry(provider, model, estimated_usd, actual, tokens_in, tokens_out, cache_hit)
        )
        return actual

    def record_cache_hit(self, tokens_in: int, tokens_out: int) -> None:
        """A cache hit costs nothing and is still ledgered.

        Recording it is what lets the saving be reported as a number rather than
        asserted.
        """
        self.ledger.append(LedgerEntry("cache", "cache", 0.0, 0.0, tokens_in, tokens_out, True))

    @property
    def tokens_avoided(self) -> int:
        return sum(e.tokens_in + e.tokens_out for e in self.ledger if e.cache_hit)

    @property
    def overestimate_ratio(self) -> float:
        """Reserved against spent. Above 1.0 means the worst case was pessimistic.

        Tracked because a guard that reserves ten times the real cost will refuse
        legitimate work long before the ceiling is genuinely reached, and that
        failure looks identical to running out of money.
        """
        if self.actual_usd <= 0:
            return 0.0
        return self.reserved_usd / self.actual_usd
