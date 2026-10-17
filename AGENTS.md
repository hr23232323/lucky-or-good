# AGENTS.md

Instructions for any coding agent (Claude, Codex, Cursor, Gemini, ...) working in this repo. Humans: see `README.md`.

## What this is

A judge for trading strategies proposed by LLMs. The judge must be hard to fool, including by you. Read `docs/design.md` before changing `src/lucky/`.

## Two roles. Know which one you're in.

**Builder**: improving the harness (`src/`, `tests/`, `config/`, docs).
**Proposer**: writing strategies in `strategies/candidates/` and judging them. Use the `propose-strategy` skill in `.claude/skills/`.

As a proposer you must not:
- edit anything outside `strategies/candidates/` (the judge, configs, tests, ledger),
- read market data files directly, or look at results for `validation` or `vault` blocks except through `lucky` commands,
- name tickers, or use knowledge of what happened in specific years. Write rules over features.

## Commands

```bash
uv sync                          # install
uv run pytest                    # all tests; must pass before every commit
uv run ruff check . && uv run ruff format --check .
uv run lucky --help              # judge CLI
uv run lucky report              # season page (never with --include-sealed as a proposer)
```

## Layout

- `src/lucky/`: the judge (data, engine, periods, ledger, checks, metrics, CLI)
- `strategies/baselines/`: human textbook strategies, same rules as everyone
- `strategies/candidates/`: proposed strategies
- `config/`: dataset and period definitions
- `intents/`: one tiny file per unit of work; status lives there
- `docs/`: human-facing docs; `docs/design.md` is the spec
- `.claude/skills/`: task playbooks (plain Markdown; any agent can follow them)
- `PROGRESS.md`: where things stand. `LEARNINGS.md`: mistakes and what we changed.

## How we work

- Start from an intent in `intents/`. New work gets a new tiny intent first.
- Commit when a coherent piece works and tests pass. Not every line, not a day's work at once. Imperative subject, body says why.
- Bug fixes: write the failing test first, then fix without editing the test.
- Anything that makes the judge easier to fool is a bug, even if no test fails. Add an adversarial test in `tests/test_anticheat.py` for it.
- Deferred work goes in a GitHub issue, not a TODO comment.
- Mistakes go in `LEARNINGS.md`: what happened, why, what rule we added. Then move on.

## Data

Market data is licensed (MarketParquet) and is never committed. Set `LUCKY_DATA_DIR` to a local copy. Tests use the synthetic market in `src/lucky/synthetic.py`.

## Things agents get wrong here

- Using `shift(-1)`, `bfill`, centred rolling windows or full-sample normalisation in a strategy. The checks reject these; don't fight them.
- Writing dates, years or tickers into a strategy. That's memory of history, not a rule; the checks reject it.
- Treating a good discovery Sharpe as a finding. It is a hypothesis until it survives validation, the trial-count deflation and a vault.
- Forgetting that statistics cannot detect look-ahead. Structural guards come first.
- Weakening a check to make a test pass. If an honest strategy trips a check, record why in `LEARNINGS.md` and narrow the check with a test on both sides (see the month-end calendar entry).
- Piping test or lint commands before `&&` (`pytest | tail && git commit`). The pipe hides the failure.
