# Learnings

Mistakes, surprises and what we changed because of them. Newest first. Keep entries short.

```
## YYYY-MM-DD: short title
What happened:
Why:
Changed:
```

## 2026-10-16: honest monthly rebalancing tripped the look-ahead check
What happened: a plain momentum strategy that rebalances on the last trading day of each month was flagged as look-ahead.
Why: when the truncation check cuts data mid-month, the cut date looks like a month-end, so the truncated run trades there and the full run doesn't. Knowing tomorrow's date isn't cheating; trading calendars are public.
Changed: `compare_prefix` ignores a final row at the cut date when the full run doesn't trade that day. Rows before it, and a row the full run does trade, are still compared. Test added for both sides.

## 2026-10-16: forking a DuckDB process can deadlock
What happened: Python warned that forking a multi-threaded process may deadlock the child.
Why: DuckDB and Arrow keep thread pools; `fork` copies locks held by other threads.
Changed: strategies run in a spawned child that reads the panel from a pickle file. Slower to start (about a second), but safe.
