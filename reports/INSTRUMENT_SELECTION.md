# Instrument selection — best 2 per strategy

> **RETRACTED.** The ETHUSD recommendation below does not survive cross-sectional
> validation. Running the identical fixed overlay across 26 crypto pairs shows the median
> asset is made WORSE (median dSharpe -0.139), only 6/26 improve on both measures, and
> ETHUSD sits at the 96th percentile -- exactly what picking best-of-5 produces by chance
> (P=0.33). Do not trade this. See CROSSSECTION_VALIDATION.md.


**Correction up front:** my previous message named **BTCUSD** as the standout for the risk
overlay, on the strength of a full-sample Bonferroni-surviving z of 2.80. Rolling
out-of-sample validation does **not** support that. BTCUSD wins only 6 of 12 drawdown
windows — a coin flip. **ETHUSD is the genuinely robust one** (8/8 Sharpe windows, 7/8
drawdown windows). Full-sample significance and regime robustness are different things, and
here they disagreed. The rolling result is the one to trust.

---

## 1. Risk-managed overlay (200d trend gate × 15% vol target) — THE TRADEABLE ONE

Rolling 3-year out-of-sample windows, 1-year step, versus volatility-matched buy-and-hold.
The overlay has no fitted parameters, so this tests regime robustness, not curve-fitting.

| Rank | Instrument | Windows | Sharpe wins | DD wins | Mean ΔDD | Verdict |
|---|---|---|---|---|---|---|
| **1** | **ETHUSD** | 8 | **8/8 (100%)** | **7/8 (88%)** | **+8.8 pt** | **Tradeable** |
| **2** | **BTCUSD** | 12 | 8/12 (67%) | 6/12 (50%) | +1.5 pt | Marginal — monitor only |
| 3 | XAUUSD | 12 | 4/12 (33%) | 6/12 (50%) | −2.4 pt | No evidence |
| 4 | XAGUSD | 12 | 1/12 (8%) | 3/12 (25%) | −7.2 pt | Actively harmful |

**Selection: ETHUSD (conviction), BTCUSD (small size or paper only).**

ETHUSD winning 8 of 8 Sharpe windows is a 1-in-256 outcome under a coin-flip null (p≈0.4%),
and it improved drawdown by an average of 8.8 points. The caveat is honest: 8 windows from
11.1 years of history, and the windows overlap, so they are not fully independent
observations. BTCUSD at 50% drawdown wins is not evidence of anything — its full-sample
result was carried by the 2016–2021 regime.

**Cost stress: passes comfortably.** At 10× the real spread, ETHUSD's Sharpe moves 1.05 →
1.03 and BTCUSD's is unchanged. Weekly rebalancing means costs are near-irrelevant — the
opposite of the intraday strategies, where costs were decisive.

## 2. VWAP+RSI — no tradeable selection exists

Best exit configuration per instrument, from the placebo-controlled run:

| Rank | Instrument | PF | E[R] | Placebo z |
|---|---|---|---|---|
| 1 | XAUUSD (trail exit) | 1.325 | +0.185 | **+1.34** |
| 2 | USOIL (fixed exit) | 1.348 | +0.151 | +0.87 |
| 3 | BTCUSD (trail exit) | 1.161 | +0.090 | +0.53 |

**None reaches the z > 1.645 threshold, so none beats random entry.** XAUUSD and USOIL are
the top 2 *by profit factor*, but that PF comes from the trailing exit harvesting drift, not
from the signal: random entries with the same exit performed statistically as well. USOIL's
number rests on 31 trades. **Ranking these is ranking noise — I do not recommend trading
either.**

## 3. ORB+Pivots — no tradeable selection exists

| Rank | Instrument | PF | E[R] | Placebo z |
|---|---|---|---|---|
| 1 | BTCUSD (trail exit) | 1.053 | +0.038 | +0.86 |
| 2 | USOIL (trail exit) | 1.040 | +0.026 | +0.47 |
| 3 | XAUUSD (trail exit) | 1.023 | +0.017 | −0.71 |

Same verdict, weaker still: profit factors barely above 1.0 and no instrument beats its
placebo. Recall that ORB is also negative at *zero* execution cost (−0.052R), so there is no
version of this that works.

---

## Recommendation

**Trade ETHUSD with the overlay. Paper-trade BTCUSD alongside it. Do not deploy VWAP+RSI or
ORB+Pivots on anything.**

Concretely, for ETHUSD: hold when price is above its 200-day moving average, size the position
at 15% annualised volatility target (capped at 1× leverage), rebalance weekly. Expected
behaviour based on 11.1 years: roughly the same risk-adjusted return as holding ETH, with
drawdowns cut by ~9 points on average and ~76% max versus ~94% for buy-and-hold.

What this is: a drawdown-control overlay for a crypto position you were going to hold anyway.
What it is not: a way to make more money than holding ETH — CAGR falls from ~96% to ~20% at
the 15% vol target, and you would need leverage to close that gap.

Before capital: paper-trade the weekly rebalance on the demo account. The rule is simple
enough to execute manually, so implementation risk is low; the real risk is that 8 overlapping
windows on one asset is a thinner evidence base than it looks.

Raw data: `overlay_validation.json`, `overlay_validation.py`, `portfolio_results.json`,
`exit_lever_results.json`.
