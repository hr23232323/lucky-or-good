# Season 1: results

Pre-registration: [`season-1.md`](season-1.md). Proposer notes and each strategy's full case: [`strategies/candidates/NOTEBOOK.md`](../../strategies/candidates/NOTEBOOK.md). The full report (charts, every trial, sealed periods) is built with `lucky report --include-sealed`.

## Outcome

No strategy passed. None of the 15 proposed strategies, and none of the 7 baselines, cleared the first gate (discovery deflated Sharpe at least 0.95). The best deflated Sharpe at the end of the season was 0.20, for a baseline. No validation look was spent.

Every strategy was then frozen and both vaults opened once for each, as pre-registered.

## Numbers

Net Sharpe after costs. Discovery is 2004-2014 (the only period the proposer saw), vault A 2001-2003, vault B 2020 to June 2026. References are not trials.

| strategy | kind | discovery | vault A | vault B |
|---|---|---:|---:|---:|
| SPY buy and hold | reference | 0.39 | -0.13 | 0.76 |
| 60/40 SPY/IEF | reference | 0.50 | n/a* | 0.67 |
| buy the dip | baseline | 0.71 | 1.03 | 0.10 |
| 013 momentum / low-vol regime switch | market-regime | 0.61 | 0.39 | 0.15 |
| 006 sell in May | popular-online | 0.58 | 0.74 | 0.20 |
| 012 breadth regime timing | market-regime | 0.54 | 0.18 | 0.36 |
| 010 composite rank (vol, momentum, MAX) | numeric | 0.53 | 0.65 | 0.56 |
| low volatility | baseline | 0.52 | 0.48 | 0.47 |
| equal weight | baseline | 0.40 | 0.39 | 0.50 |
| weekly reversal | baseline | 0.39 | 0.74 | 0.51 |
| 200-day trend | baseline | 0.39 | 0.08 | 0.67 |
| 008 relative breakout on volume | pattern | 0.37 | 0.09 | 0.54 |
| 011 residual z-score reversal | numeric | 0.36 | 0.99 | 0.54 |
| 52-week high | baseline | 0.35 | -0.40 | 0.69 |
| 12-1 momentum | baseline | 0.34 | 0.61 | 0.83 |
| 015 correlation-peer momentum | novel | 0.32 | -0.13 | 0.33 |
| 004 RSI(2) pullback | popular-online | 0.32 | 1.05 | 0.13 |
| 007 gap-down reversal candle | pattern | 0.13 | 0.38 | 0.36 |
| 005 MACD bullish state | popular-online | 0.13 | -0.15 | 0.34 |
| 001 MAX effect long-short | research | -0.11 | -0.23 | -0.33 |
| 014 quiet accumulation | novel | -0.58 | -0.71 | -0.23 |
| 003 high-volume return premium | research | -0.59 | 0.81 | 0.34 |
| 002 return seasonality | research | -0.70 | 0.13 | -0.53 |
| 009 wide-range strong close, hedged | pattern | -1.16 | -1.83 | -0.66 |

\* IEF starts in mid-2002, so the 60/40 reference covers only the rebound half of vault A. The report leaves it out there rather than compare it over different dates (its Sharpe over those 18 months was 1.01).

## What it says

- **Nothing beat holding the market where it was hard to.** In vault B, where SPY had a Sharpe of 0.76, no proposed strategy beat it, and only one baseline did (12-1 momentum, 0.83). In vault A, a falling market (SPY -0.13), most long books "beat" SPY because equal-weighted stocks beat cap-weighted ones in 2001-2003; that's a size tilt, not skill.
- **The best discovery ideas shrank most.** The top four proposed strategies in discovery (013, 006, 012, 010; Sharpe 0.53 to 0.61) scored 0.15 to 0.56 in vault B. This is the expected-max-of-noise effect the deflated Sharpe warns about, seen directly.
- **Discovery rank did carry some information**, but mostly about structure, not skill: Spearman 0.46 with vault A and 0.36 with vault B across all 22. Long-only books stay positive in rising markets and long-short books hover near zero, so ranking by discovery Sharpe mostly ranks by equity exposure.
- **Consistent losers were consistent for known reasons.** 009 lost in every period (a cost construction mistake the proposer diagnosed in discovery). 014 and 001 stayed negative.
- **One sign flip worth a note.** 003 (high-volume premium) was negative in discovery (t -1.9) and positive in both vaults with positive alpha. The proposer recorded the negative result and didn't flip it, as the rules require. With 22 strategies and three periods, one such flip is unremarkable.

## Against the prediction

Predicted: none of the 15 passes all three gates (right); two to four clear the discovery bar (wrong, none did); discovery Sharpe barely predicts vault Sharpe (partly right: weakly positive, mostly through market exposure); short-horizon ideas do worst after costs (mixed: 004 and 011 did well in vault A and poorly in vault B).

## Caveats

- Vault B is inside the proposing model's training data. Vault A is the cleaner test and is only three years.
- No dividends. SPY, 60/40 and every long book are understated by roughly 1.5 to 2% a year.
- "Alpha" here is against SPY only. Factor attribution (#2) would show how much is size and low-beta tilts.
- Residual bad prints remain in the data (documented in `docs/design.md`); the engine flagged a few position-days in discovery, none that change a conclusion.
- Process: the builder's first vault script recorded a duplicate freeze for buy the dip (ledger #24 and #25) and was stopped before opening any vault. See `LEARNINGS.md`. The ledger verifies intact.
