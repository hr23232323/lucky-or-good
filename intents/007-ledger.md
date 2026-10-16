# 007 Trial ledger
Status: done
Problem: published backtests hide the 99 tries behind the 1 winner. Without a full count, deflation is impossible and nobody can audit the result.
Outcome: each research season has an append-only JSONL ledger where every entry carries the hash of the previous one. Every evaluation is logged, including rejected files and crashes, with the strategy's content hash, hypothesis, block and metrics. Daily returns are stored per trial so trial counts and Sharpe dispersion feed the Deflated Sharpe. Validation and vault returns go in a `sealed/` folder proposers are told not to read.
Done when: `verify()` detects an edited or deleted line, and n_trials in reports counts every scored trial in the season.
