---
name: propose-strategy
description: Run the research loop as a strategy proposer. Use when asked to propose, write, test or iterate on trading strategies in this repo, or to "run the loop" or "try N strategies" against a season.
---

# Propose a strategy

You are the **proposer**. You write strategy files; the judge scores them. You never change the judge, and you never see sealed results. Read `AGENTS.md` first. `docs/design.md` explains timing, costs and the periods; the "Timing" and "Universe, costs, delistings" sections are worth a read.

## Before you start

1. `LUCKY_SEASON` must point at a season (ask the human if it isn't set). Run `uv run lucky ledger`. Entry #1 is the season itself; trials follow.
2. If the ledger has no baselines (files under `strategies/baselines/`), score them first: `for f in strategies/baselines/*.py; do uv run lucky judge "$f"; done`. They're the reference every candidate is compared with, and they count toward the season's trial total like everything else.
3. Read `strategies/candidates/NOTEBOOK.md`. It holds every earlier idea and what happened. Don't re-propose a dead idea unless you have a reason it should behave differently, and say what that reason is.
4. Skim `strategies/baselines/`. A candidate should be something else, or a clearly argued improvement on one.

## The loop (one strategy per pass)

1. **Hypothesis first.** Write one or two sentences: what market behaviour you expect, why it should exist (who is on the other side, what risk or friction keeps it there), and which direction. No hindsight: if your reason is "this worked in year X" or "these companies did well", stop and think of a rule instead.
2. **Write the file** at `strategies/candidates/NNN-short-name.py` (next free number) from `template.py` in this folder. Fill `META` honestly. `expected_sign` is the sign you expect for the portfolio's returns as written: `"+"` means the strategy as coded should make money. The report tells you whether it did.
3. **Check:** `uv run lucky check strategies/candidates/NNN-short-name.py`. Fix violations by changing the idea, not by disguising it.
4. **Judge in discovery:** `uv run lucky judge strategies/candidates/NNN-short-name.py`. The status is one of `scored`, `rejected` (static checks), `lookahead` (weights changed when future data was removed) or `error` (it crashed).
5. **Read the report like a skeptic.**
   - Compare net Sharpe with "noise alone would be expected to reach Sharpe X". Below that bar, it's not a finding.
   - Gross vs net Sharpe: if costs eat it, turnover is the problem.
   - "With one extra day of lag": only meaningful when the result is significant (t above 2). Then a collapse means the edge lives in the first day after the signal, which is fragile. On a near-zero Sharpe the difference is noise.
   - Alpha Sharpe and beta: high Sharpe with beta near 1 is just the market.
   - "Exposure" is gross exposure (long plus short), capped at 1.0. "Positions" is the average number of names held, both legs counted.
   - Costs are charged on every change in weights. Two constructions are cost traps: re-equal-weighting a changing set of names every day, and resizing a hedge across the whole universe every day. Rebalance on a schedule (weekly or monthly) unless the idea needs daily trading, and say why if it does.
6. **Write a notebook entry** (format below), even for failures. Failures are most of the value.
7. **Decide:** a new idea, a substantive change, or (rarely) validation.

If a result comes out significantly with the opposite sign, record it; don't flip the sign and rerun. That's fitting to the result. A later pass can test the reversed idea only with a mechanism argued first, and it still counts as a new trial.

## Validation is scarce

Only ask validation (`uv run lucky judge FILE --block validation`) when a candidate clears all of these in discovery:

- deflated Sharpe at least 0.9 (early in a season, with few trials, this is close to "probability the Sharpe is above zero", so it's a low bar on its own),
- t-stat above 2,
- net Sharpe above the noise bar,
- alpha Sharpe above the noise bar too,
- the result matches `expected_sign`.

The season has a small budget of looks shared by everyone, and answers are deliberately coarse. Asking twice for the same file returns the same answer. A publishable pass (see `docs/running-an-experiment.md`) asks more: deflated Sharpe above 0.95 and surviving the vaults, which only a human opens.

## Off-limits

- `uv run lucky vault ...` and `uv run lucky freeze ...`: humans only.
- Reading market data files, the season folder (`runs/`), `sealed/` results, or `ledger.jsonl` directly. Use `lucky ledger`.
- Editing anything outside `strategies/candidates/`.
- Dates, years, tickers, or knowledge of specific historical events in code or in reasoning.
- Parameter fishing: re-running the same idea with lookback 20, 21, 22... Every run is a trial, counted against you in the deflated Sharpe. Change parameters only for a reason you'd write down first.

## Notebook entry

Append to `strategies/candidates/NOTEBOOK.md`:

```
## NNN short name (discovery: status, Sharpe x.xx, t x.x, DSR x.xx)
Hypothesis: ...
Result: one or two lines of what the report showed.
Learned: what this rules in or out, and what you'd try next or never again.
```

## Stopping

Stop when you've done the number of passes you were asked for, when the validation budget is spent, or when your last five ideas were variations of each other. Finish with a short summary in the notebook: what you tried, what (if anything) looks worth a human's attention, and why.
