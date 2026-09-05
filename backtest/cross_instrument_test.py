"""CROSS-INSTRUMENT VALIDATION: VWAP+RSI on M15, unchanged default parameters.

Why this and not more parameter search:
The M5 walk-forwards established that in-sample parameter selection has no
predictive power out-of-sample (r=+0.109, p=0.72). So the way to gain
confidence is NOT a bigger grid -- it is testing the SAME fixed rules on
data the rules were never derived from. Different instruments are close to
genuinely independent samples of the same hypothesis.

Nothing is tuned here. Identical VWAPRSIParams() defaults on every symbol.
Each instrument is a fresh falsification opportunity: if the M15 edge on
XAUUSD is real rather than a 21-trade fluke, it should show up broadly. If
it appears on one symbol and not the rest, that is noise, and the honest
call is to say so.

Also reports the FRICTIONLESS expectancy implied by each symbol's win rate
and payoff, separating "signal quality" from "execution cost" -- the
distinction that showed ORB is structurally dead while VWAP+RSI is not.
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
from common.metrics import full_report
from backtest.engine import run_backtest, VWAPRSIParams

DATA_ROOT = ROOT / "data_cache"
SYMBOLS = ["XAUUSD", "XAGUSD", "USOIL", "BTCUSD", "ETHUSD"]


def analyse(symbol, timeframe="M15"):
    df = load_parquet(symbol, timeframe, root=DATA_ROOT)
    params = VWAPRSIParams()
    r = run_backtest(df, params, symbol=symbol)
    t = r["trades"]
    if len(t) < 5:
        return {"symbol": symbol, "n_trades": len(t), "note": "too few trades"}

    rep = full_report(t["pnl"], t["return"], r_multiples=t["r_multiple"], entry_ts=t["entry_ts"])
    rmult = t["r_multiple"].dropna()

    # Statistical significance of the per-trade edge (is it distinguishable
    # from zero at all?) -- one-sample t-test on the R-multiple series.
    tstat, pval = stats.ttest_1samp(rmult, 0.0) if len(rmult) > 1 else (np.nan, np.nan)
    se = rmult.std(ddof=1) / np.sqrt(len(rmult)) if len(rmult) > 1 else np.nan

    # Frictionless counterfactual: what this win rate would earn with a
    # perfect fill at the exact stop/target levels.
    payoff = params.target_atr_mult / params.stop_atr_mult
    wr = rep["win_rate"]
    frictionless = wr * payoff - (1 - wr)

    return {
        "symbol": symbol,
        "n_trades": rep["n_trades"],
        "trades_per_year": rep["trades_per_year"],
        "win_rate": rep["win_rate"],
        "profit_factor": rep["profit_factor"],
        "sharpe_r": rep.get("sharpe_r", 0.0),
        "expectancy_r": rep.get("expectancy_r", 0.0),
        "std_error": float(se),
        "t_stat": float(tstat),
        "p_value": float(pval),
        "avg_win_r": rep.get("avg_win_r", 0.0),
        "avg_loss_r": rep.get("avg_loss_r", 0.0),
        "frictionless_expectancy_r": float(frictionless),
        "total_return_pct": rep["total_return_pct"],
        "max_drawdown_pct": rep["max_drawdown_pct"],
    }


def main():
    rows = []
    for sym in SYMBOLS:
        try:
            res = analyse(sym)
        except FileNotFoundError:
            print(f"{sym}: no M15 data cached", flush=True)
            continue
        rows.append(res)
        if res.get("note"):
            print(f"{res['symbol']:8s} {res['note']} (n={res['n_trades']})", flush=True)
        else:
            print(f"{res['symbol']:8s} n={res['n_trades']:4d} ({res['trades_per_year']:5.1f}/yr) "
                  f"WR={res['win_rate']:5.1%} PF={res['profit_factor']:5.3f} "
                  f"E[R]={res['expectancy_r']:+.4f} +/- {res['std_error']:.4f} "
                  f"(p={res['p_value']:.3f}) frictionless={res['frictionless_expectancy_r']:+.4f}", flush=True)

    valid = [r for r in rows if not r.get("note")]
    if valid:
        # Pooled edge across all instruments -- the aggregate falsification test.
        total_trades = sum(r["n_trades"] for r in valid)
        pooled_e = sum(r["expectancy_r"] * r["n_trades"] for r in valid) / total_trades
        n_positive = sum(1 for r in valid if r["expectancy_r"] > 0)
        print("\n" + "=" * 72)
        print("CROSS-INSTRUMENT VERDICT (VWAP+RSI, M15, unchanged defaults)")
        print("=" * 72)
        print(f"Instruments with positive edge : {n_positive} / {len(valid)}")
        print(f"Pooled expectancy (trade-wtd)  : {pooled_e:+.4f} R per trade")
        print(f"Total trades across all        : {total_trades}")
        print(f"Mean frictionless expectancy   : "
              f"{np.mean([r['frictionless_expectancy_r'] for r in valid]):+.4f} R")

    out = ROOT / "cross_instrument_results.json"
    out.write_text(json.dumps(rows, indent=2, default=str))
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
