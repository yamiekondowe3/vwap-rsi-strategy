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

## Final verdict: not profitable out-of-sample — see `reports/FINAL_VERDICT.md`

Re-run under a **corrected cost model** (the earlier results here were
produced with fabricated commission/spread constants consuming ~68% of the
per-trade risk budget — that bug is fixed: real per-bar MT5 spread, zero
commission for Deriv's spread-only CFDs, exit-side spread now charged).

**Headline, default parameters, full 15.67y XAUUSD M5:** Sharpe **-0.71**
(was -4.07 under the broken model), total return **-35.7%** (was -71.8%),
win rate **48.8%**, expectancy **-0.090 R/trade**. Friction costs ~0.13R
per round trip while the signal's own deficit is only ~0.025R — **most of
the loss is friction, not signal.**

**Walk-forward (13 windows × 9 combos, params chosen in-sample only):**
3/13 windows positive, mean OOS expectancy **-0.121 R/trade** over 575
out-of-sample trades, mean R-normalized Sharpe **-0.786**.

**The decisive diagnostic:** in-sample optimization has **zero predictive
power** for out-of-sample results — IS→OOS correlation r=+0.109 (p=0.72),
and the mean OOS result for windows with a positive in-sample edge
(-0.1214 R) is *identical to four decimals* to that for windows with a
negative one (-0.1214 R). The optimizer cannot tell in advance which
parameters will work, because the in-sample differences it selects on are
noise. That is also why a bigger grid search would not help.

Verdict: **negative, but closer to viable than ORB** — and the highest-
leverage change is lower friction (e.g. a higher timeframe amortizing the
same spread over larger stops), not more parameter search.

## Prior stage (UNDER THE BROKEN COST MODEL — superseded, kept for the record): FAIL

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
