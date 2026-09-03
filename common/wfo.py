"""Walk-forward optimization harness supporting both paradigms from the
project brief:
  Method 1: 2y in-sample / 1y out-of-sample, rolled 1y at a time.
  Method 2: 7y in-sample / 1y out-of-sample, rolled 1y at a time.

This module only builds the rolling IS/OOS windows and runs a supplied
(optimize_fn, backtest_fn) pair over them -- it is strategy-agnostic so both
VWAP+RSI and ORB+Pivots can reuse it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any

import pandas as pd


@dataclass
class WFOWindow:
    is_start: pd.Timestamp
    is_end: pd.Timestamp
    oos_start: pd.Timestamp
    oos_end: pd.Timestamp


def build_windows(
    data_start: pd.Timestamp,
    data_end: pd.Timestamp,
    is_years: int,
    oos_years: int = 1,
    step_years: int = 1,
) -> list[WFOWindow]:
    windows = []
    is_start = data_start
    while True:
        is_end = is_start + pd.DateOffset(years=is_years)
        oos_start = is_end
        oos_end = oos_start + pd.DateOffset(years=oos_years)
        if oos_end > data_end:
            break
        windows.append(WFOWindow(is_start, is_end, oos_start, oos_end))
        is_start = is_start + pd.DateOffset(years=step_years)
    return windows


def run_wfo(
    df: pd.DataFrame,
    windows: list[WFOWindow],
    optimize_fn: Callable[[pd.DataFrame], dict],
    backtest_fn: Callable[[pd.DataFrame, dict], dict],
) -> pd.DataFrame:
    """optimize_fn(is_data) -> best_params dict, selected on IS data only.
    backtest_fn(oos_data, params) -> metrics dict (see common.metrics.full_report).
    Returns one row per window with IS params + OOS metrics, so
    OOS-performance decay is directly inspectable per window.
    """
    rows = []
    for w in windows:
        is_data = df.loc[w.is_start:w.is_end]
        oos_data = df.loc[w.oos_start:w.oos_end]
        if is_data.empty or oos_data.empty:
            continue
        params = optimize_fn(is_data)
        is_metrics = backtest_fn(is_data, params)
        oos_metrics = backtest_fn(oos_data, params)
        row = {
            "is_start": w.is_start, "is_end": w.is_end,
            "oos_start": w.oos_start, "oos_end": w.oos_end,
            "params": params,
        }
        row.update({f"is_{k}": v for k, v in is_metrics.items()})
        row.update({f"oos_{k}": v for k, v in oos_metrics.items()})
        # Efficiency ratio: how much of in-sample edge survives out-of-sample.
        is_ret, oos_ret = is_metrics.get("total_return_pct", 0), oos_metrics.get("total_return_pct", 0)
        row["efficiency_ratio"] = (oos_ret / is_ret) if is_ret not in (0, None) else float("nan")
        rows.append(row)
    return pd.DataFrame(rows)


def compare_methods(
    df: pd.DataFrame,
    optimize_fn: Callable[[pd.DataFrame], dict],
    backtest_fn: Callable[[pd.DataFrame, dict], dict],
) -> dict[str, pd.DataFrame]:
    """Runs both WFO paradigms (2y/1y and 7y/1y) over the full achieved
    history and returns both result tables for side-by-side comparison, per
    project brief Phase 4."""
    data_start, data_end = df.index.min(), df.index.max()
    method1 = build_windows(data_start, data_end, is_years=2, oos_years=1, step_years=1)
    method2 = build_windows(data_start, data_end, is_years=7, oos_years=1, step_years=1)
    return {
        "method1_short_window": run_wfo(df, method1, optimize_fn, backtest_fn),
        "method2_long_window": run_wfo(df, method2, optimize_fn, backtest_fn),
    }
