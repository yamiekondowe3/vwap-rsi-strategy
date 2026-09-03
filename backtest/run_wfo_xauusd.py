"""Real walk-forward optimization: VWAP+RSI on XAUUSD, real MT5 M5 data.

Grid-searches a small parameter space on each IS window, selects the best
by IS Sharpe (requiring a minimum trade count to avoid picking degenerate
low-sample "winners"), then evaluates that exact parameter set OOS. This is
the actual go/no-go check -- if OOS expectancy stays negative across most
windows, the strategy is dead on this instrument, not just unlucky on
defaults. Only Method 1 (2y IS / 1y OOS) is run here for time budget;
Method 2 (7y/1y) is a straightforward follow-up using the same functions.
"""
import sys
import json
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.data_fetch import load_parquet
from common.metrics import full_report
from common.wfo import build_windows, run_wfo
from backtest.engine import run_backtest, VWAPRSIParams

SHARED_DATA_ROOT = Path(__file__).resolve().parents[2] / "data_cache"

# Small, deliberately modest grid -- this is a real search, not an
# exhaustive one, per the overfitting warning in the research docs (fewer
# knobs = less spurious-winner risk). RSI thresholds held at the mechanical
# default (30/70) to keep the search space small and interpretable.
STOP_MULTS = [1.5, 2.0, 3.0]
TARGET_MULTS = [1.0, 2.0]
MIN_TRADES_FOR_SELECTION = 15


def optimize_fn(is_data: pd.DataFrame) -> dict:
    best_params, best_sharpe = VWAPRSIParams().__dict__, -float("inf")
    for stop_mult in STOP_MULTS:
        for target_mult in TARGET_MULTS:
            p = VWAPRSIParams(stop_atr_mult=stop_mult, target_atr_mult=target_mult)
            r = run_backtest(is_data, p, symbol="XAUUSD")
            trades = r["trades"]
            if len(trades) < MIN_TRADES_FOR_SELECTION:
                continue
            rep = full_report(trades["pnl"], trades["return"])
            if rep["sharpe"] > best_sharpe:
                best_sharpe = rep["sharpe"]
                best_params = p.__dict__
    return best_params


def backtest_fn(data: pd.DataFrame, params: dict) -> dict:
    r = run_backtest(data, VWAPRSIParams(**params), symbol="XAUUSD")
    trades = r["trades"]
    if len(trades) == 0:
        return {"total_return_pct": 0.0, "sharpe": 0.0, "n_trades": 0, "expectancy": 0.0, "win_rate": 0.0}
    return full_report(trades["pnl"], trades["return"])


def main():
    df = load_parquet("XAUUSD", "M5", root=SHARED_DATA_ROOT)
    print(f"Data: {df.index.min()} .. {df.index.max()} ({len(df)} bars)")

    windows = build_windows(df.index.min(), df.index.max(), is_years=2, oos_years=1, step_years=1)
    print(f"Method 1 (2y IS / 1y OOS): {len(windows)} windows, grid size {len(STOP_MULTS) * len(TARGET_MULTS)}")

    t0 = time.time()
    result = run_wfo(df, windows, optimize_fn, backtest_fn)
    print(f"WFO took {time.time()-t0:.1f}s")

    cols = ["is_start", "is_end", "oos_start", "oos_end", "params",
            "oos_n_trades", "oos_total_return_pct", "oos_sharpe", "oos_expectancy", "oos_win_rate",
            "efficiency_ratio"]
    print("\n--- WFO Method 1 results (real XAUUSD data) ---")
    print(result[cols].to_string())

    n_positive_oos = (result["oos_total_return_pct"] > 0).sum()
    print(f"\nWindows with positive OOS return: {n_positive_oos} / {len(result)}")
    print(f"Mean OOS Sharpe: {result['oos_sharpe'].mean():.3f}")
    print(f"Mean OOS expectancy: {result['oos_expectancy'].mean():.4f}")

    out_path = Path(__file__).resolve().parents[1] / "reports" / "xauusd_vwap_rsi_wfo_method1_results.json"
    result.to_json(out_path, orient="records", indent=2, date_format="iso")
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
