"""Tests for the risk-managed exposure engine."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common.portfolio import (realized_vol, vol_target_weights, trend_gate,
                              inverse_vol_weights, apply_weights,
                              vol_matched_benchmark, random_gate_placebo,
                              ulcer_index, summarize, TRADING_DAYS)


def synth_returns(n=3000, seed=1, drift=0.0, vol=0.01, regime=False):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2012-01-01", periods=n, freq="B", tz="UTC")
    if regime:   # alternating calm / turbulent volatility regimes
        v = np.where((np.arange(n) // 250) % 2 == 0, vol, vol * 3)
    else:
        v = np.full(n, vol)
    return pd.Series(rng.normal(drift, v), index=idx)


def test_vol_estimate_and_trend_gate_never_use_current_bar():
    r = synth_returns()
    rv = realized_vol(r, 20)
    # rebuild the un-shifted version; the shipped one must equal it lagged by 1
    raw = r.rolling(20).std(ddof=1) * np.sqrt(TRADING_DAYS)
    pd.testing.assert_series_equal(rv.dropna(), raw.shift(1).dropna())

    px = (1 + r).cumprod() * 100
    g = trend_gate(px, 50)
    raw_gate = (px > px.rolling(50).mean()).shift(1).fillna(False).astype(float)
    pd.testing.assert_series_equal(g, raw_gate)


def test_vol_targeting_stabilises_realised_volatility():
    """The whole point: output vol should be far steadier than input vol."""
    r = synth_returns(regime=True)
    w = vol_target_weights(r, target_vol=0.15, window=20, max_leverage=1.0)
    managed = apply_weights(r, w)

    def rolling_ann_vol(x):
        return x.rolling(60).std(ddof=1).dropna() * np.sqrt(TRADING_DAYS)

    raw_disp = rolling_ann_vol(r).std()
    man_disp = rolling_ann_vol(managed).std()
    assert man_disp < raw_disp, "vol targeting did not stabilise volatility"


def test_leverage_cap_is_respected():
    r = synth_returns(vol=0.0005)   # very calm -> uncapped weight would be huge
    w = vol_target_weights(r, target_vol=0.15, window=20, max_leverage=1.0)
    assert w.max() <= 1.0 + 1e-12


def test_turnover_costs_reduce_returns_monotonically():
    r = synth_returns(drift=0.0003)
    px = (1 + r).cumprod() * 100
    w = trend_gate(px, 50)
    prev = None
    for cost in [0.0, 0.0005, 0.002]:
        total = apply_weights(r, w, cost).sum()
        if prev is not None:
            assert total < prev, "higher cost must reduce returns"
        prev = total


def test_vol_matched_benchmark_actually_matches_vol():
    r = synth_returns(regime=True)
    px = (1 + r).cumprod() * 100
    strat = apply_weights(r, trend_gate(px, 50))
    bench = vol_matched_benchmark(r, strat)
    assert bench.std(ddof=1) == pytest.approx(strat.std(ddof=1), rel=1e-9)


def test_inverse_vol_weights_sum_to_one_and_favour_calm_assets():
    idx = pd.date_range("2015-01-01", periods=500, freq="B", tz="UTC")
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"calm": rng.normal(0, 0.005, 500),
                       "wild": rng.normal(0, 0.05, 500)}, index=idx)
    w = inverse_vol_weights(df, 20)
    # During the rolling warm-up there is no volatility estimate, so the
    # engine correctly allocates nothing; weights sum to 1 only once live.
    live = w[w.sum(axis=1) > 0]
    assert len(live) > 400
    assert np.allclose(live.sum(axis=1), 1.0)
    assert live["calm"].mean() > live["wild"].mean()


def test_no_free_lunch_on_driftless_noise():
    """Sanity control: with no drift, trend gating must NOT beat a
    vol-matched hold. If it does, the harness is flattering itself."""
    r = synth_returns(n=6000, drift=0.0, seed=11)
    px = (1 + r).cumprod() * 100
    strat = apply_weights(r, trend_gate(px, 200))
    bench = vol_matched_benchmark(r, strat)
    s_sharpe = np.sqrt(TRADING_DAYS) * strat.mean() / strat.std(ddof=1)
    b_sharpe = np.sqrt(TRADING_DAYS) * bench.mean() / bench.std(ddof=1)
    assert s_sharpe - b_sharpe < 0.35, (
        f"trend gate 'beat' vol-matched hold on pure noise: {s_sharpe:.2f} vs {b_sharpe:.2f}")


def test_random_gate_placebo_runs_and_reports():
    r = synth_returns(n=1500)
    res = random_gate_placebo(r, time_in_market=0.7, n_runs=20)
    assert res["n_runs"] == 20 and np.isfinite(res["sharpe_mean"])


def test_ulcer_and_summary_fields():
    r = synth_returns(drift=0.0004)
    px = (1 + r).cumprod() * 100
    w = trend_gate(px, 50)
    s = summarize(apply_weights(r, w), w)
    for k in ["cagr", "sharpe", "max_drawdown", "calmar", "ulcer",
              "time_in_market", "annual_turnover"]:
        assert k in s and np.isfinite(s[k])
    assert ulcer_index((1 + r).cumprod()) >= 0
