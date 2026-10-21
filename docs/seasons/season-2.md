# Season 2: P/E, pre-registration

Written and committed before any P/E strategy ran.

## Question

Does valuation, measured by P/E and nothing else, tell you when to own stocks (market level) or which stocks to own (stock level)?

## Who wrote the strategies

Not an independent proposer. Harsh asked for the ideas ("below or above median or average, or other buckets"), and the builder (Claude, the same conversation that built the judge and has seen Season 1's results) wrote them in `strategies/pe/`. Each file was written once, before any of them ran, with no parameter changes afterwards. The builder knows roughly how markets and valuations moved in these years, so this season answers "what happened to these simple rules", not "can an LLM discover something". It's the weaker kind of evidence, and the write-up will say so.

## Setup

Same data, universe, costs, references and periods as Season 1 (`config/periods/marketparquet.toml`), plus `--fundamentals`:

- **Market P/E and CAPE**: Shiller's monthly S&P 500 data (shillerdata.com, file downloaded 2026-10-21). Earnings lagged six months. Each month's value is usable only once that month is over.
- Market strategies hold the equal-weighted universe or cash. Cash earns nothing here (no interest modelled), which handicaps every rule that sits out.
- Baseline trial: `strategies/baselines/equal_weight.py` (what the market strategies hold when they're in).

Market strategies (`strategies/pe/m*.py`):

| file | rule |
|---|---|
| m1 | P/E below its 10-year median: in; else cash |
| m2 | P/E below its 10-year average: in; else cash |
| m3 | CAPE below its 10-year median: in; else cash |
| m4 | CAPE rank in the past 20 years: cheapest third 100%, middle 60%, dearest 20% |
| m5 | CAPE below its median over all history (since the 1880s): in; else cash |

Stock-level strategies will be added in a separate season, because per-stock earnings from SEC filings only exist from about 2011, so they need their own periods. That season gets its own pre-registration.

## Gates

As in Season 1: discovery deflated Sharpe at least 0.95, a positive validation answer, and positive net and alpha Sharpe in both vaults. Every strategy is frozen and both vaults are opened once for each, whatever discovery says.

## Prediction

None passes. Valuation timing is a slow signal with a handful of regime switches in a decade, so its statistics will be weak however it does. I expect the median and CAPE rules to cut drawdowns and give up return, ending with Sharpe close to holding the market, and m5 to sit in cash most of the time and lag badly. m2 should differ most from m1, because earnings collapses push the average around.
