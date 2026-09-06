"""Walk-forward validation + cost stress for the risk-managed overlay,
then the final instrument selection.

Note on method: the overlay has NO fitted parameters (20d vol, 15% target,
200d trend are all pre-registered from the literature). So "walk-forward"
here is not parameter re-fitting -- it is rolling out-of-sample stability:
does the fixed rule beat a volatility-matched hold in window after window,
or was the full-sample result carried by one lucky regime?

That is the right question. A rule with no free parameters cannot be
curve-fit, but it can still be a fluke of one era.
"""
import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from common.data_fetch import load_parquet
from common.portfolio import (vol_target_weights, trend_gate, apply_weights,
                              vol_matched_benchmark, summarize)

DATA_ROOT = ROOT / "data_cache"
ASSETS = ["XAUUSD", "XAGUSD", "USOIL", "BTCUSD", "ETHUSD"]
VOL_TARGET, VOL_WINDOW, TREND_WINDOW = 0.15, 20, 200
WINDOW_YEARS, STEP_YEARS = 3, 1


def load(sym):
    df = load_parquet(sym, "D1", root=DATA_ROOT)
    px = df["close"].dropna()
    ret = px.pct_change().fillna(0.0)
    cost = float((df["spread"] / df["close"] / 2).median())
    return px, ret, (0.0 if not np.isfinite(cost) else cost)


def overlay_weights(px, ret):
    return trend_gate(px, TREND_WINDOW) * vol_target_weights(ret, VOL_TARGET, VOL_WINDOW)


def rolling_validation(sym, cost_mult=1.0):
    px, ret, cost = load(sym)
    cost *= cost_mult
    w = overlay_weights(px, ret)
    # warm-up: the trend gate needs TREND_WINDOW bars before it means anything
    start = ret.index[TREND_WINDOW + VOL_WINDOW]
    ret, w, px = ret.loc[start:], w.loc[start:], px.loc[start:]

    wins_s, wins_dd, rows = 0, 0, []
    t0 = ret.index[0]
    while True:
        t1 = t0 + pd.DateOffset(years=WINDOW_YEARS)
        if t1 > ret.index[-1]:
            break
        sl = (ret.index >= t0) & (ret.index < t1)
        if sl.sum() < 250:
            break
        r = apply_weights(ret[sl], w[sl], cost)
        bh = apply_weights(ret[sl], pd.Series(1.0, index=ret.index[sl]), cost)
        vm = vol_matched_benchmark(bh, r)
        s, v = summarize(r), summarize(vm)
        if s and v:
            ds, ddd = s["sharpe"] - v["sharpe"], s["max_drawdown"] - v["max_drawdown"]
            wins_s += ds > 0
            wins_dd += ddd > 0
            rows.append({"start": str(t0.date()), "d_sharpe": ds, "d_dd": ddd,
                         "strat_dd": s["max_drawdown"], "vm_dd": v["max_drawdown"]})
        t0 = t0 + pd.DateOffset(years=STEP_YEARS)
    return rows, wins_s, wins_dd


def main():
    print(f"ROLLING OUT-OF-SAMPLE VALIDATION ({WINDOW_YEARS}y windows, {STEP_YEARS}y step)")
    print("Overlay = 200d trend gate x 15% vol target. No fitted parameters.\n")
    print(f"{'asset':8s} {'windows':>8s} {'Sharpe wins':>12s} {'DD wins':>9s} "
          f"{'mean dSharpe':>13s} {'mean dDD':>10s}")
    print("-" * 66)

    summary = {}
    for sym in ASSETS:
        try:
            rows, ws, wdd = rolling_validation(sym)
        except (FileNotFoundError, IndexError):
            continue
        if not rows:
            print(f"{sym:8s} insufficient history")
            continue
        n = len(rows)
        md = np.mean([r["d_sharpe"] for r in rows])
        mdd = np.mean([r["d_dd"] for r in rows])
        summary[sym] = {"n_windows": n, "sharpe_wins": ws, "dd_wins": wdd,
                        "mean_d_sharpe": md, "mean_d_dd": mdd, "windows": rows}
        print(f"{sym:8s} {n:8d} {ws:>7d}/{n:<4d} {wdd:>4d}/{n:<4d} "
              f"{md:+13.3f} {mdd*100:+9.1f}pt")

    print("\n" + "=" * 66)
    print("COST STRESS TEST (does it survive pessimistic execution?)")
    print("=" * 66)
    print(f"{'asset':8s} {'1x spread':>22s} {'3x':>16s} {'10x':>16s}")
    for sym in ["BTCUSD", "ETHUSD"]:
        line = f"{sym:8s}"
        for mult in [1, 3, 10]:
            px, ret, cost = load(sym)
            w = overlay_weights(px, ret)
            r = apply_weights(ret, w, cost * mult)
            s = summarize(r, w)
            bh = apply_weights(ret, pd.Series(1.0, index=ret.index), cost * mult)
            vm = summarize(vol_matched_benchmark(bh, r))
            line += f"   Sh {s['sharpe']:+.2f} (vm {vm['sharpe']:+.2f})"
        print(line)

    (ROOT / "overlay_validation.json").write_text(json.dumps(summary, indent=2, default=str))

    print("\n" + "=" * 66)
    print("SELECTION: which instruments carry evidence for the overlay?")
    print("=" * 66)
    ranked = sorted(summary.items(),
                    key=lambda kv: (kv[1]["dd_wins"] / kv[1]["n_windows"],
                                    kv[1]["mean_d_dd"]), reverse=True)
    for sym, s in ranked:
        frac_dd = s["dd_wins"] / s["n_windows"]
        frac_s = s["sharpe_wins"] / s["n_windows"]
        verdict = ("TRADEABLE" if frac_dd >= 0.7 and s["mean_d_dd"] > 0
                   else "no evidence")
        print(f"  {sym:8s} DD wins {frac_dd:5.0%}  Sharpe wins {frac_s:5.0%}  "
              f"mean dDD {s['mean_d_dd']*100:+5.1f}pt  -> {verdict}")


if __name__ == "__main__":
    main()
