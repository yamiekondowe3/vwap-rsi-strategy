# Risk-managed exposure — the first positive result in this project

After fourteen rounds establishing that these markets give up no alpha to price-pattern
signals, the goal changed from *predicting returns* to *managing exposure*. This is the
result, and unlike everything before it, part of it survives the controls.

## Setup

Pre-registered, nothing searched (in-sample selection was already shown to have zero
predictive power here): 20-day realised volatility, 15% annualised vol target, 200-day trend
gate, max leverage 1.0, real broker spread charged on turnover. Daily bars, 11–15.7 years.

**The decisive control is the volatility-matched benchmark.** A trend gate sits in cash ~40%
of the time, and holding less trivially reduces drawdown — that is not skill. So every rule
is compared against static buy-and-hold *levered to the same realised volatility*, which asks
the only question that matters: does **timing** exposure beat merely **sizing** it? A
random-gate placebo (same time-in-market, random timing) is reported alongside.

## Result: 3 of 15 configurations beat vol-matched hold on both Sharpe and drawdown

| Asset | Rule | Sharpe | vs vol-matched | ΔDrawdown | Placebo z |
|---|---|---|---|---|---|
| **BTCUSD** | trend × vol-target | **1.149** | **+0.064** | **+5.4 pt** | **+2.80** |
| ETHUSD | trend × vol-target | 1.046 | +0.078 | +10.6 pt | +2.03 |
| ETHUSD | trend gate | 1.026 | +0.057 | +7.2 pt | +1.90 |

**All three are crypto**, which is mechanism-consistent rather than scattered: crypto has the
strongest volatility clustering and the most persistent trends, which is exactly what these
two techniques exploit. Gold, silver and oil showed no benefit that survived the control.

With 15 configurations the Bonferroni threshold is z > 2.71, so **only BTCUSD trend × vol-target
survives correction** (z = 2.80). The two ETH results are suggestive, not established.

## The honest value proposition: drawdown, not return

BTCUSD, full 15.5-year sample:

| | CAGR | Sharpe | Max DD | Ulcer | Calmar |
|---|---|---|---|---|---|
| Buy & hold | **+109.4%** | +1.08 | **−93.1%** | 0.512 | **1.18** |
| Trend × vol-target | +24.7% | **+1.15** | **−29.2%** | **0.130** | 0.84 |

Read this carefully, because the naive reading is wrong in both directions:
- It is **not** a return improvement. CAGR falls from 109% to 25%. Against *raw* buy-and-hold
  the Calmar is worse (0.84 vs 1.18).
- It **is** a genuine risk improvement. Max drawdown falls 64 points, the Ulcer index (which
  penalises deep *and* long drawdowns) improves 4×, and at matched volatility it delivers
  more return per unit of risk than static holding.

The product here is "hold crypto through a cycle without a 93% drawdown", not "make more
money than holding crypto".

## Sub-period stability: the drawdown gain is robust, the Sharpe gain is not

Splitting each history into thirds:

| Asset | Period | ΔSharpe vs vol-matched | Strategy DD | Vol-matched DD |
|---|---|---|---|---|
| BTCUSD | 2011–2016 | **−0.076** | −29.2% | −27.9% |
| BTCUSD | 2016–2021 | +0.326 | −22.6% | −29.5% |
| BTCUSD | 2021–2026 | +0.034 | **−14.7%** | −31.1% |
| ETHUSD | 2015–2019 | +0.105 | −14.6% | −21.4% |
| ETHUSD | 2019–2023 | +0.275 | −17.7% | −20.6% |
| ETHUSD | 2023–2026 | +0.079 | −14.2% | −21.1% |

**The Sharpe advantage is regime-dependent** — concentrated in 2016–2021, negative for BTC in
the earliest third, and only marginal in the most recent third (+0.03 BTC, +0.08 ETH). Anyone
selling this as a reliable Sharpe improvement is overreading it.

**The drawdown advantage is consistent** — better in 5 of 6 sub-periods, and largest in the
most recent one (BTC −14.7% vs −31.1%, less than half). That is the part to trust.

Note ETHUSD is *more* consistent across sub-periods (3/3 positive on both measures) than
BTCUSD (2/3), despite BTC having the stronger full-sample z. Full-sample significance and
regime robustness are not the same thing.

## What did not work

- **Multi-asset diversification added nothing.** The inverse-vol and inverse-vol×trend
  portfolios both *lost* to a vol-matched equal-weight benchmark (ΔSharpe −0.13). The
  available universe is the problem: gold/silver correlate at 0.79, BTC/ETH at 0.56, and the
  broker's equity indices only reach back to 2024, so there is no genuinely different return
  driver to diversify into over this window.
- **Metals and energy showed no robust benefit.** Vol targeting improved gold's Sharpe
  (+0.067, z = +4.5) but made its drawdown *worse* than vol-matched hold, failing the gate.
  Silver and oil were negative on both measures.
- **Vol targeting alone was not enough anywhere.** On BTC it cut drawdown hugely (−93% →
  −39%) but lost to vol-matched hold on Sharpe (z = −5.3). The trend gate is what supplies
  the timing; vol targeting supplies the smoothness. Only the combination cleared the gate.

## Verdict and next step

This is a **real but modest** result, and the first thing in this project to survive its own
control. It is worth taking further, with the honest framing that it is a **crypto drawdown-
control overlay**, not a money-making signal.

Before any capital: walk-forward the BTC configuration properly (the sub-period split above is
indicative, not a walk-forward), confirm behaviour survives a pessimistic slippage scenario,
and paper-trade the weekly rebalance on the demo account. The realistic ceiling is what the
table above shows — roughly buy-and-hold's risk-adjusted return with a third of the drawdown,
which is a legitimate goal but must not be marketed as outperformance.

Raw data: `portfolio_results.json`, `portfolio_test.py`. Engine: `common/portfolio.py`
(`vol_target_weights`, `trend_gate`, `vol_matched_benchmark`, `random_gate_placebo`),
tests in `tests_portfolio.py` including a no-free-lunch check on driftless noise.
