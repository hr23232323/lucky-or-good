---
name: propose-strategy
description: Run the research loop as a strategy proposer. Use when asked to propose, write, test or iterate on trading strategies in this repo, or to "run the loop" or "try N strategies" against a season.
---

# Propose a strategy

You are the **proposer**. You write strategy files; the judge scores them. You never change the judge, and you never see sealed results. Read `AGENTS.md` first if you haven't.

## Before you start

1. `LUCKY_SEASON` must point at a season (ask the human if it isn't set). Run `uv run lucky ledger` to see what's been tried.
2. Read `strategies/candidates/NOTEBOOK.md`. It holds every earlier idea and what happened. Don't re-propose a dead idea unless you have a reason it should behave differently, and say what that reason is.
3. Skim `strategies/baselines/`. Those are textbook ideas already being tested; a candidate should be something else, or a clearly argued improvement on one.

## The loop (one strategy per pass)

1. **Hypothesis first.** Write one or two sentences: what market behaviour you expect, why it should exist (who is on the other side, what risk or friction keeps it there), and which direction. No hindsight: if your reason is "this worked in year X" or "these companies did well", stop and think of a rule instead.
2. **Write the file** at `strategies/candidates/NNN-short-name.py` (next free number) from `template.py` in this folder. Fill `META` honestly, including `expected_sign`.
3. **Check:** `uv run lucky check strategies/candidates/NNN-short-name.py`. Fix violations by changing the idea, not by disguising it.
4. **Judge in discovery:** `uv run lucky judge strategies/candidates/NNN-short-name.py`.
5. **Read the report like a skeptic.**
   - Compare Sharpe with the line "noise alone would be expected to reach Sharpe X". Below that bar, it's not a finding.
   - Gross vs net Sharpe: if costs eat it, turnover is the problem.
   - "With one extra day of lag": a collapse means the edge lives in the first day, which is fragile.
   - Alpha Sharpe vs benchmark: high Sharpe with beta near 1 is just the market.
6. **Write a notebook entry** (format below), even for failures. Failures are most of the value.
7. **Decide:** a new idea, a substantive change, or (rarely) validation.

## Validation is scarce

Only ask validation (`uv run lucky judge FILE --block validation`) when a candidate clears all of these in discovery: deflated Sharpe above 0.5, t-stat above 2, net Sharpe above the noise bar, and a sensible alpha. The season has a small budget of looks shared by everyone, and answers are deliberately coarse. Asking twice for the same file returns the same answer.

## Off-limits

- `uv run lucky vault ...` and `uv run lucky freeze ...`: humans only.
- Reading market data files, the season folder (`runs/`), `sealed/` results, or `ledger.jsonl` directly. Use `lucky ledger`.
- Editing anything outside `strategies/candidates/`.
- Dates, years, tickers, or knowledge of specific historical events in code or in reasoning.
- Parameter fishing: re-running the same idea with lookback 20, 21, 22... Every run is a trial, counted against you in the deflated Sharpe. Change parameters only for a reason you'd write down first.

## Notebook entry

Append to `strategies/candidates/NOTEBOOK.md`:

```
## NNN short name (discovery: status, Sharpe x.xx, DSR x.xx)
Hypothesis: ...
Result: one or two lines of what the report showed.
Learned: what this rules in or out, and what you'd try next or never again.
```

## Stopping

Stop when you've done the number of passes you were asked for, when the validation budget is spent, or when your last five ideas were variations of each other. Finish with a short summary in the notebook: what you tried, what (if anything) looks worth a human's attention, and why.
