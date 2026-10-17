# 013 Data download
Status: done
Problem: getting the MarketParquet archive needs a loop over yearly manifests, short-lived links, rate limits and a folder layout the judge expects. A one-off curl loop saves files under the API's names, in the current folder, with no resume or verification.
Outcome: `lucky data download` fetches chosen datasets (default `stock_daily`, `etf_daily`) into `<dest>/by_date/<dataset>/YYYY-MM-DD.parquet`, reading the API key from `MARKETPARQUET_API_KEY` only (never an argument, never printed). It skips files already present at the right size, verifies each download's byte count, writes atomically, retries with backoff and honours `Retry-After` on 429. The reader also accepts MarketParquet's own `stock_daily_YYYY-MM-DD.parquet` names.
Done when: tests against a fake API cover layout, resume, size mismatch, 429 handling, and that the key never appears in output or errors.
