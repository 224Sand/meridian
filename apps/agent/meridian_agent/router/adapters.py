"""Concrete provider adapters.

Four of the five providers speak the OpenAI chat-completions shape, so they are
one adapter with four configurations rather than four near-identical classes.
Gemini has its own request and response shape and gets its own.

Model identifiers live in configuration, not in code. Hosted model names are
renamed and retired on the provider's schedule, and a name burned into a class
becomes a deployment failure the next time that happens.

The interesting logic here is not the request. It is `_classify`, which maps a
transport-level outcome onto the failure taxonomy the router routes on. Getting
that mapping wrong is how a router ends up retrying a dead account or writing
off a healthy provider.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass

import httpx

from meridian_agent.router.providers import (
    Completion,
    Message,
    ModelTier,
    Provider,
    ProviderUnavailableError,
    QuotaExhaustedError,
    RateLimitError,
    TransportError,
)

DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

#: Substrings that mean "this key will not work again today", as distinct from
#: "slow down". Providers signal both with 429 and differentiate only in prose.
_EXHAUSTION_MARKERS = (
    "quota",
    "insufficient_quota",
    "credit balance",
    "billing",
    "exceeded your current",
    "no more credits",
)


@dataclass(frozen=True, slots=True)
class OpenAICompatibleConfig:
    name: str
    base_url: str
    api_key_env: str
    fast_model: str
    large_model: str
    min_call_gap_seconds: float = 0.0

    def model_for(self, tier: ModelTier) -> str:
        env_key = f"{self.name.upper()}_{tier.upper()}_MODEL"
        default = self.fast_model if tier == "fast" else self.large_model
        return os.environ.get(env_key, default)


#: Routing order is defined here and nowhere else. Groq leads on latency,
#: Gemini follows on generosity of free tier, the rest are depth.
OPENAI_COMPATIBLE: tuple[OpenAICompatibleConfig, ...] = (
    OpenAICompatibleConfig(
        name="groq",
        base_url="https://api.groq.com/openai/v1/chat/completions",
        api_key_env="GROQ_API_KEY",
        fast_model="llama-3.1-8b-instant",
        large_model="llama-3.3-70b-versatile",
        min_call_gap_seconds=1.0,
    ),
    OpenAICompatibleConfig(
        name="cerebras",
        base_url="https://api.cerebras.ai/v1/chat/completions",
        api_key_env="CEREBRAS_API_KEY",
        fast_model="llama3.1-8b",
        large_model="llama-3.3-70b",
        min_call_gap_seconds=1.0,
    ),
    OpenAICompatibleConfig(
        name="openrouter",
        base_url="https://openrouter.ai/api/v1/chat/completions",
        api_key_env="OPENROUTER_API_KEY",
        fast_model="meta-llama/llama-3.3-70b-instruct:free",
        large_model="meta-llama/llama-3.3-70b-instruct:free",
        min_call_gap_seconds=2.0,
    ),
    OpenAICompatibleConfig(
        name="mistral",
        base_url="https://api.mistral.ai/v1/chat/completions",
        api_key_env="MISTRAL_API_KEY",
        fast_model="mistral-small-latest",
        large_model="mistral-large-latest",
        min_call_gap_seconds=1.0,
    ),
)


def _classify(status: int, body: str) -> Exception:
    """Map an HTTP outcome onto the router's failure taxonomy.

    A 429 carrying quota language is exhaustion, not throttling. Providers
    signal both with the same status code and differentiate only in the message
    body, so this reads the body rather than trusting the code alone.
    """
    lowered = body.lower()
    exhausted = any(marker in lowered for marker in _EXHAUSTION_MARKERS)

    if status == 429:
        return QuotaExhaustedError(body[:300]) if exhausted else RateLimitError(body[:300])
    if status in (401, 403):
        # An invalid or revoked key will not become valid by retrying.
        return QuotaExhaustedError(f"authentication rejected ({status})")
    if status == 402:
        return QuotaExhaustedError(f"payment required ({status})")
    if status >= 500:
        return TransportError(f"upstream {status}: {body[:200]}")
    if exhausted:
        return QuotaExhaustedError(body[:300])
    return TransportError(f"unexpected {status}: {body[:200]}")


@dataclass(slots=True)
class OpenAICompatibleProvider:
    config: OpenAICompatibleConfig
    client: httpx.Client | None = None

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def min_call_gap_seconds(self) -> float:
        return self.config.min_call_gap_seconds

    def is_available(self, environment: str) -> bool:
        return bool(os.environ.get(self.config.api_key_env, "").strip())

    def _http(self) -> httpx.Client:
        return self.client or httpx.Client(timeout=DEFAULT_TIMEOUT)

    def complete(
        self,
        messages: Sequence[Message],
        *,
        tier: ModelTier,
        max_tokens: int,
        temperature: float,
    ) -> Completion:
        key = os.environ.get(self.config.api_key_env, "").strip()
        if not key:
            raise ProviderUnavailableError(f"{self.config.api_key_env} is not set")

        model = self.config.model_for(tier)
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            response = self._http().post(
                self.config.base_url,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
            )
        except httpx.HTTPError as error:
            raise TransportError(f"{self.name}: {error}") from error

        if response.status_code != 200:
            raise _classify(response.status_code, response.text)

        try:
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage") or {}
        except (KeyError, IndexError, ValueError) as error:
            # A 200 whose shape we do not recognise is a transport-class problem:
            # the provider is reachable and not useful.
            raise TransportError(f"{self.name}: unparseable response: {error}") from error

        return Completion(
            text=text or "",
            tokens_in=int(usage.get("prompt_tokens", 0)),
            tokens_out=int(usage.get("completion_tokens", 0)),
            model=model,
        )


@dataclass(slots=True)
class GeminiProvider:
    """Gemini speaks its own request shape and takes its key in the URL query."""

    fast_model: str = "gemini-2.0-flash"
    large_model: str = "gemini-2.0-flash"
    min_call_gap_seconds: float = 1.0
    client: httpx.Client | None = None

    name = "gemini"

    def is_available(self, environment: str) -> bool:
        return bool(os.environ.get("GEMINI_API_KEY", "").strip())

    def _http(self) -> httpx.Client:
        return self.client or httpx.Client(timeout=DEFAULT_TIMEOUT)

    def complete(
        self,
        messages: Sequence[Message],
        *,
        tier: ModelTier,
        max_tokens: int,
        temperature: float,
    ) -> Completion:
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            raise ProviderUnavailableError("GEMINI_API_KEY is not set")

        model = os.environ.get(
            f"GEMINI_{tier.upper()}_MODEL",
            self.fast_model if tier == "fast" else self.large_model,
        )
        # Gemini has no system role; a leading system message becomes
        # systemInstruction, which is where it belongs rather than being folded
        # into the first user turn.
        system = [m.content for m in messages if m.role == "system"]
        turns = [
            {"role": "model" if m.role == "assistant" else "user", "parts": [{"text": m.content}]}
            for m in messages
            if m.role != "system"
        ]
        payload: dict[str, object] = {
            "contents": turns,
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system)}]}

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        try:
            response = self._http().post(url, headers={"x-goog-api-key": key}, json=payload)
        except httpx.HTTPError as error:
            raise TransportError(f"gemini: {error}") from error

        if response.status_code != 200:
            raise _classify(response.status_code, response.text)

        try:
            data = response.json()
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts)
            usage = data.get("usageMetadata") or {}
        except (KeyError, IndexError, ValueError) as error:
            raise TransportError(f"gemini: unparseable response: {error}") from error

        return Completion(
            text=text,
            tokens_in=int(usage.get("promptTokenCount", 0)),
            tokens_out=int(usage.get("candidatesTokenCount", 0)),
            model=model,
        )


def build_default_providers(client: httpx.Client | None = None) -> list[Provider]:
    """The routing order, as configured.

    Providers with no key configured report `is_available() is False` and are
    skipped without being counted as an attempt.
    """
    groq, cerebras, openrouter, mistral = OPENAI_COMPATIBLE
    return [
        OpenAICompatibleProvider(groq, client),
        GeminiProvider(client=client),
        OpenAICompatibleProvider(cerebras, client),
        OpenAICompatibleProvider(openrouter, client),
        OpenAICompatibleProvider(mistral, client),
    ]
