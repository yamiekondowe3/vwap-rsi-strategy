# VWAP without RSI, ORB without pivots — and a project error I should own

Two questions, very different answers.

## "ORB without pivots" — that is what was always tested

`use_pivot_filter` has defaulted to `False` since the engine was written, and **no test script
ever enabled it.** The ceiling test, exit-lever sweep, session/volatility filters, final
candidates and the FX cross-section all ran plain ORB with no pivots. Pivots appeared only as
an add-on in one early run, where they moved E[R] from −0.0476 to −0.0246 and made the
placebo z *worse*.

So this is not an untested configuration — it is the one that has been falsified throughout,
including on 21 FX pairs.

## "VWAP without RSI" — a real gap, and a bigger one than asked

The source research document specifies the entry trigger as:

> *"wait for the first counter-color pullback candle toward VWAP (first red candle in an
> uptrend / first green candle in a downtrend)"*

**This project substituted RSI crossings from the first commit and never implemented the
documented trigger.** "VWAP+RSI" was a variant of my own making; the actual Video-1 strategy
was never tested. That is an error, not a design choice, and it is worth stating plainly.

Three triggers tested, sharing the identical VWAP side + slope filter, on H1 with real costs
and a random-entry placebo:

| Asset | Trigger | n | WR | PF | E[R] | Placebo z |
|---|---|---|---|---|---|---|
| XAUUSD | rsi (mine) | 173 | 48.0% | 0.888 | −0.0555 | −0.10 |
| XAUUSD | **pullback (documented)** | **5,301** | 50.3% | 0.975 | **−0.0078** | **+2.45** |
| XAUUSD | none (pure VWAP) | 7,070 | 50.1% | 0.966 | −0.0121 | +2.41 |
| BTCUSD | rsi (mine) | 132 | 50.8% | 1.012 | +0.0086 | +0.59 |
| BTCUSD | pullback | 3,171 | 50.1% | 0.987 | −0.0036 | +0.94 |
| BTCUSD | **none (pure VWAP)** | **4,124** | 50.7% | 1.009 | **+0.0066** | **+1.71** |

**You were right that RSI was hurting.** It was the weakest trigger on both assets, and it
also starved the sample (132–173 trades against 3,000–7,000), which is why every earlier VWAP
conclusion rested on such thin evidence.

**And the VWAP filter itself contains real directional information.** z = +2.45 on **5,301
trades** is the best-powered signal-versus-random result in this entire project — better than
the ORB/XAUUSD candidate (z=2.04, n=303) and better than anything the risk overlay produced.
The VWAP side+slope filter genuinely predicts better than chance on gold.

## But it still fails, for the same two reasons

**1. It does not clear costs.** XAUUSD pullback is −0.0078R after real spread — essentially
breakeven, but on the wrong side of it. Friction on XAUUSD H1 is ≈0.040R, so frictionless the
edge is roughly +0.032R. The information is real and worth about 3% of risk per trade; the
spread costs 4%.

**2. It fails cross-sectional replication**, exactly as everything else has:

| Trigger | Unseen crypto pairs | Positive | Median E[R] | BTCUSD's rank |
|---|---|---|---|---|
| pullback | 32 | **5/32 (16%)** | −0.0488 | 84th pct |
| none | 33 | **3/33 (9%)** | −0.0656 | 94th pct |

BTCUSD's positive +0.0066 is again a high-percentile draw from a negative-median distribution.
Fifth time this pattern has appeared.

## What this changes, and what it does not

**Changes:** the characterisation. The project's best-supported statement is no longer "these
signals are worthless." It is more precise and more interesting:

> The VWAP side+slope filter carries genuine, well-powered directional information on gold —
> worth roughly +0.03R per trade before costs. The RSI trigger I bolted on was destroying it,
> and the pivots were irrelevant. But +0.03R does not cover a 0.04R spread, and the effect
> does not replicate across unselected assets.

**Does not change:** the verdict. An edge smaller than the spread is not tradeable, and one
that fails cross-sectional replication is not established. Both remain true.

The one thing this genuinely reopens is the execution question. A signal worth +0.03R against
a 0.04R cost is the profile where execution improvement matters — and limit-order entry, which
would *earn* rather than pay the half-spread, was designed but never run (it was gated behind a
Gate 1 that failed). That is a real, bounded, untested lever, and it is the only one left with
a coherent mechanism behind it.

Raw data: `trigger_variants_results.json`, `trigger_variants_test.py`.
