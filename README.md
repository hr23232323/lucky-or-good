# lucky-or-good

Can an AI discover a trading strategy, or does it just get lucky?

An LLM can write a hundred trading ideas in a night. Most backtests that look good are luck, look-ahead bugs, missing costs, or the model remembering how history played out. This repo is a judge built to tell those apart, and to be hard to fool, including by the AI proposing the ideas.

Research, not financial advice.

## Status

Early. The judge is built and tested against a synthetic market where we know the truth. The first real experiment (Claude proposing strategies on 26 years of US stocks, with textbook strategies as baselines) hasn't run yet. Results and write-ups will go on [harshrana.com](https://harshrana.com). Progress lives in [`PROGRESS.md`](PROGRESS.md); mistakes and what we changed because of them in [`LEARNINGS.md`](LEARNINGS.md).

## How it works

A proposer (Claude, Codex, you) writes a strategy as one small Python file: a function that turns past prices into target weights. The judge does everything else:

- **Checks** the code before running it: no file or network access, no peeking at future rows, no hard-coded dates or tickers.
- **Runs** it in a separate process on data that stops at the end of the period being tested.
- **Re-runs** it on data cut off at random dates. If yesterday's decision changes when tomorrow's data disappears, it was reading the future.
- **Trades** at the next day's open, never on the bar that produced the signal, and charges costs and borrow fees.
- **Logs** every attempt, including failures, in a hash-chained ledger, and judges each result against how many strategies were tried (the Deflated Sharpe Ratio).

History is split into sealed periods:

| Period | What the proposer sees |
|---|---|
| Discovery (2004-2014) | Full results, as many runs as it likes |
| Validation (2015-2019) | Coarse, noisy answers, on a small budget |
| Two vaults (2001-03, 2020-26) | Nothing. A human opens each once per frozen strategy |
| Forward (after the model's training cutoff) | The only data the model can't remember |

The design and its limits are in [`docs/design.md`](docs/design.md).

`lucky report` turns a season into one self-contained HTML page: every strategy's Sharpe against the noise bar, baselines against candidates, growth-of-$1 curves, every trial, and why rejected strategies were rejected. Vault results stay hidden unless a human adds `--include-sealed`. The page is built from the season folder alone, so it can be shared without the licensed data.

A report looks like this (a baseline on the synthetic market):

```
#4  strategies/baselines/momentum_12_1.py  [discovery]  scored
  12-1 momentum: Stocks with the best returns over the past year, skipping the last month, keep outperforming (Jegadeesh & Titman 1993).
  Sharpe -0.05 (gross -0.04, t -0.2)  return -2.0%/yr  max DD -52.7%
  costs 0.2%/yr  turnover 8x/yr  positions 20  exposure 1.00
  benchmark Sharpe 0.35  beta 0.75  alpha Sharpe -0.61
  with one extra day of lag: Sharpe -0.01
  3 strategies tried in this season; noise alone would be expected to reach Sharpe 0.22. Deflated Sharpe: 0.18
```

## Try it in five minutes (no data needed)

Needs Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run lucky synthetic data/synth --edge 0.0005     # a fake market with a small planted edge
uv run lucky season new runs/try --periods config/periods/synthetic.toml \
    --data data/synth --top-n 200 --benchmark MKT
export LUCKY_SEASON=runs/try
uv run lucky judge strategies/baselines/momentum_12_1.py
uv run lucky ledger
uv run lucky report     # one HTML page with every strategy: runs/try/report.html
```

`data/` and `runs/` are git-ignored. The synthetic market has a planted edge you can try to find; the fixture in `tests/strategies/volume_shock.py` shows what finding it looks like.

## Real data

The experiments use [MarketParquet](https://marketparquet.com): split-adjusted daily bars for US stocks and ETFs since 2000, including about 8,500 delisted tickers, for a one-time $79. It's licensed, so it isn't in this repo and can't be shared. Buy the archive, create an API key on your account page, then:

```bash
read -s MARKETPARQUET_API_KEY && export MARKETPARQUET_API_KEY   # paste the key; stays out of shell history
export LUCKY_DATA_DIR=~/marketparquet
uv run lucky data download          # daily stocks + ETFs, 2000 to today; rerun any time to top up
uv run lucky season new runs/season-1 --periods config/periods/marketparquet.toml \
    --model claude-opus-5-5 --cutoff 2026-06
```

The download resumes where it left off, checks every file's size, and waits when the API asks it to. Add `--datasets stock_1hour etf_1hour` for hourly bars (several GB).

Any data in the same layout (`by_date/stock_daily/YYYY-MM-DD.parquet` with `symbol, open, high, low, close, volume` and a `date` or `timestamp` column) works.

## Let an AI propose strategies

The loop is a skill written in plain Markdown, so any coding agent can follow it: [`.claude/skills/propose-strategy/SKILL.md`](.claude/skills/propose-strategy/SKILL.md).

```bash
claude "Use the propose-strategy skill to try 5 strategies."
codex "Follow .claude/skills/propose-strategy/SKILL.md and try 5 strategies."
```

Proposers write to `strategies/candidates/` and keep a research notebook there, so later sessions don't repeat dead ideas. They can't open vaults; that's for humans. For a run you intend to publish, read [`docs/running-an-experiment.md`](docs/running-an-experiment.md) first.

## What this can't do (yet)

- Daily bars only. Prices aren't dividend-adjusted, which understates buy-and-hold by roughly the dividend yield.
- It runs on your machine, so it's not a security boundary. An agent with a shell can read the raw data if it wants to. The judge makes honest use easy and dishonest use visible.
- Sealed periods stop the search from overfitting. They don't stop a model from remembering what happened in those years; only data after its training cutoff does that.
- A few years of holdout can reject a strategy but can't confirm a modest one. Confirming a Sharpe of 0.5 takes roughly a decade of data.
- Costs are estimates, not fills.

Planned work is tracked in [issues](https://github.com/hr23232323/lucky-or-good/issues).

## Repo map

```
src/lucky/            the judge: data, engine, periods, checks, sandbox, ledger, metrics, CLI
strategies/baselines/ textbook strategies, same rules as everyone
strategies/candidates/ proposed strategies and the research notebook
config/periods/       period layouts per dataset
tests/                including test_anticheat.py, the catalogue of cheats that must stay caught
intents/              one tiny file per piece of work
.claude/skills/       playbooks for agents (plain Markdown)
```

## Contributing

Agents and humans both start with [`AGENTS.md`](AGENTS.md). New work starts as a tiny intent in `intents/`. If you find a way to fool the judge, that's the most useful contribution there is: add it as a row in `tests/test_anticheat.py` and open a pull request, even without a fix.

## License

MIT. See [`LICENSE`](LICENSE).
