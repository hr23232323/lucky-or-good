# Progress

Goal: an honest playground for LLM strategy research (see `intents/000-goal.md`).

| # | Intent | Status |
|---|---|---|
| 001 | Scaffold and agent files | done |
| 002 | Data layer (MarketParquet reader, point-in-time universe) | done |
| 003 | Synthetic market for tests | done |
| 004 | Engine: lag, costs, delistings | done |
| 005 | Metrics and deflated Sharpe | done |
| 006 | Periods and the gate | done |
| 007 | Trial ledger | done |
| 008 | Look-ahead and static checks | done |
| 009 | Baseline strategies and judge CLI | done |
| 010 | Anti-cheat test suite | done |
| 011 | Propose-strategy skill for local agents | done |
| 012 | Season report page | done |
| 013 | MarketParquet downloader | done |
| 014 | Real data: cleaning and scale | done |

## Next

1. Season 1 is done: no strategy passed ([results](docs/seasons/season-1-results.md)). Open the forward block once it has enough data (late 2027 at the earliest).
2. Factor attribution (#2) before any write-up, so "alpha" means alpha.
3. Dividends (#1): every number so far is price return only.

## Not yet

Tracked as [GitHub issues](https://github.com/hr23232323/lucky-or-good/issues): dividends (#1), factor attribution (#2), PBO (#3), judge as a separate service (#4), hourly bars (#5), point-in-time fundamentals (#6), leaderboard (#7), memory-vs-skill experiment (#8), full-archive performance (#9), ETF periods (#10), reused tickers (#11).
