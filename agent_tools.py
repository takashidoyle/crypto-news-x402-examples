#!/usr/bin/env python3
"""Framework-agnostic tool definitions & stdlib runner for Market News API (https://goat-lighthouse.site).

Works out-of-the-box with OpenAI function calling, Anthropic tool use, LangChain, CrewAI,
or custom trading agents. Runs unpaid free calls and 402 quote checks with Python 3.10+ stdlib only.
Pass a Bearer pass key via `MARKET_NEWS_PASS_KEY` (from $3 week / $9 month passes) to fetch paid
routes directly with zero extra packages, or use `example.py --pay` / `example_batch.py --pay` for x402.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

BASE_URL = "https://goat-lighthouse.site"
USER_AGENT = "market-news-agent-tools/1.0"

OPENAI_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_market_signal_batch",
            "description": (
                "Fetch one cross-market AI-scored news and signal batch ($0.10 USDC via x402 or Bearer pass) "
                "across crypto, equities, forex, commodities, and macro with sentiment counts, optional coin slices, "
                "Binance listing alerts, and tracked coin snapshot."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "markets": {
                        "type": "string",
                        "description": "Comma-separated markets (default: crypto,equities,macro).",
                    },
                    "coins": {
                        "type": "string",
                        "description": "Optional comma-separated tickers up to 10 (e.g. BTC,ETH,SOL,DOGE).",
                    },
                    "limit_per_slice": {"type": "integer", "minimum": 1, "maximum": 25},
                    "relevant": {"type": "boolean"},
                    "first_in_group": {"type": "boolean"},
                    "since": {"type": "string", "description": "Optional ISO UTC timestamp for incremental polling."},
                    "compact": {"type": "boolean", "description": "Use compact payload (format=compact)."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_crypto_news",
            "description": "Fetch latest 48h AI-scored crypto headlines ($0.005 USDC via x402 or Bearer pass).",
            "parameters": {
                "type": "object",
                "properties": {
                    "coin": {"type": "string", "description": "Ticker such as BTC, ETH, SOL, DOGE."},
                    "q": {"type": "string", "description": "Optional 2-60 char title filter."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    "since": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_free_delayed_news",
            "description": "Fetch free delayed sample headlines with no payment or pass required.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_supported_coins",
            "description": "Fetch free list of tracked market snapshot coins and news tickers.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def build_tool_url(tool_name: str, arguments: dict[str, Any] | None = None, base_url: str = BASE_URL) -> str:
    args = dict(arguments or {})
    if tool_name == "get_free_delayed_news":
        return f"{base_url}/v1/free/latest"
    if tool_name == "list_supported_coins":
        return f"{base_url}/v1/coins"
    if tool_name == "get_market_signal_batch":
        params: dict[str, str] = {}
        if args.get("markets"):
            params["markets"] = str(args["markets"])
        if args.get("coins"):
            params["coins"] = str(args["coins"])
        if args.get("limit_per_slice") is not None:
            params["limit_per_slice"] = str(int(args["limit_per_slice"]))
        if args.get("relevant"):
            params["relevant"] = "true"
        if args.get("first_in_group"):
            params["first_in_group"] = "true"
        if args.get("since"):
            params["since"] = str(args["since"])
        if args.get("compact"):
            params["format"] = "compact"
        qs = urllib.parse.urlencode(params)
        return f"{base_url}/v1/news/batch" + (f"?{qs}" if qs else "")
    if tool_name == "get_crypto_news":
        params = {}
        for k in ("coin", "q", "since"):
            if args.get(k):
                params[k] = str(args[k])
        if args.get("limit") is not None:
            params["limit"] = str(int(args["limit"]))
        qs = urllib.parse.urlencode(params)
        return f"{base_url}/v1/crypto-news" + (f"?{qs}" if qs else "")
    raise ValueError(f"Unknown tool: {tool_name}")


def _http_get(url: str, headers: dict[str, str], timeout: float = 20.0) -> tuple[int, dict[str, Any]]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"raw_error": body[:500]}
        return exc.code, parsed


def invoke_tool(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    *,
    pass_key: str | None = None,
    base_url: str = BASE_URL,
    fetcher: Callable[[str, dict[str, str], float], tuple[int, dict[str, Any]]] = _http_get,
) -> dict[str, Any]:
    """Execute one tool call; returns structured dict with status (`200` data or `402` x402 quote)."""
    url = build_tool_url(tool_name, arguments, base_url=base_url)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    token = pass_key if pass_key is not None else os.environ.get("MARKET_NEWS_PASS_KEY")
    if token:
        headers["Authorization"] = f"Bearer {token.strip()}"
    status, payload = fetcher(url, headers, 20.0)
    return {"tool": tool_name, "url": url, "http_status": status, "payment_required": status == 402, "payload": payload}


if __name__ == "__main__":
    print(json.dumps(invoke_tool("get_market_signal_batch", {"markets": "crypto,equities,macro", "coins": "BTC,ETH", "compact": True}), indent=2)[:1200])
