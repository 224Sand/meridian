"""Provider adapters, driven through a mock transport.

No network. The behaviour under test is not "can we reach Groq" - it is whether
a given HTTP outcome is classified into the right failure, because that
classification is what the router routes on. A 429 misread as exhaustion writes
off a healthy provider; exhaustion misread as a 429 hammers a dead account.
"""

from __future__ import annotations

import httpx
import pytest

from sandscope_agent.router.adapters import (
    OPENAI_COMPATIBLE,
    GeminiProvider,
    OpenAICompatibleProvider,
    _classify,
)
from sandscope_agent.router.providers import (
    Message,
    ProviderUnavailableError,
    QuotaExhaustedError,
    RateLimitError,
    TransportError,
)

GROQ = OPENAI_COMPATIBLE[0]
PROMPT = [Message("system", "You are terse."), Message("user", "why is the pool exhausted")]


def transport(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def ok_openai(text: str = "the pool is exhausted"):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": text}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 7},
            },
        )

    return handler


class TestClassification:
    def test_plain_429_is_transient(self) -> None:
        assert isinstance(_classify(429, "Rate limit reached, please slow down"), RateLimitError)

    @pytest.mark.parametrize(
        "body",
        [
            "You exceeded your current quota",
            "Your credit balance is too low",
            "insufficient_quota",
            "billing hard limit reached",
        ],
    )
    def test_429_carrying_quota_language_is_exhaustion(self, body: str) -> None:
        """Providers signal both with 429 and differentiate only in prose."""
        assert isinstance(_classify(429, body), QuotaExhaustedError)

    @pytest.mark.parametrize("status", [401, 403, 402])
    def test_auth_and_payment_failures_are_permanent(self, status: int) -> None:
        assert isinstance(_classify(status, "nope"), QuotaExhaustedError)

    @pytest.mark.parametrize("status", [500, 502, 503, 504])
    def test_server_errors_are_transient(self, status: int) -> None:
        assert isinstance(_classify(status, "upstream boom"), TransportError)

    def test_unknown_status_defaults_to_transient(self) -> None:
        """The safe default: a bounded disable, not a permanent write-off."""
        assert isinstance(_classify(418, "teapot"), TransportError)


class TestOpenAICompatible:
    def test_successful_completion_is_parsed(self, monkeypatch) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        provider = OpenAICompatibleProvider(GROQ, transport(ok_openai()))
        result = provider.complete(PROMPT, tier="fast", max_tokens=100, temperature=0.1)
        assert result.text == "the pool is exhausted"
        assert (result.tokens_in, result.tokens_out) == (12, 7)
        assert result.model == GROQ.fast_model

    def test_missing_key_makes_the_provider_unavailable(self, monkeypatch) -> None:
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        assert OpenAICompatibleProvider(GROQ).is_available("production") is False

    def test_missing_key_raises_rather_than_calling(self, monkeypatch) -> None:
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        with pytest.raises(ProviderUnavailableError, match="GROQ_API_KEY"):
            OpenAICompatibleProvider(GROQ).complete(
                PROMPT, tier="fast", max_tokens=10, temperature=0.0
            )

    def test_the_key_is_sent_as_a_bearer_token(self, monkeypatch) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "secret-value")
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["auth"] = request.headers["Authorization"]
            return ok_openai()(request)

        OpenAICompatibleProvider(GROQ, transport(handler)).complete(
            PROMPT, tier="fast", max_tokens=10, temperature=0.0
        )
        assert seen["auth"] == "Bearer secret-value"

    def test_model_can_be_overridden_by_environment(self, monkeypatch) -> None:
        """Hosted model names get retired on the provider's schedule, not ours."""
        monkeypatch.setenv("GROQ_API_KEY", "k")
        monkeypatch.setenv("GROQ_LARGE_MODEL", "some-newer-model")
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            import json

            seen["model"] = json.loads(request.content)["model"]
            return ok_openai()(request)

        OpenAICompatibleProvider(GROQ, transport(handler)).complete(
            PROMPT, tier="large", max_tokens=10, temperature=0.0
        )
        assert seen["model"] == "some-newer-model"

    def test_rate_limit_surfaces_as_rate_limit_error(self, monkeypatch) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "k")
        provider = OpenAICompatibleProvider(
            GROQ, transport(lambda r: httpx.Response(429, text="slow down"))
        )
        with pytest.raises(RateLimitError):
            provider.complete(PROMPT, tier="fast", max_tokens=10, temperature=0.0)

    def test_network_failure_is_a_transport_error(self, monkeypatch) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "k")

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no route to host")

        provider = OpenAICompatibleProvider(GROQ, transport(handler))
        with pytest.raises(TransportError, match="no route to host"):
            provider.complete(PROMPT, tier="fast", max_tokens=10, temperature=0.0)

    def test_a_200_with_an_unrecognised_shape_is_transport_class(self, monkeypatch) -> None:
        """Reachable and not useful is a transport problem, not a quota one."""
        monkeypatch.setenv("GROQ_API_KEY", "k")
        provider = OpenAICompatibleProvider(
            GROQ, transport(lambda r: httpx.Response(200, json={"unexpected": True}))
        )
        with pytest.raises(TransportError, match="unparseable"):
            provider.complete(PROMPT, tier="fast", max_tokens=10, temperature=0.0)


class TestGemini:
    def gemini_ok(self, text: str = "grounded answer"):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "candidates": [{"content": {"parts": [{"text": text}]}}],
                    "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 5},
                },
            )

        return handler

    def test_successful_completion_is_parsed(self, monkeypatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "k")
        result = GeminiProvider(client=transport(self.gemini_ok())).complete(
            PROMPT, tier="fast", max_tokens=100, temperature=0.1
        )
        assert result.text == "grounded answer"
        assert (result.tokens_in, result.tokens_out) == (20, 5)

    def test_system_message_becomes_system_instruction(self, monkeypatch) -> None:
        """Gemini has no system role; folding it into the user turn changes it
        from an instruction into content the model may argue with."""
        monkeypatch.setenv("GEMINI_API_KEY", "k")
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            import json

            body = json.loads(request.content)
            seen.update(body)
            return self.gemini_ok()(request)

        GeminiProvider(client=transport(handler)).complete(
            PROMPT, tier="fast", max_tokens=10, temperature=0.0
        )
        assert seen["systemInstruction"] == {"parts": [{"text": "You are terse."}]}
        assert all(turn["role"] != "system" for turn in seen["contents"])  # type: ignore[union-attr]

    def test_key_travels_in_the_header_not_the_query_string(self, monkeypatch) -> None:
        """A key in a URL lands in access logs and browser history."""
        monkeypatch.setenv("GEMINI_API_KEY", "secret-value")
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["header"] = request.headers.get("x-goog-api-key", "")
            seen["url"] = str(request.url)
            return self.gemini_ok()(request)

        GeminiProvider(client=transport(handler)).complete(
            PROMPT, tier="fast", max_tokens=10, temperature=0.0
        )
        assert seen["header"] == "secret-value"
        assert "secret-value" not in seen["url"]

    def test_missing_key_makes_it_unavailable(self, monkeypatch) -> None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        assert GeminiProvider().is_available("production") is False


class TestConfiguration:
    def test_every_configured_provider_has_a_distinct_name(self) -> None:
        names = [c.name for c in OPENAI_COMPATIBLE]
        assert len(set(names)) == len(names)

    def test_every_provider_declares_both_tiers(self) -> None:
        for config in OPENAI_COMPATIBLE:
            assert config.fast_model and config.large_model
