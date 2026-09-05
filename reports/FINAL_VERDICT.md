# Final verdict: VWAP+RSI on XAUUSD — not profitable out-of-sample

Conclusion of the investigation, after correcting the cost-model bug that
voided all earlier results in this repo, normalizing the metrics, and
running a disciplined walk-forward optimization.

## Method

- **Data:** real MT5/Deriv-Demo XAUUSD M5, 2011-01-02 → 2026-09-04,
  1,094,386 bars (15.67 years), with the broker's **real per-bar spread**.
- **Costs:** corrected — zero commission (Deriv prices these CFDs
  spread-only), real recorded spread charged on **both** entry and exit,
  ATR-scaled slippage. The prior model's fabricated costs consumed ~68% of
  the per-trade risk budget and invalidated everything produced under it.
- **Search space:** 3 payoff shapes (2:2, 2:1.5, 1:2 stop:target ATR) × 3
  VWAP-stretch selectivity filters (`min_vwap_dist_atr` ∈ {0.0, 0.5, 1.0}
  — the mechanical stand-in for the docs' deviation-band concept) = 9
  combinations.
- **Protocol:** 13 rolling windows, 2y in-sample → 1y out-of-sample.
  Parameters chosen on in-sample data **only**, scored by expectancy in R
  units, then applied unchanged to the next year. Minimum 30 in-sample
  trades to be selectable.

## Headline: the cost fix changed the picture substantially

Default parameters, full history:

| Metric | Broken cost model | **Corrected cost model** |
|---|---|---|
| Sharpe | -4.07 | **-0.71** |
| Total return | -71.8% | **-35.7%** |
| Win rate | 43.6% | **48.8%** |
| Max drawdown | — | -42.5% |
| Expectancy (R) | — | **-0.090 R/trade** |

Decomposition: `avg_win = +0.93R`, `avg_loss = -1.06R` — friction costs
~0.13R per round trip. At a 48.8% win rate a *frictionless* version would
be ≈ -0.025R, so **the signal itself is only slightly negative and friction
supplies most of the loss.** This is far closer to viable than ORB, and
far closer than the voided -71.8% figure implied.

## Walk-forward results

| OOS year | Chosen R:R | Stretch | IS E[R] | OOS E[R] | OOS trades | OOS win rate |
|---|---|---|---|---|---|---|
| 2013 | 2.0:2.0 | 1.0×ATR | +0.173 | **+0.022** | 44 | 54.5% |
| 2014 | 2.0:2.0 | 0.5×ATR | +0.140 | **-0.217** | 56 | 46.4% |
| 2015 | 2.0:2.0 | 1.0×ATR | -0.012 | **-0.277** | 31 | 41.9% |
| 2016 | 2.0:2.0 | 1.0×ATR | -0.149 | **-0.018** | 34 | 52.9% |
| 2017 | 2.0:1.5 | 1.0×ATR | -0.073 | **-0.193** | 19 | 52.6% |
| 2018 | 2.0:1.5 | none | +0.045 | **-0.213** | 60 | 50.0% |
| 2019 | 2.0:1.5 | none | -0.112 | **+0.081** | 60 | 65.0% |
| 2020 | 2.0:2.0 | 1.0×ATR | +0.076 | **-0.138** | 18 | 44.4% |
| 2021 | 2.0:2.0 | 0.5×ATR | +0.195 | **+0.073** | 42 | 54.8% |
| 2022 | 2.0:2.0 | 0.5×ATR | +0.020 | **-0.076** | 34 | 47.1% |
| 2023 | 2.0:2.0 | 0.5×ATR | +0.006 | **-0.302** | 38 | 36.8% |
| 2024 | 2.0:1.5 | none | -0.120 | **-0.100** | 57 | 52.6% |
| 2025 | 1.0:2.0 | 0.5×ATR | -0.091 | **-0.222** | 82 | 26.8% |

**Aggregate out-of-sample (575 trades):**
- Windows with positive OOS edge: **3 / 13**
- Mean OOS expectancy: **-0.121 R per trade**
- Mean OOS win rate: 48.2%
- Mean OOS R-normalized Sharpe: **-0.786**

## The decisive diagnostic: in-sample selection predicts nothing

Testing whether choosing parameters in-sample carries **any** information
about out-of-sample performance:

| Strategy | IS→OOS correlation | Mean OOS when IS>0 | Mean OOS when IS≤0 |
|---|---|---|---|
| VWAP+RSI | r = **+0.109** (p=0.72) | **-0.1214 R** (n=7) | **-0.1214 R** (n=6) |
| ORB+Pivots | r = **-0.033** (p=0.91) | -0.1609 R (n=4) | -0.1394 R (n=9) |

For VWAP+RSI the two conditional means are **identical to four decimal
places**: windows where the optimizer found a positive in-sample edge did
exactly as badly out-of-sample as windows where it found a negative one.
The correlation is statistically indistinguishable from zero in both
strategies.

This is the rigorous statement of what the whole project has been circling.
It is not that these signals are worthless in some abstract sense — it is
that **the optimizer cannot tell in advance which parameter set will work**,
because the in-sample differences it is selecting on are noise. Any
"optimized" configuration from this search is therefore expected to
perform at the strategy's unconditional average (~-0.12 R/trade), not at
its flattering in-sample number.

Note this diagnostic is far stronger evidence than a single negative
backtest, and it is also what invalidates the obvious next move: running a
bigger parameter search. A larger grid searched on the same noise would
produce better in-sample numbers and the same out-of-sample expectation.

## Conclusion

**VWAP+RSI is not profitable on XAUUSD M5 out-of-sample.** It is
meaningfully closer to breakeven than ORB (-0.121 R vs -0.146 R per trade;
Sharpe -0.71 vs -2.07 at default parameters), and most of its loss is
friction rather than signal — but it is still negative, and the
walk-forward evidence shows optimization cannot fix that.

Honest next steps would be genuinely new hypotheses, not further search:
- **Lower-friction execution** is the highest-leverage change, since
  friction (~0.13R/round trip) exceeds the signal's own deficit (~0.025R).
  A higher timeframe (M15/H1) would amortize the same spread over larger
  ATR-scaled stops.
- A different instrument (the other four are already downloaded).
- A different session anchor or a fundamentally different signal.

Raw data: `reports/xauusd_vwap_rsi_selectivity_wfo_results.json`,
`reports/vwap_selectivity_wfo_log.txt`.
