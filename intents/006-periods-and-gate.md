# 006 Periods and the gate
Status: done
Problem: if a proposer can see results for every period, every period becomes training data. Sealed periods only work if something enforces them.
Outcome: periods are defined in `config/periods/*.toml`. The judge only loads data up to the end of the requested block (plus warm-up before it). `discovery` answers fully. `validation` answers coarsely with noise, Thresholdout-style, and spends a budget only when validation disagrees with discovery. `vault` and `forward` need the strategy frozen first and allow one look per frozen strategy, recorded in the ledger.
Done when: tests show a strategy can't load data past its block, a second vault look for the same strategy is refused, validation stops answering when the budget runs out, and editing a frozen file voids the freeze.
