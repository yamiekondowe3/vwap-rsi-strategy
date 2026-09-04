"""Performance metrics: Sharpe, Sortino, Max DD, Profit Factor, Calmar,
Expectancy, Win Rate, Recovery Factor -- computed from a trade-return series
and/or an equity curve.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def equity_curve(trade_returns: pd.Series, starting_equity: float = 1.0) -> pd.Series:
    return starting_equity * (1 + trade_returns).cumprod()


def trades_per_year(entry_ts: pd.Series, n_trades: int) -> float:
    """Actual trade frequency, used to annualize a PER-TRADE return series.

    Annualizing per-trade returns with a hardcoded 252 (as this module did
    originally) is wrong whenever the strategy doesn't happen to take one
    trade per trading day -- it silently rescales Sharpe by
    sqrt(252 / true_rate). These strategies take ~511 trades/year, so the
    old numbers were inflated by ~sqrt(2).
    """
    ts = pd.to_datetime(entry_ts)
    span_years = (ts.max() - ts.min()).total_seconds() / (365.25 * 24 * 3600)
    if span_years <= 0:
        return float(n_trades)
    return n_trades / span_years


def expectancy_r(r_multiples: pd.Series) -> float:
    """Mean per-trade edge in R (risk) units -- the normalized edge measure.

    This is the number to compare across configurations: unlike dollar
    expectancy it is immune to position size, account size, and the
    compounding path (a wiped-out account mechanically forces dollar
    expectancy to -starting_equity/n_trades regardless of the strategy,
    which previously made four very different R:R settings look identical).
    Positive means a real edge per unit risked; 0 means breakeven.
    """
    r = r_multiples.dropna()
    return float(r.mean()) if len(r) else 0.0


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


def full_report(trade_pnls: pd.Series, trade_returns: pd.Series, periods_per_year: int | None = None,
                r_multiples: pd.Series | None = None, entry_ts: pd.Series | None = None) -> dict:
    """trade_pnls: $ per trade. trade_returns: fractional return per trade
    (pnl/equity_at_entry). r_multiples: pnl / dollars-risked per trade --
    supply it to get the normalized, size-independent edge measures.
    entry_ts: trade entry timestamps, used to annualize correctly.

    `periods_per_year` is derived from the actual trade frequency when
    `entry_ts` is given; the 252 default is only a fallback for callers
    that can't supply timestamps.
    """
    eq = equity_curve(trade_returns)
    max_dd, dd_duration = max_drawdown(eq)

    if periods_per_year is None:
        periods_per_year = (
            trades_per_year(entry_ts, len(trade_pnls)) if entry_ts is not None and len(trade_pnls)
            else 252
        )

    report = {
        "n_trades": int(len(trade_pnls)),
        "trades_per_year": round(float(periods_per_year), 1),
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

    # Normalized (size- and path-independent) edge measures -- the ones to
    # compare across configurations.
    if r_multiples is not None and len(r_multiples):
        r = r_multiples.dropna()
        report["expectancy_r"] = expectancy_r(r)
        report["r_std"] = float(r.std(ddof=1)) if len(r) > 1 else 0.0
        # Per-trade edge divided by its own dispersion, annualized by the
        # real trade rate -- the cleanest cross-config comparison.
        report["sharpe_r"] = (
            float(np.sqrt(periods_per_year) * r.mean() / r.std(ddof=1))
            if len(r) > 1 and r.std(ddof=1) > 0 else 0.0
        )
        report["avg_win_r"] = float(r[r > 0].mean()) if (r > 0).any() else 0.0
        report["avg_loss_r"] = float(r[r < 0].mean()) if (r < 0).any() else 0.0
    return report
