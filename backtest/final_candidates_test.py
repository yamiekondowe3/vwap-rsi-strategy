"""FINAL TEST — the three candidates that were never properly controlled.

Three cells from the 45-cell ceiling sweep were positive at zero cost with
real samples. They predate the placebo harness and the cross-sectional
test, so they have never faced the controls that killed everything else.

THE CRUX: these three were SELECTED from 45 cells on in-sample performance.
Re-testing them on the same data is circular — that is exactly the mistake
that made ETHUSD look tradeable (8/8 rolling windows, all on the asset
chosen for being best). So the decisive gate is Gate C: replication on the
26-pair crypto universe, data that played no part in selecting them.
Gates A, B and D are supporting evidence only.

Pre-registered decision rule:
  passes Gate C  -> genuine candidate, proceed to small-size paper trading
  fails Gate C   -> book closed
"""
import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from common.data_fetch import load_parquet
from common.backtest_core import run as run_core
from common.exits import ExitPolicy
from common.metrics import full_report
from common.placebo import run_placebo
from common.portfolio import (effective_sample_size, average_pairwise_correlation,
                              block_bootstrap_ci, TRADING_DAYS)

DATA_ROOT = ROOT / "data_cache"
POLICY = ExitPolicy(mode="fixed", stop_atr=2.0, target_atr=2.0)   # as in the ceiling sweep
PLACEBO_RUNS = 200

CANDIDATES = [
    {"name": "ORB vol2x", "strategy": "ORB", "symbol": "XAUUSD", "tf": "H1",
     "ceiling_er": +0.1158, "cross_section": False},
    {"name": "ORB vol2x", "strategy": "ORB", "symbol": "BTCUSD", "tf": "H1",
     "ceiling_er": +0.1149, "cross_section": True},
    {"name": "VWAP+RSI p10", "strategy": "VWAP+RSI", "symbol": "BTCUSD", "tf": "M15",
     "ceiling_er": +0.0961, "cross_section": True},
]


def signals(strategy, df):
    """Engines are reused UNCHANGED — any edit to the rules would invalidate
    the replication, so this only calls their existing prepare_signals."""
    if strategy == "ORB":
        sys.path.insert(0, str(ROOT / "orb-pivots-strategy"))
    else:
        sys.path.insert(0, str(ROOT / "vwap-rsi-strategy"))
    for m in [k for k in list(sys.modules) if k.startswith("backtest")]:
        del sys.modules[m]
    if strategy == "ORB":
        from backtest.engine import prepare_signals, ORBPivotParams
        p = ORBPivotParams(or_window_bars=1, stop_atr_mult=2.0, target_atr_mult=2.0,
                           use_volume_filter=True, volume_mult=2.0)
    else:
        from backtest.engine import prepare_signals, VWAPRSIParams
        p = VWAPRSIParams(adaptive_rsi=True, rsi_pctile=10, rsi_pctile_window=500,
                          stop_atr_mult=2.0, target_atr_mult=2.0)
    return prepare_signals(df, p)


def evaluate(strategy, symbol, tf, with_placebo=False):
    df = load_parquet(symbol, tf, root=DATA_ROOT)
    sig = signals(strategy, df)
    t = run_core(sig, POLICY, symbol)["trades"]
    if len(t) < 30:
        return None
    rep = full_report(t["pnl"], t["return"], r_multiples=t["r_multiple"],
                      entry_ts=t["entry_ts"])
    r = t["r_multiple"].dropna()
    _, pval = stats.ttest_1samp(r, 0.0)
    out = {"n_trades": rep["n_trades"], "win_rate": rep["win_rate"],
           "profit_factor": rep["profit_factor"], "expectancy_r": rep["expectancy_r"],
           "sharpe_r": rep["sharpe_r"], "p_value": float(pval), "r_series": r}
    if with_placebo:
        plc = run_placebo(sig, POLICY, symbol, n_entries=len(t),
                          long_ratio=float((t["side"] == 1).mean()),
                          eligible=sig["atr"].notna(), n_runs=PLACEBO_RUNS)
        z = np.nan
        if plc.get("n_runs", 0) > 2 and plc["expectancy_r_std"] > 0:
            z = (rep["expectancy_r"] - plc["expectancy_r_mean"]) / plc["expectancy_r_std"]
        out["placebo_er"] = plc.get("expectancy_r_mean", np.nan)
        out["placebo_z"] = float(z)
    return out


def rolling_windows(strategy, symbol, tf, years=3, step=1):
    df = load_parquet(symbol, tf, root=DATA_ROOT)
    sig = signals(strategy, df)
    t = run_core(sig, POLICY, symbol)["trades"]
    if len(t) < 50:
        return [], []
    t = t.copy()
    t["entry_ts"] = pd.to_datetime(t["entry_ts"])
    overlap, nonoverlap = [], []
    t0 = t["entry_ts"].min()
    end = t["entry_ts"].max()
    while t0 + pd.DateOffset(years=years) <= end:
        t1 = t0 + pd.DateOffset(years=years)
        chunk = t[(t["entry_ts"] >= t0) & (t["entry_ts"] < t1)]
        if len(chunk) >= 20:
            overlap.append(float(chunk["r_multiple"].mean()))
        t0 = t0 + pd.DateOffset(years=step)
    t0 = t["entry_ts"].min()
    while t0 + pd.DateOffset(years=years) <= end:
        t1 = t0 + pd.DateOffset(years=years)
        chunk = t[(t["entry_ts"] >= t0) & (t["entry_ts"] < t1)]
        if len(chunk) >= 20:
            nonoverlap.append(float(chunk["r_multiple"].mean()))
        t0 = t1
    return overlap, nonoverlap


def crypto_universe(tf):
    out = []
    for p in sorted((DATA_ROOT).glob("*")):
        if not p.is_dir():
            continue
        f = p / tf / f"{p.name}_{tf}.parquet"
        if f.exists() and p.name not in {"XAUUSD", "XAGUSD", "USOIL", "US500",
                                         "US30", "DE40", "JP225"}:
            out.append(p.name)
    return out


def main():
    results = {"candidates": [], "cross_section": {}}

    print("=" * 84)
    print("GATE A+B — real costs and random-entry placebo (on the ORIGINAL asset)")
    print("=" * 84)
    print(f"{'candidate':16s} {'asset':8s} {'TF':4s} {'n':>5s} {'PF':>7s} "
          f"{'E[R] real':>10s} {'ceiling':>9s} {'placebo':>9s} {'z':>7s}")
    for c in CANDIDATES:
        res = evaluate(c["strategy"], c["symbol"], c["tf"], with_placebo=True)
        if not res:
            print(f"{c['name']:16s} {c['symbol']:8s} insufficient trades")
            continue
        res.pop("r_series", None)
        c.update(res)
        results["candidates"].append({k: v for k, v in c.items() if k != "r_series"})
        print(f"{c['name']:16s} {c['symbol']:8s} {c['tf']:4s} {res['n_trades']:5d} "
              f"{res['profit_factor']:7.3f} {res['expectancy_r']:+10.4f} "
              f"{c['ceiling_er']:+9.4f} {res['placebo_er']:+9.4f} {res['placebo_z']:+7.2f}")
    print("\n  placebo thresholds: z>1.645 (single), z>2.39 (Bonferroni across 3)")

    print("\n" + "=" * 84)
    print("GATE D — rolling windows, overlapping vs NON-overlapping")
    print("=" * 84)
    for c in CANDIDATES:
        ov, nov = rolling_windows(c["strategy"], c["symbol"], c["tf"])
        if not ov:
            continue
        print(f"  {c['name']:16s} {c['symbol']:8s} overlapping {sum(1 for x in ov if x>0)}/{len(ov)} positive"
              f"   |  NON-overlapping {sum(1 for x in nov if x>0)}/{len(nov)} positive"
              f"   (mean E[R] {np.mean(nov):+.4f})" if nov else "")

    print("\n" + "=" * 84)
    print("GATE C — CROSS-SECTIONAL REPLICATION (the decisive test)")
    print("Same fixed config on 26 crypto pairs that played no part in selecting it.")
    print("=" * 84)

    for c in CANDIDATES:
        if not c.get("cross_section"):
            print(f"\n{c['name']} / {c['symbol']} {c['tf']}: NO CROSS-SECTION AVAILABLE.")
            print("  Silver already failed and oil has only 2.6y, so this candidate cannot")
            print("  reach the same evidential standard as the crypto ones. Not tradeable")
            print("  on Gates A/B/D alone.")
            continue

        tf = c["tf"]
        universe = [s for s in crypto_universe(tf) if s != c["symbol"]]
        print(f"\n{c['name']} / {tf}  — {len(universe)} unseen pairs")
        rows, series = [], {}
        for sym in universe:
            try:
                res = evaluate(c["strategy"], sym, tf)
            except Exception:
                continue
            if not res:
                continue
            series[sym] = res.pop("r_series")
            rows.append({"symbol": sym, **res})
        if not rows:
            print("  no assets produced enough trades")
            continue
        d = pd.DataFrame(rows)
        n = len(d)
        pos = int((d["expectancy_r"] > 0).sum())
        print(f"  {'symbol':10s} {'n':>6s} {'PF':>7s} {'E[R]':>9s}")
        for _, r in d.sort_values("expectancy_r", ascending=False).iterrows():
            print(f"  {r['symbol']:10s} {r['n_trades']:6.0f} {r['profit_factor']:7.3f} "
                  f"{r['expectancy_r']:+9.4f}")
        R = pd.DataFrame({k: v.reset_index(drop=True) for k, v in series.items()})
        rho = average_pairwise_correlation(R.dropna()) if R.shape[1] > 1 else 0.0
        print(f"\n  positive E[R]      : {pos}/{n} ({pos/n:.0%})")
        print(f"  median E[R]        : {d['expectancy_r'].median():+.4f}")
        print(f"  IQR                : {d['expectancy_r'].quantile(.25):+.4f} to "
              f"{d['expectancy_r'].quantile(.75):+.4f}")
        print(f"  original asset E[R]: {c['expectancy_r']:+.4f} "
              f"({stats.percentileofscore(d['expectancy_r'], c['expectancy_r']):.0f}th pct)")
        print(f"  effective sample   : {effective_sample_size(n, rho):.1f} of {n} (rho={rho:.2f})")
        gate = pos / n >= 0.6 and d["expectancy_r"].median() > 0
        print(f"  GATE C: {'PASS' if gate else 'FAIL'}")
        results["cross_section"][f"{c['name']}|{c['symbol']}|{tf}"] = {
            "n_assets": n, "positive": pos, "median_er": float(d["expectancy_r"].median()),
            "rho": rho, "effective_n": effective_sample_size(n, rho), "pass": bool(gate),
            "rows": rows}

    (ROOT / "final_candidates_results.json").write_text(
        json.dumps(results, indent=2, default=str))
    print("\nSaved final_candidates_results.json")


if __name__ == "__main__":
    main()
