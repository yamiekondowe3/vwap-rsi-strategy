"""Test the VWAP entry triggers that were never tested.

Two gaps, both raised by the user:

1. "VWAP without RSI" -- a pure VWAP side+slope filter, no oscillator.
2. Worse: the source research document specifies the trigger as the "first
   counter-color pullback candle toward VWAP", NOT an RSI cross. This
   project substituted RSI from the very first commit, so the DOCUMENTED
   strategy was never actually implemented or tested. That is an error in
   this project, not a deliberate simplification.

Full control stack, same as everything else: real broker costs, random-entry
placebo, and cross-sectional replication -- because in-sample numbers have
been worthless in this project every single time.

("ORB without pivots" needs no test: use_pivot_filter has defaulted to False
and no test script ever enabled it, so every ORB result already WAS the
plain no-pivot version.)
"""
import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "vwap-rsi-strategy"))

from common.data_fetch import load_parquet
from common.backtest_core import run as run_core
from common.exits import ExitPolicy
from common.metrics import full_report
from common.placebo import run_placebo
from backtest.engine import prepare_signals, VWAPRSIParams

POLICY = ExitPolicy(mode="fixed", stop_atr=2.0, target_atr=2.0)
TRIGGERS = ["rsi", "pullback", "none"]
PRIMARY = [("XAUUSD", "H1"), ("BTCUSD", "H1")]


def evaluate(symbol, tf, trigger, placebo=False):
    df = load_parquet(symbol, tf, root=ROOT / "data_cache")
    p = VWAPRSIParams(trigger=trigger, stop_atr_mult=2.0, target_atr_mult=2.0,
                      adaptive_rsi=(trigger == "rsi"), rsi_pctile=20)
    sig = prepare_signals(df, p)
    t = run_core(sig, POLICY, symbol)["trades"]
    if len(t) < 30:
        return None
    rep = full_report(t["pnl"], t["return"], r_multiples=t["r_multiple"],
                      entry_ts=t["entry_ts"])
    r = t["r_multiple"].dropna()
    _, pv = stats.ttest_1samp(r, 0.0)
    out = {"n": rep["n_trades"], "wr": rep["win_rate"], "pf": rep["profit_factor"],
           "er": rep["expectancy_r"], "p": float(pv)}
    if placebo:
        plc = run_placebo(sig, POLICY, symbol, n_entries=len(t),
                          long_ratio=float((t["side"] == 1).mean()),
                          eligible=sig["atr"].notna(), n_runs=150)
        z = np.nan
        if plc.get("n_runs", 0) > 2 and plc["expectancy_r_std"] > 0:
            z = (rep["expectancy_r"] - plc["expectancy_r_mean"]) / plc["expectancy_r_std"]
        out["placebo_er"] = plc.get("expectancy_r_mean", np.nan)
        out["z"] = float(z)
    return out


def main():
    print("STAGE 1 — the three triggers on the primary assets, with placebo\n")
    print(f"{'asset':8s} {'tf':4s} {'trigger':10s} {'n':>6s} {'WR':>7s} {'PF':>7s} "
          f"{'E[R]':>9s} {'placebo':>9s} {'z':>7s}")
    print("-" * 74)
    results = []
    for sym, tf in PRIMARY:
        for trig in TRIGGERS:
            r = evaluate(sym, tf, trig, placebo=True)
            if not r:
                print(f"{sym:8s} {tf:4s} {trig:10s} too few trades")
                continue
            results.append({"symbol": sym, "tf": tf, "trigger": trig, **r})
            flag = "  <-- beats placebo" if np.isfinite(r["z"]) and r["z"] > 1.645 else ""
            print(f"{sym:8s} {tf:4s} {trig:10s} {r['n']:6d} {r['wr']*100:6.1f}% "
                  f"{r['pf']:7.3f} {r['er']:+9.4f} {r['placebo_er']:+9.4f} "
                  f"{r['z']:+7.2f}{flag}", flush=True)

    # Cross-section only for triggers that look worth it — but run it regardless
    # for the documented one, since that is the whole point of the exercise.
    print("\n\nSTAGE 2 — cross-sectional replication on unseen crypto pairs (H1)")
    print("The decisive test. In-sample numbers have been worthless every time.\n")
    universe = sorted({p.name for p in (ROOT / "data_cache").glob("*")
                       if (p / "H1" / f"{p.name}_H1.parquet").exists()
                       and p.name not in {"XAUUSD", "XAGUSD", "USOIL"}
                       and not p.name.startswith(("EUR", "GBP", "USD", "AUD", "NZD",
                                                  "CAD", "CHF", "NZD"))})
    cross = {}
    for trig in ["pullback", "none"]:
        rows = []
        for sym in universe:
            if sym == "BTCUSD":
                continue
            try:
                r = evaluate(sym, "H1", trig)
            except Exception:
                continue
            if r:
                rows.append({"symbol": sym, **r})
        if not rows:
            continue
        d = pd.DataFrame(rows)
        pos = int((d["er"] > 0).sum())
        cross[trig] = {"n_assets": len(d), "positive": pos,
                       "median_er": float(d["er"].median())}
        print(f"  trigger '{trig}': {pos}/{len(d)} positive ({pos/len(d):.0%}), "
              f"median E[R] {d['er'].median():+.4f}")
        base = [r for r in results if r["trigger"] == trig and r["symbol"] == "BTCUSD"]
        if base:
            pct = stats.percentileofscore(d["er"], base[0]["er"])
            print(f"     BTCUSD ({base[0]['er']:+.4f}) sits at the {pct:.0f}th percentile")

    (ROOT / "trigger_variants_results.json").write_text(
        json.dumps({"primary": results, "cross_section": cross}, indent=2, default=str))
    print("\nSaved trigger_variants_results.json")


if __name__ == "__main__":
    main()
