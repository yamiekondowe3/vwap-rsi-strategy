"""Proof-of-concept end-to-end run: synthetic OHLCV -> backtest -> metrics
-> Monte Carlo -> WFO harness sanity check.

This uses SYNTHETIC data (no live MT5 connection yet -- see reports/ for the
honest data-coverage status). It exists to prove the pipeline wiring end to
end per the plan's verification step, not to claim any edge.
"""
import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.metrics import full_report
from common.monte_carlo import run_monte_carlo
from common.wfo import build_windows, run_wfo
from backtest.engine import run_backtest, VWAPRSIParams


def make_synthetic_ohlcv(n=50_000, freq="5min", seed=42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2018-01-01", periods=n, freq=freq, tz="UTC")
    ret = rng.normal(0, 0.0007, n)
    close = 1300 * np.exp(np.cumsum(ret))
    high = close * (1 + np.abs(rng.normal(0, 0.0005, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.0005, n)))
    open_ = np.roll(close, 1); open_[0] = close[0]
    volume = rng.integers(10, 1000, n).astype(float)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=idx)


def main():
    df = make_synthetic_ohlcv()
    print(f"Synthetic data: {df.index.min()} .. {df.index.max()} ({len(df)} bars)")

    params = VWAPRSIParams()
    result = run_backtest(df, params, symbol="XAUUSD")
    trades = result["trades"]
    print(f"\nTrades generated: {len(trades)}")
    if len(trades) < 5:
        print("Too few trades for meaningful stats on this synthetic sample -- pipeline check only.")
        return

    report = full_report(trades["pnl"], trades["return"])
    print("\n--- Performance report (SYNTHETIC DATA -- not a real edge) ---")
    print(json.dumps(report, indent=2, default=str))

    mc = run_monte_carlo(trades["return"], n_iterations=5000, method="bootstrap", seed=1)
    print("\n--- Monte Carlo (5,000 iterations, bootstrap) ---")
    print(json.dumps(mc, indent=2, default=str))

    # WFO wiring sanity check with trivial optimize/backtest functions
    # (optimize_fn just returns the default params; a real WFO would grid-search here).
    def optimize_fn(is_data):
        return params.__dict__

    def backtest_fn(data, p):
        r = run_backtest(data, VWAPRSIParams(**p), symbol="XAUUSD")
        t = r["trades"]
        if len(t) == 0:
            return {"total_return_pct": 0.0}
        return full_report(t["pnl"], t["return"])

    windows = build_windows(df.index.min(), df.index.max(), is_years=2, oos_years=1)
    print(f"\nWFO Method 1 (2y IS / 1y OOS) windows built: {len(windows)}")
    if windows:
        wfo_result = run_wfo(df, windows[:1], optimize_fn, backtest_fn)  # just 1 window for a quick sanity check
        print(wfo_result[["is_start", "is_end", "oos_start", "oos_end", "efficiency_ratio"]].to_string())


if __name__ == "__main__":
    main()
