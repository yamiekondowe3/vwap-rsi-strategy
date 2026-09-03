"""Monte Carlo stress testing: resample trade returns and shuffle trade
order to estimate VaR, expected max-drawdown distribution, and ruin
probability. Per project brief: 5,000 iterations by default.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .metrics import equity_curve, max_drawdown


def run_monte_carlo(
    trade_returns: pd.Series,
    n_iterations: int = 5000,
    starting_equity: float = 1.0,
    ruin_threshold: float = 0.5,
    method: str = "bootstrap",
    seed: int | None = None,
) -> dict:
    """method: 'bootstrap' (sample with replacement, same N trades) or
    'shuffle' (reorder the exact same trades, no replacement) -- run both
    and compare per the project brief.
    """
    rng = np.random.default_rng(seed)
    returns = trade_returns.dropna().to_numpy()
    n = len(returns)
    if n == 0:
        raise ValueError("No trade returns to simulate")

    final_equities = np.empty(n_iterations)
    max_dds = np.empty(n_iterations)
    ruined = np.zeros(n_iterations, dtype=bool)

    for i in range(n_iterations):
        if method == "bootstrap":
            sample = rng.choice(returns, size=n, replace=True)
        elif method == "shuffle":
            sample = rng.permutation(returns)
        else:
            raise ValueError("method must be 'bootstrap' or 'shuffle'")

        eq = equity_curve(pd.Series(sample), starting_equity=starting_equity)
        final_equities[i] = eq.iloc[-1]
        dd, _ = max_drawdown(eq)
        max_dds[i] = dd
        ruined[i] = bool((eq <= starting_equity * ruin_threshold).any())

    pnl_dist = final_equities - starting_equity
    return {
        "method": method,
        "n_iterations": n_iterations,
        "n_trades_per_sim": n,
        "var_95": float(np.percentile(pnl_dist, 5)),
        "var_99": float(np.percentile(pnl_dist, 1)),
        "median_final_equity": float(np.median(final_equities)),
        "mean_final_equity": float(np.mean(final_equities)),
        "worst_max_drawdown": float(np.min(max_dds)),
        "median_max_drawdown": float(np.median(max_dds)),
        "p95_max_drawdown": float(np.percentile(max_dds, 5)),
        "ruin_probability": float(ruined.mean()),
        "ruin_threshold": ruin_threshold,
    }
