"""
End-to-end auth gate test: runs a real FastMCP server with the auth
middleware over the in-memory transport (no network, no browser).

Confirms the requirement: the server must not work until the user signs in.
"""

import asyncio

import pytest
from fastmcp import Client, FastMCP

from word_document_server import auth


def _build_server() -> FastMCP:
    mcp = FastMCP("auth-integration-check")

    @mcp.tool
    def secret_tool() -> str:
        return "SENSITIVE RESULT"

    mcp.add_middleware(auth.build_auth_middleware())
    return mcp


@pytest.fixture()
def server(monkeypatch):
    monkeypatch.setattr(
        auth, "sign_in_url", lambda: "https://sanglabs.vercel.app/mcp/signup"
    )
    return _build_server()


def _unauthenticated(monkeypatch):
    monkeypatch.setattr(auth, "ensure_authenticated", lambda timeout=None: False)


def _authenticated(monkeypatch):
    monkeypatch.setattr(auth, "ensure_authenticated", lambda timeout=None: True)


def _list_and_call(server):
    async def _run():
        async with Client(server) as client:
            tools = await client.list_tools()
            result = await client.call_tool("secret_tool", {})
            return tools, result

    return asyncio.run(_run())


def _expect_blocked(coro_fn, method):
    async def _run():
        async with Client(server := coro_fn) as client:
            await method(client)

    return _run


def _expect_blocked(coro_fn, method):
    async def _run():
        async with Client(server := coro_fn) as client:
            await method(client)

    return _run


def test_blocked_when_unauthenticated(server, monkeypatch):
    from mcp.shared.exceptions import MCPError

    _unauthenticated(monkeypatch)

    async def _run():
        async with Client(server) as client:
            with pytest.raises(MCPError) as list_exc:
                await client.list_tools()
            with pytest.raises(MCPError) as call_exc:
                await client.call_tool("secret_tool", {})
        return list_exc.value, call_exc.value

    list_err, call_err = asyncio.run(_run())

    for err in (list_err, call_err):
        assert err.code == auth.AUTH_REQUIRED_CODE
        assert "Authentication required" in err.message
        assert "sanglabs.vercel.app/mcp/signup" in err.message


def test_allowed_when_authenticated(server, monkeypatch):
    _authenticated(monkeypatch)

    tools, result = _list_and_call(server)

    assert any(t.name == "secret_tool" for t in tools)
    assert result.is_error is False
    assert "SENSITIVE RESULT" in str(result.content)
