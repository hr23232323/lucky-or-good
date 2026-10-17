# 012 Season report
Status: done
Problem: results only exist as one CLI report per strategy and a terse ledger listing. Nobody can see a season at a glance, and there's nothing to publish.
Outcome: `lucky report` writes one self-contained HTML page per season (no network, opens anywhere, safe to post): headline numbers, every strategy's discovery Sharpe against the noise bar, baselines vs candidates, growth-of-$1 curves against the benchmark, every trial in a table, and why rejected strategies were rejected. Sealed results (true validation numbers, vault results) appear only with `--include-sealed`, which is for humans after a vault is opened.
Done when: a report renders from a demo season with baselines, candidates, a rejection, a validation answer and an opened vault; without `--include-sealed` it contains no sealed numbers (tested).
Notes: the page is written into the season folder by default, which proposers are told not to read.
