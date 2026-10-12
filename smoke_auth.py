"""Smoke test: real MCP client over stdio against the auth-gated server.

Path A: synthetic credentials (valid JWT exp) -> tool call must succeed.
Path B: no credentials + tiny wait -> tool call must fail with the
        "Authentication required" message (no browser opens: SANGLABS_CREDENTIALS_PATH
        points at an empty file and webbrowser.open is not triggered because the
        listener wait times out quickly).
"""
import asyncio
import base64
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


def make_jwt() -> str:
    def b64(obj) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

    return (
        f"{b64({'alg': 'HS256', 'typ': 'JWT'})}."
        f"{b64({'sub': 'smoke', 'exp': int(time.time()) + 3600})}.sig"
    )


def env_with(**extra: str) -> dict:
    return {
        **os.environ,
        "SANGLABS_LOGIN_WAIT_SECONDS": "2",
        "SANGLABS_LOGIN_LINGER_SECONDS": "3",
        "PYTHONPATH": os.getcwd(),
        **extra,
    }


async def authed_call() -> None:
    creds = Path(tempfile.mktemp(suffix=".json"))
    creds.write_text(
        json.dumps({"access_token": make_jwt(), "refresh_token": "r", "user_id": "smoke"}),
        encoding="utf-8",
    )
    try:
        transport = StdioTransport(
            command=sys.executable, args=["word_mcp_server.py"],
            env=env_with(SANGLABS_CREDENTIALS_PATH=str(creds)),
        )
        async with Client(transport) as client:
            tools = await client.list_tools()
            print(f"[A] connected; {len(tools)} tools visible")
            result = await client.call_tool(
                "list_available_documents", {"directory": os.getcwd()}
            )
            print(f"[A] tool call OK (auth passed): {str(result)[:60]}...")
    finally:
        creds.unlink(missing_ok=True)


async def blocked_call() -> None:
    creds = Path(tempfile.mktemp(suffix=".json"))
    creds.unlink(missing_ok=True)  # ensure it does not exist
    try:
        transport = StdioTransport(
            command=sys.executable, args=["word_mcp_server.py"],
            env=env_with(
                SANGLABS_CREDENTIALS_PATH=str(creds),
                # Headless CI: pretend webbrowser.open worked but nobody signs in.
                SANGLABS_LOGIN_WAIT_SECONDS="1",
                SANGLABS_NO_BROWSER="1",
            ),
        )
        async with Client(transport) as client:
            try:
                await client.call_tool("list_available_documents", {"directory": os.getcwd()})
            except Exception as exc:  # ToolError expected
                assert "Authentication required" in str(exc), f"unexpected error: {exc}"
                print(f"[B] unauthenticated call correctly blocked: {str(exc)[:70]}...")
            else:
                raise AssertionError("tool call should have been blocked")
    finally:
        creds.unlink(missing_ok=True)


async def main() -> None:
    await authed_call()
    await blocked_call()
    print("smoke OK")


asyncio.run(main())
