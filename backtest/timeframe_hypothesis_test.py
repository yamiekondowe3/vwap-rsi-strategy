"""PRE-REGISTERED HYPOTHESIS TEST: does a coarser timeframe fix the friction drag?

Motivation (from the M5 walk-forward diagnostics, not from searching):
  VWAP+RSI on M5 showed avg_win +0.93R / avg_loss -1.06R, i.e. friction
  costs ~0.13R per round trip while the signal's own deficit is only
  ~0.025R. Friction, not signal, supplies most of the loss. The broker's
  spread is a fixed ~$0.15 regardless of bar size, but ATR-scaled stops
  grow with the timeframe -- so on coarser bars the SAME spread is a
  smaller fraction of R.

This is ONE hypothesis with NO free parameters: identical default
parameters, identical rules, only the bar size changes. Nothing is
searched, so there is nothing to overfit. The prediction is falsifiable
and stated in advance:
  -> friction cost per round trip (in R) should fall roughly in proportion
     to the ATR ratio between timeframes
  -> if the signal deficit is genuinely small, expectancy_r should improve
     materially; if the signal itself is worthless, it will not.

ORB's opening-range window is held at the same WALL-CLOCK length (15 min)
across timeframes, so its definition is unchanged too.
"""
import sys
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "vwap-rsi-strategy"))

from common.data_fetch import load_parquet
from common.metrics import full_report
from common.indicators import atr as atr_fn

DATA_ROOT = ROOT / "data_cache"


def friction_cost_r(rep):
    """Friction per round trip in R units.

    With symmetric ATR stops/targets a frictionless system would show
    avg_win = +target/stop R and avg_loss = -1R exactly. The shortfall on
    wins plus the excess on losses is what execution cost took.
    """
    return (rep.get("avg_win_r", 0.0), rep.get("avg_loss_r", 0.0))


def run_vwap(timeframe):
    from backtest.engine import run_backtest, VWAPRSIParams
    df = load_parquet("XAUUSD", timeframe, root=DATA_ROOT)
    r = run_backtest(df, VWAPRSIParams(), symbol="XAUUSD")
    t = r["trades"]
    if len(t) == 0:
        return None
    rep = full_report(t["pnl"], t["return"], r_multiples=t["r_multiple"], entry_ts=t["entry_ts"])
    rep["median_atr"] = float(atr_fn(df, 14).median())
    return rep


def run_orb(timeframe, or_window_bars):
    sys.path.insert(0, str(ROOT / "orb-pivots-strategy"))
    # import fresh so the ORB engine's own `backtest` package wins
    for mod in [m for m in list(sys.modules) if m.startswith("backtest")]:
        del sys.modules[mod]
    from backtest.engine import run_backtest as orb_run, ORBPivotParams
    df = load_parquet("XAUUSD", timeframe, root=DATA_ROOT)
    p = ORBPivotParams(or_window_bars=or_window_bars, stop_atr_mult=2.0, target_atr_mult=1.5)
    r = orb_run(df, p, symbol="XAUUSD")
    t = r["trades"]
    if len(t) == 0:
        return None
    rep = full_report(t["pnl"], t["return"], r_multiples=t["r_multiple"], entry_ts=t["entry_ts"])
    rep["median_atr"] = float(atr_fn(df, 14).median())
    return rep


def show(label, rep):
    if rep is None:
        print(f"{label}: no trades")
        return
    aw, al = friction_cost_r(rep)
    print(f"\n--- {label} ---")
    print(f"  trades           : {rep['n_trades']} ({rep['trades_per_year']:.0f}/yr)")
    print(f"  median ATR       : ${rep['median_atr']:.2f}")
    print(f"  win rate         : {rep['win_rate']:.1%}")
    print(f"  profit factor    : {rep['profit_factor']:.3f}")
    print(f"  Sharpe (R-norm)  : {rep.get('sharpe_r', 0):+.3f}")
    print(f"  expectancy       : {rep.get('expectancy_r', 0):+.4f} R/trade")
    print(f"  avg win / loss   : {aw:+.3f}R / {al:+.3f}R")
    print(f"  total return     : {rep['total_return_pct']:+.1%}")
    print(f"  max drawdown     : {rep['max_drawdown_pct']:.1%}")


def main():
    results = {}

    print("=" * 72)
    print("VWAP+RSI -- identical default params, only timeframe changes")
    print("=" * 72)
    for tf in ["M5", "M15"]:
        rep = run_vwap(tf)
        results[f"vwap_{tf}"] = rep
        show(f"VWAP+RSI {tf}", rep)

    print("\n" + "=" * 72)
    print("ORB -- identical params, 15-min opening range held constant")
    print("=" * 72)
    for tf, orb_bars in [("M5", 3), ("M15", 1)]:
        rep = run_orb(tf, orb_bars)
        results[f"orb_{tf}"] = rep
        show(f"ORB {tf} (OR window = {orb_bars} bar(s) = 15 min)", rep)

    out = ROOT / "timeframe_hypothesis_results.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
