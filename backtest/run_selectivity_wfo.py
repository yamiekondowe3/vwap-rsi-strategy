"""FINAL OPTIMIZATION TEST: walk-forward search for VWAP+RSI on XAUUSD.

Counterpart to orb-pivots-strategy/backtest/run_selectivity_wfo.py, and the
replacement for this repo's earlier verdict, which was produced under a
broken cost model (fabricated commission/spread consuming ~68% of the
per-trade risk budget) and is therefore void.

Search space -- two levers, both grounded in the source research rather
than picked arbitrarily:
  * payoff shape (stop/target ATR multiples) -- the ORB study found this
    mattered more than any entry filter, so it is searched here rather
    than assumed.
  * min_vwap_dist_atr -- require price to have genuinely stretched from
    VWAP before buying the pullback. This is the mechanical stand-in for
    the docs' VWAP deviation-band concept (trade the ~1-1.5 sigma stretch,
    not noise around the mean).

Discipline (identical to the ORB test): parameters are chosen on
IN-SAMPLE data only, scored by normalized per-trade edge (expectancy in R
units -- immune to position size and the compounding path), then applied
unchanged to the following OUT-OF-SAMPLE year. The verdict is the OOS
aggregate, never the best in-sample number. A minimum in-sample trade
count keeps the search from "winning" on a handful of lucky trades.
"""
import sys
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.data_fetch import load_parquet
from common.metrics import full_report
from common.wfo import build_windows
from backtest.engine import run_backtest, VWAPRSIParams

SHARED_DATA_ROOT = Path(__file__).resolve().parents[2] / "data_cache"

# (stop_atr_mult, target_atr_mult): 1:1, the ORB-best 2:1.5 shape, and a
# positive-RR 1:2 for contrast.
RR_SHAPES = [(2.0, 2.0), (2.0, 1.5), (1.0, 2.0)]
MIN_VWAP_DIST_ATRS = [0.0, 0.5, 1.0]   # 0.0 = no selectivity (current default)
MIN_TRADES_IS = 30                      # selection eligibility floor


def make_params(stop_mult, target_mult, min_dist):
    return VWAPRSIParams(stop_atr_mult=stop_mult, target_atr_mult=target_mult,
                         min_vwap_dist_atr=min_dist)


def evaluate(data, params):
    r = run_backtest(data, params, symbol="XAUUSD")
    t = r["trades"]
    if len(t) == 0:
        return None, 0
    rep = full_report(t["pnl"], t["return"], r_multiples=t["r_multiple"], entry_ts=t["entry_ts"])
    return rep, len(t)


def main():
    df = load_parquet("XAUUSD", "M5", root=SHARED_DATA_ROOT)
    print(f"Data: {df.index.min()} .. {df.index.max()} ({len(df)} bars)", flush=True)

    windows = build_windows(df.index.min(), df.index.max(), is_years=2, oos_years=1, step_years=1)
    grid = [(s, t, d) for (s, t) in RR_SHAPES for d in MIN_VWAP_DIST_ATRS]
    print(f"{len(windows)} walk-forward windows x {len(grid)} combos "
          f"({len(RR_SHAPES)} R:R shapes x {len(MIN_VWAP_DIST_ATRS)} VWAP-stretch filters)\n", flush=True)

    rows = []
    t_start = time.time()
    for wi, w in enumerate(windows, 1):
        is_data = df.loc[w.is_start:w.is_end]
        oos_data = df.loc[w.oos_start:w.oos_end]
        if is_data.empty or oos_data.empty:
            continue

        # --- select on IN-SAMPLE only, by normalized per-trade edge ---
        best = None
        for stop_mult, target_mult, min_dist in grid:
            rep, n = evaluate(is_data, make_params(stop_mult, target_mult, min_dist))
            if rep is None or n < MIN_TRADES_IS:
                continue
            score = rep.get("expectancy_r", -np.inf)
            if best is None or score > best["score"]:
                best = {"score": score, "stop": stop_mult, "target": target_mult,
                        "min_dist": min_dist, "is_n_trades": n}
        if best is None:
            print(f"[{wi}/{len(windows)}] {w.oos_start.date()}: no eligible IS combo", flush=True)
            continue

        # --- apply unchanged to OUT-OF-SAMPLE ---
        oos_rep, oos_n = evaluate(oos_data, make_params(best["stop"], best["target"], best["min_dist"]))
        row = {
            "oos_year": str(w.oos_start.date()),
            "chosen_rr": f"{best['stop']}:{best['target']}",
            "chosen_min_vwap_dist_atr": best["min_dist"],
            "is_expectancy_r": round(best["score"], 4),
            "is_n_trades": best["is_n_trades"],
            "oos_n_trades": oos_n,
            "oos_expectancy_r": round(oos_rep.get("expectancy_r", 0.0), 4) if oos_rep else 0.0,
            "oos_win_rate": round(oos_rep["win_rate"], 4) if oos_rep else 0.0,
            "oos_sharpe_r": round(oos_rep.get("sharpe_r", 0.0), 3) if oos_rep else 0.0,
            "oos_total_return_pct": round(oos_rep["total_return_pct"], 4) if oos_rep else 0.0,
        }
        rows.append(row)
        print(f"[{wi}/{len(windows)}] OOS {row['oos_year']}: "
              f"chose RR {row['chosen_rr']}, stretch>={row['chosen_min_vwap_dist_atr']}xATR | "
              f"IS E[R]={row['is_expectancy_r']:+.4f} -> OOS E[R]={row['oos_expectancy_r']:+.4f} "
              f"({row['oos_n_trades']} trades, WR {row['oos_win_rate']:.1%})", flush=True)

    result = pd.DataFrame(rows)
    print(f"\nTotal walk-forward time: {time.time()-t_start:.0f}s")
    if result.empty:
        print("No windows produced results.")
        return

    print("\n" + "=" * 70)
    print("FINAL OUT-OF-SAMPLE VERDICT (normalized, per-trade edge in R units)")
    print("=" * 70)
    mean_oos_r = result["oos_expectancy_r"].mean()
    pos_windows = int((result["oos_expectancy_r"] > 0).sum())
    print(result.to_string(index=False))
    print(f"\nWindows with positive OOS edge : {pos_windows} / {len(result)}")
    print(f"Mean OOS expectancy            : {mean_oos_r:+.4f} R per trade")
    print(f"Total OOS trades               : {int(result['oos_n_trades'].sum())}")
    print(f"Mean OOS win rate              : {result['oos_win_rate'].mean():.1%}")
    print(f"Mean OOS Sharpe (R-normalized) : {result['oos_sharpe_r'].mean():+.3f}")
    verdict = "PROFITABLE out-of-sample" if mean_oos_r > 0 else "NOT profitable out-of-sample"
    print(f"\nVERDICT: {verdict}")

    out_path = Path(__file__).resolve().parents[1] / "reports" / "xauusd_vwap_rsi_selectivity_wfo_results.json"
    out_path.write_text(json.dumps({
        "grid": {"rr_shapes": RR_SHAPES, "min_vwap_dist_atrs": MIN_VWAP_DIST_ATRS},
        "windows": rows,
        "summary": {"mean_oos_expectancy_r": mean_oos_r, "positive_windows": pos_windows,
                    "total_windows": len(result), "total_oos_trades": int(result["oos_n_trades"].sum()),
                    "mean_oos_win_rate": float(result["oos_win_rate"].mean()),
                    "mean_oos_sharpe_r": float(result["oos_sharpe_r"].mean()),
                    "verdict": verdict},
    }, indent=2, default=str))
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
