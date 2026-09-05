"""Self-calibrating RSI threshold: does it restore sample size AND keep the
friction advantage of the coarser timeframe?

The problem it addresses: a hardcoded RSI 30/70 is implicitly tuned to one
timeframe's noise. On M15 it fired 21 times in 15.67 years -- a sample too
small to conclude anything (and demonstrably so: before the RNG was seeded,
two identical runs of it disagreed on the SIGN of the edge).

The fix is structural rather than fitted: threshold on RSI's own trailing
percentile, so "oversold" means the same rarity on every timeframe and
every instrument, with no per-market numbers to tune. One rule everywhere.

Reported per instrument, on M15, with a single pre-registered percentile
(20/80). Includes a t-test so no result gets read as an edge unless the
sample can actually support the claim -- the failure mode that produced the
earlier false positive.
"""
import sys
import json
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "vwap-rsi-strategy"))

from common.data_fetch import load_parquet
from common.metrics import full_report
from backtest.engine import run_backtest, VWAPRSIParams

DATA_ROOT = ROOT / "data_cache"
SYMBOLS = ["XAUUSD", "XAGUSD", "USOIL", "BTCUSD", "ETHUSD"]


def analyse(symbol, params, timeframe="M15"):
    df = load_parquet(symbol, timeframe, root=DATA_ROOT)
    t = run_backtest(df, params, symbol=symbol)["trades"]
    if len(t) < 5:
        return {"symbol": symbol, "n_trades": len(t), "note": "too few trades"}
    rep = full_report(t["pnl"], t["return"], r_multiples=t["r_multiple"], entry_ts=t["entry_ts"])
    r = t["r_multiple"].dropna()
    tstat, pval = stats.ttest_1samp(r, 0.0)
    payoff = params.target_atr_mult / params.stop_atr_mult
    wr = rep["win_rate"]
    return {
        "symbol": symbol, "n_trades": rep["n_trades"],
        "trades_per_year": rep["trades_per_year"], "win_rate": wr,
        "profit_factor": rep["profit_factor"], "sharpe_r": rep.get("sharpe_r", 0.0),
        "expectancy_r": rep.get("expectancy_r", 0.0),
        "std_error": float(r.std(ddof=1) / np.sqrt(len(r))),
        "p_value": float(pval),
        "frictionless_expectancy_r": float(wr * payoff - (1 - wr)),
        "total_return_pct": rep["total_return_pct"],
        "max_drawdown_pct": rep["max_drawdown_pct"],
    }


def report(label, params):
    print("\n" + "=" * 78)
    print(label)
    print("=" * 78)
    rows = []
    for sym in SYMBOLS:
        try:
            res = analyse(sym, params)
        except FileNotFoundError:
            continue
        rows.append(res)
        if res.get("note"):
            print(f"{res['symbol']:8s} {res['note']} (n={res['n_trades']})", flush=True)
        else:
            sig = "SIGNIFICANT" if res["p_value"] < 0.05 else "not significant"
            print(f"{res['symbol']:8s} n={res['n_trades']:5d} ({res['trades_per_year']:6.1f}/yr) "
                  f"WR={res['win_rate']:5.1%} PF={res['profit_factor']:5.3f} "
                  f"Sharpe={res['sharpe_r']:+6.3f} E[R]={res['expectancy_r']:+.4f}"
                  f"+/-{res['std_error']:.4f} p={res['p_value']:.3f} ({sig})", flush=True)
    valid = [r for r in rows if not r.get("note")]
    if valid:
        tot = sum(r["n_trades"] for r in valid)
        pooled = sum(r["expectancy_r"] * r["n_trades"] for r in valid) / tot
        print(f"\n  pooled across {len(valid)} instruments: {pooled:+.4f} R/trade over {tot} trades")
        print(f"  instruments with positive edge: {sum(1 for r in valid if r['expectancy_r'] > 0)}/{len(valid)}")
    return rows


def main():
    out = {}
    out["fixed_30_70"] = report(
        "BASELINE: fixed RSI 30/70 on M15 (sample-starved)",
        VWAPRSIParams(),
    )
    out["adaptive_p20"] = report(
        "ADAPTIVE: RSI trailing 20th/80th percentile on M15 (self-calibrating)",
        VWAPRSIParams(adaptive_rsi=True, rsi_pctile=20.0, rsi_pctile_window=500),
    )
    (ROOT / "adaptive_rsi_results.json").write_text(json.dumps(out, indent=2, default=str))
    print(f"\nSaved to {ROOT / 'adaptive_rsi_results.json'}")


if __name__ == "__main__":
    main()
