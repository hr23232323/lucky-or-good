# 005 Metrics and deflated Sharpe
Status: done
Problem: a Sharpe ratio on its own says nothing about how many strategies were tried to find it.
Outcome: `lucky.metrics` has the usual numbers (Sharpe, t-stat, drawdown, cost drag, turnover, beta and alpha vs a benchmark) plus the Probabilistic and Deflated Sharpe Ratio (Bailey & Lopez de Prado) and the expected best Sharpe from N skill-less trials.
Done when: the best of 200 noise strategies looks good alone and fails deflation; a real edge passes.
