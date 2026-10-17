---
name: harden-judge
description: Fix the judge when a cheat gets through or an honest strategy is wrongly rejected. Use when working on src/lucky/checks.py, sandbox.py, engine.py or judge.py, or when a report looks too good to be true.
---

# Harden the judge

You are a **builder**. The judge's job is to be hard to fool. Two kinds of bug matter most: a cheat that scores, and an honest strategy that's rejected. Both erode trust; the first is worse.

## A cheat got through

1. Reproduce it as one row in `CATALOGUE` in `tests/test_anticheat.py`: a minimal strategy, the status it should get (`rejected` or `lookahead`), and the rule name if it's static.
2. Run `uv run pytest tests/test_anticheat.py -k <id>` and watch it fail. Commit nothing yet.
3. Fix the narrowest layer that can catch it:
   - visible in syntax (a call, an import, a literal): a static rule in `checks.py`;
   - only visible in behaviour (depends on future rows): the truncation check already covers it, so ask why it didn't (sampled dates? an exception path?);
   - outside the strategy (data loading, timing, costs, ledger): `data.py`, `engine.py` or `judge.py`.
4. Run the whole suite, including `tests/test_baselines.py`: a new rule must not reject the honest baselines.
5. Add an entry to `LEARNINGS.md`, and a line to the threat model in `docs/design.md` if the gap is general.

## An honest strategy was rejected

1. Confirm it's honest: would it make the same decision at t with no data after t? Calendar knowledge (is tomorrow a trading day? is today a month-end?) is honest. Anything about prices, volumes or events after t is not.
2. Write a test that the honest case passes and a test that the nearest cheat still fails (see the month-end tests in `tests/test_checks.py`).
3. Narrow the check. Never delete or loosen a check without both tests.
4. Record it in `LEARNINGS.md`.

## A result looks too good

A Sharpe above about 2 on daily US equities, after costs, should be treated as a bug until proven otherwise. Check, in order: the extra-lag Sharpe (a collapse means same-day information), turnover and costs, exposure and beta, delisted names in the holdings, and whether the strategy only works in one stretch of the block.
