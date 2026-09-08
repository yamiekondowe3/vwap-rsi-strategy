# Information edge — funding, order flow, positioning

The last untested hypothesis: that a different *kind* of input might carry information price
history does not. Three directions requested; two were testable.

## Positioning: not testable, and I will not fake it

- **CFTC Commitment of Traders** — every endpoint returns HTTP 403 from this network.
- **Binance open interest / long-short ratios** — the crypto analogue, but Binance retains
  only **~20 days**. We established ~1,500 trades are needed to establish a +0.05R edge.

Twenty days cannot answer the question. Reported as untested rather than dressed up.

## Data actually used

24 Binance USDT perpetuals, 8-hour bars (funding's native cadence), 5–9 years each,
~7,000 funding records per symbol. Costs modelled as **Binance taker fees (4bp/side)** rather
than Deriv CFD spreads — a materially cheaper venue, which matters because the previous
strategy failed by 0.008R.

Two fetch bugs were found and fixed en route, both of which silently truncated history:
`fundingRate` caps at 500 rows per call regardless of `limit`, and it **ignores
`startTime=0`**, returning only the most recent 500. Uncaught, either would have given ~5
months of funding data instead of 7 years.

## Stage 1–2: majors, frictionless then with real costs

| Symbol | Signal | n | WR | PF | E[R] (real costs) | Placebo z |
|---|---|---|---|---|---|---|
| BTCUSDT | funding_fade | 392 | 48.7% | 0.928 | −0.0347 | +0.19 |
| BTCUSDT | **of_momentum** | 550 | 53.5% | 1.116 | **+0.0599** | +1.36 |
| BTCUSDT | of_fade | 554 | 44.6% | 0.777 | −0.1175 | −1.47 |
| ETHUSDT | funding_fade | 412 | 47.8% | 0.900 | −0.0507 | −0.38 |
| ETHUSDT | **of_momentum** | 521 | 52.6% | 1.095 | **+0.0452** | +1.27 |
| ETHUSDT | of_fade | 523 | 47.0% | 0.881 | −0.0659 | −0.61 |

**The funding/crowding hypothesis fails outright** — negative on both majors even at zero
cost. Extreme funding does not predict reversal at this horizon.

**Order-flow momentum survives real costs on both majors.** Aggressive-buyer dominance
persists rather than exhausting; the fade version is its exact mirror, which is a useful
internal consistency check.

## Stage 3: cross-section — the best result this project has produced, and still not enough

| Signal | Positive | Median E[R] | Effective N |
|---|---|---|---|
| funding_fade | 4/24 (17%) | −0.0318 | 24.0 |
| **of_momentum** | **12/24 (50%)** | **+0.0008** | 22.9 |
| of_fade | 2/24 (8%) | −0.0414 | 21.8 |

ρ ≈ 0.00, so these are ~23 genuinely independent observations — real statistical power, unlike
the risk-overlay cross-section where ρ=0.36 collapsed 26 assets into 2.6.

**Order-flow momentum is the first signal in this entire project whose cross-sectional median
is not negative.** Everything before it — VWAP, ORB, pivots, the risk overlay, every exit and
filter — had a clearly negative median. This one is *neutral*.

But neutral is not tradeable: mean E[R] +0.0083, **t=0.80, p=0.43 — not distinguishable from
zero**, and 12/24 positive is a coin flip.

## The one structurally interesting finding, and why it died

Performance was strongly related to market liquidity — **Spearman(liquidity, E[R]) = +0.569,
p = 0.004** across all 24 assets. That is a *shape* test over the whole cross-section, not a
cherry-picked subset, and it has a coherent mechanism identified in the source research:
taker-volume imbalance measures real aggressive flow, and crypto volume is heavily
wash-traded (Bitwise: ~95% of reported BTC volume fake; Cong et al.: >70% on unregulated
venues). The signal should work where the measurement is real and fail where it is noise —
which is exactly the observed pattern.

That was genuinely different from the five earlier false positives, which were all "one asset
looked good." So it got its own out-of-sample test — a time split it did not choose:

| Period | Spearman(liquidity, E[R]) | p |
|---|---|---|
| First half (→2022) | +0.484 | **0.016** |
| Second half (2023→) | +0.029 | **0.894** |

**The relationship is present in one half and completely absent in the other.** It is
period-specific, not structural. Had I stopped at the p=0.004 headline — which was tempting,
because the mechanism was plausible and pre-identifiable — this would have become the sixth
false positive.

## Verdict

**Best of the three: order-flow momentum.** It is the only signal in this project to reach a
non-negative cross-sectional median, it survives real exchange fees on the majors, and it has
a coherent mechanism. It is still not tradeable: indistinguishable from zero across the
cross-section, and its one distinguishing structure fails out-of-time.

Ranking, honestly: **order flow momentum (neutral) > funding/crowding (negative) > order flow
fade (negative) > positioning (untestable)**.

The information-edge hypothesis is not refuted in general — taker-volume imbalance is a crude
proxy for order flow, and real order-book or trade-level data on a quality venue is a
different and untested thing. But the cheap version of it, on free data, does not produce a
tradeable edge.

Raw data: `info_edge_results.json`, `info_edge_test.py`, `fetch_binance_info.py`.
