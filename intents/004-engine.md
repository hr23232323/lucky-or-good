# 004 Engine
Status: done
Problem: turning target weights into returns is where most backtests lie: same-bar trading, free trades, positions in dead companies quietly turning into cash at the last price.
Outcome: `lucky.engine.backtest(panel, weights, costs)` executes weights decided at the close of t at the open of t+1, earns open-to-open returns, drifts positions between trades, charges costs by liquidity bucket on actual turnover plus borrow on shorts, enforces the universe and a gross exposure cap, and applies a terminal return when a held symbol stops trading.
Done when: hand-computed examples match; a strategy that "trades" on today's move earns nothing in a noise market; holding a failed company costs the terminal loss; the planted edge shows up net of costs.
Notes: semantics a strategy relies on: an all-NaN row means "don't trade today", a NaN inside a traded row means zero weight. Cash earns nothing for now.
