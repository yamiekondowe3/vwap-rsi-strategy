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


def prepare_signals(df: pd.DataFrame, p: VWAPRSIParams) -> pd.DataFrame:
    out = df.copy()
    anchor_mask = out.index.to_series().dt.floor("D").diff().fillna(pd.Timedelta(0)) != pd.Timedelta(0)
    anchor_mask.iloc[0] = True
    out["vwap"] = anchored_vwap(out, anchor_mask)
    out["vwap_slope_up"] = out["vwap"] > out["vwap"].shift(p.vwap_slope_window)
    out["vwap_slope_down"] = out["vwap"] < out["vwap"].shift(p.vwap_slope_window)
    out["rsi"] = rsi(out["close"], p.rsi_period)
    out["atr"] = atr(out, p.atr_period)

    # Entry filters, evaluated on the CLOSED bar (signal), executed next bar.
    long_signal = (
        (out["close"] > out["vwap"]) & out["vwap_slope_up"]
        & (out["rsi"].shift(1) < p.rsi_oversold) & (out["rsi"] >= p.rsi_oversold)  # RSI recovering from oversold
    )
    short_signal = (
        (out["close"] < out["vwap"]) & out["vwap_slope_down"]
        & (out["rsi"].shift(1) > p.rsi_overbought) & (out["rsi"] <= p.rsi_overbought)
    )
    out["long_signal"] = long_signal.fillna(False)
    out["short_signal"] = short_signal.fillna(False)
    return out


def run_backtest(df: pd.DataFrame, params: VWAPRSIParams, symbol: str, starting_equity: float = 10_000.0) -> dict:
    sig = prepare_signals(df, params)
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
        }

    trades_df = pd.DataFrame(trades)
    return {"trades": trades_df, "final_equity": equity, "params": params.__dict__}
