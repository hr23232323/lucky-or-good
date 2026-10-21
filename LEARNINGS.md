# Learnings

Mistakes, surprises and what we changed because of them. Newest first. Keep entries short.

```
## YYYY-MM-DD: short title
What happened:
Why:
Changed:
```

## 2026-10-20: the real archive has bad prints that the synthetic market never had
What happened: first contact with the full MarketParquet archive (38M rows, 16,410 symbols). 824 symbols have prices that jump more than 3x and snap back the next day; others have runs of stray prints on a handful of shares, unadjusted reverse splits (JDSU 2006, Level 3 2011), and prices like $70 billion a share. A held position would book thousands of percent in a day, and because the fake price inflates dollar volume, broken names ranked into the "most liquid 1,000".
Why: vendor data is cleaned for the common cases only. Our tests used a synthetic market we generated, which by construction had none of this.
Changed: the loader drops impossible bars (four rules) and adjusts unadjusted splits, with a test per failure mode taken from a real example. In-universe moves above +100% in discovery fell from 30 to 16, mostly real events now. The engine notes any held position above +300% in a day. Residual gaps (spinoffs, long junk stretches on another price scale) are documented in docs/design.md. Lesson: look at the real data's extremes before trusting any result on it; the synthetic market can't teach you what you didn't put in it.

## 2026-10-16: sealed results leaked into the public ledger
What happened: while building the season report, the vault rows showed a deflated Sharpe. The ledger hid vault and validation Sharpe ratios but kept the deflated Sharpe and the "matched expected sign" flag, which `lucky ledger` prints to proposers. Both say how a sealed period went.
Why: sealing used a deny-list of fields to remove. Every field added later (deflation, sign check) leaked by default.
Changed: sealed entries now keep an allow-list of fields that say nothing about performance (`SEALED_PUBLIC_FIELDS`), with a test that fails if any performance field appears on a validation, vault or forward entry. Lesson: for anything sealed, allow-list. Found by looking at a rendered page, not by a test.

## 2026-10-16: retro on the first build session
What happened: the judge went from empty repo to a tested v0 in one session, ending with a fresh agent running the proposer loop.
What worked: writing the cheat catalogue as tests before hardening (10 of 22 cheats got through at first, so the tests were really testing something); asking an outside agent to use the skill and report friction (ten useful points in one run); keeping a synthetic market where the truth is known.
What didn't: three of the bugs found were in the test fixture itself (free alpha, benchmark timing, smooth failures), and all three passed every test until a person or an agent looked at the numbers. Unit tests check what we thought of; reading real output finds the rest.
Changed: keep doing one "look at the numbers" pass per piece of work, and a fresh-agent dry run after any change to the skill.

## 2026-10-16: an agent's dry run found a fake effect in the fake market
What happened: in the first dry run of the proposer skill, a "short lottery stocks" strategy lost money at t = -3.4 on the synthetic market, where the only planted effect is a volume shock.
Why: failing companies slid down smoothly, so they looked like calm, low-MAX stocks right before their -30% terminal loss. Without delistings the result dropped to t = -1.85, i.e. noise.
Changed: failing companies now get distress-level volatility on the way down (as real ones do), with a test. Any delisting model creates some effect, so the synthetic module now says plainly it is a test rig, not a market model. Lesson: when a result surprises you on synthetic data, suspect the generator first; it's the one part with no outside check.

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
