# What would it take to make these strategies trade-worthy?

> **CORRECTION (superseded in part).** This document claimed nothing could help.
> That was wrong on two counts: the 56.5% win-rate bar it derives is only valid at a
> 1:1 payoff, and exits were never tested. Asymmetric exits were subsequently tested
> and reached **PF 1.325** on XAUUSD H1. The overall conclusion still stands -- the
> gain is drift-harvesting that a random-entry placebo captures almost as well, and
> buy-and-hold beats every configuration -- but the reasoning below is incomplete.
> See EXIT_LEVER_RESULTS.md for the corrected analysis.


Scope: **XAUUSD, USOIL, BTCUSD** (XAGUSD and ETHUSD dropped). Both strategies.
Bar: **PF > 1.3 and Sharpe > 1.0.**

Answer, in one line: **we need a signal with real predictive power. These two
are ~50/50 coin flips at scale, and the shortfall is larger than the entire
execution-cost budget, so no amount of tuning, timeframe or order-type work
can close it.**

---

## 1. The requirement, quantified

| Target | What it demands |
|---|---|
| PF > 1.3 (at 1:1 payoff) | **Win rate ≥ 56.5%** net of costs |
| Sharpe > 1.0 | **E[R] ≥ +0.07R** at ~200 trades/yr, **≥ +0.17R** at ~35 trades/yr |
| Provable, not lucky | **≥1,537 trades** to establish a +0.05R edge at 95% confidence |

Break-even win rate required after real friction (1:1 payoff):

| | M5 | M15 | H1 | H4 |
|---|---|---|---|---|
| XAUUSD | 54.8% | 53.1% | 52.0% | 51.5% |
| USOIL | 55.6% | 53.6% | 52.3% | 51.6% |
| BTCUSD | 51.9% | 51.5% | 51.3% | 51.2% |

**The entire friction budget is ~3 win-rate points** (the M5→H4 span). The gap
from what the signals deliver to the bar is ~7 points. That ratio is the whole
story: even flawless execution closes under half of it.

## 2. The ceiling test — the decisive result

45 configurations (2 strategies × 3 instruments × 3 timeframes × 3–4 selectivity
levels) run with **execution costs removed entirely**. Zero cost is the
unreachable best case, so anything that fails here can never be fixed by a
better venue, order type, timeframe or parameter.

**Result: 0 of 45 configurations reach 56.5% win rate with an adequate sample
(≥300 trades).**

- Best frictionless win rate at n≥300: **54.8%** (VWAP+RSI, BTCUSD M15, n=562) —
  **1.7 points short of the bar before paying a single cost.**
- Large-sample configurations cluster at **49–51%** — statistically a coin flip:
  - VWAP+RSI XAUUSD M15, n=1,724 → 50.9%
  - VWAP+RSI BTCUSD M15, n=2,024 → 50.7%
  - ORB XAUUSD M15, n=5,464 → 50.2%
  - ORB XAUUSD H1, n=4,122 → 49.8%
  - ORB BTCUSD M15, n=2,984 → 49.4%

## 3. The apparent winners are exactly what noise looks like

Three cells looked promising (PF 1.21–1.26, p≈0.02–0.05). They do not survive
scrutiny:

| Check | Result |
|---|---|
| Configurations tested | 45 |
| p < 0.05 found | **2** |
| p < 0.05 **expected by chance** | **2.25** |
| Bonferroni threshold | p < 0.00111 |
| Survivors after correction | **0** (best was p=0.023) |

Finding 2 "significant" results from 45 tests when chance predicts 2.25 is not
evidence of an edge — it is the definition of a multiple-comparisons artifact.
This is the same trap that produced the earlier false positives in this project
(the 21-trade M15 result that flipped sign on an unseeded RNG), and it is why
the ceiling test was run before any further optimisation.

Even taken at face value and costed honestly, the best candidates fall short:

| Config | n | Frictionless E[R] | **After friction** | Net PF |
|---|---|---|---|---|
| ORB BTCUSD H1 | 296 | +0.115 | **+0.089R** | **1.19** |
| ORB XAUUSD H1 | 285 | +0.116 | **+0.076R** | **1.16** |
| VWAP+RSI BTCUSD M15 | 562 | +0.096 | **+0.066R** | **1.14** |

All below PF 1.3, none surviving multiple-comparisons correction.

## 4. Selectivity does not concentrate signal — it dilutes it

If real signal lived in the tails, win rate would rise monotonically as entries
tightened. It does the opposite on the largest sample available:

**VWAP+RSI XAUUSD M15 (frictionless):** p20 → **50.9%** (n=1,724); p10 → **48.4%**
(n=345); p5 → **47.0%** (n=83).

Tightening selectivity made it *worse*. The high win rates that appear at extreme
selectivity (61.5% at n=13, 70.0% at n=10, 68.8% at n=16) are small-sample noise,
not concentrated edge. There is no tail to exploit.

## 5. So — what would we actually need?

**A signal that predicts direction better than a coin flip.** Concretely: **+5.6
win-rate points of genuine signal improvement**, on top of perfect execution. For
scale, that is nearly twice the entire friction budget available across every
timeframe.

What will **not** deliver it — all now tested and excluded on this data:
- More parameters or a bigger grid (in-sample selection has zero predictive
  power for out-of-sample: r=+0.109 p=0.72, and r=-0.033 p=0.91)
- More filters (pivot bias, abnormal volume, opening-range width, VWAP stretch)
- Different payoff ratios (1:2, 2:1.5, 1.5:1, 2:1 all tested)
- Coarser timeframes (M15/H1/H4 — helps friction, confirmed mechanism, but the
  friction budget is too small to matter)
- Better execution (limit orders would save ~1.5–3 WR points; the gap is 5.6
  frictionless, so even free execution is insufficient)

What could plausibly deliver it — none of which is a refinement of this work:
- **A different signal class.** VWAP, RSI, opening ranges and pivots are the most
  widely known indicators in retail trading; the source research documents said
  up front that their published edges were fragile and cost-sensitive. That
  prediction has now been confirmed independently on 15.7 years of real data.
- **An information edge** rather than a price-pattern edge — order-flow/book data,
  cross-asset or macro relationships, positioning or funding data.
- **A different market role** — earning spread (market-making) rather than paying
  it, where the ~50% hit rate stops being fatal.

## 6. Recommendation

Do not trade either strategy. Do not invest further effort in tuning them — the
ceiling test shows the destination is unreachable, so the journey is not worth
taking.

The infrastructure built here is sound and reusable for testing a genuinely new
signal: a correct broker-calibrated cost model, deterministic seeded backtests,
no-look-ahead-tested indicators, R-normalized metrics, walk-forward harness with
in-sample-only selection, Monte Carlo, and now a frictionless ceiling test that
can kill a bad idea in one cheap pass instead of ten expensive ones. **That
last piece is the most valuable output of this project** — it should be the first
gate applied to any future strategy, before any optimisation is attempted.

Raw data: `ceiling_test_results.json`, `ceiling_test.py`.
