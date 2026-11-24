#!/usr/bin/env python3
"""Zero-dependency local MCP stdio bridge for Market News API (https://goat-lighthouse.site/mcp).

Lets any stdio-only MCP host (Claude Desktop, Cursor, Windsurf, Cline, etc.) talk to the
remote Streamable HTTP MCP endpoint with Python 3.10+ stdlib only (no pip installs).

Tool discovery, catalogue, delayed sample, supported coins, and unpaid x402 quotes are free.
Paid tools return x402 payment requirements when called without `_meta["x402/payment"]`.

Usage:
  python3 mcp_stdio_bridge.py                  # Run MCP stdio JSON-RPC loop
  python3 mcp_stdio_bridge.py --check          # Verify remote endpoint & list tools (free)
  MCP_ENDPOINT=https://goat-lighthouse.site/mcp python3 mcp_stdio_bridge.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Callable, TextIO

DEFAULT_ENDPOINT = "https://goat-lighthouse.site/mcp"
DEFAULT_PROTOCOL_VERSION = "2025-06-18"
USER_AGENT = "market-news-mcp-stdio-bridge/1.0"


def _parse_sse_payload(raw_text: str) -> list[dict[str, Any]]:
    """Extract JSON-RPC objects from a text/event-stream response body."""
    messages: list[dict[str, Any]] = []
    data_lines: list[str] = []
    for line in raw_text.splitlines():
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
        elif not line.strip() and data_lines:
            chunk = "\n".join(data_lines).strip()
            data_lines.clear()
            if chunk and chunk != "[DONE]":
                try:
                    obj = json.loads(chunk)
                    if isinstance(obj, dict):
                        messages.append(obj)
                except json.JSONDecodeError:
                    pass
    if data_lines:
        chunk = "\n".join(data_lines).strip()
        if chunk and chunk != "[DONE]":
            try:
                obj = json.loads(chunk)
                if isinstance(obj, dict):
                    messages.append(obj)
            except json.JSONDecodeError:
                pass
    return messages


class StreamableHttpTransport:
    """Thin stdlib HTTP transport for MCP Streamable HTTP JSON-RPC."""

    def __init__(
        self,
        endpoint: str = DEFAULT_ENDPOINT,
        protocol_version: str = DEFAULT_PROTOCOL_VERSION,
        timeout: float = 30.0,
    ) -> None:
        self.endpoint = endpoint
        self.protocol_version = protocol_version
        self.timeout = timeout
        self.session_id: str | None = None

    def send(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": self.protocol_version,
            "User-Agent": USER_AGENT,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        req = urllib.request.Request(self.endpoint, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            sid = resp.headers.get("Mcp-Session-Id")
            if sid:
                self.session_id = sid
            content_type = (resp.headers.get("Content-Type") or "").lower()
            raw = resp.read().decode("utf-8", errors="replace").strip()
            if not raw or resp.status == 202:
                return []
            if "text/event-stream" in content_type:
                return _parse_sse_payload(raw)
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, dict)]
            if isinstance(parsed, dict):
                return [parsed]
            return []


def handle_jsonrpc_line(
    line: str,
    sender: Callable[[dict[str, Any]], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Process one newline-delimited JSON-RPC message from stdio and return response dicts."""
    stripped = line.strip()
    if not stripped:
        return []
    try:
        msg = json.loads(stripped)
    except json.JSONDecodeError as exc:
        return [
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {exc}"},
            }
        ]
    if not isinstance(msg, dict):
        return [
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Invalid Request: expected JSON object"},
            }
        ]

    has_id = "id" in msg and msg["id"] is not None
    method = msg.get("method")

    # Local ping works even offline.
    if method == "ping" and has_id:
        return [{"jsonrpc": "2.0", "id": msg["id"], "result": {}}]

    try:
        responses = sender(msg)
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:300]
        if not has_id:
            return []
        return [
            {
                "jsonrpc": "2.0",
                "id": msg["id"],
                "error": {"code": -32603, "message": f"Upstream HTTP {exc.code}: {err_body}"},
            }
        ]
    except Exception as exc:  # noqa: BLE001
        if not has_id:
            return []
        return [
            {
                "jsonrpc": "2.0",
                "id": msg["id"],
                "error": {"code": -32603, "message": f"Upstream transport error: {exc}"},
            }
        ]

    # Never emit unsolicited responses for notifications without an id.
    if not has_id:
        return [r for r in responses if "id" in r and r["id"] is not None]
    return responses


def run_stdio_loop(
    in_stream: TextIO,
    out_stream: TextIO,
    sender: Callable[[dict[str, Any]], list[dict[str, Any]]],
) -> int:
    for line in in_stream:
        for resp in handle_jsonrpc_line(line, sender):
            out_stream.write(json.dumps(resp, separators=(",", ":")) + "\n")
            out_stream.flush()
    return 0


def run_self_check(endpoint: str, timeout: float) -> int:
    transport = StreamableHttpTransport(endpoint=endpoint, timeout=timeout)
    init_res = transport.send(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": DEFAULT_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "market-news-stdio-bridge", "version": "1.0.0"},
            },
        }
    )
    list_res = transport.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tools = []
    if list_res and isinstance(list_res[0].get("result"), dict):
        tools = list_res[0]["result"].get("tools", [])
    summary = {
        "endpoint": endpoint,
        "initialized": bool(init_res and "result" in init_res[0]),
        "server_info": (init_res[0].get("result", {}).get("serverInfo") if init_res else None),
        "tool_count": len(tools),
        "tools": [t.get("name") for t in tools if isinstance(t, dict)],
    }
    print(json.dumps(summary, indent=2))
    return 0 if summary["initialized"] and summary["tool_count"] > 0 else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--endpoint",
        default=os.environ.get("MCP_ENDPOINT", DEFAULT_ENDPOINT),
        help=f"Remote MCP Streamable HTTP URL (default: {DEFAULT_ENDPOINT})",
    )
    ap.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds")
    ap.add_argument("--check", action="store_true", help="Verify connectivity and list remote MCP tools (free)")
    args = ap.parse_args(argv)

    if args.check:
        return run_self_check(args.endpoint, args.timeout)

    transport = StreamableHttpTransport(endpoint=args.endpoint, timeout=args.timeout)
    return run_stdio_loop(sys.stdin, sys.stdout, transport.send)


if __name__ == "__main__":
    raise SystemExit(main())
