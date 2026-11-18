"""Inspect coins and an unpaid quote, or explicitly pay for the same request."""
import asyncio
import json
import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "https://goat-lighthouse.site"
URL = f"{BASE}/v1/crypto-news?limit=1"
HEADERS = {"User-Agent": "market-news-x402-example/1.0"}


def inspect_quote():
    """Read the free coins catalogue and payment requirements without signing."""
    with urlopen(Request(f"{BASE}/v1/coins", headers=HEADERS), timeout=15) as response:
        print("Coins:", json.dumps(json.load(response)))
    try:
        with urlopen(Request(URL, headers=HEADERS), timeout=15) as response:
            raise RuntimeError(f"Expected 402, received {response.status}")
    except HTTPError as error:
        if error.code != 402:
            raise
        print("Quote status:", error.code)
        print("Quote:", error.read().decode())


async def pay():
    """Pay once with the explicitly supplied Base wallet."""
    from eth_account import Account
    from x402 import x402Client
    from x402.http.clients import x402HttpxClient
    from x402.mechanisms.evm import EthAccountSigner
    from x402.mechanisms.evm.exact.register import register_exact_evm_client

    client = x402Client()
    register_exact_evm_client(client, EthAccountSigner(Account.from_key(os.environ["EVM_PRIVATE_KEY"])), networks="eip155:8453")
    async with x402HttpxClient(client, timeout=30.0) as http:
        response = await http.get(URL, headers=HEADERS)
        response.raise_for_status()
        print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    inspect_quote()
    if sys.argv[1:] == ["--pay"]:
        asyncio.run(pay())
    elif sys.argv[1:]:
        raise SystemExit("Usage: python3 example.py [--pay]")
