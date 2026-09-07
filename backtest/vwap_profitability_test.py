"""Can the VWAP filter be made profitable? Attacking the cost side.

Established: the VWAP side+slope filter with the documented pullback trigger
carries a real edge on XAUUSD H1 -- z=+2.45 vs random entry on 5,301 trades,
the best-powered result in this project. It is worth roughly +0.032R before
costs. Friction is ~0.040R. It loses by about 0.008R.

So the binding constraint is COST, not signal, and the gap is small. Every
lever below attacks cost or exposure with a stated mechanism -- none is a
parameter search:

  limit    entry rests a bid instead of crossing the spread; a mean-reversion
           entry is a natural limit order. Saves the half-spread, at the price
           of adverse selection (unfilled setups are the ones that ran away).
  wide     friction in R is cost/(stop_atr x ATR). Doubling the stop halves
           friction in R. Purely mechanical.
  h4       same mechanism via a coarser bar: ATR grows, the fixed spread
           shrinks relative to it.
  ny       the NY-open session improved 5/5 configs in earlier testing.
  long     gold and BTC both trended up across the sample; the short side may
           simply be fighting drift.

Then the combination of whatever helps, and finally the only test that has
ever mattered here: cross-sectional replication on unselected assets.
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
from common.filters import named_session_mask
from common.placebo import run_placebo
from backtest.engine import prepare_signals, VWAPRSIParams

DATA = ROOT / "data_cache"


def get(symbol, tf):
    if tf == "H4":
        h1 = load_parquet(symbol, "H1", root=DATA)
        d = h1.resample("4h").agg({"open": "first", "high": "max", "low": "min",
                                   "close": "last", "volume": "sum", "spread": "median"})
        return d.dropna()
    return load_parquet(symbol, tf, root=DATA)


def evaluate(symbol, tf="H1", stop=2.0, entry_mode="market", limit_offset=0.0,
             session=None, direction="both", placebo=False, trigger="pullback"):
    df = get(symbol, tf)
    sig = prepare_signals(df, VWAPRSIParams(trigger=trigger, stop_atr_mult=stop,
                                            target_atr_mult=stop))
    if session:
        m = named_session_mask(sig.index, session)
        sig = sig.copy()
        sig["long_signal"] &= m
        sig["short_signal"] &= m
    pol = ExitPolicy(mode="fixed", stop_atr=stop, target_atr=stop)
    res = run_core(sig, pol, symbol, entry_mode=entry_mode,
                   limit_offset_atr=limit_offset, limit_max_wait=3,
                   direction=direction)
    t = res["trades"]
    if len(t) < 30:
        return None
    rep = full_report(t["pnl"], t["return"], r_multiples=t["r_multiple"],
                      entry_ts=t["entry_ts"])
    out = {"n": rep["n_trades"], "wr": rep["win_rate"], "pf": rep["profit_factor"],
           "er": rep["expectancy_r"], "fill": res.get("fill_rate", 1.0)}
    if placebo:
        plc = run_placebo(sig, pol, symbol, n_entries=len(t),
                          long_ratio=float((t["side"] == 1).mean()),
                          eligible=sig["atr"].notna(), n_runs=120)
        z = np.nan
        if plc.get("n_runs", 0) > 2 and plc["expectancy_r_std"] > 0:
            z = (rep["expectancy_r"] - plc["expectancy_r_mean"]) / plc["expectancy_r_std"]
        out["z"] = float(z)
    return out


def main():
    print("STAGE 1 — cost levers on XAUUSD H1 (pullback trigger)\n")
    print(f"{'lever':28s} {'n':>6s} {'fill':>6s} {'WR':>7s} {'PF':>7s} {'E[R]':>9s}")
    print("-" * 68)
    levers = [
        ("baseline (market, 2xATR)", dict()),
        ("limit @ close", dict(entry_mode="limit", limit_offset=0.0)),
        ("limit @ close-0.25ATR", dict(entry_mode="limit", limit_offset=0.25)),
        ("wide stop 4xATR", dict(stop=4.0)),
        ("wide stop 6xATR", dict(stop=6.0)),
        ("H4 timeframe", dict(tf="H4")),
        ("NY session only", dict(session="ny_open")),
        ("long only", dict(direction="long_only")),
        ("short only", dict(direction="short_only")),
    ]
    rows = []
    for name, kw in levers:
        r = evaluate("XAUUSD", **kw)
        if not r:
            print(f"{name:28s} too few trades")
            continue
        rows.append({"lever": name, **r, **{k: str(v) for k, v in kw.items()}})
        print(f"{name:28s} {r['n']:6d} {r['fill']*100:5.0f}% {r['wr']*100:6.1f}% "
              f"{r['pf']:7.3f} {r['er']:+9.4f}", flush=True)

    best = max(rows, key=lambda r: r["er"])
    print(f"\nBest single lever: {best['lever']} (E[R] {best['er']:+.4f})")

    print("\n\nSTAGE 2 — combining the levers that helped, with placebo\n")
    combos = [
        ("limit + wide 4xATR", dict(entry_mode="limit", limit_offset=0.0, stop=4.0)),
        ("limit + wide + NY", dict(entry_mode="limit", limit_offset=0.0, stop=4.0,
                                   session="ny_open")),
        ("limit + wide + long", dict(entry_mode="limit", limit_offset=0.0, stop=4.0,
                                     direction="long_only")),
        ("limit + H4", dict(entry_mode="limit", limit_offset=0.0, tf="H4")),
        ("wide 4xATR + NY", dict(stop=4.0, session="ny_open")),
    ]
    print(f"{'combo':26s} {'n':>6s} {'WR':>7s} {'PF':>7s} {'E[R]':>9s} {'placebo z':>10s}")
    print("-" * 70)
    combo_rows = []
    for name, kw in combos:
        r = evaluate("XAUUSD", placebo=True, **kw)
        if not r:
            print(f"{name:26s} too few trades")
            continue
        combo_rows.append({"combo": name, **r, **{k: str(v) for k, v in kw.items()}})
        flag = "  <-- profitable + beats placebo" if (r["er"] > 0 and r.get("z", 0) > 1.645) else ""
        print(f"{name:26s} {r['n']:6d} {r['wr']*100:6.1f}% {r['pf']:7.3f} "
              f"{r['er']:+9.4f} {r.get('z', float('nan')):+10.2f}{flag}", flush=True)

    winners = [c for c in combo_rows if c["er"] > 0 and c.get("z", 0) > 1.645]
    out = {"levers": rows, "combos": combo_rows}

    print("\n\nSTAGE 3 — cross-sectional replication (the only test that has mattered)\n")
    if not winners:
        print("  No combination is both profitable and beats its placebo on XAUUSD.")
        print("  Nothing qualifies for cross-sectional testing.")
    else:
        universe = sorted({p.name for p in DATA.glob("*")
                           if (p / "H1" / f"{p.name}_H1.parquet").exists()
                           and p.name not in {"XAUUSD", "XAGUSD", "USOIL"}
                           and not p.name.startswith(("EUR", "GBP", "USD", "AUD",
                                                      "NZD", "CAD", "CHF"))})
        for w in winners:
            kw = dict(next(k for n, k in combos if n == w["combo"]))
            print(f"  {w['combo']} across {len(universe)} unseen pairs:")
            ers = []
            for sym in universe:
                try:
                    r = evaluate(sym, **kw)
                except Exception:
                    continue
                if r:
                    ers.append(r["er"])
            if ers:
                ers = np.array(ers)
                pos = int((ers > 0).sum())
                pct = stats.percentileofscore(ers, w["er"])
                print(f"    positive {pos}/{len(ers)} ({pos/len(ers):.0%}), "
                      f"median {np.median(ers):+.4f}, XAUUSD at {pct:.0f}th pct")
                out.setdefault("cross", {})[w["combo"]] = {
                    "n": len(ers), "positive": pos,
                    "median": float(np.median(ers)), "xau_pct": float(pct)}

    (ROOT / "vwap_profitability_results.json").write_text(
        json.dumps(out, indent=2, default=str))
    print("\nSaved vwap_profitability_results.json")


if __name__ == "__main__":
    main()
