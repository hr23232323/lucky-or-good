# 003 Synthetic market
Status: done
Problem: we only have a one-week sample of real data, and tests must not depend on licensed files anyway. We also need a market where we know the truth, to check the judge finds real edges and rejects fake ones.
Outcome: `lucky.synthetic` writes a fake market in MarketParquet's exact layout and schema: factor-driven returns, IPOs, failures and mergers (with `-DELISTED` names), the column switch, and an optional planted edge (a volume shock that predicts the next day's return) with known strength.
Done when: the volume shock predicts next-session returns in an edge market and not in a noise market (rank IC). The engine tests later check the same edge shows up as a positive Sharpe.
