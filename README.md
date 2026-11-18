# crypto-news-x402-examples

Examples for the [Market News API](https://goat-lighthouse.site/), by Takashi Doyle. Crypto-labelled headlines include publisher, timestamps, tags and an AI estimate of crypto-price impact, with a reason when scored. Scores are model estimates, not trading advice. Some records may lack scores or labels.

Start free: [catalogue](https://goat-lighthouse.site/), [delayed sample](https://goat-lighthouse.site/v1/free/latest), [supported coins and news tickers](https://goat-lighthouse.site/v1/coins), and [OpenAPI](https://goat-lighthouse.site/openapi.json). Query the latest news by `coin=BTC` or another currently supported ticker, or use the fixed-coin routes [`/v1/bitcoin-news`](https://goat-lighthouse.site/journal/bitcoin-news-api-ai-agents) and [`/v1/ethereum-news`](https://goat-lighthouse.site/journal/ethereum-news-api-ai-agents). The free coins response distinguishes news tickers from the market snapshot list. The paid response is 402 until a payment is supplied. Latest-news responses carry `next_before` while older matching records remain; pass it as `before` to page back through the 48 hours. Add `q=etf` (or any 2 to 60 character keyword) to keep only headlines whose title contains it; a paid request with no match is refused before any charge.

Prices checked 18 November 2026: crypto news, latest market news, latest announcements and market snapshot $0.005 per call; listing events $0.01; crypto news day and market news day $0.05 each; annual announcement archive $0.25. Passes are $3 for seven days and $9 for 30 days. The response quote is authoritative; prices can change. Pay-per-call supports USDC on Base or Solana; the examples use Base.

Measured 18 November 2026: one scored headline record is about 150 to 290 tokens, while reading the article behind one headline took 1,200 to 1,700 tokens as extracted text, or 42,000 to 55,000 as raw HTML, before any scoring. These are character-count estimates; actual sizes vary.

## Inspect without paying

Python 3.10+ and Node 24+ each run without packages for the free request and unpaid quote:

```sh
python3 example.py
node example.ts
```

Both print the coins response and the 402 quote. They do not sign or pay unless the explicit `--pay` argument is supplied.

## Pay once on Base

Fund your own Base wallet with USDC and provide its private key through `EVM_PRIVATE_KEY` in your environment. Never commit it. The example request is $0.005 at the date above; `--pay` signs a payment and spends real funds.

```sh
python3 -m pip install 'x402[httpx,evm]==2.28.0' eth-account
python3 example.py --pay
```

```sh
npm install @x402/fetch@2.31.0 @x402/evm@2.31.0 viem@2.58.0
node example.ts --pay
```

Package versions, names and call signatures were checked against [PyPI](https://pypi.org/project/x402/), [npm](https://www.npmjs.com/package/@x402/fetch) and the official [x402 source](https://github.com/coinbase/x402) on 18 November 2026. Please open an issue if a payment step fails.

## MCP

Use [mcp.json](mcp.json) with an MCP client that supports remote streamable HTTP servers. Call `list_supported_coins` first. Then call `get_crypto_news` with, for example, `{"limit":"1"}` and no payment to see the price and matching count. If matching data is unavailable, the tool returns a refusal before charging. The other data tools are `get_latest_news`, `get_latest_announcements`, `get_news_day`, `get_crypto_news_day`, `get_market_snapshot`, `get_listing_events` and `get_announcement_history`. The free tools `market_catalogue` and `news_sample` describe coverage and a historical sample. `buy_week_pass` and `buy_month_pass` quote and buy passes, and the free `check_pass` reports a pass key's status and expiry (REST: `GET /v1/pass/status` with `Authorization: Bearer`).

For a direct unpaid check with a client supporting this protocol version:

```sh
curl -sS https://goat-lighthouse.site/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json' \
  -H 'MCP-Protocol-Version: 2025-06-18' \
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_supported_coins","arguments":{}}}'
curl -sS https://goat-lighthouse.site/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json' \
  -H 'MCP-Protocol-Version: 2025-06-18' \
  --data '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_crypto_news","arguments":{"limit":"1"}}}'
```

Tool discovery and quotes are free. To pay for data through MCP, use a client that supports in-tool x402 payments; the client signs the returned payment requirements and retries the same tool with the payment in `_meta["x402/payment"]`. For bearer pass access use the supported REST routes. Consult the [service documentation](https://goat-lighthouse.site/docs).

MIT licensed. Data is subject to its original terms.
