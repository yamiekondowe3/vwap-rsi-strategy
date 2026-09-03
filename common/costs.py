"""Realistic friction models: commissions, slippage, spread, latency.

These models exist to close the backtest-to-live gap called out in the
project brief: fixed-pip/fixed-dollar cost assumptions systematically
overstate strategy edges (see Brusco's ORB replication, where the
Zarattini/Aziz edge died at ~2.2c/share of slippage). Every model here is
volatility-aware rather than a flat constant.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
import numpy as np
import pandas as pd

ASSET_CLASS = {
    "XAUUSD": "metals", "XAGUSD": "metals",
    "USOIL": "energy",
    "BTCUSD": "crypto", "ETHUSD": "crypto",
}

# Commission per side, in basis points of notional, by asset class.
# These are starting points -- calibrate to the actual broker/venue before
# trusting any backtest result.
COMMISSION_BPS = {
    "metals": 1.5,   # typical MT5 ECN-style commission on XAUUSD/XAGUSD
    "energy": 2.0,
    "crypto": 5.0,   # taker fee, e.g. 0.05% on a major exchange/perp venue
}

# Baseline half-spread in bps of price, during normal liquid hours.
# Widened dynamically around session opens/rollovers/news (see spread()).
BASE_SPREAD_BPS = {
    "metals": 1.2,
    "energy": 3.0,
    "crypto": 2.0,
}

# Session windows (UTC) where spreads are known to widen materially.
WIDE_SPREAD_WINDOWS = [
    (time(21, 55), time(22, 10)),  # FX/CFD daily rollover ~22:00 UTC
    (time(0, 0), time(0, 15)),     # thin post-rollover liquidity
]


@dataclass
class FrictionModel:
    symbol: str
    asset_class: str = field(init=False)
    latency_ms_range: tuple[int, int] = (50, 250)
    rng: np.random.Generator = field(default_factory=np.random.default_rng)

    def __post_init__(self):
        self.asset_class = ASSET_CLASS.get(self.symbol, "metals")

    def commission(self, notional: float) -> float:
        """Round-turn-independent, per-side commission in price-equivalent terms."""
        return notional * COMMISSION_BPS[self.asset_class] / 1e4

    def spread(self, ts: pd.Timestamp, price: float) -> float:
        """Half-spread in price terms, widened around known illiquid windows."""
        bps = BASE_SPREAD_BPS[self.asset_class]
        t = ts.time()
        for start, end in WIDE_SPREAD_WINDOWS:
            if start <= t <= end:
                bps *= 4.0
                break
        return price * bps / 1e4

    def slippage(self, price: float, atr: float, side: int) -> float:
        """Variable slippage scaled to ATR (volatility), not a fixed pip amount.

        side: +1 for buys (slippage pushes fill price up), -1 for sells
        (slippage pushes fill price down). Magnitude drawn from a
        volatility-scaled half-normal distribution so spikes occasionally
        produce much worse fills, matching real fill behavior around
        breakouts/news.
        """
        if atr <= 0 or not np.isfinite(atr):
            return 0.0
        magnitude = abs(self.rng.normal(loc=0.05, scale=0.05)) * atr
        return side * magnitude

    def latency_bars(self, bar_seconds: int) -> int:
        """Execution delay expressed in whole bars, given a 50-250ms latency draw."""
        ms = self.rng.uniform(*self.latency_ms_range)
        return int(np.ceil((ms / 1000.0) / bar_seconds)) if bar_seconds else 0

    def apply_fill(self, ts: pd.Timestamp, signal_price: float, atr: float, side: int) -> float:
        """Full fill-price model: signal price -> spread -> slippage -> commission-adjusted.

        side: +1 buy, -1 sell. Returns the effective fill price (commission
        is charged separately in $ terms via commission()).
        """
        half_spread = self.spread(ts, signal_price)
        slip = self.slippage(signal_price, atr, side)
        return signal_price + side * half_spread + slip
