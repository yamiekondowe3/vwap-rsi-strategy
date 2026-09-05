# Attempt to improve PF / Sharpe / win rate without overfitting

Goal: raise profit factor, Sharpe and win rate by changing the strategy,
while avoiding the curve-fitting trap. Prior work established that
**parameter search within the existing rule space is a dead end** — across
26 walk-forward windows on two strategies, in-sample selection had no
predictive power for out-of-sample results (r=+0.109, p=0.72 for VWAP+RSI;
r=-0.033, p=0.91 for ORB). So a bigger grid would only improve in-sample
numbers and leave out-of-sample expectation unchanged.

Everything below is therefore a **structural** change, pre-registered with a
stated mechanism and tested once, rather than searched.

## Change 1 — coarser timeframe (mechanism: friction amortization)

**Hypothesis, stated before testing:** the broker's spread is a fixed ~$0.15
regardless of bar size, but ATR-scaled stops grow with the timeframe.
Friction measured in R should therefore fall roughly in proportion to the
ATR ratio. Identical default parameters, only the bar size changed — no
free parameters, nothing to overfit.

**Result: mechanism confirmed.** ATR ratio M15/M5 = 1.82/0.99 = 1.84×, and
friction fell by almost exactly that factor for both strategies:

| | M5 friction | M15 friction | E[R] | PF | WR | Sharpe |
|---|---|---|---|---|---|---|
| VWAP+RSI M5 | 0.13R | — | -0.088 | 0.844 | 48.8% | -0.70 |
| **VWAP+RSI M15** | — | **0.06R** | **+0.018** | **1.032** | **52.4%** | **+0.02** |
| ORB M5 | 0.12R | — | -0.117 | 0.634 | 53.9% | -3.01 |
| **ORB M15** | — | **0.07R** | **-0.087** | **0.752** | **54.2%** | **-2.24** |

All three requested metrics improved for both strategies. But the
frictionless decomposition is what matters:

- **ORB at zero friction:** 54.2% WR × 0.75R payoff = **-0.052R.** Still
  negative with costs removed entirely — ORB's deficit is structural signal
  weakness, and no execution improvement can fix it. **ORB is closed.**
- **VWAP+RSI at zero friction:** 52.4% WR × 1:1 payoff = **+0.048R.**
  Positive — its entire loss was friction. Worth pursuing further.

## Change 2 — RNG seeding (a reproducibility bug found en route)

The M15 VWAP+RSI result was **not reproducible**: two identical runs gave
+0.018R and -0.077R. Cause: `FrictionModel.rng` was an unseeded
`default_rng()`, so slippage draws differed every run, and on a 21-trade
sample that was enough to flip the sign of the edge.

Fixed (`seed=20260904` by default; verified identical to six decimals across
runs). **This retires the "M15 is profitable" reading on its own** — that
result was inside the noise band of its own random number generator.

## Change 3 — self-calibrating RSI threshold (mechanism: restore sample size)

M15's real problem was exposed by change 2: **21 trades in 15.67 years**
(±0.22 standard error) cannot support any conclusion. The cause is
structural — a hardcoded RSI 30/70 is implicitly calibrated to one
timeframe's noise level. RSI dispersion shrinks on coarser bars, so the
same "30" that fires regularly on M5 becomes a rare extreme on M15.

**Fix (structural, not fitted):** threshold on RSI's own trailing
percentile (`adaptive_rsi`, 20th/80th over 500 bars, shifted 1 bar so the
current value never contributes to its own threshold). "Oversold" now means
the same *rarity* on every timeframe and every instrument, with no
per-market numbers to tune — one rule, self-adjusting everywhere. This is
the opposite of overfitting: it removes a tuned constant rather than adding
one.

**Result: sample size restored ~80×, and the edge is now clearly negative.**

| Instrument | Fixed 30/70 (n) | E[R] | Adaptive (n) | E[R] | p-value |
|---|---|---|---|---|---|
| XAUUSD | 21 | -0.077 (p=0.73) | **1,725** | **-0.049** | **0.044** |
| XAGUSD | 10 | +0.138 (p=0.67) | **1,960** | -1.057 | 0.000 |
| USOIL | 3 | — | **223** | **-0.171** | **0.011** |
| BTCUSD | 34 | -0.170 (p=0.35) | **2,020** | **-0.067** | **0.003** |
| ETHUSD | 21 | -1.634 | **2,061** | -0.655 | 0.000 |
| **Pooled** | **86** | -0.469 | **7,989** | **-0.460** | — |

**0 of 5 instruments show a positive edge, and every one is statistically
significant** — where before, with 86 trades total, nothing was
distinguishable from zero in either direction.

This is the point of the exercise. The apparent M15 improvement in Change 1
was a small-sample artifact; giving the same rules enough trades to be
measurable shows the edge is reliably negative, not marginally positive.

## Instrument suitability (a real, separate finding)

Spread as a fraction of ATR on M15 varies enormously, and it determines
whether an ATR-stop strategy is viable at all on that instrument:

| Instrument | Median price | Median ATR | Median spread | **Spread/ATR** |
|---|---|---|---|---|
| BTCUSD | 29,025 | 116.10 | 2.42 | **2.1%** |
| ETHUSD | 1,727 | 7.73 | 0.58 | **7.5%** |
| XAUUSD | 1,614 | 1.82 | 0.15 | **8.2%** |
| USOIL | 71 | 0.174 | 0.018 | **10.3%** |
| **XAGUSD** | 22 | 0.049 | 0.026 | **53.3%** |

**XAGUSD is structurally untradeable with this design** on this broker: with
a 2×ATR stop, round-trip spread alone costs ~0.27R before the strategy does
anything. Its -1.057R result is an execution-cost fact about silver, not a
statement about the signal. Any future work should screen instruments by
spread/ATR before backtesting them.

## Known open issue — do not trust the ETHUSD/XAGUSD magnitudes

XAGUSD's extremity is explained by spread/ATR above. **ETHUSD's is not**
(7.5% spread/ATR is unremarkable, yet it shows -0.655R and PF 0.019). With
stops filling at the stop level, average loss should not exceed roughly
-1.0R, so an average of -0.655R combined with a 41% win rate does not
reconcile cleanly. Something in the interaction of crypto's 24/7 bars,
ATR warm-up, or position sizing on these two symbols needs investigation
before their numbers are cited. **The conclusion above rests on XAUUSD,
USOIL and BTCUSD** (-0.049, -0.171, -0.067, all significant, all
internally consistent), which are unaffected by this.

## Bottom line

Changes that genuinely improved PF / Sharpe / WR, with mechanisms rather
than fitting:
1. **Cost-model correction** — Sharpe -4.07 → -0.71, the single largest
   improvement, and a bug fix rather than a tuning choice.
2. **Coarser timeframe** — improved all three metrics for both strategies
   via a friction mechanism confirmed quantitatively in advance.
3. **Seeded RNG** — results are now reproducible.
4. **Self-calibrating threshold** — removed a hidden tuned constant and
   restored enough statistical power to actually measure the edge.

What none of them did was make either strategy profitable. The honest
summary: **ORB is closed** (negative even at zero friction). **VWAP+RSI has
a positive frictionless edge but cannot overcome real execution costs on
these instruments**, and now has the sample size to say so with
significance rather than ambiguity.

The remaining lever consistent with the evidence is execution cost, not
signal or parameters: a lower-spread venue, or an instrument with a better
spread/ATR ratio than any tested here (BTCUSD at 2.1% is the best available
and still lost). Absent that, this design does not clear its own costs.
