# Season 3: stock P/E buckets, pre-registration

Written and committed before any stock-level P/E strategy ran.

## Question

Sorting stocks by P/E alone, do cheap stocks beat dear ones in the 1,000 most liquid US stocks, after costs, and is any difference more than the market moving everything together?

## Who wrote the strategies

As in Season 2: ideas from Harsh, files written once by the builder before any ran, no changes afterwards. Weaker evidence than an independent proposer.

## Setup

- Prices, universe, costs, references: as in Season 1.
- Earnings: SEC EDGAR XBRL, trailing twelve months of diluted EPS (basic if diluted is missing), each period as first reported, usable from the business day after the filing. Converted to the price archive's split-adjusted units (see `src/lucky/edgar.py`). Unknown after 15 months without a new filing.
- Ticker matching: live tickers through the SEC's current ticker file; delisted ones through their company name in SEC fails-to-deliver data, matched to EDGAR's list of every name a company has used. Unmatched stocks have no P/E and can't be held by a P/E strategy. Coverage by year is reported with the results.
- Periods: `config/periods/marketparquet-edgar.toml`. Discovery 2011-2017, validation 2018-2019, vault B 2020 to June 2026. Per-stock P/E only exists from about 2010, so there's no early vault and the only vault is inside the model's training data.

Strategies (`strategies/pe/s*.py`), all monthly and equally weighted:

| file | rule |
|---|---|
| s0 | every universe stock with known earnings (the pool the buckets come from) |
| s1 | P/E below the median of profitable stocks |
| s2 | P/E above that median |
| s3 | long the cheapest fifth, short the dearest fifth, dollar-neutral |
| s4 | stocks with negative trailing earnings |
| s5 | profitable stocks whose P/E is below their own one-year median |
| s6 | the cheapest tenth only |

## Gates

As before: discovery deflated Sharpe at least 0.95, a positive validation answer, and positive net and alpha Sharpe in the vault. Every strategy is frozen and the vault opened once for each.

## What else gets reported

Since the point is a gut check: each bucket's beta and correlation with SPY, so "do they all just move with the market" is answered directly.

## Prediction

None passes. Buckets s0, s1, s2, s5 and s6 will correlate above 0.9 with the market and differ mainly in beta. Over 2011-2026 the dear half (s2) beats the cheap half (s1); the long-short spread (s3) is negative or near zero. Loss-makers (s4) have the worst Sharpe of the long-only buckets.
