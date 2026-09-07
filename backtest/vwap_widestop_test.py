"""Follow-up: the levers that actually helped, plus the obvious objection.

Stage 1 showed limit entry HURTS (adverse selection costs more than the
spread saved), while wide stops help monotonically:
  2xATR -0.0078 | 4xATR -0.0007 | 6xATR +0.0686
That is the friction mechanism working as predicted: friction in R is
cost/(stop_atr x ATR), so widening the stop mechanically shrinks it.

THE OBJECTION THIS MUST ANSWER: a very wide stop with a matching target
means long holding periods and few trades. On an asset that trended up for
15 years, that converges toward simply being long gold. If the "edge" is
just drift capture, buy-and-hold gets it for free with no trading at all.
So this compares against buy-and-hold and reports holding periods, not only
E[R].

Also checks whether the monotonic stop trend continues (8x, 10x). If E[R]
keeps rising with stop width indefinitely, that is the signature of drift
capture, not signal.
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
from common.portfolio import summarize
from backtest.engine import prepare_signals, VWAPRSIParams

DATA = ROOT / "data_cache"
TRADING_H1_PER_YEAR = 24 * 365


def evaluate(symbol, stop=6.0, direction="both", placebo=False, tf="H1"):
    df = load_parquet(symbol, tf, root=DATA)
    sig = prepare_signals(df, VWAPRSIParams(trigger="pullback", stop_atr_mult=stop,
                                            target_atr_mult=stop))
    pol = ExitPolicy(mode="fixed", stop_atr=stop, target_atr=stop)
    res = run_core(sig, pol, symbol, direction=direction)
    t = res["trades"]
    if len(t) < 25:
        return None
    rep = full_report(t["pnl"], t["return"], r_multiples=t["r_multiple"],
                      entry_ts=t["entry_ts"])
    out = {"n": rep["n_trades"], "wr": rep["win_rate"], "pf": rep["profit_factor"],
           "er": rep["expectancy_r"], "sharpe_r": rep["sharpe_r"],
           "total_return": rep["total_return_pct"],
           "avg_bars_held": float(t["bars_held"].mean())}
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
    print("STAGE A — does the stop-width trend keep going? (drift-capture check)\n")
    print(f"{'stop':10s} {'n':>6s} {'avg bars held':>14s} {'WR':>7s} {'PF':>7s} {'E[R]':>9s}")
    print("-" * 60)
    trend = []
    for stop in [2.0, 4.0, 6.0, 8.0, 10.0]:
        r = evaluate("XAUUSD", stop=stop)
        if not r:
            print(f"{stop:>5.0f}xATR  too few trades")
            continue
        trend.append({"stop": stop, **r})
        print(f"{stop:>5.0f}xATR  {r['n']:6d} {r['avg_bars_held']:14.0f} "
              f"{r['wr']*100:6.1f}% {r['pf']:7.3f} {r['er']:+9.4f}", flush=True)

    print("\nIf E[R] rises without limit as the stop widens, the 'edge' is just")
    print("holding longer on a trending asset -- i.e. drift, not signal.\n")

    print("\nSTAGE B — the indicated combination, with placebo\n")
    print(f"{'config':28s} {'n':>6s} {'WR':>7s} {'PF':>7s} {'E[R]':>9s} {'placebo z':>10s}")
    print("-" * 72)
    combos = [
        ("6xATR (both sides)", dict(stop=6.0)),
        ("6xATR long only", dict(stop=6.0, direction="long_only")),
        ("8xATR long only", dict(stop=8.0, direction="long_only")),
    ]
    results = []
    for name, kw in combos:
        r = evaluate("XAUUSD", placebo=True, **kw)
        if not r:
            print(f"{name:28s} too few trades")
            continue
        results.append({"config": name, **r, **{k: str(v) for k, v in kw.items()}})
        flag = "  <--" if (r["er"] > 0 and r.get("z", 0) > 1.645) else ""
        print(f"{name:28s} {r['n']:6d} {r['wr']*100:6.1f}% {r['pf']:7.3f} "
              f"{r['er']:+9.4f} {r.get('z', float('nan')):+10.2f}{flag}", flush=True)

    print("\n\nSTAGE C — versus simply holding gold\n")
    df = load_parquet("XAUUSD", "H1", root=DATA)
    px = df["close"].dropna()
    bh_ret = px.pct_change().fillna(0.0)
    bh = summarize(bh_ret, periods_per_year=TRADING_H1_PER_YEAR)
    yrs = (px.index[-1] - px.index[0]).days / 365.25
    print(f"  buy & hold gold : CAGR {bh['cagr']*100:+6.1f}%  Sharpe {bh['sharpe']:+.2f}  "
          f"maxDD {bh['max_drawdown']*100:6.1f}%")
    for r in results:
        cagr = (1 + r["total_return"]) ** (1 / yrs) - 1 if r["total_return"] > -1 else np.nan
        print(f"  {r['config']:26s}: CAGR {cagr*100:+6.1f}%  "
              f"total {r['total_return']*100:+7.1f}%  (Sharpe_R {r['sharpe_r']:+.2f})")

    print("\n\nSTAGE D — cross-sectional replication of anything that qualified\n")
    winners = [r for r in results if r["er"] > 0 and r.get("z", 0) > 1.645]
    out = {"stop_trend": trend, "combos": results, "buy_hold": bh}
    if not winners:
        print("  Nothing both profitable and beating its placebo. Nothing to replicate.")
    else:
        universe = sorted({p.name for p in DATA.glob("*")
                           if (p / "H1" / f"{p.name}_H1.parquet").exists()
                           and p.name not in {"XAUUSD", "XAGUSD", "USOIL"}
                           and not p.name.startswith(("EUR", "GBP", "USD", "AUD",
                                                      "NZD", "CAD", "CHF"))})
        for w in winners:
            kw = dict(next(k for n, k in combos if n == w["config"]))
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
                print(f"  {w['config']}: {pos}/{len(ers)} positive ({pos/len(ers):.0%}), "
                      f"median {np.median(ers):+.4f}, XAUUSD at {pct:.0f}th pct")
                out.setdefault("cross", {})[w["config"]] = {
                    "n": len(ers), "positive": pos, "median": float(np.median(ers)),
                    "xau_pct": float(pct)}

    (ROOT / "vwap_widestop_results.json").write_text(json.dumps(out, indent=2, default=str))
    print("\nSaved vwap_widestop_results.json")


if __name__ == "__main__":
    main()
