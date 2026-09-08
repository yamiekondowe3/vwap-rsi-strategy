"""INFORMATION-EDGE TEST — funding and order flow, through the same controls.

These are the first signals tested in this project that are not derived from
price history. That is the whole point: every price-pattern arrangement has
been falsified here, and the remaining hypothesis was that a different KIND
of input might carry information that price alone does not.

Signals (each self-calibrating by trailing percentile, so no per-market
constants to tune -- the same anti-overfit device used for adaptive RSI):

  funding_fade   extreme positive funding = leveraged longs paying heavily to
                 stay in = crowded = fade it. Extreme negative = crowded
                 shorts = go long. A positioning/crowding signal.
  of_momentum    aggressive-buyer dominance persists (informed flow).
  of_fade        aggressive-buyer dominance exhausts (liquidity provision).
                 Both directions are tested because the literature supports
                 each at different horizons; whichever wins must still clear
                 the placebo and the cross-section.

Costs are BINANCE taker fees (4bp/side), not Deriv CFD spreads -- a genuinely
cheaper venue, which matters because the last strategy failed by 0.008R.

Control stack, unchanged: frictionless ceiling -> real costs -> random-entry
placebo -> cross-sectional replication on unselected symbols.
"""
import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
DATA = ROOT / "data_binance"

from common.backtest_core import run as run_core
from common.costs import FrictionModel
from common.exits import ExitPolicy
from common.indicators import atr
from common.metrics import full_report
from common.placebo import run_placebo
from common.portfolio import effective_sample_size, average_pairwise_correlation

# Binance perp taker fee ~0.04% per side. Modelled as a spread-equivalent so
# the existing FrictionModel charges it on entry and exit.
TAKER_BPS = 4.0
POLICY = ExitPolicy(mode="fixed", stop_atr=2.0, target_atr=2.0)
PCT_WINDOW = 500          # trailing bars defining "extreme"


def load(sym):
    df = pd.read_parquet(DATA / f"{sym}_8h.parquet")
    df["atr"] = atr(df, 14)
    # spread-equivalent of the taker fee, so entry+exit each pay half of it
    df["spread"] = df["close"] * (2 * TAKER_BPS / 1e4)
    return df


def build_signals(df, kind, pct=10.0):
    """All thresholds are trailing percentiles, shifted one bar so the current
    bar never contributes to the threshold it is judged against."""
    out = df.copy()
    if kind.startswith("funding"):
        src = out["funding"]
    else:
        src = out["of_imbalance"]
    roll = src.rolling(PCT_WINDOW, min_periods=PCT_WINDOW // 2)
    lo = roll.quantile(pct / 100.0).shift(1)
    hi = roll.quantile(1 - pct / 100.0).shift(1)

    if kind == "funding_fade":
        # crowded longs (funding high) -> short ; crowded shorts -> long
        long_sig, short_sig = src <= lo, src >= hi
    elif kind == "of_momentum":
        long_sig, short_sig = src >= hi, src <= lo
    elif kind == "of_fade":
        long_sig, short_sig = src <= lo, src >= hi
    else:
        raise ValueError(kind)

    out["long_signal"] = long_sig.fillna(False)
    out["short_signal"] = short_sig.fillna(False)
    return out


def evaluate(sym, kind, pct=10.0, frictionless=False, placebo=False):
    df = load(sym)
    sig = build_signals(df, kind, pct)
    fm = FrictionModel(symbol=sym, frictionless=frictionless)
    if not frictionless:
        fm.commission_bps_override = 0.0     # fee already in the spread column
    t = run_core(sig, POLICY, sym, friction=fm)["trades"]
    if len(t) < 40:
        return None
    rep = full_report(t["pnl"], t["return"], r_multiples=t["r_multiple"],
                      entry_ts=t["entry_ts"])
    r = t["r_multiple"].dropna()
    _, pv = stats.ttest_1samp(r, 0.0)
    out = {"n": rep["n_trades"], "wr": rep["win_rate"], "pf": rep["profit_factor"],
           "er": rep["expectancy_r"], "p": float(pv), "r_series": r}
    if placebo:
        plc = run_placebo(sig, POLICY, sym, n_entries=len(t),
                          long_ratio=float((t["side"] == 1).mean()),
                          eligible=sig["atr"].notna(), n_runs=150)
        z = np.nan
        if plc.get("n_runs", 0) > 2 and plc["expectancy_r_std"] > 0:
            z = (rep["er"] if False else rep["expectancy_r"] - plc["expectancy_r_mean"]) \
                / plc["expectancy_r_std"]
        out["z"] = float(z)
    return out


def main():
    universe = json.loads((DATA / "universe.json").read_text())
    print(f"universe: {len(universe)} symbols\n")
    kinds = ["funding_fade", "of_momentum", "of_fade"]

    print("STAGE 1 — frictionless ceiling on BTCUSDT/ETHUSDT")
    print("(if it cannot work at zero cost, nothing downstream matters)\n")
    print(f"{'symbol':10s} {'signal':14s} {'n':>6s} {'WR':>7s} {'PF':>7s} {'E[R]':>9s}")
    print("-" * 58)
    for sym in ["BTCUSDT", "ETHUSDT"]:
        for k in kinds:
            r = evaluate(sym, k, frictionless=True)
            if r:
                r.pop("r_series", None)
                print(f"{sym:10s} {k:14s} {r['n']:6d} {r['wr']*100:6.1f}% "
                      f"{r['pf']:7.3f} {r['er']:+9.4f}", flush=True)

    print("\n\nSTAGE 2 — real Binance costs + random-entry placebo\n")
    print(f"{'symbol':10s} {'signal':14s} {'n':>6s} {'WR':>7s} {'PF':>7s} "
          f"{'E[R]':>9s} {'placebo z':>10s}")
    print("-" * 70)
    stage2 = []
    for sym in ["BTCUSDT", "ETHUSDT"]:
        for k in kinds:
            r = evaluate(sym, k, placebo=True)
            if not r:
                continue
            r.pop("r_series", None)
            stage2.append({"symbol": sym, "signal": k, **r})
            flag = "  <--" if (r["er"] > 0 and r.get("z", 0) > 1.645) else ""
            print(f"{sym:10s} {k:14s} {r['n']:6d} {r['wr']*100:6.1f}% {r['pf']:7.3f} "
                  f"{r['er']:+9.4f} {r.get('z', float('nan')):+10.2f}{flag}", flush=True)

    print("\n\nSTAGE 3 — cross-sectional replication (the decisive test)\n")
    results = {"stage2": stage2, "cross": {}}
    for k in kinds:
        rows, series = [], {}
        for sym in universe:
            try:
                r = evaluate(sym, k)
            except Exception:
                continue
            if r:
                series[sym] = r.pop("r_series")
                rows.append({"symbol": sym, **r})
        if not rows:
            continue
        d = pd.DataFrame(rows)
        pos = int((d["er"] > 0).sum())
        R = pd.DataFrame({s: v.reset_index(drop=True) for s, v in series.items()})
        rho = average_pairwise_correlation(R.dropna()) if R.shape[1] > 1 else 0.0
        neff = effective_sample_size(len(d), rho)
        print(f"  {k:14s} {pos}/{len(d)} positive ({pos/len(d):.0%}), "
              f"median E[R] {d['er'].median():+.4f}, "
              f"rho {rho:.2f}, effective N {neff:.1f}")
        best = d.nlargest(3, "er")[["symbol", "n", "pf", "er"]]
        print("      best 3:", ", ".join(f"{r.symbol} {r.er:+.3f}" for r in best.itertuples()))
        results["cross"][k] = {"n": len(d), "positive": pos,
                               "median_er": float(d["er"].median()),
                               "rho": rho, "effective_n": neff,
                               "rows": rows}

    (ROOT / "info_edge_results.json").write_text(json.dumps(results, indent=2, default=str))
    print("\nSaved info_edge_results.json")

    print("\n" + "=" * 62)
    print("VERDICT")
    print("=" * 62)
    winners = [k for k, v in results["cross"].items()
               if v["positive"] / v["n"] >= 0.6 and v["median_er"] > 0]
    if winners:
        for w in winners:
            print(f"  {w}: replicates across the cross-section — genuine candidate")
    else:
        print("  No signal replicates. Same outcome as every price-based test:")
        print("  isolated positives, negative median, no generalisation.")


if __name__ == "__main__":
    main()
