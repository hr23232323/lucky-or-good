# Learnings

Mistakes, surprises and what we changed because of them. Newest first. Keep entries short.

```
## YYYY-MM-DD: short title
What happened:
Why:
Changed:
```

## 2026-10-16: the "noise" market handed out free alpha
What happened: in the first full-size dry run, plain equal-weight showed an alpha Sharpe of 1.1 against the market in a synthetic market with no planted edge. Every test still passed.
Why: stock noise had a zero *log* mean, which means a positive *arithmetic* mean (+sigma^2/2 a day, about 5%/yr). Monthly rebalancing harvests that. Separately, the benchmark's open was timed differently from the stocks', which deflated measured beta.
Changed: noise now has zero arithmetic mean, and the benchmark uses the same overnight/intraday split. Two tests pin both (the first fails on the old generator). Lesson: a test fixture that's meant to contain no edge needs its own test proving it.

## 2026-10-16: a lint failure slipped into a commit
What happened: I ran `ruff check . | tail -3 && git commit ...`; ruff failed but the commit went through.
Why: a pipe's exit status is the last command's (`tail`), so the failure was swallowed.
Changed: never pipe gate commands (tests, lint) before `&&`. Fixed with an amend before pushing.

## 2026-10-16: honest monthly rebalancing tripped the look-ahead check
What happened: a plain momentum strategy that rebalances on the last trading day of each month was flagged as look-ahead.
Why: when the truncation check cuts data mid-month, the cut date looks like a month-end, so the truncated run trades there and the full run doesn't. Knowing tomorrow's date isn't cheating; trading calendars are public.
Changed: `compare_prefix` ignores a final row at the cut date when the full run doesn't trade that day. Rows before it, and a row the full run does trade, are still compared. Test added for both sides.

## 2026-10-16: forking a DuckDB process can deadlock
What happened: Python warned that forking a multi-threaded process may deadlock the child.
Why: DuckDB and Arrow keep thread pools; `fork` copies locks held by other threads.
Changed: strategies run in a spawned child that reads the panel from a pickle file. Slower to start (about a second), but safe.
