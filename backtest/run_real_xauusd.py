"""Real-data run: VWAP+RSI on XAUUSD, full achieved MT5 history (~15.7y,
M5 bars). This is the actual go/no-go check per the project plan -- real
data, real friction model, full Monte Carlo, WFO sanity check.

Run `backtest/run_poc.py` first if you want the synthetic-data pipeline
smoke test; this script is the real deliverable.
"""
import sys
import json
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.data_fetch import load_parquet, report_coverage

# The shared data cache lives at the trading-systems project root (populated
# by the ad-hoc fetch in the project root, shared across both strategy repos).
SHARED_DATA_ROOT = Path(__file__).resolve().parents[2] / "data_cache"
from common.metrics import full_report
from common.monte_carlo import run_monte_carlo
from common.wfo import build_windows, run_wfo
from backtest.engine import run_backtest, VWAPRSIParams


def main():
    df = load_parquet("XAUUSD", "M5", root=SHARED_DATA_ROOT)
    cov = report_coverage(df, "XAUUSD-M5")
    print("--- Data coverage (REAL, from MT5/Deriv-Demo) ---")
    print(json.dumps(cov, indent=2, default=str))

    params = VWAPRSIParams()
    print(f"\nRunning backtest over {len(df)} bars ({cov['achieved_start']} .. {cov['achieved_end']})...")
    t0 = time.time()
    result = run_backtest(df, params, symbol="XAUUSD")
    print(f"Backtest took {time.time()-t0:.1f}s")

    trades = result["trades"]
    print(f"\nTrades generated: {len(trades)}")
    if len(trades) < 10:
        print("Too few trades for meaningful stats.")
        return

    report = full_report(trades["pnl"], trades["return"])
    print("\n--- Performance report (REAL DATA, default un-optimized params) ---")
    print(json.dumps(report, indent=2, default=str))

    mc_boot = run_monte_carlo(trades["return"], n_iterations=5000, method="bootstrap", seed=1)
    mc_shuf = run_monte_carlo(trades["return"], n_iterations=5000, method="shuffle", seed=1)
    print("\n--- Monte Carlo: bootstrap (5,000 iterations) ---")
    print(json.dumps(mc_boot, indent=2, default=str))
    print("\n--- Monte Carlo: shuffle (5,000 iterations) ---")
    print(json.dumps(mc_shuf, indent=2, default=str))

    # WFO wiring check with default (non-optimized) params -- a real
    # optimize_fn (grid search) is a follow-up step, not run here.
    def optimize_fn(is_data):
        return params.__dict__

    def backtest_fn(data, p):
        r = run_backtest(data, VWAPRSIParams(**p), symbol="XAUUSD")
        t = r["trades"]
        if len(t) == 0:
            return {"total_return_pct": 0.0}
        return full_report(t["pnl"], t["return"])

    print("\n--- Walk-forward windows available on real history ---")
    m1 = build_windows(df.index.min(), df.index.max(), is_years=2, oos_years=1)
    m2 = build_windows(df.index.min(), df.index.max(), is_years=7, oos_years=1)
    print(f"Method 1 (2y IS/1y OOS): {len(m1)} windows")
    print(f"Method 2 (7y IS/1y OOS): {len(m2)} windows")

    out = {"coverage": cov, "report": report, "monte_carlo_bootstrap": mc_boot, "monte_carlo_shuffle": mc_shuf}
    out_path = Path(__file__).resolve().parents[1] / "reports" / "xauusd_vwap_rsi_real_data_results.json"
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nSaved results to {out_path}")


if __name__ == "__main__":
    main()
