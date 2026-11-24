// Inspect an unpaid 402 quote for /v1/news/batch ($0.10 cross-market snapshot), or pay explicitly.
const base = "https://goat-lighthouse.site";
const url = `${base}/v1/news/batch?markets=crypto,equities,macro&coins=BTC,ETH&format=compact`;

async function main(): Promise<void> {
  const quote = await fetch(url, { headers: { "User-Agent": "market-news-x402-batch-ts/1.0" } });
  if (quote.status !== 402) throw new Error(`Expected 402, got ${quote.status}`);
  console.log("Route:", url);
  console.log("Quote status:", quote.status);
  console.log("Quote:", await quote.text());
  if (process.argv.slice(2).length === 0) return;
  if (process.argv.slice(2).join(" ") !== "--pay") throw new Error("Usage: node example_batch.ts [--pay]");
  const key = process.env.EVM_PRIVATE_KEY;
  if (!key || !/^0x[0-9a-fA-F]{64}$/.test(key)) throw new Error("Set EVM_PRIVATE_KEY to a Base wallet private key");
  const { x402Client, wrapFetchWithPayment } = await import("@x402/fetch");
  const { registerExactEvmScheme } = await import("@x402/evm/exact/client");
  const { privateKeyToAccount } = await import("viem/accounts");
  const client = new x402Client();
  registerExactEvmScheme(client, { signer: privateKeyToAccount(key as `0x${string}`), networks: ["eip155:8453"] });
  const response = await wrapFetchWithPayment(fetch, client)(url);
  if (!response.ok) throw new Error(`Paid request: HTTP ${response.status}`);
  console.log(JSON.stringify(await response.json(), null, 2));
}

main().catch((error: unknown) => { console.error(error); process.exitCode = 1; });
