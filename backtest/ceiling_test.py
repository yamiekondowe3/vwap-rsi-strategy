"""PHASE 1 -- CEILING TEST: can either signal reach the bar even with costs removed?

The bar (user-chosen): PF > 1.3 and Sharpe > 1.0. At a 1:1 payoff, PF > 1.3
requires a win rate of 1.3/2.3 = 56.5%.

The logic of this test: if a signal cannot reach 56.5% win rate with
execution costs removed ENTIRELY, then no venue, timeframe, order type or
parameter change can ever get it there -- because zero cost is the
unreachable best case. That makes this a cheap, decisive gate to run before
spending any further compute.

What to read: the SHAPE of the edge-vs-selectivity curve, not the best cell.
If win rate rises monotonically as entries get more selective, that is
evidence of real signal concentrated in the tails. If it is flat or noisy,
there is no signal at any selectivity. Monotonicity across a continuum is
much harder to produce by chance than one good cell -- which is why this is
not the in-sample parameter search already shown to have zero predictive
power (r=+0.109, p=0.72).

Instruments: XAUUSD, USOIL, BTCUSD (XAGUSD and ETHUSD dropped).
NOTE: USOIL has only ~2.6 years of history; its rows are labelled and carry
far less weight than the ~15.7-year metals/crypto series.
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
from common.costs import FrictionModel
from common.metrics import full_report

DATA_ROOT = ROOT / "data_cache"
SYMBOLS = ["XAUUSD", "USOIL", "BTCUSD"]
TIMEFRAMES = ["M15", "H1", "H4"]

PF_TARGET = 1.3
WR_TARGET = PF_TARGET / (1 + PF_TARGET)   # 56.5% at 1:1 payoff
MIN_TRADES = 300                           # a ceiling claim needs a real sample


def get_data(symbol, timeframe):
    """H4 is resampled from H1 (MT5's python API exposes no H4 constant)."""
    if timeframe == "H4":
        h1 = load_parquet(symbol, "H1", root=DATA_ROOT)
        df = h1.resample("4h").agg({"open": "first", "high": "max", "low": "min",
                                    "close": "last", "volume": "sum", "spread": "median"})
        return df.dropna()
    return load_parquet(symbol, timeframe, root=DATA_ROOT)


def summarise(trades, params_payoff):
    if len(trades) < 10:
        return None
    rep = full_report(trades["pnl"], trades["return"],
                      r_multiples=trades["r_multiple"], entry_ts=trades["entry_ts"])
    r = trades["r_multiple"].dropna()
    tstat, pval = stats.ttest_1samp(r, 0.0) if len(r) > 1 else (np.nan, np.nan)
    rep["p_value"] = float(pval)
    rep["payoff"] = params_payoff
    return rep


def run_vwap(symbol, timeframe, pctile, frictionless):
    sys.path.insert(0, str(ROOT / "vwap-rsi-strategy"))
    for m in [k for k in list(sys.modules) if k.startswith("backtest")]:
        del sys.modules[m]
    from backtest.engine import run_backtest, VWAPRSIParams

    df = get_data(symbol, timeframe)
    p = VWAPRSIParams(adaptive_rsi=True, rsi_pctile=pctile, rsi_pctile_window=500,
                      stop_atr_mult=2.0, target_atr_mult=2.0)
    fm = FrictionModel(symbol=symbol, frictionless=frictionless)
    t = run_backtest(df, p, symbol=symbol, friction=fm)["trades"]
    return summarise(t, p.target_atr_mult / p.stop_atr_mult)


def run_orb(symbol, timeframe, volume_mult, frictionless):
    sys.path.insert(0, str(ROOT / "orb-pivots-strategy"))
    for m in [k for k in list(sys.modules) if k.startswith("backtest")]:
        del sys.modules[m]
    from backtest.engine import run_backtest, ORBPivotParams

    df = get_data(symbol, timeframe)
    # Keep the opening range at 15 wall-clock minutes where the timeframe allows.
    or_bars = {"M15": 1, "H1": 1, "H4": 1}[timeframe]
    p = ORBPivotParams(or_window_bars=or_bars, stop_atr_mult=2.0, target_atr_mult=2.0,
                       use_volume_filter=True, volume_mult=volume_mult)
    fm = FrictionModel(symbol=symbol, frictionless=frictionless)
    t = run_backtest(df, p, symbol=symbol, friction=fm)["trades"]
    return summarise(t, p.target_atr_mult / p.stop_atr_mult)


def main():
    print(f"CEILING TEST -- can any config reach WR >= {WR_TARGET:.1%} (PF {PF_TARGET}) "
          f"with ZERO execution cost?\n")
    rows = []

    for strat, runner, sweep, label in [
        ("VWAP+RSI", run_vwap, [20, 10, 5, 2], "rsi_pctile"),
        ("ORB", run_orb, [1.0, 2.0, 3.0], "volume_mult"),
    ]:
        print("=" * 92)
        print(f"{strat}: frictionless ceiling by selectivity ({label})")
        print("=" * 92)
        print(f"{'symbol':8s} {'TF':4s} {label:>12s} {'n':>6s} {'WR':>7s} {'PF':>7s} "
              f"{'E[R]':>8s} {'Sharpe':>8s} {'p':>7s}  verdict")
        for sym in SYMBOLS:
            for tf in TIMEFRAMES:
                for val in sweep:
                    try:
                        rep = runner(sym, tf, val, frictionless=True)
                    except FileNotFoundError:
                        continue
                    except Exception as e:  # noqa: BLE001 - report, don't hide
                        print(f"{sym:8s} {tf:4s} {val:>12} ERROR {type(e).__name__}: {e}")
                        continue
                    if rep is None:
                        continue
                    hits = (rep["win_rate"] >= WR_TARGET and rep["n_trades"] >= MIN_TRADES)
                    verdict = "*** CLEARS BAR" if hits else ""
                    rows.append({"strategy": strat, "symbol": sym, "timeframe": tf,
                                 label: val, "n_trades": rep["n_trades"],
                                 "win_rate": rep["win_rate"], "profit_factor": rep["profit_factor"],
                                 "expectancy_r": rep.get("expectancy_r", 0.0),
                                 "sharpe_r": rep.get("sharpe_r", 0.0),
                                 "p_value": rep["p_value"], "clears_bar": bool(hits)})
                    print(f"{sym:8s} {tf:4s} {val:>12} {rep['n_trades']:6d} "
                          f"{rep['win_rate']:6.1%} {rep['profit_factor']:7.3f} "
                          f"{rep.get('expectancy_r', 0):+8.4f} {rep.get('sharpe_r', 0):+8.3f} "
                          f"{rep['p_value']:7.3f}  {verdict}", flush=True)
            print()

    df = pd.DataFrame(rows)
    (ROOT / "ceiling_test_results.json").write_text(json.dumps(rows, indent=2, default=str))

    print("=" * 92)
    print("GATE 1 VERDICT")
    print("=" * 92)
    if df.empty:
        print("No results produced.")
        return
    clears = df[df["clears_bar"]]
    print(f"Configurations tested                     : {len(df)}")
    print(f"Clearing WR >= {WR_TARGET:.1%} with >= {MIN_TRADES} trades : {len(clears)}")
    best = df.loc[df[df['n_trades'] >= MIN_TRADES]['win_rate'].idxmax()] if (df['n_trades'] >= MIN_TRADES).any() else None
    if best is not None:
        print(f"Best frictionless WR (n>={MIN_TRADES})          : {best['win_rate']:.1%} "
              f"({best['strategy']} {best['symbol']} {best['timeframe']}, n={best['n_trades']})")
        print(f"  -> required for PF {PF_TARGET}                 : {WR_TARGET:.1%}")
        print(f"  -> shortfall                             : {(WR_TARGET - best['win_rate'])*100:.1f} points")
    if len(clears) == 0:
        print("\nGATE 1: FAILED. No configuration reaches the bar even with execution")
        print("costs removed entirely. Since zero cost is the unreachable best case,")
        print("no venue, order type, timeframe or parameter change can get there.")
        print("STOP -- do not proceed to Phase 2.")
    else:
        print("\nGATE 1: PASSED for the configurations marked above. Proceed to Phase 2")
        print("(execution modelling) for those only.")


if __name__ == "__main__":
    main()
