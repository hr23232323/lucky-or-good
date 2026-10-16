# 008 Look-ahead and static checks
Status: done
Problem: LLM-written strategy code runs fine and silently peeks at the future (negative shifts, back-fills, full-sample normalisation) or reaches outside its box (files, network, imports).
Outcome: static checks on the strategy's syntax tree (import allow-list, banned calls and patterns, required `META` and `weights`), the strategy runs in a subprocess with a timeout and no data path, and a dynamic truncation check: weights up to t must be identical whether or not data after t exists. An extra-lag diagnostic reports how much Sharpe depends on the first day.
Done when: each known cheat in `tests/test_anticheat.py` is caught by at least one check.
