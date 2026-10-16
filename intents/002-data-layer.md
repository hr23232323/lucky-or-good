# 002 Data layer
Status: done
Problem: strategies need daily bars for ~2,000 symbols as aligned matrices, read from MarketParquet's one-file-per-day layout, without survivorship bias.
Outcome: `lucky.data` loads `by_date/{asset}_daily/*.parquet` through DuckDB into a `Panel` (wide open/high/low/close/volume by date x symbol), handles the 2026-03-27 `timestamp` to `date` column switch, keeps `-DELISTED` symbols, and builds a point-in-time liquidity universe from data through t-1.
Done when: tests on the synthetic market show the universe at t never depends on data at or after t, delisted names appear while they traded, and both column schemas load.
Notes: no consolidated cache yet; DuckDB over the glob is fast enough for daily. Revisit for minute bars.
