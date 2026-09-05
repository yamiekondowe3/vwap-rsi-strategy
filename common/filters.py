"""Signal filters: session hours, volatility regime, and direction.

All three are documented in the source research and none was implemented.
VWAP+RSI in particular had NO session filter at all, so it traded the
illiquid Asian session and the 22:00 UTC rollover window where this
broker's recorded spread widens materially.

Design note: the volatility filter thresholds on ATR's own trailing
percentile rather than an absolute level, for the same reason `adaptive_rsi`
does -- an absolute threshold is implicitly calibrated to one instrument and
one era, whereas a percentile means the same rarity everywhere and adds no
tunable constant per market.
"""
from __future__ import annotations

import pandas as pd

from .indicators import atr

# Active-hours windows in UTC, from the research documents.
#   FX/metals/energy: London open through the London-NY overlap.
#   Crypto: 12:00-20:00 UTC, covering the overlap and the ~16:00-17:00 peak
#   identified by Brauneis, Mestel & Theissen (2025).
SESSION_WINDOWS = {
    "metals": (7, 17),
    "energy": (7, 17),
    "crypto": (12, 20),
}


def session_mask(index: pd.DatetimeIndex, asset_class: str) -> pd.Series:
    """True on bars inside the instrument's active trading window."""
    start, end = SESSION_WINDOWS.get(asset_class, (7, 17))
    hours = index.hour
    return pd.Series((hours >= start) & (hours < end), index=index)


def volatility_regime_mask(df: pd.DataFrame, pctile: float = 50.0,
                           window: int = 500, atr_period: int = 14) -> pd.Series:
    """True when ATR sits in the upper `pctile` of its own trailing distribution.

    The percentile is shifted one bar so the current bar never contributes to
    the threshold it is tested against (same no-look-ahead contract as
    `adaptive_rsi`).
    """
    a = atr(df, atr_period)
    threshold = a.rolling(window, min_periods=window // 2).quantile(pctile / 100.0).shift(1)
    return (a >= threshold).fillna(False)


def apply_direction(long_signal: pd.Series, short_signal: pd.Series,
                    direction: str) -> tuple[pd.Series, pd.Series]:
    """direction: 'both' | 'long_only' | 'short_only'.

    Worth testing because gold and BTC both trended strongly upward across
    the sample: a symmetric long/short strategy may be losing on the short
    side simply by fighting drift.
    """
    if direction == "long_only":
        return long_signal, short_signal & False
    if direction == "short_only":
        return long_signal & False, short_signal
    return long_signal, short_signal
