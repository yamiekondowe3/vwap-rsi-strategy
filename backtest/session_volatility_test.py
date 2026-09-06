"""Session and volatility-regime filters on top of the trailing exit.

The exit test established that a trailing exit produces the best economics
(PF 1.325 on XAUUSD H1) but that a random-entry placebo captures most of it.
Filters are the remaining documented, untested lever: both research
documents specify active-hours windows and note that returns concentrate in
high-volatility regimes, and neither was ever applied.

Two distinct questions are answered separately, because they are not the
same question:

  Q1 -- ABSOLUTE: does filtering improve the strategy's own performance
        versus trading unfiltered? (filtered vs unfiltered strategy)
  Q2 -- SIGNAL: does the signal still beat random entries drawn from the
        SAME filtered bars? (placebo z)

Q1 can improve simply because a session is a better time to trade at all;
only Q2 says the signal itself is doing work. A filter that wins Q1 but not
Q2 means "trade this session", not "this strategy predicts".

Held fixed (not searched): exit = E1_trail, the best mechanism from the
prior test. 4 filters x 2 strategies x 3 instruments = 24 configurations,
Bonferroni-corrected.
"""
import sys
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from common.data_fetch import load_parquet
from common.backtest_core import run as run_core
from common.exits import POLICIES
from common.filters import named_session_mask, volatility_regime_mask
from common.metrics import full_report
from common.placebo import run_placebo, buy_and_hold

DATA_ROOT = ROOT / "data_cache"
SYMBOLS = ["XAUUSD", "USOIL", "BTCUSD"]
TIMEFRAME = "H1"
EXIT = "E1_trail"
PLACEBO_RUNS = 30


def vwap_signals(df):
    sys.path.insert(0, str(ROOT / "vwap-rsi-strategy"))
    for m in [k for k in list(sys.modules) if k.startswith("backtest")]:
        del sys.modules[m]
    from backtest.engine import prepare_signals, VWAPRSIParams
    return prepare_signals(df, VWAPRSIParams(adaptive_rsi=True, rsi_pctile=20))


def orb_signals(df):
    sys.path.insert(0, str(ROOT / "orb-pivots-strategy"))
    for m in [k for k in list(sys.modules) if k.startswith("backtest")]:
        del sys.modules[m]
    from backtest.engine import prepare_signals, ORBPivotParams
    return prepare_signals(df, ORBPivotParams(or_window_bars=1, use_volume_filter=False))


STRATEGIES = {"VWAP+RSI": vwap_signals, "ORB": orb_signals}


def build_masks(df):
    idx = df.index
    return {
        "none": pd.Series(True, index=idx),
        "london_open": named_session_mask(idx, "london_open"),
        "ny_open": named_session_mask(idx, "ny_open"),
        "london_ny": named_session_mask(idx, "london_ny"),
        "vol_regime_p50": volatility_regime_mask(df, pctile=50.0, window=500),
    }


def evaluate(sig, mask, symbol, policy, run_placebo_too=True):
    s = sig.copy()
    s["long_signal"] = s["long_signal"] & mask
    s["short_signal"] = s["short_signal"] & mask
    eligible = mask & s["atr"].notna()

    t = run_core(s, policy, symbol)["trades"]
    if len(t) < 20:
        return None, len(t)

    rep = full_report(t["pnl"], t["return"], r_multiples=t["r_multiple"],
                      entry_ts=t["entry_ts"])
    out = {"n_trades": rep["n_trades"], "win_rate": rep["win_rate"],
           "profit_factor": rep["profit_factor"], "expectancy_r": rep["expectancy_r"],
           "sharpe_r": rep["sharpe_r"], "payoff": (abs(rep["avg_win_r"] / rep["avg_loss_r"])
                                                   if rep["avg_loss_r"] else np.nan),
           "max_drawdown_pct": rep["max_drawdown_pct"],
           "total_return_pct": rep["total_return_pct"]}
    if run_placebo_too:
        plc = run_placebo(sig, policy, symbol, n_entries=len(t),
                          long_ratio=float((t["side"] == 1).mean()),
                          eligible=eligible, n_runs=PLACEBO_RUNS)
        z = np.nan
        if plc.get("n_runs", 0) > 2 and plc["expectancy_r_std"] > 0:
            z = (rep["expectancy_r"] - plc["expectancy_r_mean"]) / plc["expectancy_r_std"]
        out["placebo_expectancy_r"] = plc.get("expectancy_r_mean", np.nan)
        out["placebo_z"] = float(z)
    return out, len(t)


def main():
    policy = POLICIES[EXIT]
    print(f"Exit held fixed at {EXIT}: {policy.describe()}")
    print(f"Timeframe {TIMEFRAME}. Session windows are UTC and widened to span DST.\n")

    rows, bh = [], {}
    t0 = time.time()

    for sym in SYMBOLS:
        df = load_parquet(sym, TIMEFRAME, root=DATA_ROOT)
        bh[sym] = buy_and_hold(df, 24 * 365)
        masks = build_masks(df)
        print(f"\n{sym}  (buy&hold Sharpe {bh[sym]['sharpe']:+.2f})")
        print(f"  {'strategy':9s} {'filter':15s} {'n':>5s} {'WR':>6s} {'payoff':>7s} "
              f"{'PF':>7s} {'E[R]':>9s} {'vs unfilt':>10s} {'plc z':>7s}")

        for strat_name, sig_fn in STRATEGIES.items():
            sig = sig_fn(df)
            base, _ = evaluate(sig, masks["none"], sym, policy)
            if base is None:
                continue

            for fname, mask in masks.items():
                res, n = evaluate(sig, mask, sym, policy)
                if res is None:
                    print(f"  {strat_name:9s} {fname:15s} only {n} trades - skipped")
                    continue
                delta = res["expectancy_r"] - base["expectancy_r"]
                rows.append({"symbol": sym, "strategy": strat_name, "filter": fname,
                             "delta_vs_unfiltered": delta, **res})
                z = res.get("placebo_z", np.nan)
                flag = ""
                if np.isfinite(z) and z > 1.645:
                    flag = " *BEATS PLACEBO"
                print(f"  {strat_name:9s} {fname:15s} {res['n_trades']:5d} "
                      f"{res['win_rate']:5.1%} {res['payoff']:7.2f} "
                      f"{res['profit_factor']:7.3f} {res['expectancy_r']:+9.4f} "
                      f"{delta:+10.4f} {z:+7.2f}{flag}", flush=True)

    out = pd.DataFrame(rows)
    (ROOT / "session_volatility_results.json").write_text(
        json.dumps({"results": rows, "buy_and_hold": bh, "exit": EXIT}, indent=2, default=str))
    print(f"\nTotal time {time.time()-t0:.0f}s")

    print("\n" + "=" * 96)
    print("Q1 -- ABSOLUTE: did filtering improve the strategy vs trading unfiltered?")
    print("=" * 96)
    filt = out[out["filter"] != "none"]
    for fname in ["london_open", "ny_open", "london_ny", "vol_regime_p50"]:
        sub = filt[filt["filter"] == fname]
        if len(sub):
            better = int((sub["delta_vs_unfiltered"] > 0).sum())
            print(f"  {fname:15s} mean dE[R] {sub['delta_vs_unfiltered'].mean():+.4f}  "
                  f"improved {better}/{len(sub)}  mean PF {sub['profit_factor'].mean():.3f}")

    print("\n" + "=" * 96)
    print("Q2 -- SIGNAL: does the signal beat random entries within the same filtered bars?")
    print("=" * 96)
    n_tests = len(filt)
    beats = filt[filt["placebo_z"] > 1.645]
    zcrit = stats.norm.ppf(1 - 0.05 / n_tests) if n_tests else np.nan
    surv = filt[filt["placebo_z"] > zcrit]
    print(f"  filtered configurations tested : {n_tests}")
    print(f"  beating placebo (z>1.645)      : {len(beats)}  (expected by chance {n_tests*0.05:.1f})")
    print(f"  Bonferroni z threshold         : {zcrit:.2f}")
    print(f"  surviving correction           : {len(surv)}")

    print("\n" + "=" * 96)
    print("JOINT GATE: positive expectancy AND beats placebo AND beats buy-and-hold")
    print("=" * 96)
    passed = []
    for _, r in filt.iterrows():
        if r["expectancy_r"] > 0 and r["placebo_z"] > 1.645 and r["sharpe_r"] > bh[r["symbol"]]["sharpe"]:
            passed.append(r)
    if not passed:
        print("  NONE.")
        cand = filt[(filt["expectancy_r"] > 0) & (filt["placebo_z"] > 1.645)]
        if len(cand):
            print("  (configs positive AND beating placebo, but losing to buy-and-hold:)")
            for _, r in cand.iterrows():
                print(f"    {r['strategy']:9s} {r['symbol']:7s} {r['filter']:15s} "
                      f"Sharpe {r['sharpe_r']:+.3f} vs buy&hold {bh[r['symbol']]['sharpe']:+.2f}")
    else:
        for r in passed:
            print(f"  PASS: {r['strategy']} {r['symbol']} {r['filter']} "
                  f"PF={r['profit_factor']:.3f} Sharpe={r['sharpe_r']:+.3f} z={r['placebo_z']:+.2f}")


if __name__ == "__main__":
    main()
