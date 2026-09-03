"""Performance metrics: Sharpe, Sortino, Max DD, Profit Factor, Calmar,
Expectancy, Win Rate, Recovery Factor -- computed from a trade-return series
and/or an equity curve.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def equity_curve(trade_returns: pd.Series, starting_equity: float = 1.0) -> pd.Series:
    return starting_equity * (1 + trade_returns).cumprod()


def sharpe_ratio(returns: pd.Series, periods_per_year: int = 252, rf: float = 0.0) -> float:
    excess = returns - rf / periods_per_year
    std = excess.std(ddof=1)
    if std == 0 or np.isnan(std):
        return 0.0
    return float(np.sqrt(periods_per_year) * excess.mean() / std)


def sortino_ratio(returns: pd.Series, periods_per_year: int = 252, rf: float = 0.0) -> float:
    excess = returns - rf / periods_per_year
    downside = excess[excess < 0]
    dd_std = downside.std(ddof=1)
    if dd_std == 0 or np.isnan(dd_std):
        return 0.0
    return float(np.sqrt(periods_per_year) * excess.mean() / dd_std)


def max_drawdown(equity: pd.Series):
    """Returns (max_dd_pct as a negative fraction, longest DD duration).

    Duration is a pd.Timedelta when `equity` has a datetime index (real
    backtests); otherwise (e.g. Monte Carlo resamples with a plain integer
    index) it's an int count of bars underwater.
    """
    is_datetime_index = isinstance(equity.index, pd.DatetimeIndex)
    running_max = equity.cummax()
    dd = equity / running_max - 1.0
    max_dd = float(dd.min())
    underwater = dd < 0
    duration = pd.Timedelta(0) if is_datetime_index else 0
    if underwater.any():
        segment = (~underwater).cumsum()
        if is_datetime_index:
            durations = dd[underwater].groupby(segment[underwater]).apply(
                lambda s: s.index[-1] - s.index[0] if len(s) > 1 else pd.Timedelta(0)
            )
        else:
            durations = dd[underwater].groupby(segment[underwater]).size() - 1
        if len(durations):
            duration = durations.max()
    return max_dd, duration


def profit_factor(trade_pnls: pd.Series) -> float:
    gains = trade_pnls[trade_pnls > 0].sum()
    losses = -trade_pnls[trade_pnls < 0].sum()
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return float(gains / losses)


def calmar_ratio(returns: pd.Series, equity: pd.Series, periods_per_year: int = 252) -> float:
    annual_return = (equity.iloc[-1] / equity.iloc[0]) ** (periods_per_year / len(returns)) - 1 if len(returns) else 0.0
    max_dd, _ = max_drawdown(equity)
    if max_dd == 0:
        return 0.0
    return float(annual_return / abs(max_dd))


def expectancy(trade_pnls: pd.Series) -> float:
    if len(trade_pnls) == 0:
        return 0.0
    win_rate = (trade_pnls > 0).mean()
    avg_win = trade_pnls[trade_pnls > 0].mean() if (trade_pnls > 0).any() else 0.0
    avg_loss = trade_pnls[trade_pnls < 0].mean() if (trade_pnls < 0).any() else 0.0
    return float(win_rate * avg_win + (1 - win_rate) * avg_loss)


def win_rate(trade_pnls: pd.Series) -> float:
    if len(trade_pnls) == 0:
        return 0.0
    return float((trade_pnls > 0).mean())


def recovery_factor(trade_pnls: pd.Series, equity: pd.Series) -> float:
    max_dd, _ = max_drawdown(equity)
    if max_dd == 0:
        return 0.0
    net_profit = trade_pnls.sum()
    return float(net_profit / abs(max_dd * equity.iloc[0]))


def full_report(trade_pnls: pd.Series, trade_returns: pd.Series, periods_per_year: int = 252) -> dict:
    """trade_pnls: $ per trade. trade_returns: fractional return per trade (pnl/equity_at_entry)."""
    eq = equity_curve(trade_returns)
    max_dd, dd_duration = max_drawdown(eq)
    return {
        "n_trades": int(len(trade_pnls)),
        "sharpe": sharpe_ratio(trade_returns, periods_per_year),
        "sortino": sortino_ratio(trade_returns, periods_per_year),
        "max_drawdown_pct": max_dd,
        "max_drawdown_duration": str(dd_duration),
        "profit_factor": profit_factor(trade_pnls),
        "calmar": calmar_ratio(trade_returns, eq, periods_per_year),
        "expectancy": expectancy(trade_pnls),
        "win_rate": win_rate(trade_pnls),
        "recovery_factor": recovery_factor(trade_pnls, eq),
        "total_return_pct": float(eq.iloc[-1] / eq.iloc[0] - 1) if len(eq) else 0.0,
    }
