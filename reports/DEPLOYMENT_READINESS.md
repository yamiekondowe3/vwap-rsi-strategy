# Deployment readiness — two real bugs found and fixed

Neither bug was found by any backtest. Both would have caused failures in live deployment.

## Bug 1: unbounded position size when ATR collapses (silent capital risk)

Size is `risk_amount / (stop_atr × ATR)`. When ATR shrinks toward the spread — FX majors on
H1 during quiet Asian hours, where ATR approaches zero while the broker's spread sits at its
floor — size explodes, and the fixed spread on that oversized position costs many R despite a
nominal 1R stop. There was **no minimum-ATR guard anywhere**.

Measured on real data, before and after the fix:

| Pair | Median R before | Median R after |
|---|---|---|
| EURUSD | **−19.55** | −1.001 |
| USDCHF | −11.80 | −1.002 |
| GBPUSD | −12.07 | −1.001 |
| EURGBP | −1.002 | +0.984 |

**Fix:** `max_cost_ratio` (default 0.20) skips any setup whose round-trip execution cost
exceeds that fraction of intended risk, plus `max_leverage` (default 50×) capping notional.
Both in `common/backtest_core.py` and mirrored in both MQL5 EAs. Three regression tests,
including one that reproduces the pathology and then confirms the guard blocks it.

A related flaw was fixed in the EAs: `MathMax(minLot, ...)` forced size back *up* to the
broker minimum after the cap was applied, silently defeating it. Sub-minimum setups are now
skipped instead.

**Effect on conclusions:** the FX cross-section magnitudes were inflated by this bug, so it
was re-run with the guard. The verdict is unchanged — 3/21 pairs positive (was 1/21), median
E[R] −0.209 (was −5.73), and **XAUUSD still sits at the 100th percentile of its peer group.**
The finding rests on corrected numbers.

## Bug 2: every order would have been rejected (total deployment failure)

Both EAs hardcoded `ORDER_FILLING_IOC`. This broker reports `filling_mode=1` (FOK only) on
XAUUSD and BTCUSD, so **every order would have failed with retcode 10030, "Unsupported
filling mode"** — the EAs would have run indefinitely, signalled correctly, and never placed
a single trade.

**Fix:** `PickFillingMode()` queries `SYMBOL_FILLING_MODE` and selects a supported mode.

Found by `ops_rehearsal.py` using `order_check()`, which validates a request against margin,
volume, stop distance and filling mode **without executing it**. This is the entire argument
for an ops rehearsal: it is the only step that exercises the order path, and no amount of
backtesting would have revealed it.

## Pipeline status: 15/15 checks pass

Connection, demo-account verification, algo-trading permission, symbol resolution, live ticks,
history reads, order validity, margin, and both monitoring paths. No orders were placed.

**This says nothing about strategy profitability.** Every strategy in this project was
falsified — see `PROJECT_SUMMARY.md`. The value here is that if a genuine edge is ever found,
deployment will not be the thing that breaks.

Raw: `ops_rehearsal.py`, `fx_guarded_results.json`.
