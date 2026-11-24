#!/usr/bin/env python3
"""Mac offline unit tests for agent_tools.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_tools as at


def test_build_tool_url_encodes_batch_and_crypto_params() -> None:
    u = at.build_tool_url(
        "get_market_signal_batch",
        {"markets": "crypto,equities,macro", "coins": "BTC,ETH", "limit_per_slice": 5, "compact": True, "relevant": True},
    )
    assert u.startswith("https://goat-lighthouse.site/v1/news/batch?")
    assert "format=compact" in u
    assert "relevant=true" in u
    assert "limit_per_slice=5" in u

    u2 = at.build_tool_url("get_crypto_news", {"coin": "BTC", "limit": 3})
    assert u2 == "https://goat-lighthouse.site/v1/crypto-news?coin=BTC&limit=3"
    assert at.build_tool_url("list_supported_coins") == "https://goat-lighthouse.site/v1/coins"


def test_invoke_tool_passes_bearer_pass_and_flags_402_quote() -> None:
    captured: list[tuple[str, dict[str, str]]] = []

    def fake_get(url: str, headers: dict[str, str], _timeout: float):
        captured.append((url, headers))
        if "Authorization" in headers:
            return 200, {"count": 2, "by_market": {"crypto": {"count": 2}}}
        return 402, {"x402Version": 2, "accepts": [{"amount": "100000"}]}

    q = at.invoke_tool("get_market_signal_batch", {"compact": True}, pass_key="", fetcher=fake_get)
    assert q["http_status"] == 402 and q["payment_required"] is True

    ok = at.invoke_tool("get_market_signal_batch", {"compact": True}, pass_key="demo-pass-token", fetcher=fake_get)
    assert ok["http_status"] == 200 and ok["payment_required"] is False
    assert captured[-1][1]["Authorization"] == "Bearer demo-pass-token"
