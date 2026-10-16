# 009 Baseline strategies and judge CLI
Status: done
Problem: "the LLM found nothing" means little without a reference. If textbook strategies also die, the story is that backtests flatter everyone; if they survive and the LLM's don't, that's a different story. And nobody should need Python to use the judge.
Outcome: `strategies/baselines/` holds classic human strategies (equal weight, 12-1 momentum, short-term reversal, low volatility, trend, 52-week high, buy the dip) written under the same rules as everyone. A `lucky` CLI covers the loop: make a synthetic market, start a season, check, judge, freeze, open a vault, list the ledger, verify it.
Done when: every baseline passes static and truncation checks on the synthetic market, and the CLI runs the full loop end to end in a test.
Notes: value and quality need point-in-time fundamentals (SEC filings), not available yet.
