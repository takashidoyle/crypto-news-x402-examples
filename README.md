
# crypto-news-x402-examples

[![Market News API MCP connector](https://glama.ai/mcp/connectors/site.goat-lighthouse/market-news/badges/score.svg)](https://glama.ai/mcp/connectors/site.goat-lighthouse/market-news)

Examples and a zero-dependency local MCP `stdio` bridge for the [Market News API](https://goat-lighthouse.site/), by Takashi Doyle. Crypto, equities, forex, commodities, macro headlines, and Binance exchange announcements include publisher, timestamps, market/ticker/event tags, and an AI impact score with a one-sentence reason where scored. Scores are model estimates, not trading advice. Some records may lack scores or labels.

Start free: [catalogue](https://goat-lighthouse.site/), [delayed sample](https://goat-lighthouse.site/v1/free/latest), [supported coins and news tickers](https://goat-lighthouse.site/v1/coins), [A2A agent card](https://goat-lighthouse.site/.well-known/agent-card.json), [research journal](https://goat-lighthouse.site/journal/macro-shocks-vs-reactive-crypto-headlines), and [OpenAPI](https://goat-lighthouse.site/openapi.json). Query the latest news by `coin=BTC` or another currently supported ticker, use the fixed-coin routes [`/v1/bitcoin-news`](https://goat-lighthouse.site/journal/bitcoin-news-api-ai-agents) and [`/v1/ethereum-news`](https://goat-lighthouse.site/journal/ethereum-news-api-ai-agents), or pull a grouped cross-market snapshot in one call with `/v1/news/batch`. The free coins response distinguishes news tickers from the market snapshot list. Paid routes return HTTP `402` until an x402 payment or Bearer pass key is supplied. Latest-news responses carry `next_before` while older matching records remain; pass it as `before` to page back through the 48 hours. Add `q=etf` (or any 2 to 60 character keyword) to keep only headlines whose title contains it; a paid request with no match is refused before any charge.

Prices checked 24 November 2026: crypto news, latest market news, latest announcements, and market snapshot `$0.005` per call; listing events `$0.01`; crypto news day and market news day `$0.05` each (available UTC archive dates are enumerated live at [`/health`](https://goat-lighthouse.site/health)); multi-market signal batch (`/v1/news/batch`) `$0.10`; annual announcement archive `$0.25`. Passes are `$3` for seven days and `$9` for 30 days. The response quote is authoritative; prices can change. Pay-per-call supports USDC on Base or Solana; the scripts below use Base.

Measured 18 November 2026: one scored headline record is about 150 to 290 tokens, while reading the article behind one headline took 1,200 to 1,700 tokens as extracted text, or 42,000 to 55,000 as raw HTML, before any scoring. These are character-count estimates; actual sizes vary.

## Inspect without paying

Python 3.10+ and Node 24+ each run without packages for the free catalogue request and unpaid `402` quote:

```sh
python3 example.py
python3 example_batch.py
python3 agent_tools.py
node example.ts
node example_batch.ts
```

None of these sign or pay unless you explicitly pass `--pay` (or supply a Bearer pass key via `MARKET_NEWS_PASS_KEY` to `agent_tools.py`).

## Framework Tool Calling (OpenAI / LangChain / CrewAI)

`agent_tools.py` exports `OPENAI_TOOLS` (JSON function-calling schemas) and a zero-dependency `invoke_tool(...)` runner supporting free routes, unpaid x402 quotes, and Bearer pass access (`MARKET_NEWS_PASS_KEY`).

## Pay once on Base

Fund your own Base wallet with USDC and provide its private key through `EVM_PRIVATE_KEY` in your environment. Never commit it. `--pay` signs a real x402 payment and spends real USDC (`$0.005` for `example.py`, `$0.10` for `example_batch.py` at the date above).

```sh
python3 -m pip install 'x402[httpx,evm]==2.28.0' eth-account
python3 example.py --pay
python3 example_batch.py --pay
```

```sh
npm install @x402/fetch@2.31.0 @x402/evm@2.31.0 viem@2.58.0
node example.ts --pay
```

Package versions, names, and call signatures were checked against [PyPI](https://pypi.org/project/x402/), [npm](https://www.npmjs.com/package/@x402/fetch), and the official [x402 source](https://github.com/coinbase/x402). Please open an issue if a payment step fails.

## MCP (Streamable HTTP & Local `stdio` Bridge)

Remote endpoint: `https://goat-lighthouse.site/mcp` (Streamable HTTP, 15 tools). Authentication: none — there is no login or API key, and paid data is paid per call with x402 inside the tool call.

### Option A: Remote Streamable HTTP clients

Use [mcp.json](mcp.json) with any MCP client that supports remote Streamable HTTP servers:

```json
{
  "mcpServers": {
    "market-news": {
      "type": "http",
      "url": "https://goat-lighthouse.site/mcp"
    }
  }
}
```

### Option B: Local `stdio` clients (Claude Desktop, Cursor, Windsurf, Cline)

Run the zero-dependency Python 3.10+ bridge [mcp_stdio_bridge.py](mcp_stdio_bridge.py) (stdlib only, no `pip install` needed). First verify connectivity and list all 15 tools for free:

```sh
python3 mcp_stdio_bridge.py --check
```

Then configure your `stdio` MCP host using [mcp-stdio.json](mcp-stdio.json) (pointing to the path of `mcp_stdio_bridge.py`):

```json
{
  "mcpServers": {
    "market-news": {
      "command": "python3",
      "args": ["/path/to/mcp_stdio_bridge.py"]
    }
  }
}
```

### Available MCP Tools (15)

- **Free discovery & quotes**: `market_catalogue`, `news_sample`, `list_supported_coins`, `check_pass`.
- **Paid market news & data (free quote when called without payment)**:
  - `get_market_signal_batch` (`$0.10`): one cross-market snapshot across crypto, equities, forex, commodities, and macro with sentiment counts, optional per-coin slices, listing alerts, and tracked prices.
  - `get_crypto_news` (`$0.005`), `get_latest_news` (`$0.005`), `get_latest_announcements` (`$0.005`), `get_market_snapshot` (`$0.005`).
  - `get_listing_events` (`$0.01`), `get_news_day` (`$0.05`), `get_crypto_news_day` (`$0.05`), `get_announcement_history` (`$0.25`).
- **Access passes**: `buy_week_pass` (`$3`), `buy_month_pass` (`$9`).

Direct unpaid check over HTTP:

```sh
curl -sS https://goat-lighthouse.site/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json' \
  -H 'MCP-Protocol-Version: 2025-06-18' \
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_supported_coins","arguments":{}}}'
curl -sS https://goat-lighthouse.site/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json' \
  -H 'MCP-Protocol-Version: 2025-06-18' \
  --data '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_market_signal_batch","arguments":{"markets":"crypto,equities,macro","coins":"BTC,ETH","format":"compact"}}}'
```

Tool discovery and quotes are free. To pay for data through MCP, use a client that supports in-tool x402 payments; the client signs the returned payment requirements and retries the same tool with the payment in `_meta["x402/payment"]`. For Bearer pass access use the supported REST routes. Consult the [service documentation](https://goat-lighthouse.site/docs).

MIT licensed. Data is subject to its original terms.
