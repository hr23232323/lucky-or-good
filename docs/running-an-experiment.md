# Running an experiment you can publish

A checklist for a run whose results you'll share. The point is that a skeptic can audit it: they can see every attempt, not just the winners, and can tell nobody peeked.

## 1. Write down the question and the bar first

Before any strategy runs, write (on your site, in an issue, anywhere timestamped):

- the question ("Can Claude, given discovery data only, find a strategy that survives both vaults after costs?"),
- the proposing model and its training cutoff,
- what counts as a pass. A reasonable default: deflated Sharpe above 0.95 in discovery, a validation answer above zero, and a positive Sharpe after costs in each vault, opened once.
- what you expect to happen.

Link the git commit of the judge you'll use. Changing the judge mid-season means a new season.

## 2. Start a season

```bash
export LUCKY_DATA_DIR=/path/to/marketparquet
cp config/periods/marketparquet.toml my-periods.toml
# edit my-periods.toml: make `forward` start after the model's training cutoff,
# and end `vault_b` the day before
uv run lucky season new runs/season-1 --periods my-periods.toml \
    --model claude-opus-5-5 --cutoff 2026-06 --top-n 1000 --budget 25
export LUCKY_SEASON=runs/season-1
```

The season copies the period layout in, so later edits to the config don't affect it.

## 3. Score the baselines

```bash
for f in strategies/baselines/*.py; do uv run lucky judge "$f"; done
```

They're contestants, not decoration. Their trials count toward the season's total like everyone else's.

## 4. Run the proposer with guardrails

```bash
claude "Use the propose-strategy skill to try 20 strategies."
```

What protects the run, and what doesn't:

- `.claude/settings.json` denies `lucky vault`, `lucky freeze` and reading `runs/` through Claude Code's file tools. Codex and other agents don't read that file; give them equivalent instructions or settings.
- These are guardrails for an honest agent, not a wall. Claude Code's own docs note that Bash deny rules match the usual command text only, and a `Read` deny doesn't stop `cat` through the shell. The judge also runs in the same environment as the agent, so the agent's machine has the data.
- What makes it auditable: keep the agent's full transcript, and after the run search it for any access to the data folder, `runs/`, `sealed/` or `ledger.jsonl`. Any hit voids the season.

Stronger isolation (an agent that can submit strategies but never touch the data) needs the judge to run as a separate service. That isn't built yet; see the issues.

## 5. Human review

1. `uv run lucky ledger` and the notebook in `strategies/candidates/NOTEBOOK.md`.
2. Read the code of every candidate you're considering. A strategy built to detect the look-ahead check is the main gap the checks can't close; reading it is the backstop.
3. Freeze the finalists: `uv run lucky freeze strategies/candidates/NNN-name.py --note "why"`.
4. Open each vault once per finalist: `uv run lucky vault FILE --block vault_a`, then `vault_b`. Full results land in `runs/season-1/sealed/`.
5. The forward block accrues as new data arrives. Open it once, later, for a frozen strategy.

## 6. Publish

- `uv run lucky verify` must print `ledger intact`.
- `uv run lucky report --include-sealed` writes `runs/season-1/report-sealed.html`: the page to link from a write-up. Only make it after the vaults you intend to open are opened.
- Share `runs/season-1/` (ledger, returns, sealed results, frozen files), the notebook, the transcripts, and the judge commit. These contain your results but not the licensed price data.
- Report every strategy tried, the baselines alongside the AI's, and the failures. The interesting result is usually how many things looked good before they didn't.
