"""FINAL TEST — ORB vol2x on the FX cross-section, the correct peer group for XAUUSD.

The ORB/XAUUSD candidate is the last survivor: +0.077R over 303 trades,
PF 1.159, placebo z=+2.04, 3/5 non-overlapping windows positive. Its one
untested weakness is cross-sectional replication.

It was previously replicated only against crypto, where it managed 9/33.
But that was arguably the wrong falsification test: an opening-range
breakout is DEFINED by a session open, and crypto trades 24/7 with no real
open, so the "opening range" computed there was an arbitrary hour. FX is
ORB's natural home and gold trades like FX — session-driven, 24/5, same
London/NY structure. ~35 FX pairs at H1 is the correct peer group.

Two outcomes, both useful:
  XAUUSD mid-pack among FX  -> confirmed artifact, conclusion airtight
  rule works broadly on FX  -> genuine finding, proceed to walk-forward
"""
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from common.data_fetch import save_parquet, load_parquet
from common.backtest_core import run as run_core
from common.exits import ExitPolicy
from common.metrics import full_report
from common.portfolio import effective_sample_size, average_pairwise_correlation

DATA_ROOT = ROOT / "data_cache"
POLICY = ExitPolicy(mode="fixed", stop_atr=2.0, target_atr=2.0)
MIN_YEARS = 6.0

# Scoped to 21 liquid majors and major crosses rather than all 51 symbols.
# Reason: requesting history makes MT5 cache it server-side, and an earlier
# unscoped run across ~90 symbols x 4 timeframes filled the disk with 21GB.
# H1-only across 21 pairs is ~700MB, and 21 near-independent observations
# is ample for a cross-section (the crypto one had rho=0.01 and ~30 assets).
FX_UNIVERSE = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
    "EURJPY", "EURGBP", "EURCHF", "EURAUD", "EURCAD",
    "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD",
    "AUDJPY", "AUDNZD", "CADJPY", "CHFJPY", "NZDJPY",
]


def fetch_fx():
    import MetaTrader5 as mt5
    if not mt5.initialize():
        raise RuntimeError(mt5.last_error())
    try:
        available = {s.name for s in mt5.symbols_get()}
        names = [n for n in FX_UNIVERSE if n in available]
        print(f"{len(names)} FX pairs requested (scoped to limit MT5 cache growth)")
        import time
        kept = []
        for name in names:
            mt5.symbol_select(name, True)
            info = mt5.symbol_info(name)
            # MT5 downloads history lazily: the first request for an untouched
            # symbol often returns 0 bars while it fetches in the background.
            # Retry a few times rather than silently dropping half the universe.
            rates = None
            for attempt in range(4):
                rates = mt5.copy_rates_from(name, mt5.TIMEFRAME_H1,
                                            datetime.now(timezone.utc), 60000)
                if rates is not None and len(rates) >= MIN_YEARS * 365 * 20:
                    break
                time.sleep(2.0)
            if rates is None or len(rates) < MIN_YEARS * 365 * 20:
                print(f"  {name:10s} skip ({0 if rates is None else len(rates)} bars)")
                continue
            df = pd.DataFrame(rates)
            df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True)
            df = df.set_index("timestamp")
            df["spread"] = df["spread"] * (info.point if info else 0.0)
            df = df.rename(columns={"tick_volume": "volume"})[
                ["open", "high", "low", "close", "volume", "spread"]]
            yrs = (df.index[-1] - df.index[0]).days / 365.25
            if yrs < MIN_YEARS:
                continue
            save_parquet(df, name, "H1")
            kept.append(name)
            print(f"  {name:10s} {len(df):6d} bars {yrs:5.1f}y", flush=True)
        return kept
    finally:
        mt5.shutdown()


def orb_signals(df):
    sys.path.insert(0, str(ROOT / "orb-pivots-strategy"))
    for m in [k for k in list(sys.modules) if k.startswith("backtest")]:
        del sys.modules[m]
    from backtest.engine import prepare_signals, ORBPivotParams
    return prepare_signals(df, ORBPivotParams(
        or_window_bars=1, stop_atr_mult=2.0, target_atr_mult=2.0,
        use_volume_filter=True, volume_mult=2.0))


def evaluate(symbol):
    df = load_parquet(symbol, "H1", root=DATA_ROOT)
    t = run_core(orb_signals(df), POLICY, symbol)["trades"]
    if len(t) < 40:
        return None
    rep = full_report(t["pnl"], t["return"], r_multiples=t["r_multiple"],
                      entry_ts=t["entry_ts"])
    r = t["r_multiple"].dropna()
    _, p = stats.ttest_1samp(r, 0.0)
    return {"n_trades": rep["n_trades"], "win_rate": rep["win_rate"],
            "profit_factor": rep["profit_factor"], "expectancy_r": rep["expectancy_r"],
            "p_value": float(p), "r_series": r}


def main():
    print("Fetching FX universe at H1...\n")
    pairs = fetch_fx()
    print(f"\n{len(pairs)} FX pairs with >= {MIN_YEARS}y of H1 history\n")

    print("=" * 74)
    print("ORB vol2x on the FX cross-section (identical config to the XAUUSD candidate)")
    print("=" * 74)
    rows, series = [], {}
    for sym in pairs + ["XAGUSD", "XAUUSD"]:
        try:
            res = evaluate(sym)
        except Exception as e:
            print(f"  {sym:10s} error: {type(e).__name__}")
            continue
        if not res:
            continue
        series[sym] = res.pop("r_series")
        rows.append({"symbol": sym, **res})

    d = pd.DataFrame(rows).sort_values("expectancy_r", ascending=False)
    print(f"  {'symbol':10s} {'n':>6s} {'WR':>7s} {'PF':>7s} {'E[R]':>9s} {'p':>7s}")
    for _, r in d.iterrows():
        mark = "  <-- CANDIDATE" if r["symbol"] == "XAUUSD" else ""
        print(f"  {r['symbol']:10s} {r['n_trades']:6.0f} {r['win_rate']*100:6.1f}% "
              f"{r['profit_factor']:7.3f} {r['expectancy_r']:+9.4f} {r['p_value']:7.3f}{mark}")

    fx_only = d[~d["symbol"].isin(["XAUUSD", "XAGUSD"])]
    n = len(fx_only)
    pos = int((fx_only["expectancy_r"] > 0).sum())
    R = pd.DataFrame({k: v.reset_index(drop=True) for k, v in series.items()
                      if k not in ("XAUUSD", "XAGUSD")})
    rho = average_pairwise_correlation(R.dropna()) if R.shape[1] > 1 else 0.0
    xau = float(d.loc[d["symbol"] == "XAUUSD", "expectancy_r"].iloc[0])
    pct = stats.percentileofscore(fx_only["expectancy_r"], xau)

    print("\n" + "=" * 74)
    print("VERDICT")
    print("=" * 74)
    print(f"  FX pairs tested        : {n}")
    print(f"  positive E[R]          : {pos}/{n} ({pos/n:.0%})")
    print(f"  median E[R]            : {fx_only['expectancy_r'].median():+.4f}")
    print(f"  IQR                    : {fx_only['expectancy_r'].quantile(.25):+.4f} to "
          f"{fx_only['expectancy_r'].quantile(.75):+.4f}")
    print(f"  average pairwise rho   : {rho:.2f}")
    print(f"  effective sample       : {effective_sample_size(n, rho):.1f} of {n}")
    print(f"\n  XAUUSD candidate E[R]  : {xau:+.4f}  ->  {pct:.0f}th percentile of FX")
    gate = pos / n >= 0.6 and fx_only["expectancy_r"].median() > 0
    print(f"\n  GATE: {'PASS - rule works broadly on FX' if gate else 'FAIL - XAUUSD is not supported by its peer group'}")
    if not gate:
        print(f"  A rule positive on only {pos/n:.0%} of session-driven assets will produce a")
        print(f"  positive XAUUSD draw about that often. The candidate is unsupported.")

    (ROOT / "fx_crosssection_results.json").write_text(
        json.dumps({"rows": rows, "n_fx": n, "positive": pos,
                    "median_er": float(fx_only["expectancy_r"].median()),
                    "rho": rho, "xau_er": xau, "xau_percentile": float(pct),
                    "pass": bool(gate)}, indent=2, default=str))
    print("\nSaved fx_crosssection_results.json")


if __name__ == "__main__":
    main()
