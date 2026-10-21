# Season 1: pre-registration

Written and committed before any proposed strategy ran. The commit that last changes this file is the judge version for the whole season; changing the judge means a new season.

## Question

Can Claude, writing rules over price and volume features and seeing only the discovery period (2004 to 2014), find a strategy for the 1,000 most liquid US stocks that holds up, after costs, in periods it was never shown?

## Setup

- Data: MarketParquet daily bars, 2000-01-03 to 2026-10-16, cleaned as described in `docs/design.md`.
- Universe: top 1,000 US stocks by trailing 60-day median dollar volume, chosen each day from data before that day.
- Periods: `config/periods/marketparquet.toml`. Discovery 2004-2014 (open), validation 2015-2019 (coarse, noisy answers, 25 looks for the season), vault A 2001-2003, vault B 2020 to June 2026, forward July 2026 onwards.
- Proposer: Claude (claude-opus-5-5, training cutoff about June 2026), run as a separate agent following `.claude/skills/propose-strategy/SKILL.md`, with no access to the data, the season folder or the builder's conversation. 15 strategies, spread across: published research, ideas popular with retail traders online, chart patterns, statistical or numeric rules, market-regime ("macro") rules built from market-wide signals in the price data, and novel ideas of its own. Each is written up with its case before it is tested.
- Baselines: the seven strategies in `strategies/baselines/`, scored first, counted in the season's trial total.
- References (not trials): SPY bought and held, and a 60/40 balanced portfolio of SPY and IEF (7-10 year Treasuries), rebalanced daily. IEF starts in mid-2002, so the balanced reference doesn't cover the first 18 months of vault A.
- Costs: 3 bps per trade for the 200 most liquid names, 8 bps up to 1,000, 20 bps below; 50 bps a year to borrow for shorts.

## What counts as a pass

A strategy passes only if all of these hold:

1. Discovery: deflated Sharpe at least 0.95, counting every strategy scored in the season.
2. Validation: the coarse answer is positive.
3. Net Sharpe above zero in both vault A and vault B, and alpha Sharpe against SPY above zero in both.

So that the report can show how every idea held up, not just the winners, every strategy scored in discovery (baselines included) will be frozen and each vault opened once for it after the proposer finishes. Vault results are deflated by the number of vault opens. The forward block (July 2026 onwards) has under four months of data, too little to judge, and will be opened later.

## Known weaknesses, stated up front

- Vault B (2020 to 2026) is inside the proposing model's training data. A pass there is weaker evidence than a pass in vault A.
- Statistics can't detect look-ahead; the structural checks and a human reading of every finalist's code are the backstop.
- No dividends: buy-and-hold styles are understated by roughly 1.5 to 2% a year, including the SPY reference.
- The proposer runs on the same machine as the judge. Its transcript will be checked for any access to data or sealed results; any hit voids the season.
- Before writing this, the builder (also Claude, in a separate conversation from the proposer) ran the seven baselines in a shakedown season to test the judge on real data, so their discovery results were known to the builder: buy the dip 0.71, low volatility 0.52, equal weight 0.40, weekly reversal 0.39, 200-day trend 0.39, 52-week high 0.35, 12-1 momentum 0.34, against SPY's 0.39. The proposer hasn't seen these except through the season ledger, like any proposer.

## Prediction

My guess before running: none of the 15 passes all three gates. Two to four clear the discovery bar, and validation or a vault knocks them out. In the vaults, discovery Sharpe will barely predict vault Sharpe, and the short-horizon ideas (whose Sharpe collapses with one extra day of lag) will do worst after costs.
