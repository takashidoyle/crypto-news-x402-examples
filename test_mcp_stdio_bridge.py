#!/usr/bin/env python3
"""Mac offline unit tests for mcp_stdio_bridge.py."""

from __future__ import annotations

import io
import json
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mcp_stdio_bridge as bridge


def test_stdio_loop_forwards_initialize_and_tools_list_and_skips_notifications() -> None:
    seen: list[str] = []

    def fake_send(msg: dict) -> list[dict]:
        seen.append(str(msg.get("method")))
        if msg.get("method") == "initialize":
            return [{"jsonrpc": "2.0", "id": msg["id"], "result": {"serverInfo": {"name": "market-news"}}}]
        if msg.get("method") == "notifications/initialized":
            return []
        if msg.get("method") == "tools/list":
            return [{"jsonrpc": "2.0", "id": msg["id"], "result": {"tools": [{"name": "get_market_signal_batch"}]}}]
        return []

    inp = io.StringIO(
        "\n".join(
            [
                json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
                json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
                json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
                json.dumps({"jsonrpc": "2.0", "id": 3, "method": "ping"}),
                "",
            ]
        )
        + "\n"
    )
    out = io.StringIO()
    rc = bridge.run_stdio_loop(inp, out, fake_send)
    assert rc == 0
    lines = [json.loads(ln) for ln in out.getvalue().splitlines() if ln.strip()]
    assert [r["id"] for r in lines] == [1, 2, 3]
    assert lines[1]["result"]["tools"][0]["name"] == "get_market_signal_batch"
    assert lines[2]["result"] == {}
    assert seen == ["initialize", "notifications/initialized", "tools/list"]


def test_sse_parser_handles_multi_event_payloads() -> None:
    raw = (
        "event: message\n"
        'data: {"jsonrpc":"2.0","id":7,"result":{"ok":true}}\n\n'
        "data: [DONE]\n\n"
    )
    msgs = bridge._parse_sse_payload(raw)
    assert len(msgs) == 1
    assert msgs[0]["id"] == 7
    assert msgs[0]["result"]["ok"] is True


def test_parse_error_and_http_error_return_jsonrpc_error_envelopes() -> None:
    bad = bridge.handle_jsonrpc_line("{not valid json", lambda _m: [])
    assert bad[0]["error"]["code"] == -32700

    def fail_http(_m: dict) -> list[dict]:
        raise urllib.error.HTTPError("https://goat-lighthouse.site/mcp", 503, "Service Unavailable", {}, io.BytesIO(b"busy"))

    res = bridge.handle_jsonrpc_line(json.dumps({"jsonrpc": "2.0", "id": 9, "method": "tools/list"}), fail_http)
    assert res[0]["id"] == 9
    assert res[0]["error"]["code"] == -32603
    assert "503" in res[0]["error"]["message"]
