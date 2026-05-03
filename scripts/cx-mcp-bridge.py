#!/usr/bin/env python3
"""
CX Agent Studio MCP stdio bridge.

Translates Claude Code's stdio MCP protocol to HTTP, injecting auto-refreshed
GCP credentials on every request. Token is managed by google-auth ADC — no
manual renewal needed.

One-time setup:
    gcloud auth application-default login   # first time only
    ./scripts/setup-cx-mcp.sh              # registers MCP in Claude Code

If auth ever breaks: gcloud auth application-default login
"""
import asyncio
import json
import sys
import threading

import google.auth
import google.auth.transport.requests
import httpx

MCP_URL = "https://ces.googleapis.com/mcp"

_creds, _ = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
_auth_req = google.auth.transport.requests.Request()
_lock = threading.Lock()
_session_id: str | None = None


def _token() -> str:
    with _lock:
        if not _creds.valid:
            _creds.refresh(_auth_req)
        return _creds.token


def _headers() -> dict[str, str]:
    h = {
        "Authorization": f"Bearer {_token()}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if _session_id:
        h["Mcp-Session-Id"] = _session_id
    return h


def _emit(obj: object) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


async def _dispatch(client: httpx.AsyncClient, msg: dict) -> None:
    global _session_id
    try:
        async with client.stream(
            "POST",
            MCP_URL,
            json=msg,
            headers=_headers(),
            timeout=httpx.Timeout(90.0, connect=10.0),
        ) as resp:
            if sid := resp.headers.get("mcp-session-id"):
                _session_id = sid

            ct = resp.headers.get("content-type", "")
            if "text/event-stream" in ct:
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or line.startswith(":"):
                        continue
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        if data and data != "[DONE]":
                            try:
                                _emit(json.loads(data))
                            except json.JSONDecodeError:
                                pass
            else:
                body = await resp.aread()
                if body.strip():
                    try:
                        _emit(json.loads(body))
                    except json.JSONDecodeError:
                        pass
    except Exception as exc:
        _emit({
            "jsonrpc": "2.0",
            "id": msg.get("id"),
            "error": {"code": -32603, "message": str(exc)},
        })


async def _run() -> None:
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    await loop.connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader), sys.stdin
    )
    async with httpx.AsyncClient() as client:
        pending: set[asyncio.Task] = set()
        while True:
            line = await reader.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            task = asyncio.create_task(_dispatch(client, msg))
            pending.add(task)
            task.add_done_callback(pending.discard)
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(_run())
