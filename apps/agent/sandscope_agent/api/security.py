"""Authentication for the agent runtime.

The runtime is publicly reachable and the browser must never hold this token
(THREAT_MODEL T-3). Only the BFF does, server-side.

Comparison is constant-time. A token checked with `==` leaks its length and then
its content through response timing, one byte at a time, to anyone patient
enough to measure. `secrets.compare_digest` is the whole fix and costs nothing.
"""

from __future__ import annotations

import os
import secrets

from fastapi import Header, HTTPException, status


class TokenNotConfiguredError(RuntimeError):
    """The runtime was started with no token.

    Refusing to start is the only safe response. A service that falls back to
    "no auth required" when its secret is missing is one bad deploy away from
    being open, and the failure is silent.
    """


def expected_token() -> str:
    token = os.environ.get("AGENT_SERVICE_TOKEN", "").strip()
    if not token:
        raise TokenNotConfiguredError(
            "AGENT_SERVICE_TOKEN is not set. The runtime refuses to serve "
            "unauthenticated requests rather than defaulting to open."
        )
    if len(token) < 32:
        raise TokenNotConfiguredError(
            f"AGENT_SERVICE_TOKEN is {len(token)} characters; at least 32 are required."
        )
    return token


def require_token(authorization: str = Header(default="")) -> None:
    """FastAPI dependency. Rejects before any work is done.

    Rejection happens in the dependency rather than inside a handler so that an
    unauthenticated request never reaches retrieval, a model call, or the spend
    guard.
    """
    try:
        expected = expected_token()
    except TokenNotConfiguredError as error:
        # 503, not 401: the caller did nothing wrong and retrying with a
        # different token will not help. Saying 401 here would send an operator
        # hunting for a credential problem that does not exist.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error

    scheme, _, presented = authorization.partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(presented.strip(), expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
