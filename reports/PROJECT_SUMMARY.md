# Project summary — what was tested, what failed, and what is worth keeping

Authoritative record. Supersedes the individual reports, several of which carry retraction
banners because their conclusions were later overturned by better tests. Where they disagree
with this document, this document is correct.

## The question

Can VWAP+RSI or ORB+Pivots be made into a tradeable strategy on XAUUSD, XAGUSD, USOIL,
BTCUSD or ETHUSD, using a Deriv MT5 retail CFD account?

## The answer

**No.** No strategy, on any asset, at any timeframe, with any exit or filter tested, survived
controlled validation. The only evidence-backed position produced by this work is: **hold the
asset and overlay nothing** — buy-and-hold beat everything built here.

## What was tested

| # | Test | Result |
|---|---|---|
| 1 | VWAP+RSI, default params, 15.7y real XAUUSD | −71.8%, Sharpe −4.07 |
| 2 | Walk-forward, 13 windows, in-sample selection | 2/13 OOS-positive; **IS→OOS correlation r=+0.109, p=0.72** |
| 3 | ORB+Pivots baseline + pivot filter + volume filter | All wipe out; frictionless still −0.052R |
| 4 | R:R sweep (1:2, 2:1.5, 1.5:1, 2:1) | All negative |
| 5 | **Cost-model bug found** | Fabricated costs were eating 68% of per-trade risk; everything above re-run |
| 6 | Frictionless ceiling test, 45 configs | 0/45 reach the required win rate with costs removed entirely |
| 7 | Asymmetric exits (trail, scale-out, breakeven, timed) | Reached **PF 1.325** — but placebo improved just as much |
| 8 | Session filters (London/NY opens) | NY open improved **5/5** configs — but **0/18** beat the placebo |
| 9 | Volatility-regime filter | Hurt in 4/5 cases — contradicts the source research |
| 10 | Risk overlay (trend gate × vol target) | Looked strong on ETHUSD: 8/8 rolling windows |
| 11 | Overlay cross-section, 26 crypto pairs | **6/26 improve; median worse.** ETH was a best-of-5 artifact (P=0.33) |
| 12 | Final 3 candidates, full control stack | 2 cleared the placebo; **both failed cross-sectional replication** (27% and 3% positive) |

## The single lesson

**Every promising result was the best of a set, and every one reverted to the population
median when replicated on data that had no part in choosing it.**

- ETHUSD overlay: 96th percentile of 26 assets; P(best-of-5 ≥ it) = 0.33
- ORB vol2× BTCUSD: 94th percentile of 33 assets; population median −0.080
- VWAP+RSI p10 BTCUSD: **100th percentile of 35 assets**; population median −0.177

Rolling out-of-sample windows do **not** catch this. The ETH overlay won 8 of 8 windows and
was still an artifact, because those windows re-tested the very asset that had been chosen for
being best. Only replication on unselected data exposes it.

## Genuine findings worth keeping

1. **Instrument screening by spread/ATR.** Ranges from 2.1% (BTCUSD M15) to **53% (XAGUSD)**.
   Silver is structurally untradeable with ATR-based stops on this broker — round-trip spread
   alone costs ~0.27R. Screen on this ratio before backtesting anything.
2. **The New York open (12:00–16:00 UTC) is materially better to trade** than the rest of the
   day, consistently across two unrelated strategies and three instruments (5/5). It is a
   market-structure fact, not an edge — it helps random entries equally.
3. **Friction scales predictably with timeframe.** ATR ratio M5→M15 of 1.84× moved friction
   0.13R → 0.06R, exactly as predicted. Useful for sizing cost expectations in advance.
4. **The volatility-regime filter is harmful here**, contradicting the source research's
   implication that high-volatility regimes are where these strategies earn.
5. **ORB on BTCUSD contains real information** — it beat random entry at z=4.2–4.8, surviving
   Bonferroni. The information is genuine and simply smaller than the cost of acting on it.

## The durable asset: the validation harness

The reason this project reached a correct negative instead of a plausible false positive is
the control stack, built incrementally as each earlier method proved insufficient:

| Control | What it catches | Where it lives |
|---|---|---|
| Broker-calibrated cost model | Fabricated costs (this bug invalidated a full round) | `common/costs.py` |
| Seeded RNG | Irreproducible results — two runs once disagreed on the *sign* | `common/costs.py` |
| R-normalised metrics | Path-contaminated dollar expectancy | `common/metrics.py` |
| Frictionless ceiling test | Ideas that cannot work even at zero cost — kills them in one pass | `ceiling_test.py` |
| Random-entry placebo | Exit/drift harvesting masquerading as signal | `common/placebo.py` |
| Vol-matched benchmark | "Lower drawdown" that is just lower exposure | `common/portfolio.py` |
| Cross-sectional replication | **Selection bias — the one that caught everything** | `crosssection_test.py` |
| Effective sample size | Correlated assets inflating apparent evidence | `common/portfolio.py` |
| Block bootstrap | CIs that ignore volatility clustering | `common/portfolio.py` |
| No-free-lunch sanity checks | A harness that flatters itself | `tests_exits.py`, `tests_portfolio.py` |

Recommended order for any future idea, cheapest-first: **ceiling test → placebo → vol-matched
benchmark → cross-sectional replication.** Most ideas die at step one, in about an hour.

## If the work continues

Price-derived signals on retail CFD execution have been explored thoroughly here and the
answer was no. Genuine remaining directions, all substantial new projects rather than
refinements:

- **An information edge** rather than a price-pattern edge — funding rates, order-flow, on-chain
  or positioning data. Requires data sources beyond the broker.
- **A different market role** — earning the spread rather than paying it. The ORB/BTCUSD
  finding (real information, smaller than costs) is precisely the profile that flips when you
  are the one collecting the spread. Needs exchange infrastructure, not a CFD account.
- **Nothing.** Buy-and-hold beat every strategy tested here, on every instrument with a
  meaningful sample. That is a legitimate conclusion, not a failure to find one.

## Repository state

Two repos, ~50 passing tests, 15.7 years of real broker data for 5 instruments plus ~33 crypto
pairs, dual Python/MQL5 implementations, and a read-only MT5 monitor. Every negative result is
documented with its raw data. Reports that were later overturned carry retraction banners
rather than being deleted, so the reasoning trail stays intact.
