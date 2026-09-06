# Final candidates — all three fail. The book is closed.

Three configurations from the 45-cell ceiling sweep were positive at zero cost and had never
faced the placebo or cross-sectional controls. This is that test.

## Gate A+B — real costs and random-entry placebo (original asset)

| Candidate | Asset | TF | n | PF | E[R] real | Placebo | z |
|---|---|---|---|---|---|---|---|
| ORB vol2× | XAUUSD | H1 | 303 | 1.159 | **+0.0766** | −0.0429 | **+2.04** |
| ORB vol2× | BTCUSD | H1 | 191 | 1.159 | +0.0726 | −0.0274 | +1.28 |
| VWAP+RSI p10 | BTCUSD | M15 | 226 | 1.190 | +0.0914 | −0.0332 | +1.83 |

All three stayed positive after real costs. Two cleared the single-test placebo threshold
(z>1.645) — the **first things in this project to beat a random-entry control**. None cleared
Bonferroni across the three (z>2.39).

## Gate D — rolling windows

| Candidate | Overlapping | Non-overlapping |
|---|---|---|
| ORB XAUUSD H1 | 8/13 | **3/5** (mean E[R] +0.070) |
| ORB BTCUSD H1 | 2/4 | 1/2 |
| VWAP+RSI BTCUSD M15 | 2/2 | 1/1 |

Only the XAUUSD candidate has enough windows to say anything; the other two are too sparse to
count as evidence in either direction.

## Gate C — cross-sectional replication: FAIL, decisively

The same fixed configuration, unchanged, on crypto pairs that played no part in selecting it.

**ORB vol2× on H1 — 33 unseen pairs**

| | |
|---|---|
| Positive E[R] | **9/33 (27%)** |
| Median E[R] | **−0.0801** |
| IQR | −0.2228 to +0.0039 |
| Original asset (BTCUSD) | **94th percentile** |
| Effective sample | **26.6 of 33 (ρ=0.01)** |

**VWAP+RSI p10 on M15 — 34 unseen pairs**

| | |
|---|---|
| Positive E[R] | **1/34 (3%)** |
| Median E[R] | **−0.1770** |
| IQR | −0.4044 to −0.0953 |
| Original asset (BTCUSD) | **100th percentile — the single best of 35** |
| Effective sample | **34.0 of 34 (ρ=−0.01)** |

The losers are severe, not marginal: TRUUSD −4.58 and XTZUSD −1.76 on ORB; TRUUSD −15.75 and
XTZUSD −3.79 on VWAP+RSI.

## Why this test is stronger than the overlay's cross-section

When the risk overlay was tested cross-sectionally, ρ=0.36 collapsed 26 assets into ~2.6
effective observations, so even that result was weakly powered. **Here ρ≈0.01 and the
effective sample is essentially the full 26–34.** The reason is structural: the overlay holds
continuous positions whose daily returns are dominated by a common crypto factor, whereas
these strategies take sparse, asynchronous trades, so their per-trade R-multiples are close to
independent across assets.

So this is not a weak test that happened to fail. It is roughly 30 genuinely independent
observations, and they say no.

## The XAUUSD candidate

ORB vol2× on XAUUSD is the only one not directly killed: it cleared the placebo (z=+2.04),
stayed positive after costs (+0.077R over 303 trades), and won 3 of 5 non-overlapping windows.
It has **no comparable cross-section** — silver already failed and oil has 2.6 years — so it
cannot be validated the way the crypto candidates were.

But the indirect evidence is damning. **The identical rule was just tested on 33 other assets
and worked on 9 of them (27%).** A rule that produces a positive result on roughly a quarter
of assets by chance will produce one on XAUUSD about a quarter of the time. XAUUSD is one more
draw from a distribution whose median is −0.08. Its z=+2.04, uncorrected and selected from 45
cells, is exactly the kind of result this project has repeatedly shown to evaporate.

**Verdict: not tradeable.** Not disproven in isolation, but unsupported, and the family it
belongs to has been falsified.

## Decision

Per the pre-registered rule — **fails Gate C, so the book is closed.** No paper trading, no
further parameter work.

The pattern across the whole project is now consistent and, in hindsight, predictable: every
configuration that looked good was the best of a set, and every time it was replicated on data
that had no hand in choosing it, it reverted to the population median — which is negative
after costs.

Raw data: `final_candidates_results.json`, `final_candidates_test.py`.
