"""
Tests for the Sang Labs browser-auth module (no network, no real browser).
"""

import asyncio
import base64
import json
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from word_document_server import auth


def make_jwt(exp_offset: int = 3600) -> str:
    """Builds an unverifiable JWT whose exp claim is exp_offset seconds away."""

    def b64(obj) -> str:
        raw = json.dumps(obj).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    header = b64({"alg": "HS256", "typ": "JWT"})
    payload = b64({"sub": "user-123", "exp": int(time.time()) + exp_offset})
    return f"{header}.{payload}.signature"


@pytest.fixture()
def creds_file(tmp_path, monkeypatch):
    path = tmp_path / "credentials.json"
    monkeypatch.setenv("SANGLABS_CREDENTIALS_PATH", str(path))
    auth.reset_login_state_for_tests()
    yield path
    auth.reset_login_state_for_tests()


class TestCredentialStore:
    def test_round_trip(self, creds_file):
        creds = {"access_token": "a", "refresh_token": "r", "user_id": "u1"}
        auth.save_credentials(creds)
        assert auth.load_credentials() == creds

    def test_missing_file_returns_none(self, creds_file):
        assert auth.load_credentials() is None

    def test_corrupt_file_returns_none(self, creds_file):
        creds_file.write_text("{not json", encoding="utf-8")
        assert auth.load_credentials() is None

    def test_clear(self, creds_file):
        auth.save_credentials({"access_token": "a"})
        auth.clear_credentials()
        assert auth.load_credentials() is None


class TestTokenValidation:
    def test_valid_expiry(self, creds_file):
        creds = {"access_token": make_jwt(exp_offset=3600)}
        assert auth._access_token_valid(creds) is True

    def test_expired(self, creds_file):
        creds = {"access_token": make_jwt(exp_offset=-120)}
        assert auth._access_token_valid(creds) is False

    def test_garbage_token(self, creds_file):
        assert auth._access_token_valid({"access_token": "not-a-jwt"}) is False

    def test_validate_token_success(self, creds_file, monkeypatch):
        monkeypatch.setattr(
            auth.httpx, "get",
            lambda *a, **k: httpx.Response(200, json={"id": "user-123"}),
        )
        assert auth.validate_token("tok") == {"id": "user-123"}

    def test_validate_token_rejected(self, creds_file, monkeypatch):
        monkeypatch.setattr(
            auth.httpx, "get",
            lambda *a, **k: httpx.Response(401, json={"msg": "invalid"}),
        )
        assert auth.validate_token("tok") is None

    def test_validate_token_network_error(self, creds_file, monkeypatch):
        def boom(*a, **k):
            raise httpx.ConnectError("offline")

        monkeypatch.setattr(auth.httpx, "get", boom)
        assert auth.validate_token("tok") is None


class TestRefresh:
    def test_refresh_success_saves_new_session(self, creds_file, monkeypatch):
        monkeypatch.setattr(
            auth.httpx, "post",
            lambda *a, **k: httpx.Response(
                200,
                json={
                    "access_token": "new-access",
                    "refresh_token": "new-refresh",
                    "expires_in": 3600,
                    "user": {"id": "user-123"},
                },
            ),
        )
        refreshed = auth.refresh_session({"refresh_token": "old-refresh"})
        assert refreshed is not None
        assert refreshed["access_token"] == "new-access"
        stored = auth.load_credentials()
        assert stored["refresh_token"] == "new-refresh"

    def test_refresh_rejected_clears_nothing(self, creds_file, monkeypatch):
        monkeypatch.setattr(
            auth.httpx, "post",
            lambda *a, **k: httpx.Response(400, json={"msg": "invalid refresh token"}),
        )
        assert auth.refresh_session({"refresh_token": "bad"}) is None


class TestLoopbackFlow:
    def _run_login(self, creds_file, monkeypatch, state=None, tokens=None, timeout=5,
                   validate=None):
        """Starts the listener, fakes the browser callback, waits for it."""
        opened = {}
        monkeypatch.setattr(auth.webbrowser, "open", lambda url: opened.setdefault("url", url))
        monkeypatch.setattr(auth, "validate_token", validate or (lambda token: {"id": "user-123"}))

        url = auth._start_login_flow()
        parsed = urlparse(url)
        assert parsed.path == "/mcp/signup"
        query = parse_qs(parsed.query)
        redirect = query["redirect_uri"][0]
        expected_state = query["state"][0]
        assert redirect.startswith("http://127.0.0.1:")
        assert opened["url"] == url

        cb = urlparse(redirect)
        got_state = state if state is not None else expected_state
        got_tokens = tokens if tokens is not None else {
            "access_token": make_jwt(),
            "refresh_token": "refresh-1",
        }
        httpx.get(
            f"http://127.0.0.1:{cb.port}/callback",
            params={
                "state": got_state,
                "access_token": got_tokens["access_token"],
                "refresh_token": got_tokens["refresh_token"],
            },
        )
        return auth.wait_for_login(timeout=timeout)

    def test_callback_saves_credentials(self, creds_file, monkeypatch):
        assert self._run_login(creds_file, monkeypatch) is True
        stored = auth.load_credentials()
        assert stored is not None
        assert stored["refresh_token"] == "refresh-1"
        assert stored["user_id"] == "user-123"

    def test_wrong_state_is_rejected(self, creds_file, monkeypatch):
        assert self._run_login(creds_file, monkeypatch, state="attacker-state", timeout=0.5) is False
        assert auth.load_credentials() is None

    def test_unverifiable_session_is_rejected(self, creds_file, monkeypatch):
        assert self._run_login(
            creds_file, monkeypatch, timeout=0.5, validate=lambda token: None
        ) is False
        assert auth.load_credentials() is None


class TestEnsureAuthenticated:
    def test_valid_credentials_short_circuit(self, creds_file, monkeypatch):
        auth.save_credentials({"access_token": make_jwt(), "refresh_token": "r", "user_id": "u"})
        monkeypatch.setattr(auth, "record_last_used", lambda creds: None)
        assert auth.ensure_authenticated() is True

    def test_expired_token_triggers_refresh(self, creds_file, monkeypatch):
        auth.save_credentials(
            {"access_token": make_jwt(exp_offset=-120), "refresh_token": "r", "user_id": "u"}
        )
        monkeypatch.setattr(
            auth, "refresh_session",
            lambda creds: {"access_token": make_jwt(), "refresh_token": "r2"},
        )
        assert auth.ensure_authenticated() is True

    def test_no_credentials_starts_browser_flow(self, creds_file, monkeypatch):
        # No credentials, browser flow never completes -> False after timeout.
        monkeypatch.setattr(auth.webbrowser, "open", lambda url: None)
        monkeypatch.setattr(auth, "LOGIN_TIMEOUT_SECONDS", 0.2)
        monkeypatch.setattr(auth, "LISTENER_LINGER_SECONDS", 0.5)
        assert auth.ensure_authenticated() is False


class TestMiddleware:
    def test_blocks_tool_calls_until_authenticated(self, creds_file, monkeypatch):
        monkeypatch.setattr(auth, "ensure_authenticated", lambda timeout=None: False)
        monkeypatch.setattr(auth, "sign_in_url", lambda: "https://sanglabs.vercel.app/mcp/signup?x=1")
        middleware = auth.build_auth_middleware()

        async def call_next(context):
            return "should not run"

        with pytest.raises(Exception) as exc:
            asyncio.run(middleware.on_call_tool(None, call_next))
        assert "Authentication required" in str(exc.value)
        assert "sanglabs.vercel.app/mcp/signup" in str(exc.value)

    def test_authenticated_calls_pass_through(self, creds_file, monkeypatch):
        monkeypatch.setattr(auth, "ensure_authenticated", lambda timeout=None: True)
        middleware = auth.build_auth_middleware()

        async def call_next(context):
            return "tool result"

        assert asyncio.run(middleware.on_call_tool(None, call_next)) == "tool result"

    def test_blocks_tools_list_until_authenticated(self, creds_file, monkeypatch):
        monkeypatch.setattr(auth, "ensure_authenticated", lambda timeout=None: False)
        monkeypatch.setattr(auth, "sign_in_url", lambda: "https://sanglabs.vercel.app/mcp/signup?x=1")
        middleware = auth.build_auth_middleware()

        class FakeContext:
            method = None

        async def call_next(context):
            return "should not run"

        for method in ("tools/list", "resources/list", "prompts/list", "tools/call"):
            context = FakeContext()
            context.method = method
            with pytest.raises(Exception) as exc:
                asyncio.run(middleware.on_request(context, call_next))
            assert "sanglabs.vercel.app/mcp/signup" in str(exc.value)

    def test_tools_list_raises_protocol_error(self, creds_file, monkeypatch):
        # Must be an MCPError (code -32001) so hosts see the sign-in message
        # instead of a generic "Internal server error".
        from mcp.shared.exceptions import MCPError

        monkeypatch.setattr(auth, "ensure_authenticated", lambda timeout=None: False)
        monkeypatch.setattr(auth, "sign_in_url", lambda: "https://sanglabs.vercel.app/mcp/signup?x=1")
        middleware = auth.build_auth_middleware()

        class FakeContext:
            method = "tools/list"

        async def call_next(context):
            return "should not run"

        with pytest.raises(MCPError) as exc:
            asyncio.run(middleware.on_request(FakeContext(), call_next))
        assert exc.value.code == auth.AUTH_REQUIRED_CODE
        assert "Authentication required" in exc.value.message
        assert "sanglabs.vercel.app/mcp/signup" in exc.value.message

    def test_authenticated_tools_list_passes(self, creds_file, monkeypatch):
        monkeypatch.setattr(auth, "ensure_authenticated", lambda timeout=None: True)
        middleware = auth.build_auth_middleware()

        class FakeContext:
            method = "tools/list"

        async def call_next(context):
            return [object()]

        assert asyncio.run(middleware.on_request(FakeContext(), call_next)) is not None

    def test_handshake_methods_are_exempt(self, creds_file, monkeypatch):
        events = []
        monkeypatch.setattr(auth, "ensure_authenticated", lambda timeout=None: events.append("auth"))
        middleware = auth.build_auth_middleware()

        class FakeContext:
            method = None

        async def call_next(context):
            return "ok"

        for method in ("initialize", "ping", "server/discover"):
            context = FakeContext()
            context.method = method
            assert asyncio.run(middleware.on_request(context, call_next)) == "ok"
        assert events == []

    def test_hosted_transports_also_require_sign_in(self, creds_file, monkeypatch):
        monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
        monkeypatch.setattr(auth, "ensure_authenticated", lambda timeout=None: False)
        monkeypatch.setattr(auth, "sign_in_url", lambda: "https://sanglabs.vercel.app/mcp/signup")
        middleware = auth.build_auth_middleware()

        async def call_next(context):
            return "should not run"

        with pytest.raises(Exception) as exc:
            asyncio.run(middleware.on_call_tool(None, call_next))
        assert "Authentication required" in str(exc.value)
        assert "sanglabs.vercel.app/mcp/signup" in str(exc.value)
