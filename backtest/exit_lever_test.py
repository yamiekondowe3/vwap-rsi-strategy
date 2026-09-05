"""THE EXIT LEVER TEST: do asymmetric exits rescue these strategies?

Five pre-registered exit mechanisms, both strategies, three instruments, on
H1. Each real result is paired with a RANDOM-ENTRY PLACEBO using identical
exits, filters and costs -- because on trending instruments a trailing stop
can look profitable while carrying no information at all.

The gate is deliberately not "did PF go up". It is:
  1. does the strategy beat its own random-entry placebo, and
  2. does it beat buy-and-hold risk-adjusted?
A configuration that fails either is drift-harvesting, not an edge.

Bonferroni correction is reported because a previous 45-cell sweep in this
project produced exactly the number of "significant" results chance predicts.
"""
import sys
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from common.data_fetch import load_parquet
from common.backtest_core import run as run_core
from common.exits import POLICIES
from common.metrics import full_report
from common.placebo import run_placebo, buy_and_hold

DATA_ROOT = ROOT / "data_cache"
SYMBOLS = ["XAUUSD", "USOIL", "BTCUSD"]
TIMEFRAME = "H1"
PLACEBO_RUNS = 30
BARS_PER_YEAR = 24 * 365


def vwap_signals(df):
    sys.path.insert(0, str(ROOT / "vwap-rsi-strategy"))
    for m in [k for k in list(sys.modules) if k.startswith("backtest")]:
        del sys.modules[m]
    from backtest.engine import prepare_signals, VWAPRSIParams
    return prepare_signals(df, VWAPRSIParams(adaptive_rsi=True, rsi_pctile=20,
                                             rsi_pctile_window=500))


def orb_signals(df):
    sys.path.insert(0, str(ROOT / "orb-pivots-strategy"))
    for m in [k for k in list(sys.modules) if k.startswith("backtest")]:
        del sys.modules[m]
    from backtest.engine import prepare_signals, ORBPivotParams
    return prepare_signals(df, ORBPivotParams(or_window_bars=1, use_volume_filter=False))


STRATEGIES = {"VWAP+RSI": vwap_signals, "ORB": orb_signals}


def main():
    rows, benchmarks = [], {}
    t_start = time.time()

    for sym in SYMBOLS:
        df = load_parquet(sym, TIMEFRAME, root=DATA_ROOT)
        benchmarks[sym] = buy_and_hold(df, BARS_PER_YEAR)
        print(f"\n{sym}: {len(df)} H1 bars, buy&hold CAGR "
              f"{benchmarks[sym]['cagr']:+.1%}, Sharpe {benchmarks[sym]['sharpe']:+.2f}, "
              f"maxDD {benchmarks[sym]['max_drawdown_pct']:.1%}", flush=True)

        for strat_name, sig_fn in STRATEGIES.items():
            sig = sig_fn(df)
            eligible = sig["atr"].notna()

            for pol_name, policy in POLICIES.items():
                res = run_core(sig, policy, sym)
                t = res["trades"]
                if len(t) < 20:
                    print(f"  {strat_name:9s} {pol_name:15s} only {len(t)} trades - skipped",
                          flush=True)
                    continue

                rep = full_report(t["pnl"], t["return"], r_multiples=t["r_multiple"],
                                  entry_ts=t["entry_ts"])
                r = t["r_multiple"].dropna()
                _, pval = stats.ttest_1samp(r, 0.0)
                long_ratio = float((t["side"] == 1).mean())

                plc = run_placebo(sig, policy, sym, n_entries=len(t),
                                  long_ratio=long_ratio, eligible=eligible,
                                  n_runs=PLACEBO_RUNS)

                # z-score of the real result within the placebo distribution
                z = np.nan
                if plc.get("n_runs", 0) > 2 and plc["expectancy_r_std"] > 0:
                    z = (rep["expectancy_r"] - plc["expectancy_r_mean"]) / plc["expectancy_r_std"]

                row = {
                    "strategy": strat_name, "symbol": sym, "exit": pol_name,
                    "exit_desc": policy.describe(), "n_trades": rep["n_trades"],
                    "win_rate": rep["win_rate"], "profit_factor": rep["profit_factor"],
                    "expectancy_r": rep["expectancy_r"],
                    "avg_win_r": rep["avg_win_r"], "avg_loss_r": rep["avg_loss_r"],
                    "payoff": (abs(rep["avg_win_r"] / rep["avg_loss_r"])
                               if rep["avg_loss_r"] else np.nan),
                    "sharpe_r": rep["sharpe_r"], "total_return_pct": rep["total_return_pct"],
                    "max_drawdown_pct": rep["max_drawdown_pct"], "p_value": float(pval),
                    "placebo_expectancy_r": plc.get("expectancy_r_mean", np.nan),
                    "placebo_pf": plc.get("profit_factor_mean", np.nan),
                    "edge_vs_placebo": rep["expectancy_r"] - plc.get("expectancy_r_mean", np.nan),
                    "placebo_z": float(z),
                }
                rows.append(row)
                beats_placebo = np.isfinite(z) and z > 1.645     # ~95% one-sided
                flag = " *** BEATS PLACEBO" if beats_placebo else ""
                print(f"  {strat_name:9s} {pol_name:15s} n={rep['n_trades']:4d} "
                      f"WR={rep['win_rate']:5.1%} payoff={row['payoff']:.2f} "
                      f"PF={rep['profit_factor']:5.3f} E[R]={rep['expectancy_r']:+.4f} "
                      f"| placebo {plc.get('expectancy_r_mean', float('nan')):+.4f} "
                      f"z={z:+.2f}{flag}", flush=True)

    out = pd.DataFrame(rows)
    (ROOT / "exit_lever_results.json").write_text(
        json.dumps({"results": rows, "buy_and_hold": benchmarks}, indent=2, default=str))
    print(f"\nTotal time: {time.time()-t_start:.0f}s")

    if out.empty:
        print("No results.")
        return

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    n = len(out)
    beats = out[out["placebo_z"] > 1.645]
    print(f"Configurations tested                 : {n}")
    print(f"Beating random-entry placebo (z>1.645): {len(beats)}  "
          f"(expected by chance: {n*0.05:.1f})")
    print(f"Bonferroni z threshold                : "
          f"{stats.norm.ppf(1 - 0.05/n):.2f}")
    surv = out[out["placebo_z"] > stats.norm.ppf(1 - 0.05 / n)]
    print(f"Surviving Bonferroni correction       : {len(surv)}")

    best = out.loc[out["expectancy_r"].idxmax()]
    print(f"\nBest raw expectancy: {best['strategy']} {best['symbol']} {best['exit']} "
          f"E[R]={best['expectancy_r']:+.4f} PF={best['profit_factor']:.3f}")
    print(f"  its placebo      : {best['placebo_expectancy_r']:+.4f} "
          f"(z={best['placebo_z']:+.2f})")

    print("\nPayoff ratios achieved (the point of asymmetric exits):")
    for pol in POLICIES:
        sub = out[out["exit"] == pol]
        if len(sub):
            print(f"  {pol:15s} mean payoff {sub['payoff'].mean():.2f}  "
                  f"mean WR {sub['win_rate'].mean():.1%}  mean PF {sub['profit_factor'].mean():.3f}")

    if len(surv) == 0:
        print("\nNO configuration beats its own random-entry placebo after correction.")
        print("Any raw improvement from asymmetric exits is drift-harvesting that")
        print("random entries capture equally well -- i.e. not signal.")
    else:
        print("\nSurvivors advance to the buy-and-hold comparison and walk-forward.")
        print(surv[["strategy", "symbol", "exit", "profit_factor", "expectancy_r",
                    "placebo_z"]].to_string(index=False))


if __name__ == "__main__":
    main()
