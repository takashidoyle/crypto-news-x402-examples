"""Inspect an unpaid quote for /v1/news/batch ($0.10 cross-market snapshot), or pay explicitly."""
import asyncio
import json
import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "https://goat-lighthouse.site"
URL = f"{BASE}/v1/news/batch?markets=crypto,equities,macro&coins=BTC,ETH&format=compact"
HEADERS = {"User-Agent": "market-news-x402-batch-example/1.0"}


def inspect_quote():
    """Fetch the unpaid 402 quote for a cross-market signal batch without signing."""
    try:
        with urlopen(Request(URL, headers=HEADERS), timeout=15) as response:
            raise RuntimeError(f"Expected 402, received {response.status}")
    except HTTPError as error:
        if error.code != 402:
            raise
        print("Route:", URL)
        print("Quote status:", error.code)
        print("Quote:", error.read().decode())


async def pay():
    """Pay once ($0.10 USDC on Base) with the explicitly supplied wallet."""
    from eth_account import Account
    from x402 import x402Client
    from x402.http.clients import x402HttpxClient
    from x402.mechanisms.evm import EthAccountSigner
    from x402.mechanisms.evm.exact.register import register_exact_evm_client

    client = x402Client()
    register_exact_evm_client(
        client,
        EthAccountSigner(Account.from_key(os.environ["EVM_PRIVATE_KEY"])),
        networks="eip155:8453",
    )
    async with x402HttpxClient(client, timeout=30.0) as http:
        response = await http.get(URL, headers=HEADERS)
        response.raise_for_status()
        print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    inspect_quote()
    if sys.argv[1:] == ["--pay"]:
        asyncio.run(pay())
    elif sys.argv[1:]:
        raise SystemExit("Usage: python3 example_batch.py [--pay]")
