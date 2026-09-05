"""Shared bar-loop backtester driven by a signal frame plus an ExitPolicy.

Both strategies (and the random-entry placebo) produce a signal frame and
run it through this identical core, which is what makes the placebo
comparison valid: strategy and control differ ONLY in which bars they enter
on, never in how positions are managed or costed.

Signal frame must carry: open, high, low, close, atr, spread (optional),
long_signal, short_signal. Fills execute at the NEXT bar's open, exits at
the level reached, both crossing the spread against the trader.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .costs import FrictionModel
from .exits import ExitPolicy, Position, open_position, process_bar


def run(sig: pd.DataFrame, policy: ExitPolicy, symbol: str,
        starting_equity: float = 10_000.0, risk_pct: float = 0.005,
        friction: FrictionModel | None = None,
        max_trades_per_day: int | None = None) -> dict:
    if friction is None:
        friction = FrictionModel(symbol=symbol)

    equity = starting_equity
    pos: Position | None = None
    trades: list[dict] = []
    trades_today, current_day = 0, None

    idx = sig.index
    has_spread = "spread" in sig.columns
    # Column-wise numpy access: the loop runs millions of iterations and
    # DataFrame.iloc per bar is the dominant cost.
    o = sig["open"].to_numpy(); h = sig["high"].to_numpy()
    lo = sig["low"].to_numpy(); c = sig["close"].to_numpy()
    a = sig["atr"].to_numpy()
    spr = sig["spread"].to_numpy() if has_spread else np.full(len(sig), np.nan)
    ls = sig["long_signal"].to_numpy(); ss = sig["short_signal"].to_numpy()

    def close_leg(level, fraction, ts, bar_spread, reason):
        nonlocal equity
        exit_price = level - pos.side * friction.half_spread(ts, level, bar_spread)
        qty = pos.size * fraction
        pnl = pos.side * (exit_price - pos.entry_price) * qty
        pnl -= friction.commission(abs(qty * exit_price))
        pos.realized_pnl += pnl
        equity += pnl
        return reason

    for i in range(len(idx) - 1):
        ts_next = idx[i + 1]
        day = idx[i].normalize()
        if day != current_day:
            current_day, trades_today = day, 0

        if pos is not None:
            bar = {"high": h[i + 1], "low": lo[i + 1], "close": c[i + 1]}
            legs = process_bar(pos, bar, ts_next, policy)
            last_reason = None
            for leg in legs:
                last_reason = close_leg(leg["level"], leg["fraction"], ts_next,
                                        spr[i + 1], leg["reason"])
            if pos.remaining <= 1e-9:
                trades.append({
                    "entry_ts": pos.entry_ts, "exit_ts": ts_next, "side": pos.side,
                    "entry_price": pos.entry_price, "size": pos.size,
                    "bars_held": pos.bars_held, "exit_reason": last_reason,
                    "pnl": pos.realized_pnl,
                    "return": pos.realized_pnl / pos.equity_at_entry,
                    "risk_amount": pos.risk_amount,
                    "r_multiple": (pos.realized_pnl / pos.risk_amount
                                   if pos.risk_amount > 0 else np.nan),
                })
                pos = None
            continue

        if max_trades_per_day is not None and trades_today >= max_trades_per_day:
            continue
        atr_now = a[i]
        if not np.isfinite(atr_now) or atr_now <= 0:
            continue

        side = 1 if ls[i] else (-1 if ss[i] else 0)
        if side == 0:
            continue

        entry_price = friction.apply_fill(ts_next, o[i + 1], atr_now, side,
                                          bar_spread=spr[i + 1] if has_spread else None)
        risk_per_unit = policy.stop_atr * atr_now
        if risk_per_unit <= 0:
            continue
        risk_amount = risk_pct * equity
        size = risk_amount / risk_per_unit

        pos = open_position(side, entry_price, atr_now, policy, size, ts_next,
                            equity, risk_amount)
        trades_today += 1

    return {"trades": pd.DataFrame(trades), "final_equity": equity}
