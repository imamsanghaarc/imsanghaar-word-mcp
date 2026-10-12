"""
Tests for the configurable rate-limiting middleware (no server, no network).

Covers enable/disable rules, environment parsing, client identification, and
that the token bucket actually admits a burst and then rejects.
"""

import asyncio

import pytest
from fastmcp.server.middleware import MiddlewareContext
from fastmcp.server.middleware.rate_limiting import RateLimitError

from word_document_server import rate_limit


def call(middleware, context):
    """Runs one request through the middleware, returning 'ok' or raising."""

    async def call_next(_context):
        return "ok"

    return asyncio.run(middleware.on_request(context, call_next))


def context_for(client_id=None, session_id="sess-1"):
    """A MiddlewareContext carrying just enough for client-identifier lookups."""

    class _FakeContext:
        pass

    fastmcp_context = _FakeContext()
    fastmcp_context.client_id = client_id
    fastmcp_context.session_id = session_id
    return MiddlewareContext(message=object(), fastmcp_context=fastmcp_context)


class TestEnablement:
    def test_auto_disabled_for_stdio(self, monkeypatch):
        monkeypatch.delenv("MCP_RATE_LIMIT_ENABLED", raising=False)
        assert rate_limit.rate_limit_enabled("stdio") is False

    def test_auto_enabled_for_network_transports(self, monkeypatch):
        monkeypatch.delenv("MCP_RATE_LIMIT_ENABLED", raising=False)
        assert rate_limit.rate_limit_enabled("streamable-http") is True
        assert rate_limit.rate_limit_enabled("sse") is True

    def test_explicit_true_overrides_stdio(self, monkeypatch):
        monkeypatch.setenv("MCP_RATE_LIMIT_ENABLED", "true")
        assert rate_limit.rate_limit_enabled("stdio") is True

    def test_explicit_false_overrides_network(self, monkeypatch):
        monkeypatch.setenv("MCP_RATE_LIMIT_ENABLED", "false")
        assert rate_limit.rate_limit_enabled("streamable-http") is False

    def test_invalid_value_falls_back_to_auto(self, monkeypatch):
        monkeypatch.setenv("MCP_RATE_LIMIT_ENABLED", "banana")
        assert rate_limit.rate_limit_enabled("stdio") is False
        assert rate_limit.rate_limit_enabled("streamable-http") is True


class TestBuildMiddleware:
    def test_build_returns_none_for_stdio_auto(self, monkeypatch):
        monkeypatch.delenv("MCP_RATE_LIMIT_ENABLED", raising=False)
        assert rate_limit.build_rate_limit_middleware("stdio") is None

    def test_build_returns_middleware_for_http(self, monkeypatch):
        monkeypatch.delenv("MCP_RATE_LIMIT_ENABLED", raising=False)
        middleware = rate_limit.build_rate_limit_middleware("streamable-http")
        assert middleware is not None

    def test_reads_rps_and_burst_from_env(self, monkeypatch):
        monkeypatch.setenv("MCP_RATE_LIMIT_RPS", "3")
        monkeypatch.setenv("MCP_RATE_LIMIT_BURST", "7")
        middleware = rate_limit.build_rate_limit_middleware(
            "streamable-http", global_limit=True
        )
        assert middleware.max_requests_per_second == 3.0
        assert middleware.burst_capacity == 7


class TestClientIdentifier:
    def test_prefers_client_id(self):
        ctx = context_for(client_id="client-abc")
        assert rate_limit._client_identifier(ctx) == "client-abc"

    def test_falls_back_to_session(self):
        ctx = context_for(client_id=None, session_id="session-xyz")
        assert rate_limit._client_identifier(ctx) == "session:session-xyz"

    def test_falls_back_to_global(self):
        ctx = MiddlewareContext(message=object())
        assert rate_limit._client_identifier(ctx) == "global"


class TestEnforcement:
    def test_burst_then_reject_global(self, monkeypatch):
        monkeypatch.delenv("MCP_RATE_LIMIT_ENABLED", raising=False)
        middleware = rate_limit.build_rate_limit_middleware(
            "streamable-http", rps=1, burst=2, global_limit=True
        )
        ctx = MiddlewareContext(message=object())

        assert call(middleware, ctx) == "ok"
        assert call(middleware, ctx) == "ok"
        with pytest.raises(RateLimitError):
            call(middleware, ctx)

    def test_per_client_buckets_are_independent(self, monkeypatch):
        monkeypatch.delenv("MCP_RATE_LIMIT_ENABLED", raising=False)
        middleware = rate_limit.build_rate_limit_middleware(
            "streamable-http", rps=1, burst=1, global_limit=False
        )

        a = context_for(client_id="client-a")
        b = context_for(client_id="client-b")

        assert call(middleware, a) == "ok"
        with pytest.raises(RateLimitError):
            call(middleware, a)
        # A different client has its own bucket and is still admitted.
        assert call(middleware, b) == "ok"

    def test_bucket_refills_over_time(self, monkeypatch):
        monkeypatch.delenv("MCP_RATE_LIMIT_ENABLED", raising=False)
        middleware = rate_limit.build_rate_limit_middleware(
            "streamable-http", rps=100, burst=1, global_limit=True
        )
        ctx = MiddlewareContext(message=object())

        assert call(middleware, ctx) == "ok"
        with pytest.raises(RateLimitError):
            call(middleware, ctx)
        # ~50ms at 100 tokens/s refills the single-token bucket.
        import time

        time.sleep(0.05)
        assert call(middleware, ctx) == "ok"
