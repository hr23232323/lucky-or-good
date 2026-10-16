# Design

One page on how the judge works and why. Read this before changing anything in `src/lucky/`.

## The problem

An LLM can generate hundreds of trading ideas a night. Most backtests that look good are luck, look-ahead bugs, missing costs, or the model remembering how history played out. The judge exists to tell those apart from a real edge, and to be hard to fool, including by the agent proposing strategies.

## Shape

```
strategy file ──▶ static checks ──▶ run in subprocess ──▶ look-ahead checks ──▶ engine ──▶ metrics ──▶ ledger
(proposer writes)  (AST rules)      (timeout, no data     (truncation, extra   (lag,      (Sharpe,   (append-only,
                                     outside the block)    lag)                  costs)     PSR/DSR)   hash-chained)
```

The proposer (a human, Claude, Codex, anything) only ever writes strategy files. Everything else is the judge, and the proposer never edits it.

## Strategy contract

A strategy is one Python file exposing:

```python
META = {"name": ..., "hypothesis": ..., "expected_sign": ..., "author": ...}


def weights(panel) -> pd.DataFrame: ...
```

`panel` holds wide DataFrames (index = date, columns = symbol): `open`, `high`, `low`, `close`, `volume`, `dollar_volume`, and `universe` (bool). Row `t` of the returned weights is the target portfolio decided after the close of `t`, using information up to and including `t`. Weights are fractions of capital; negative means short.

## Timing (the most important rule)

The engine, not the strategy, applies the lag. Weights decided at the close of `t` are traded at the open of `t+1` and earn open-to-open returns until the next rebalance. A strategy cannot express same-bar trading even if it tries.

## Periods

History is split into blocks defined in `config/periods/<dataset>.toml`:

| Kind | What the proposer gets |
|---|---|
| `discovery` | Full results, unlimited runs |
| `validation` | Coarse, noised pass/fail answers against a budget of looks (Thresholdout-style) |
| `vault` | Nothing until a strategy is frozen; then one look per frozen strategy, recorded in the ledger |
| `forward` | Data after the proposing model's training cutoff; accrues over time |

Strategies may read a warm-up window before a block starts for lookbacks. Returns are only scored inside the block.

A sealed block protects against *search* overfitting. It does not protect against the model *remembering* the period. Only `forward` data, or a model whose training cutoff predates the block, does that.

## Universe, costs, delistings

- Universe is chosen point-in-time: top N by trailing median dollar volume, using data through `t-1`. Never today's list.
- Costs are charged on drift-adjusted turnover, by liquidity bucket, plus a borrow fee on shorts.
- When a held symbol's data ends, the engine applies a terminal return: a configurable loss if it looked like a failure (low price or a large drawdown before delisting), otherwise zero.
- Prices are split-adjusted, not total return. Dividends are not yet modelled. This understates buy-and-hold slightly and is noted in every report.

## Integrity

- Every trial is logged, including failures and rejected files. Reports judge a strategy against the full count of trials in its season (Deflated Sharpe).
- The ledger is append-only and hash-chained, so edits are detectable.
- Look-ahead is prevented structurally (engine lag, data truncated to the block) and checked dynamically (weights at `t` must not change when data after `t` is removed).
- Statistics cannot catch leakage: a leaky strategy can pass every statistical test. That is why the structural checks exist.

## Threat model (honest version)

This runs locally. An agent with shell access can read the raw Parquet files and see vault data, whatever this code does. The judge makes honest use easy and dishonest use visible (ledger, static checks), but it is not a security boundary. For publishable runs, run the proposing agent without read access to the data directory and call the judge from outside its sandbox. See `docs/running-an-experiment.md`.

## Scale

Everything reads Parquet lazily through DuckDB and works on wide matrices. The free sample is a few MB; the full archive is about 1.5 GB of daily bars and 100+ GB of minute bars. Code paths must not assume the data fits in memory beyond the daily panel for the chosen universe.
