"""
Browser-based authentication for the Sang Labs Word MCP server.

Flow (stdio transport, local agents like Claude Code / Gemini / OpenCode):

1. First tool call with no stored credentials starts a loopback HTTP listener
   on 127.0.0.1 (ephemeral port) and opens the user's browser at
   ``https://sanglabs.vercel.app/mcp/signup?redirect_uri=...&state=...``.
2. The user signs up (name, email, occupation, password) or logs in and clicks
   "Continue with this account". The site hands the Supabase session tokens to
   the loopback listener (RFC 8252 native-app pattern) after verifying the
   redirect target is loopback-only.
3. This module validates the session with Supabase (``GET /auth/v1/user``),
   stores it in ``~/.sanglabs/word-mcp/credentials.json`` and refreshes it
   transparently when the access token expires.

No API keys are involved; the credential is the user's own Sang Labs session.
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

# Public values (the anon/publishable key ships in every browser bundle too).
DEFAULT_SITE_URL = "https://sanglabs.vercel.app"
DEFAULT_SUPABASE_URL = "https://jfnhntefueujmgpfonuy.supabase.co"
DEFAULT_SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpmbmhudGVmdWV1am1ncGZvbnV5Iiwicm9sZSI6ImFub24i"
    "LCJpYXQiOjE3OTE2MTA2NjMsImV4cCI6MjEwNzE4NjY2M30."
    "UQ9xMpPni8lKr6C4qNbQJmz7Kzr5L1f1s6-2cTSFYEQ"
)

SITE_URL = os.getenv("SANGLABS_SITE_URL", DEFAULT_SITE_URL).rstrip("/")
SUPABASE_URL = os.getenv("SANGLABS_SUPABASE_URL", DEFAULT_SUPABASE_URL).rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SANGLABS_SUPABASE_ANON_KEY", DEFAULT_SUPABASE_ANON_KEY)

MCP_SLUG = "MSOW-MCP"
SIGNUP_PATH = "/mcp/signup"

# How long the first (triggering) tool call waits for the browser sign-in.
LOGIN_TIMEOUT_SECONDS = float(os.getenv("SANGLABS_LOGIN_WAIT_SECONDS", "45"))
# How long the loopback listener keeps listening after the tool call gives up.
LISTENER_LINGER_SECONDS = float(os.getenv("SANGLABS_LOGIN_LINGER_SECONDS", "300"))

_session_lock = threading.Lock()
_login_event = threading.Event()
_login_thread: Optional[threading.Thread] = None
_login_state: dict[str, Any] = {"expected_state": None, "url": None}


def credentials_path() -> Path:
    """Where the Supabase session is stored locally (0600 best-effort)."""
    override = os.getenv("SANGLABS_CREDENTIALS_PATH")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".sanglabs" / "word-mcp" / "credentials.json"


def _api_headers() -> dict[str, str]:
    return {"apikey": SUPABASE_ANON_KEY}


def load_credentials() -> Optional[dict[str, Any]]:
    try:
        data = json.loads(credentials_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def save_credentials(creds: dict[str, Any]) -> None:
    path = credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(creds, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:  # e.g. filesystems without POSIX permissions
        pass
    tmp.replace(path)


def clear_credentials() -> None:
    try:
        credentials_path().unlink(missing_ok=True)
    except OSError:
        pass


def _parse_jwt_exp(token: str) -> Optional[float]:
    """Reads the ``exp`` claim from a JWT without verifying it (Supabase already did)."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return float(claims["exp"])
    except (IndexError, KeyError, ValueError):
        return None


def _access_token_valid(creds: dict[str, Any]) -> bool:
    exp = _parse_jwt_exp(str(creds.get("access_token", "")))
    return exp is not None and exp > time.time() + 30


def validate_token(access_token: str) -> Optional[dict[str, Any]]:
    """Confirms an access token with Supabase; returns the user record or None."""
    try:
        response = httpx.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={**_api_headers(), "Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        if response.status_code == 200:
            data = response.json()
            return data if isinstance(data, dict) else None
    except httpx.HTTPError:
        pass
    return None


def refresh_session(creds: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Exchanges a refresh token for a fresh session; None when rejected."""
    refresh_token = creds.get("refresh_token")
    if not refresh_token:
        return None
    try:
        response = httpx.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=refresh_token",
            headers=_api_headers(),
            json={"refresh_token": refresh_token},
            timeout=15,
        )
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    data = response.json()
    access_token = data.get("access_token")
    if not access_token:
        return None
    refreshed = {
        "access_token": access_token,
        "refresh_token": data.get("refresh_token") or refresh_token,
        "expires_at": time.time() + float(data.get("expires_in", 3600)),
        "user_id": (data.get("user") or {}).get("id") or creds.get("user_id"),
    }
    save_credentials(refreshed)
    return refreshed


def record_last_used(creds: dict[str, Any]) -> None:
    """Fire-and-forget: bump last_used_at on the mcp_connections row (RLS: own JWT)."""

    def _send() -> None:
        access_token = creds.get("access_token")
        user_id = creds.get("user_id")
        if not access_token or not user_id:
            return
        try:
            httpx.patch(
                f"{SUPABASE_URL}/rest/v1/mcp_connections"
                f"?user_id=eq.{user_id}&mcp_slug=eq.{MCP_SLUG}",
                headers={
                    **_api_headers(),
                    "Authorization": f"Bearer {access_token}",
                    "Prefer": "return=minimal",
                },
                json={"last_used_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                timeout=10,
            )
        except httpx.HTTPError:
            pass

    threading.Thread(target=_send, daemon=True).start()


class _AuthState:
    """Shared state between the tool call waiting for sign-in and the listener."""

    def __init__(self) -> None:
        self.expected_state = ""
        self.received: Optional[dict[str, Any]] = None


def _make_handler(state: _AuthState, done: threading.Event):
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (http.server API)
            parsed = urlparse(self.path)
            if parsed.path != "/callback":
                self._respond(404, "Not found.")
                return
            params = parse_qs(parsed.query)
            got_state = (params.get("state") or [""])[0]
            access_token = (params.get("access_token") or [""])[0]
            refresh_token = (params.get("refresh_token") or [""])[0]

            if got_state != state.expected_state or not access_token or not refresh_token:
                self._respond(400, "Invalid sign-in response. You can close this tab.")
                return
            user = validate_token(access_token)
            if user is None:
                self._respond(400, "The session could not be verified. Please try again.")
                return

            state.received = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": time.time() + 3600,
                "user_id": user.get("id"),
            }
            done.set()
            self._respond(
                200,
                "<!doctype html><html><head><title>Sang Labs — Word MCP</title></head>"
                "<body style=\"font-family:system-ui,sans-serif;display:flex;align-items:"
                "center;justify-content:center;height:100vh;margin:0\">"
                "<div style=\"text-align:center\">"
                "<h1 style=\"font-size:1.4rem\">You're signed in</h1>"
                "<p style=\"color:#555\">Return to your agent — it will continue automatically.</p>"
                "</div></body></html>",
                content_type="text/html",
            )

        def _respond(self, status: int, text: str, content_type: str = "text/plain; charset=utf-8") -> None:
            body = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: Any) -> None:  # keep the console quiet
            pass

    return _Handler


def _start_login_flow() -> str:
    """Starts the loopback listener and opens the browser. Returns the site URL."""
    global _login_thread

    with _session_lock:
        if _login_thread and _login_thread.is_alive() and _login_state["url"]:
            return str(_login_state["url"])

        state = _AuthState()
        state.expected_state = uuid.uuid4().hex
        server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(state, _login_event))
        port = server.server_address[1]
        redirect_uri = f"http://127.0.0.1:{port}/callback"
        params = urlencode({"redirect_uri": redirect_uri, "state": state.expected_state})
        url = f"{SITE_URL}{SIGNUP_PATH}?{params}"

        def _serve() -> None:
            deadline = time.time() + LISTENER_LINGER_SECONDS
            while not _login_event.is_set() and time.time() < deadline:
                server.timeout = 5
                server.handle_request()
            server.server_close()

        _login_event.clear()
        state.received = None
        _login_state["expected_state"] = state.expected_state
        _login_state["url"] = url
        _login_state["_handler_state"] = state
        _login_thread = threading.Thread(target=_serve, daemon=True)
        _login_thread.start()

    print(f"[auth] Waiting for sign-in — if the browser did not open, visit:\n  {url}", flush=True)
    if os.getenv("SANGLABS_NO_BROWSER", "").lower() in {"1", "true", "yes"}:
        print("[auth] SANGLABS_NO_BROWSER set — skipping webbrowser.open", flush=True)
    else:
        try:
            webbrowser.open(url)
        except Exception:  # pragma: no cover - depends on the desktop environment
            pass
    return url


def wait_for_login(timeout: float) -> bool:
    """Blocks until the browser flow completes or the timeout elapses."""
    if _login_event.wait(timeout=timeout):
        state: Optional[_AuthState] = _login_state.get("_handler_state")
        if state and state.received:
            save_credentials(state.received)
            record_last_used(state.received)
            _login_event.clear()
            return True
    return False


_last_used_recorded = False


def ensure_authenticated(timeout: Optional[float] = None) -> bool:
    """True when a valid (refreshed if needed) session is available."""
    global _last_used_recorded

    creds = load_credentials()
    if creds:
        if _access_token_valid(creds):
            if not _last_used_recorded:
                _last_used_recorded = True
                record_last_used(creds)
            return True
        refreshed = refresh_session(creds)
        if refreshed:
            return True
        clear_credentials()
        creds = None

    # No usable credentials — run the browser flow.
    _start_login_flow()
    return wait_for_login(LOGIN_TIMEOUT_SECONDS if timeout is None else timeout)


def logout_local() -> None:
    """``--logout``: revoke this machine's session server-side and delete it locally."""
    creds = load_credentials()
    if creds and creds.get("access_token"):
        try:
            httpx.post(
                f"{SUPABASE_URL}/auth/v1/logout",
                headers={
                    **_api_headers(),
                    "Authorization": f"Bearer {creds['access_token']}",
                },
                json={"scope": "local"},
                timeout=15,
            )
        except httpx.HTTPError:
            pass
    clear_credentials()


def sign_in_url() -> str:
    """Fallback URL shown when the browser flow cannot complete in time."""
    return _login_state.get("url") or f"{SITE_URL}{SIGNUP_PATH}"


def reset_login_state_for_tests() -> None:
    """Testing helper: clears module-level login state."""
    global _login_thread, _last_used_recorded
    _login_event.clear()
    _login_thread = None
    _last_used_recorded = False
    _login_state.clear()
    _login_state.update({"expected_state": None, "url": None})


def _is_local_stdio() -> bool:
    return os.getenv("MCP_TRANSPORT", "stdio").lower() == "stdio"


def build_auth_middleware():
    """Creates the fastmcp middleware that hard-gates every tool call."""
    from fastmcp.exceptions import ToolError
    from fastmcp.server.middleware import Middleware

    class AuthMiddleware(Middleware):
        """Rejects tool calls until the user has signed in via the browser."""

        async def on_call_tool(self, context, call_next):
            import asyncio

            if not _is_local_stdio():
                raise ToolError(
                    "Authentication for the hosted (HTTP) deployment is not available yet. "
                    "Please use the local server instead: "
                    "uvx --from msow-imsanghaar-mcp word_mcp_server"
                )

            # Never block the event loop while the browser flow runs.
            ok = await asyncio.to_thread(ensure_authenticated)
            if ok:
                return await call_next(context)

            raise ToolError(
                "Authentication required — I tried to open the Sang Labs sign-in page in "
                f"your browser. If it did not open, visit:\n  {sign_in_url()}\n"
                "Sign in (or sign up) and click 'Continue with this account', then ask me again."
            )

    return AuthMiddleware()


__all__ = [
    "MCP_SLUG",
    "SITE_URL",
    "SUPABASE_URL",
    "build_auth_middleware",
    "credentials_path",
    "clear_credentials",
    "ensure_authenticated",
    "load_credentials",
    "logout_local",
    "record_last_used",
    "refresh_session",
    "reset_login_state_for_tests",
    "save_credentials",
    "sign_in_url",
    "validate_token",
]
