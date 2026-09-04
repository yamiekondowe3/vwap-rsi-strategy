# Data coverage status

## MT5 connectivity: resolved

The Python API was initially blocked by `(-6, 'Terminal: Authorization
failed')`. Root cause (found via the MT5 terminal's own log, not the
Options dialog): the AutoTrading toolbar toggle had been clicked several
times in a row and landed on **disabled** as its final state. Once toggled
back on, `MetaTrader5.initialize()` connects immediately (~100ms).

Connected account: `6289430` on `Deriv-Demo` (Deriv.com Limited), demo,
hedging mode, $10,000 starting balance.

## Real achieved history (confirmed, not assumed)

This broker's symbol names don't all match the canonical names in the
project brief — resolved via `common.data_fetch.BROKER_SYMBOL_MAP`:

| Canonical | Broker symbol | D1 history | M5 history (bars) |
|---|---|---|---|
| XAUUSD | `XAUUSD` | 2011-01-02 → 2026-09-03 (~15.7y) | 1,094,283 |
| XAGUSD | `XAGUSD` | 2011-01-02 → 2026-09-03 (~15.7y) | 1,098,366 |
| USOIL | `US Oil` (note the space) | 2024-01-22 → 2026-09-03 (**~2.6y only**) | 185,356 |
| BTCUSD | `BTCUSD` | 2011-03-23 → 2026-09-03 (~15.4y) | 923,475 |
| ETHUSD | `ETHUSD` | 2015-08-07 → 2026-09-03 (~11.1y) | 922,746 |

**Takeaway:** this broker's history is much deeper than the "typical 1–5
year" assumption in the original plan — 4 of 5 assets have 11–15.7 years of
real M5 data, close to the requested 16 years. **USOIL is the exception**:
only ~2.6 years is available under any symbol this broker offers (checked
`OIL`, `WTI`, `BRENT`, `CRUDE`, `USO` substrings — `UK Brent Oil` is the
only other oil-adjacent symbol, not fetched). Any USOIL walk-forward
analysis will be materially less robust than the other four assets and
should be flagged as such wherever it's reported, not silently backfilled
to look comparable.

All 5 assets' M5 OHLCV are cached as Parquet under `../data_cache/` (91MB
total, single Deriv venue, tick volume — see the FX/crypto volume-quality
caveats in the research docs before trusting this as true traded volume,
particularly for BTCUSD/ETHUSD where this is one broker's derived
tick-volume series, not a real spot-exchange volume feed).

## Real-data VWAP+RSI result on XAUUSD (go/no-go check)

Full achieved history (2011-01-02 to 2026-09-03, 1,094,283 M5 bars),
**default/un-optimized parameters**, real friction model:

- 981 trades, **Sharpe -4.07**, **total return -71.8%**, max drawdown
  -72.5%, win rate 43.6%, profit factor 0.65.
- Monte Carlo (5,000 iterations, both bootstrap and trade-order-shuffle):
  ruin probability (equity < 50% of starting) ≈ **100%**.

This fails the plan's go/no-go gate decisively with default parameters.
Per the research docs' explicit warning against tuning a fragile edge into
apparent profitability, this was **not** hand-tuned to look better — instead
a real (small, deliberately non-exhaustive) grid-search walk-forward
optimization was run: `backtest/run_wfo_xauusd.py`, grid-searching
stop/target ATR multiples on each 2-year in-sample window (selected by IS
Sharpe, minimum 15 trades to avoid degenerate low-sample "winners"),
evaluated out-of-sample on the following year, across all 13 available
2011–2026 windows.

**WFO verdict: FAIL.** Only 2/13 windows had positive OOS return; mean OOS
Sharpe −3.81; mean OOS expectancy −9.18 per trade. The grid consistently
selected wide stops (mostly 3.0x ATR) in-sample, and even the "best"
in-sample configuration lost money out-of-sample in most years. **This
strategy has no real edge on XAUUSD** — confirmed on real data, real
costs, and genuine walk-forward validation, not an unlucky default-parameter
artifact. Consistent with the research docs' prediction that VWAP
mean-reversion has essentially no independent net-of-cost support.

Full result JSONs: `reports/xauusd_vwap_rsi_real_data_results.json`,
`reports/xauusd_vwap_rsi_wfo_method1_results.json`.

**Recommendation per the plan's staged approach:** do not keep tuning this
strategy/instrument pair looking for a positive result — that is exactly
the overfitting risk the research docs warn about. Either (a) test
VWAP+RSI on the other 4 assets in case the edge is instrument-specific
(unlikely given how uniformly negative this is, but cheap to check), or
(b) move to validating the ORB+Pivots strategy instead, which has a
different (though similarly fragile per the research docs) mechanism.

## Not done yet

- External backfill adapters (Dukascopy/exchange APIs) — not needed for
  XAUUSD/XAGUSD/BTCUSD/ETHUSD given the achieved MT5 depth above, but still
  relevant for USOIL if 16y depth is required there specifically.
- Method 2 WFO (7y IS / 1y OOS) — not yet run (Method 1 prioritized for
  time budget); same `run_wfo`/`build_windows` functions apply directly.
- Replication to XAGUSD / USOIL / BTCUSD / ETHUSD.
- MQL5 EA Strategy Tester validation.
