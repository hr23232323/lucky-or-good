# Season 2: results (market P/E timing)

Pre-registration: [`season-2.md`](season-2.md).

## Outcome

Nothing passed. No rule beat holding the market in discovery; the best deflated Sharpe was the equal-weight baseline's 0.84. Every strategy was frozen and both vaults opened once each.

Net Sharpe, and the share of months each rule was invested:

| rule | 2004-14 Sharpe | in market | 2001-03 Sharpe | in market | 2020-26 Sharpe | in market |
|---|---:|---:|---:|---:|---:|---:|
| SPY buy and hold (reference) | 0.39 | 100% | -0.13 | 100% | 0.76 | 100% |
| 60/40 (reference) | 0.50 | | n/a | | 0.67 | |
| equal weight (always in) | 0.40 | 100% | 0.39 | 100% | 0.50 | 100% |
| m1 P/E below 10y median | 0.19 | 72% | 0.55 | 8% | 0.27 | 15% |
| m2 P/E below 10y average | 0.32 | 87% | 0.55 | 8% | 0.52 | 21% |
| m3 CAPE below 10y median | 0.33 | 86% | 0.64 | 53% | 0.61 | 13% |
| m4 CAPE terciles, graded | 0.40 | 66%* | 0.72 | 33%* | 0.53 | 21%* |
| m5 CAPE below long-run median | 0.27 | 5% | 0.00 | 0% | 0.00 | 0% |

\* average exposure (20% to 100%).

## What it says

- **Trailing P/E looked cheap right before the 2008 crash.** Earnings peak just before a recession, so P/E falls as prices start to fall. m1-m3 were invested through 2008 and took the full 62% drawdown.
- **The rules mostly sat out 2001-2003 and 2020-2026.** That avoided the dot-com bust (good) and missed most of the recent rally (bad). With cash earning nothing here, sitting out costs a lot of return; the Sharpe ratios stay respectable only because the few invested months went well.
- **CAPE did better than one-year P/E**, as the textbook says, but it was invested in only 13% of 2020-26 and still lost to SPY on Sharpe.
- **m5 never bought.** By the standard of the whole history since the 1880s, the US market has been expensive for essentially the whole 26 years.
- So: in the market, yes, prices of everything move together and valuation shifts slowly. P/E timing is a handful of decisions per decade, and in these periods it mostly said "stay out".

## Against the prediction

Predicted: none passes (right); lower drawdowns and Sharpe close to the market (mixed: drawdowns were lower in the vaults but not in 2004-14); m5 in cash and lagging (right); m2 the most different from m1 (it was, in 2020-26).

## Caveats

- Ideas from Harsh, written by the builder, who knows how these years went. Not an independent test.
- Cash earns 0%. With T-bill interest, the out-of-market months would have earned something, mostly in 2001-2007 and 2023-2026.
- Shiller's file is today's vintage, so any revisions to old S&P earnings are in it.
- No dividends.
