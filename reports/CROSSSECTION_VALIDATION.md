# Cross-sectional validation — the overlay does not generalise

**This retracts the recommendation in `INSTRUMENT_SELECTION.md`.** I recommended trading
ETHUSD with the risk overlay on the strength of an 8/8 rolling-window result. Testing the
identical, unchanged rule across the broker's whole crypto universe shows that result was a
selection artifact. **ETHUSD should not be traded on this basis.**

## Method

The overlay (200d trend gate × 15% vol target, weekly rebalance) has **no fitted
parameters**, so every crypto pair the project had never examined is a free, genuine
out-of-sample test. 26 pairs with ≥3 years of daily history, identical rule, compared against
volatility-matched buy-and-hold — the same control used throughout.

A synthetic control ran first: on driftless random walks the overlay improved Sharpe in only
**3%** of assets. So the harness is conservative — the trend gate's whipsaw cost makes it
*lose* when there is no trend to capture. It is not a harness that flatters itself.

## Result: Gate 1 FAILS

| Measure | Result |
|---|---|
| Assets tested | 26 |
| Sharpe improved | **10/26 (38%)** |
| Drawdown improved | **8/26 (31%)** |
| **Both improved** | **6/26 (23%)** |
| Median ΔSharpe | **−0.139** (IQR −0.268 to +0.079) |
| Median ΔDD | **−3.2 pt** (IQR −10.5 to +0.7) |

**The median crypto asset is made worse by the overlay**, on both measures. The losers are
not marginal: XTZUSD −0.780 Sharpe, UNIUSD −0.772, XMRUSD −0.499 (and −35.4pt drawdown),
ZECUSD −0.498, APEUSD −0.428.

## ETHUSD was exactly what best-of-5 selection produces

ETHUSD's ΔSharpe of +0.208 sits at the **96th percentile** of the 26-asset distribution. We
originally chose it as the best of five assets tested (gold, silver, oil, BTC, ETH):

| | |
|---|---|
| P(a single random asset ≥ ETH's result) | 0.08 |
| **P(best of 5 random assets ≥ ETH's result)** | **0.33** |

A one-in-three chance. Picking the best of five candidates from this distribution routinely
produces a result as good as ETH's. The 8/8 rolling windows did not catch this because they
re-tested *the same asset that was chosen for being good* — rolling windows check regime
stability, not selection bias. That was the gap, and it is exactly why the cross-section was
the right next test.

## Statistical power was never there

- Average pairwise correlation across the universe: **ρ = 0.36**
- **Effective sample size: 2.6 independent observations**, not 26

Even had the cross-section looked good, 26 correlated crypto pairs are worth under three
independent tests. And the aggregate is not significant: an equal-weight portfolio of all 26
overlay sleeves has Sharpe +0.54 with a **block-bootstrap 95% CI of [−0.70, +1.48]** — it
comfortably contains zero. (Block bootstrap, not i.i.d., because volatility clustering is
precisely the structure this strategy trades.)

## What is genuinely true, stated carefully

**The mechanism is not nothing.** On pure noise it helped 3% of assets; on real crypto it
helped 38%. Trend-following plus vol targeting does capture something real about trending,
volatility-clustering assets. It is simply **not enough to beat holding a smaller static
position** — which is what the vol-matched benchmark represents.

**The drawdown reduction versus raw buy-and-hold is real but trivial.** Across the universe
the overlay cut max drawdown from typically −70% to −98% down to −16% to −53%. That looks
spectacular and means almost nothing: it is achieved by holding roughly a fifth of the
exposure. A static 20% position achieves the same thing without any rule. That is exactly
what the vol-matched control was built to expose, and it does.

## Verdict

**Do not trade the overlay on ETHUSD or anything else.** Per the pre-registered gate, work
stops here — the robustness surface and leverage frontier planned as Phases 3 and 4 are not
worth running against a rule that fails to generalise.

The honest summary of this project: every strategy examined — VWAP+RSI, ORB+Pivots, and the
risk overlay — has now failed a properly controlled test. Two failed against a random-entry
placebo; this one failed against a volatility-matched benchmark and cross-sectional
replication.

## The part that did work

The controls caught a false positive that a conventional backtest would have taken to live
capital. The ETH result had everything a retail process looks for — 8/8 out-of-sample
windows, survives 10× costs, a plausible economic mechanism, Bonferroni-surviving
significance on a sibling asset — and it was still selection noise. What exposed it was
cheap: run the same fixed rule on assets nobody chose.

That sequence — **frictionless ceiling test → random-entry placebo → vol-matched benchmark →
cross-sectional replication → effective sample size** — is the durable output of this work,
and it is worth more than any of the strategies it rejected.

Raw data: `crosssection_results.json`, `crosssection_test.py`.
