"""Bar-by-bar backtest engine for the VWAP+RSI strategy.

Deliberately a straightforward loop (not a vectorized/JIT engine) so the
no-look-ahead and friction-model wiring stays easy to audit -- correctness
over raw speed for this proof-of-concept. Every entry uses only CLOSED-bar
data and fills at the NEXT bar's open, consistent with the research docs'
look-ahead-trap warnings.
"""
from __future__ import annotations

import sys
from pathlib import Path
from dataclasses import dataclass

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.costs import FrictionModel
from common.indicators import anchored_vwap, rsi, atr


@dataclass
class VWAPRSIParams:
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    vwap_slope_window: int = 15
    atr_period: int = 14
    stop_atr_mult: float = 2.0
    target_atr_mult: float = 2.0   # 1.0R by default; tune per go/no-go gate
    risk_pct: float = 0.005        # 0.5% equity risk per trade
    day_boundary_hour_utc: int = 0  # daily VWAP reset anchor
    # Selectivity: require price to have actually stretched away from VWAP
    # before taking the pullback, rather than firing on any RSI cross near
    # the mean. This is the mechanical stand-in for the research docs'
    # VWAP deviation-band concept (trade the 1-1.5 sigma stretch, not noise
    # around the average). 0.0 disables.
    min_vwap_dist_atr: float = 0.0
    # Self-calibrating RSI thresholds. A hardcoded 30/70 is implicitly
    # calibrated to ONE timeframe's noise level: RSI dispersion shrinks on
    # coarser bars, so the same 30 that fires often on M5 becomes a rare
    # extreme on M15 (21 trades in 15 years -- statistically useless). Using
    # a rolling PERCENTILE of RSI's own recent distribution keeps the
    # threshold at a constant rarity across timeframes AND instruments,
    # with no per-market tuning. That is a structural fix, not a fitted
    # parameter: one rule, self-adjusting everywhere.
    adaptive_rsi: bool = False
    rsi_pctile: float = 20.0        # enter when RSI is in its lowest/highest N% (longs/shorts)
    rsi_pctile_window: int = 500
    # Entry trigger. The source research document specifies a "first
    # counter-color pullback candle toward VWAP" -- NOT an RSI cross. This
    # project substituted RSI from the start, so the documented strategy was
    # never actually tested. "pullback" is the faithful implementation;
    # "none" is the pure VWAP side+slope filter with no trigger at all.
    trigger: str = "rsi"            # rsi | pullback | none    # trailing bars defining "recent distribution"


def prepare_signals(df: pd.DataFrame, p: VWAPRSIParams) -> pd.DataFrame:
    out = df.copy()
    anchor_mask = out.index.to_series().dt.floor("D").diff().fillna(pd.Timedelta(0)) != pd.Timedelta(0)
    anchor_mask.iloc[0] = True
    out["vwap"] = anchored_vwap(out, anchor_mask)
    out["vwap_slope_up"] = out["vwap"] > out["vwap"].shift(p.vwap_slope_window)
    out["vwap_slope_down"] = out["vwap"] < out["vwap"].shift(p.vwap_slope_window)
    out["rsi"] = rsi(out["close"], p.rsi_period)
    out["atr"] = atr(out, p.atr_period)

    # Entry thresholds: either fixed levels, or RSI's own trailing
    # percentiles so the threshold means the same thing on any timeframe.
    # The percentile window is shifted by 1 bar so the current bar's RSI
    # never contributes to the threshold it is being tested against.
    if p.adaptive_rsi:
        roll = out["rsi"].rolling(p.rsi_pctile_window, min_periods=p.rsi_pctile_window // 2)
        oversold_level = roll.quantile(p.rsi_pctile / 100.0).shift(1)
        overbought_level = roll.quantile(1.0 - p.rsi_pctile / 100.0).shift(1)
    else:
        oversold_level = pd.Series(p.rsi_oversold, index=out.index)
        overbought_level = pd.Series(p.rsi_overbought, index=out.index)
    out["rsi_oversold_level"] = oversold_level
    out["rsi_overbought_level"] = overbought_level

    # Entry filters, evaluated on the CLOSED bar (signal), executed next bar.
    # Shared directional filter: price on the correct side of VWAP, VWAP
    # sloping that way. Identical across all three triggers.
    long_ok = (out["close"] > out["vwap"]) & out["vwap_slope_up"]
    short_ok = (out["close"] < out["vwap"]) & out["vwap_slope_down"]

    if p.trigger == "rsi":
        long_signal = long_ok & (out["rsi"].shift(1) < oversold_level) & (out["rsi"] >= oversold_level)
        short_signal = short_ok & (out["rsi"].shift(1) > overbought_level) & (out["rsi"] <= overbought_level)
    elif p.trigger == "pullback":
        # The documented trigger: the FIRST counter-color candle while the
        # filter holds -- a red candle in an uptrend, green in a downtrend.
        # "First" means the previous bar was not itself counter-color, so a
        # run of red candles fires once, not repeatedly.
        red = out["close"] < out["open"]
        green = out["close"] > out["open"]
        long_signal = long_ok & red & ~red.shift(1).fillna(False)
        short_signal = short_ok & green & ~green.shift(1).fillna(False)
    elif p.trigger == "none":
        # Pure VWAP side + slope, entering on the bar the filter first turns
        # true (not every bar it stays true, which would just re-enter).
        long_signal = long_ok & ~long_ok.shift(1).fillna(False)
        short_signal = short_ok & ~short_ok.shift(1).fillna(False)
    else:
        raise ValueError(f"unknown trigger {p.trigger!r}")
    if p.min_vwap_dist_atr > 0:
        stretched = (out["close"] - out["vwap"]).abs() >= p.min_vwap_dist_atr * out["atr"]
        long_signal &= stretched.fillna(False)
        short_signal &= stretched.fillna(False)

    out["long_signal"] = long_signal.fillna(False)
    out["short_signal"] = short_signal.fillna(False)
    return out


def run_backtest(df: pd.DataFrame, params: VWAPRSIParams, symbol: str, starting_equity: float = 10_000.0,
                 friction: FrictionModel | None = None) -> dict:
    """`friction` may be injected to override the default cost model -- e.g. a
    `FrictionModel(frictionless=True)` to measure the signal's ceiling."""
    sig = prepare_signals(df, params)
    if friction is None:
        friction = FrictionModel(symbol=symbol)

    equity = starting_equity
    position = None  # dict with side, entry_price, stop, target, size, entry_ts
    trades = []

    idx = sig.index
    for i in range(len(idx) - 1):
        row = sig.iloc[i]
        next_row = sig.iloc[i + 1]
        ts_next = idx[i + 1]

        if position is not None:
            hit_stop = (position["side"] == 1 and next_row["low"] <= position["stop"]) or \
                       (position["side"] == -1 and next_row["high"] >= position["stop"])
            hit_target = (position["side"] == 1 and next_row["high"] >= position["target"]) or \
                         (position["side"] == -1 and next_row["low"] <= position["target"])
            if hit_stop or hit_target:
                # Conservative: assume stop fills first if both are touched in one bar.
                level = position["stop"] if hit_stop else position["target"]
                # Exit crosses the spread against us too (this was missing before).
                exit_price = level - position["side"] * friction.half_spread(
                    ts_next, level, next_row.get("spread")
                )
                pnl = position["side"] * (exit_price - position["entry_price"]) * position["size"]
                pnl -= friction.commission(abs(position["size"] * exit_price))
                equity += pnl
                trades.append({
                    "entry_ts": position["entry_ts"], "exit_ts": ts_next,
                    "side": position["side"], "entry_price": position["entry_price"],
                    "exit_price": exit_price, "size": position["size"],
                    "pnl": pnl, "return": pnl / position["equity_at_entry"],
                    # Normalized edge: pnl per unit of capital actually risked.
                    "risk_amount": position["risk_amount"],
                    "r_multiple": pnl / position["risk_amount"] if position["risk_amount"] > 0 else np.nan,
                })
                position = None
            continue

        if not np.isfinite(row.get("atr", np.nan)) or row["atr"] <= 0:
            continue

        side = 1 if row["long_signal"] else (-1 if row["short_signal"] else 0)
        if side == 0:
            continue

        entry_price = friction.apply_fill(ts_next, next_row["open"], row["atr"], side,
                                          bar_spread=next_row.get("spread"))
        stop = entry_price - side * params.stop_atr_mult * row["atr"]
        target = entry_price + side * params.target_atr_mult * row["atr"]
        risk_per_unit = abs(entry_price - stop)
        if risk_per_unit <= 0:
            continue
        size = (params.risk_pct * equity) / risk_per_unit

        position = {
            "side": side, "entry_price": entry_price, "stop": stop, "target": target,
            "size": size, "entry_ts": ts_next, "equity_at_entry": equity,
            "risk_amount": params.risk_pct * equity,
        }

    trades_df = pd.DataFrame(trades)
    return {"trades": trades_df, "final_equity": equity, "params": params.__dict__}
