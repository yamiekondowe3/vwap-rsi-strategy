# vwap-rsi-strategy

Session-anchored VWAP + RSI mean-reversion/trend-continuation strategy, with
a realistic-friction Python backtester and a companion MQL5 Expert Advisor.

**Status: proof-of-concept, one strategy on one asset (XAUUSD).** Built per
a staged plan that validates end-to-end wiring before replicating across
the remaining strategy×asset matrix (XAGUSD, USOIL, BTCUSD, ETHUSD; the
ORB+Pivots strategy lives in the sibling `orb-pivots-strategy` repo).

## Honesty notice (read before trusting any number in this repo)

Independent replications of the closest published analogues to this system
(Zarattini & Aziz's VWAP/ORB papers) show the reported edges are highly
sensitive to slippage assumptions and often concentrated in a single
volatile year. **Nothing in this repo should be read as a validated,
profitable strategy until it has been run on real (not synthetic) data,
through the full walk-forward + Monte Carlo pipeline, and shown to survive
realistic costs out-of-sample.** See `common/costs.py` for the friction
model and `common/wfo.py` / `common/monte_carlo.py` for the validation
harness this repo is built around.

## Real-data result (headline finding): FAIL

Full 15.7-year XAUUSD history was pulled from the connected MT5 demo
account (Deriv-Demo). Default parameters lost **-71.8%** (Sharpe -4.07,
~100% Monte Carlo ruin probability). A genuine walk-forward grid search
(not hand-tuned to look better) across all 13 available 2011-2026
IS/OOS windows confirms it wasn't just bad luck: **only 2/13 windows had
positive out-of-sample return, mean OOS Sharpe -3.81.** VWAP+RSI has no
real edge on XAUUSD — see `reports/data_coverage.md` for the full
writeup and `reports/xauusd_vwap_rsi_real_data_results.json` /
`reports/xauusd_vwap_rsi_wfo_method1_results.json` for the raw numbers.
Reported as-is per the project's honesty mandate, not smoothed over.

## Current state

- `common/` — shared no-look-ahead VWAP/RSI/ATR/pivot math, friction model
  (commission/spread/slippage/latency), performance metrics, Monte Carlo,
  and walk-forward-optimization harness (vendored copy; canonical source is
  the sibling `trading-systems/common/`).
- `backtest/engine.py` — bar-by-bar VWAP+RSI backtest engine; fills execute
  at the next bar's open using only closed-bar signals.
- `backtest/run_poc.py` — end-to-end pipeline sanity run on **synthetic**
  OHLCV (no live data connected yet — see `reports/data_coverage.md`).
- `mql5_ea/VWAP_RSI_EA.mq5` — parameter-mirrored MQL5 EA. **Not yet
  validated in the MT5 Strategy Tester** — review before any demo/live use.
- `live_monitor/live_monitor.py` — read-only MT5 position/PnL digest CLI.
  Never places orders.
- `tests/` — no-look-ahead and cost-model unit tests (`pytest`).

## Not done yet

- Real MT5/external historical data ingestion (MT5 Python API connection is
  currently blocked locally — see `reports/data_coverage.md`).
- Walk-forward optimization and Monte Carlo results on real data.
- Replication to XAGUSD / USOIL / BTCUSD / ETHUSD.
- MQL5 EA Strategy Tester validation.

## Running the proof-of-concept

```
../venv/Scripts/python.exe -m pytest tests/ -v
../venv/Scripts/python.exe backtest/run_poc.py
```
