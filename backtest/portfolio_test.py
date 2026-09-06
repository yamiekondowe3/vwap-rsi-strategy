"""Risk-managed exposure: does dynamic sizing beat static sizing at matched risk?

Pre-registered configuration, nothing searched (in-sample selection was
already shown to have zero predictive power in this project):
  volatility estimate  20-day realised, annualised
  volatility target    15% annualised
  trend gate           200-day moving average
  max leverage         1.0 (no borrowing)
  costs                the broker's real recorded spread, charged on turnover

Four exposure rules per asset, each compared against THREE benchmarks:
  - raw buy & hold                (the flattering benchmark)
  - VOLATILITY-MATCHED buy & hold (the decisive one)
  - random-gate placebo           (same time-in-market, random timing)

The vol-matched benchmark is the whole point. Any rule that sits in cash
part of the time reduces drawdown simply by holding less, which is not
skill. Levering static buy-and-hold to the same realised volatility asks
the only question that matters: does TIMING the exposure beat merely
SIZING it?
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
                              vol_matched_benchmark, random_gate_placebo,
                              inverse_vol_weights, summarize, TRADING_DAYS)

DATA_ROOT = ROOT / "data_cache"
# USOIL has only ~2.6y (vs 11-15.7y for the rest) and is flagged, not excluded.
ASSETS = ["XAUUSD", "XAGUSD", "USOIL", "BTCUSD", "ETHUSD"]
SHORT_HISTORY = {"USOIL"}

VOL_TARGET, VOL_WINDOW, TREND_WINDOW = 0.15, 20, 200


def load(sym):
    df = load_parquet(sym, "D1", root=DATA_ROOT)
    px = df["close"].dropna()
    ret = px.pct_change().fillna(0.0)
    # half-spread as a fraction of price = cost of one unit of turnover
    cost = float((df["spread"] / df["close"] / 2).median())
    if not np.isfinite(cost):
        cost = 0.0
    return px, ret, cost


def rules(px, ret):
    ones = pd.Series(1.0, index=ret.index)
    return {
        "buy_and_hold": ones,
        "vol_target": vol_target_weights(ret, VOL_TARGET, VOL_WINDOW),
        "trend_gate": trend_gate(px, TREND_WINDOW),
        "trend_x_voltarget": trend_gate(px, TREND_WINDOW) * vol_target_weights(ret, VOL_TARGET, VOL_WINDOW),
    }


def main():
    rows = []
    print(f"Pre-registered: {VOL_WINDOW}d vol estimate, {VOL_TARGET:.0%} target, "
          f"{TREND_WINDOW}d trend gate, max leverage 1.0, real spread costs.\n")

    for sym in ASSETS:
        try:
            px, ret, cost = load(sym)
        except FileNotFoundError:
            continue
        tag = "  [SHORT HISTORY - low weight]" if sym in SHORT_HISTORY else ""
        yrs = (px.index[-1] - px.index[0]).days / 365.25
        print(f"\n{sym}  ({yrs:.1f}y, turnover cost {cost*1e4:.2f} bps){tag}")
        print(f"  {'rule':20s} {'CAGR':>8s} {'Sharpe':>7s} {'maxDD':>8s} {'Calmar':>7s} "
              f"{'ulcer':>7s} {'inMkt':>6s} | {'vs vol-matched':>22s}")

        bh_ret = apply_weights(ret, rules(px, ret)["buy_and_hold"], cost)
        for name, w in rules(px, ret).items():
            r = apply_weights(ret, w, cost)
            s = summarize(r, w)
            if not s:
                continue
            row = {"symbol": sym, "rule": name, **s}

            if name != "buy_and_hold":
                vm = vol_matched_benchmark(bh_ret, r)
                vms = summarize(vm)
                row["vm_sharpe"] = vms["sharpe"]
                row["vm_max_drawdown"] = vms["max_drawdown"]
                row["d_sharpe_vs_vm"] = s["sharpe"] - vms["sharpe"]
                row["d_dd_vs_vm"] = s["max_drawdown"] - vms["max_drawdown"]
                plc = random_gate_placebo(ret, s["time_in_market"], n_runs=200,
                                          cost_per_unit_turnover=cost)
                row["placebo_sharpe"] = plc["sharpe_mean"]
                row["placebo_z"] = ((s["sharpe"] - plc["sharpe_mean"]) / plc["sharpe_std"]
                                    if plc["sharpe_std"] > 0 else np.nan)
                verdict = (f"S {row['d_sharpe_vs_vm']:+.3f} DD {row['d_dd_vs_vm']*100:+.1f}pt "
                           f"z{row['placebo_z']:+.1f}")
                beat = (row["d_sharpe_vs_vm"] > 0 and row["d_dd_vs_vm"] > 0)
                verdict += "  BEATS" if beat else ""
            else:
                verdict = "(benchmark)"
            rows.append(row)
            print(f"  {name:20s} {s['cagr']*100:+7.1f}% {s['sharpe']:+7.2f} "
                  f"{s['max_drawdown']*100:+7.1f}% {s['calmar']:7.2f} {s['ulcer']:7.3f} "
                  f"{s['time_in_market']*100:5.0f}% | {verdict:>22s}", flush=True)

    # ---- multi-asset, long-history sleeve only ----
    print("\n" + "=" * 100)
    print("MULTI-ASSET PORTFOLIO (inverse-vol weights, long-history assets only)")
    print("=" * 100)
    long_assets = [a for a in ASSETS if a not in SHORT_HISTORY]
    px_all, ret_all, costs = {}, {}, {}
    for a in long_assets:
        p, r, c = load(a)
        px_all[a], ret_all[a], costs[a] = p, r, c
    R = pd.DataFrame(ret_all).dropna()
    P = pd.DataFrame(px_all).reindex(R.index)
    avg_cost = float(np.mean(list(costs.values())))
    print(f"  common window: {R.index[0].date()} .. {R.index[-1].date()} ({len(R)} days)")
    print("\n  correlation of daily returns:")
    print(R.corr().round(2).to_string().replace("\n", "\n    "))

    ew = pd.DataFrame(1.0 / len(long_assets), index=R.index, columns=R.columns)
    iv = inverse_vol_weights(R, VOL_WINDOW)
    gate = pd.DataFrame({a: trend_gate(P[a], TREND_WINDOW) for a in long_assets})
    iv_gated = (iv * gate)
    iv_gated = iv_gated.div(iv_gated.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0) \
                       * iv_gated.sum(axis=1).clip(upper=1.0).to_frame().values

    print()
    for name, W in [("equal_weight_BH", ew), ("inverse_vol", iv), ("inv_vol_x_trend", iv_gated)]:
        r = apply_weights(R, W, avg_cost)
        s = summarize(r, W)
        rows.append({"symbol": "PORTFOLIO", "rule": name, **s})
        extra = ""
        if name != "equal_weight_BH":
            base = apply_weights(R, ew, avg_cost)
            vm = summarize(vol_matched_benchmark(base, r))
            extra = (f" | vs vol-matched EW: S {s['sharpe']-vm['sharpe']:+.3f} "
                     f"DD {(s['max_drawdown']-vm['max_drawdown'])*100:+.1f}pt")
        print(f"  {name:18s} CAGR {s['cagr']*100:+7.1f}%  Sharpe {s['sharpe']:+.2f}  "
              f"maxDD {s['max_drawdown']*100:+7.1f}%  Calmar {s['calmar']:5.2f}{extra}")

    pd.DataFrame(rows).to_json(ROOT / "portfolio_results.json", orient="records", indent=2)

    print("\n" + "=" * 100)
    print("GATE: beats VOL-MATCHED buy & hold on BOTH Sharpe and max drawdown")
    print("=" * 100)
    df = pd.DataFrame([r for r in rows if "d_sharpe_vs_vm" in r])
    if df.empty:
        print("  no comparable rows")
        return
    winners = df[(df["d_sharpe_vs_vm"] > 0) & (df["d_dd_vs_vm"] > 0)]
    print(f"  configurations compared : {len(df)}")
    print(f"  beating vol-matched hold: {len(winners)}")
    if len(winners):
        print(winners[["symbol", "rule", "sharpe", "vm_sharpe", "d_sharpe_vs_vm",
                       "d_dd_vs_vm", "placebo_z"]].to_string(index=False))
    else:
        print("  NONE - the drawdown reduction is explained by lower exposure alone.")


if __name__ == "__main__":
    main()
