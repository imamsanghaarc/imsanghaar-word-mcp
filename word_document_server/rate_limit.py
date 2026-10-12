"""
Configurable rate limiting for the Word Document MCP server.

Rate limiting is off by default for local ``stdio`` use (a single user on their
own machine) and on by default for the network transports (``streamable-http``,
``sse``), where an exposed endpoint can otherwise be flooded.

It builds on FastMCP's built-in token-bucket middleware: a short burst is
allowed up to the bucket capacity, after which requests are admitted at the
sustained rate. Limits are applied per client where an identifier is available
and fall back to a single shared bucket otherwise.

Environment variables:

- ``MCP_RATE_LIMIT_ENABLED``: ``auto`` (default), ``true``, or ``false``.
  ``auto`` enables limiting only for the network transports.
- ``MCP_RATE_LIMIT_RPS``: sustained requests per second (default ``10``).
- ``MCP_RATE_LIMIT_BURST``: maximum burst capacity (default ``2 x RPS``).
- ``MCP_RATE_LIMIT_GLOBAL``: ``true`` for one shared bucket, ``false``
  (default) for a bucket per client.

No external services are contacted; buckets live in memory for the life of the
process.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware

#: Transports that accept remote connections and therefore benefit from limits.
NETWORK_TRANSPORTS = frozenset({"streamable-http", "sse"})

_TRUTHY = frozenset({"1", "true", "yes", "on"})
_FALSY = frozenset({"0", "false", "no", "off"})


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in _TRUTHY:
        return True
    if value in _FALSY:
        return False
    return default


def rate_limit_enabled(transport: Optional[str] = None) -> bool:
    """Whether rate limiting should be active for ``transport``.

    Defaults to ``auto``: enabled for the network transports, disabled for
    ``stdio``. An explicit ``MCP_RATE_LIMIT_ENABLED`` value always wins.
    """
    if transport is None:
        transport = os.getenv("MCP_TRANSPORT", "stdio").lower()

    raw = os.getenv("MCP_RATE_LIMIT_ENABLED", "auto").strip().lower()
    if raw in _TRUTHY:
        return True
    if raw in _FALSY:
        return False
    return transport in NETWORK_TRANSPORTS


def _client_identifier(context: Any) -> str:
    """Best-effort stable key for the calling client.

    Prefers the OAuth/authenticated client id, then the MCP session id. When
    neither is available every caller shares one bucket.
    """
    fastmcp_context = getattr(context, "fastmcp_context", None)
    if fastmcp_context is not None:
        try:
            client_id = fastmcp_context.client_id
        except Exception:  # pragma: no cover - depends on the transport
            client_id = None
        if client_id:
            return str(client_id)

        try:
            session_id = fastmcp_context.session_id
        except Exception:  # pragma: no cover - no session yet
            session_id = None
        if session_id:
            return f"session:{session_id}"

    return "global"


def build_rate_limit_middleware(
    transport: Optional[str] = None,
    *,
    rps: Optional[float] = None,
    burst: Optional[int] = None,
    global_limit: Optional[bool] = None,
) -> Optional[RateLimitingMiddleware]:
    """Create the middleware that enforces the rate limit, or ``None`` if disabled.

    Keyword arguments override the environment and exist mainly for tests.
    """
    if transport is None:
        transport = os.getenv("MCP_TRANSPORT", "stdio").lower()

    if not rate_limit_enabled(transport):
        return None

    if rps is None:
        rps = float(os.getenv("MCP_RATE_LIMIT_RPS", "10"))
    if burst is None:
        raw_burst = os.getenv("MCP_RATE_LIMIT_BURST")
        burst = int(raw_burst) if raw_burst else None
    if global_limit is None:
        global_limit = _env_bool("MCP_RATE_LIMIT_GLOBAL", False)

    return RateLimitingMiddleware(
        max_requests_per_second=rps,
        burst_capacity=burst,
        get_client_id=None if global_limit else _client_identifier,
        global_limit=global_limit,
    )


__all__ = [
    "NETWORK_TRANSPORTS",
    "build_rate_limit_middleware",
    "rate_limit_enabled",
]
