"""The agent runtime's HTTP surface.

The runtime is publicly reachable and the BFF is its only legitimate client, so
the tests that matter here are about what it REFUSES: unauthenticated requests,
unknown workloads, and its own misconfiguration.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from sandscope_agent.api.security import TokenNotConfiguredError, expected_token

TOKEN = "t" * 48


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Context-managed, so FastAPI's lifespan actually runs.

    A bare TestClient(app) skips startup entirely, so the corpus never loads and
    every route that needs it fails for a reason that has nothing to do with the
    code under test.
    """
    monkeypatch.setenv("AGENT_SERVICE_TOKEN", TOKEN)
    monkeypatch.setenv("SANDSCOPE_ENV", "test")
    monkeypatch.setenv("RUN_BUDGET_USD", "0.02")
    import importlib

    from sandscope_agent.api import app as module

    importlib.reload(module)
    with TestClient(module.app) as test_client:
        yield test_client


def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


class TestStartupRefusesBadConfiguration:
    """A service that starts in a state where every request fails is worse than
    one that refuses to start. The failure surfaces at request time, once per
    user, as a stack trace."""

    def test_a_zero_budget_prevents_startup(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """RUN_BUDGET_USD=0 is the spend guard's 'cannot spend' state. It is the
        correct DEFAULT and an unusable RUNTIME value: every run died mid-stream
        with an unhandled BudgetError before this check existed."""
        monkeypatch.setenv("AGENT_SERVICE_TOKEN", TOKEN)
        monkeypatch.setenv("RUN_BUDGET_USD", "0")
        import importlib

        from sandscope_agent.api import app as module

        importlib.reload(module)
        with pytest.raises(RuntimeError, match="RUN_BUDGET_USD"), TestClient(module.app):
            pass

    def test_a_negative_budget_prevents_startup(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENT_SERVICE_TOKEN", TOKEN)
        monkeypatch.setenv("RUN_BUDGET_USD", "-1")
        import importlib

        from sandscope_agent.api import app as module

        importlib.reload(module)
        with pytest.raises(RuntimeError, match="RUN_BUDGET_USD"), TestClient(module.app):
            pass

    def test_a_missing_token_is_rejected_at_the_boundary(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Refusing is the only safe response. A service that falls back to
        'no auth required' when its secret is missing is one deploy from open."""
        monkeypatch.delenv("AGENT_SERVICE_TOKEN", raising=False)
        with pytest.raises(TokenNotConfiguredError, match="refuses to serve"):
            expected_token()

    def test_a_short_token_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENT_SERVICE_TOKEN", "short")
        with pytest.raises(TokenNotConfiguredError, match="at least 32"):
            expected_token()


class TestAuthentication:
    def test_health_is_open(self, client: TestClient) -> None:
        """The warm-ping cron needs it and it reveals nothing."""
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["corpus_ready"] is True

    def test_no_token_is_rejected(self, client: TestClient) -> None:
        assert client.get("/v1/providers").status_code == 401

    def test_a_wrong_token_is_rejected(self, client: TestClient) -> None:
        assert (
            client.get("/v1/providers", headers={"Authorization": "Bearer wrong"}).status_code
            == 401
        )

    def test_the_wrong_scheme_is_rejected(self, client: TestClient) -> None:
        assert (
            client.get("/v1/providers", headers={"Authorization": f"Basic {TOKEN}"}).status_code
            == 401
        )

    def test_a_valid_token_is_accepted(self, client: TestClient) -> None:
        assert client.get("/v1/providers", headers=auth()).status_code == 200

    def test_comparison_is_constant_time(self) -> None:
        """A token checked with == leaks its length and then its content through
        response timing, one byte at a time."""
        import ast
        import inspect

        from sandscope_agent.api import security

        tree = ast.parse(inspect.getsource(security))
        assert any(
            isinstance(node, ast.Attribute) and node.attr == "compare_digest"
            for node in ast.walk(tree)
        ), "token comparison must use secrets.compare_digest"


class TestRunEndpoint:
    def test_an_unknown_workload_is_rejected_before_any_work(self, client: TestClient) -> None:
        response = client.post(
            "/v1/runs/stream",
            headers=auth(),
            json={"workload": "does_not_exist", "subject": "s", "body": "b"},
        )
        assert response.status_code == 422
        assert "unknown workload" in response.json()["detail"]

    def test_an_empty_body_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/v1/runs/stream",
            headers=auth(),
            json={"workload": "incident_triage", "subject": "s", "body": ""},
        )
        assert response.status_code == 422

    def test_an_oversized_body_is_rejected(self, client: TestClient) -> None:
        """An unbounded body is unbounded tokens, which is unbounded cost."""
        response = client.post(
            "/v1/runs/stream",
            headers=auth(),
            json={"workload": "incident_triage", "subject": "s", "body": "x" * 5000},
        )
        assert response.status_code == 422

    def test_the_stream_is_server_sent_events(self, client: TestClient) -> None:
        response = client.post(
            "/v1/runs/stream",
            headers=auth(),
            json={
                "workload": "incident_triage",
                "subject": "s",
                "body": "what is the disaster recovery failover procedure",
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "event: run_started" in response.text
        assert "event: run_completed" in response.text or "event: error" in response.text


class TestWorkloads:
    def test_both_workloads_are_advertised(self, client: TestClient) -> None:
        names = {w["name"] for w in client.get("/v1/workloads", headers=auth()).json()["workloads"]}
        assert names == {"incident_triage", "change_review"}
