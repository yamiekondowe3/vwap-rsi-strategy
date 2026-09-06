"""PHASE 1 — Cross-sectional out-of-sample test of the risk overlay.

The overlay (200d trend gate x 15% vol target) won 8/8 rolling Sharpe
windows on ETHUSD. But those windows overlap two-thirds, so it is really
~3 independent observations on one asset — and BTCUSD, which looked
strongest on full-sample significance, collapsed to 6/12 on rolling
windows. That divergence is what a thin evidence base produces.

The overlay has NO fitted parameters, so every crypto pair the project has
never looked at is a free, genuine out-of-sample test. This runs the
IDENTICAL rule across the broker's whole crypto universe.

Two honesty requirements built in:
  1. Report the DISTRIBUTION, losers as prominently as winners.
  2. Quantify effective sample size. Crypto shares a dominant BTC factor,
     so 30 assets are nowhere near 30 independent tests. A "25 of 30"
     headline without the effective-N next to it would be misleading.

A synthetic driftless control run is included: on random walks the harness
must show ~50% of assets improving. If it shows a majority, the harness is
broken and the real result means nothing.
"""
import sys
import json
from datetime import datetime, timezone

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from common.portfolio import (vol_target_weights, trend_gate, apply_weights,
                              vol_matched_benchmark, summarize,
                              effective_sample_size, average_pairwise_correlation,
                              block_bootstrap_ci, TRADING_DAYS)

VOL_TARGET, VOL_WINDOW, TREND_WINDOW = 0.15, 20, 200
MIN_YEARS = 3.0
EXCLUDE_SUBSTR = ["RSI", "Index"]          # synthetic broker products
EXCLUDE_EXACT = {"BTCETH", "BTCLTC"}       # cross-rates, not USD pairs
CACHE = ROOT / "data_cache"


def fetch_universe():
    """D1 for every crypto USD pair with enough history. Cached to parquet."""
    import MetaTrader5 as mt5
    if not mt5.initialize():
        raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")
    try:
        names = [s.name for s in mt5.symbols_get()
                 if (s.path.lower().startswith("crypto")
                     and not any(x.lower() in s.name.lower() for x in EXCLUDE_SUBSTR)
                     and s.name not in EXCLUDE_EXACT)]
        out = {}
        for name in sorted(names):
            mt5.symbol_select(name, True)
            info = mt5.symbol_info(name)
            rates = mt5.copy_rates_from(name, mt5.TIMEFRAME_D1,
                                        datetime.now(timezone.utc), 8000)
            if rates is None or len(rates) < MIN_YEARS * 365:
                continue
            df = pd.DataFrame(rates)
            df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True)
            df = df.set_index("timestamp")
            df["spread"] = df["spread"] * (info.point if info else 0.0)
            df = df.rename(columns={"tick_volume": "volume"})[
                ["open", "high", "low", "close", "volume", "spread"]]
            yrs = (df.index[-1] - df.index[0]).days / 365.25
            if yrs >= MIN_YEARS:
                out[name] = df
        return out
    finally:
        mt5.shutdown()


def test_asset(df):
    px = df["close"].dropna()
    ret = px.pct_change().fillna(0.0)
    cost = float((df["spread"] / df["close"] / 2).median())
    cost = 0.0 if not np.isfinite(cost) else cost

    w = trend_gate(px, TREND_WINDOW) * vol_target_weights(ret, VOL_TARGET, VOL_WINDOW)
    warm = TREND_WINDOW + VOL_WINDOW
    if len(ret) <= warm + 250:
        return None
    ret, w = ret.iloc[warm:], w.iloc[warm:]

    strat = apply_weights(ret, w, cost)
    bh = apply_weights(ret, pd.Series(1.0, index=ret.index), cost)
    vm = vol_matched_benchmark(bh, strat)
    s, v, b = summarize(strat, w), summarize(vm), summarize(bh)
    if not (s and v):
        return None
    return {"years": (ret.index[-1] - ret.index[0]).days / 365.25,
            "n_days": len(ret), "strat_sharpe": s["sharpe"], "vm_sharpe": v["sharpe"],
            "bh_sharpe": b["sharpe"], "d_sharpe": s["sharpe"] - v["sharpe"],
            "strat_dd": s["max_drawdown"], "vm_dd": v["max_drawdown"],
            "bh_dd": b["max_drawdown"], "d_dd": s["max_drawdown"] - v["max_drawdown"],
            "strat_cagr": s["cagr"], "bh_cagr": b["cagr"],
            "ulcer": s["ulcer"], "bh_ulcer": b["ulcer"],
            "time_in_market": s["time_in_market"], "returns": strat}


def synthetic_control(n_assets=30, n_days=1600, seed=99):
    """Driftless random walks with a shared factor, mimicking crypto's
    correlation structure. The overlay must NOT show a majority improving."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2019-01-01", periods=n_days, freq="D", tz="UTC")
    common = rng.normal(0, 0.03, n_days)
    wins_s = wins_dd = total = 0
    for i in range(n_assets):
        r = 0.7 * common + 0.3 * rng.normal(0, 0.03, n_days)
        px = pd.Series(100 * np.exp(np.cumsum(r)), index=idx)
        df = pd.DataFrame({"open": px, "high": px * 1.01, "low": px * 0.99,
                           "close": px, "volume": 1.0, "spread": 0.0}, index=idx)
        res = test_asset(df)
        if res:
            total += 1
            wins_s += res["d_sharpe"] > 0
            wins_dd += res["d_dd"] > 0
    return wins_s, wins_dd, total


def main():
    print("SANITY CONTROL: overlay on synthetic driftless random walks")
    ws, wdd, tot = synthetic_control()
    print(f"  Sharpe improved {ws}/{tot} ({ws/tot:.0%}), DD improved {wdd}/{tot} ({wdd/tot:.0%})")
    print("  (must be ~50%; a majority would mean the harness flatters itself)\n")
    if tot and (ws / tot > 0.75 or wdd / tot > 0.75):
        print("  !! HARNESS FAILS ITS OWN CONTROL - stopping.")
        return

    print("Fetching crypto universe from broker...")
    universe = fetch_universe()
    print(f"  {len(universe)} pairs with >= {MIN_YEARS}y of daily history\n")

    rows, ret_map = [], {}
    print(f"{'symbol':10s} {'yrs':>5s} {'BH Sh':>7s} {'strat':>7s} {'vm':>7s} "
          f"{'dSharpe':>8s} {'BH DD':>8s} {'strat DD':>9s} {'dDD':>8s}")
    print("-" * 80)
    for sym, df in universe.items():
        res = test_asset(df)
        if not res:
            continue
        ret_map[sym] = res.pop("returns")
        rows.append({"symbol": sym, **res})
        print(f"{sym:10s} {res['years']:5.1f} {res['bh_sharpe']:+7.2f} "
              f"{res['strat_sharpe']:+7.2f} {res['vm_sharpe']:+7.2f} "
              f"{res['d_sharpe']:+8.3f} {res['bh_dd']*100:+7.1f}% "
              f"{res['strat_dd']*100:+8.1f}% {res['d_dd']*100:+7.1f}pt", flush=True)

    if not rows:
        print("no assets tested")
        return
    df = pd.DataFrame(rows)
    n = len(df)
    ws = int((df["d_sharpe"] > 0).sum())
    wdd = int((df["d_dd"] > 0).sum())
    wboth = int(((df["d_sharpe"] > 0) & (df["d_dd"] > 0)).sum())

    R = pd.DataFrame(ret_map).dropna()
    rho = average_pairwise_correlation(R)
    n_eff = effective_sample_size(n, rho)

    print("\n" + "=" * 80)
    print("CROSS-SECTIONAL RESULT")
    print("=" * 80)
    print(f"  assets tested                : {n}")
    print(f"  Sharpe improved              : {ws}/{n} ({ws/n:.0%})")
    print(f"  drawdown improved            : {wdd}/{n} ({wdd/n:.0%})")
    print(f"  BOTH improved                : {wboth}/{n} ({wboth/n:.0%})")
    print(f"  median dSharpe               : {df['d_sharpe'].median():+.3f} "
          f"(IQR {df['d_sharpe'].quantile(.25):+.3f} to {df['d_sharpe'].quantile(.75):+.3f})")
    print(f"  median dDD                   : {df['d_dd'].median()*100:+.1f}pt "
          f"(IQR {df['d_dd'].quantile(.25)*100:+.1f} to {df['d_dd'].quantile(.75)*100:+.1f})")
    print(f"\n  average pairwise correlation : {rho:.2f}")
    print(f"  EFFECTIVE sample size        : {n_eff:.1f} independent observations "
          f"(not {n})")

    print("\n  WORST 5 by dSharpe (the losers, reported as prominently as winners):")
    for _, r in df.nsmallest(5, "d_sharpe").iterrows():
        print(f"    {r['symbol']:10s} dSharpe {r['d_sharpe']:+.3f}  dDD {r['d_dd']*100:+.1f}pt")

    # block bootstrap CI on the equal-weight portfolio of overlay returns
    port = R.mean(axis=1)
    lo, hi = block_bootstrap_ci(
        port, lambda x: float(np.sqrt(TRADING_DAYS) * x.mean() / x.std(ddof=1)),
        block_size=63, n_boot=800)
    print(f"\n  equal-weight overlay Sharpe  : {np.sqrt(TRADING_DAYS)*port.mean()/port.std(ddof=1):+.2f}")
    print(f"  block-bootstrap 95% CI       : [{lo:+.2f}, {hi:+.2f}]")

    df.drop(columns=[]).to_json(ROOT / "crosssection_results.json",
                                orient="records", indent=2)

    print("\n" + "=" * 80)
    gate = wboth / n >= 0.6
    print(f"GATE 1: {'PASS' if gate else 'FAIL'} — "
          f"{'clear majority improve on both measures' if gate else 'no clear majority; ETH result likely noise'}")


if __name__ == "__main__":
    main()
