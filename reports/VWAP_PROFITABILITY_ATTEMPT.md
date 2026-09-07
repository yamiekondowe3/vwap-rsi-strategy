# Making VWAP profitable — every cost lever tested. It closes, then fails anyway.

Starting point: the VWAP side+slope filter with the documented pullback trigger carries a
real edge on XAUUSD H1 — z=+2.45 vs random entry on 5,301 trades, worth roughly +0.032R
before costs against ~0.040R of friction. It lost by about 0.008R. The binding constraint was
cost, and the gap was small, so every lever below attacks cost or exposure with a stated
mechanism.

## Limit-order entry: my hypothesis, and it was wrong

A mean-reversion entry is a natural limit order — rest a bid instead of crossing the spread,
converting the half-spread from cost to saving. Tested with conservative fills (filled only if
price trades through; unfilled setups expire and are counted as trades not taken).

| Entry | n | Fill rate | WR | PF | E[R] |
|---|---|---|---|---|---|
| market (baseline) | 5,301 | 100% | 50.3% | 0.975 | −0.0078 |
| **limit @ close** | 4,692 | 83% | **44.1%** | 0.757 | **−0.1328** |
| limit @ close −0.25×ATR | 4,399 | 71% | 47.0% | 0.858 | −0.0743 |

**Limit entry made it 17× worse.** Adverse selection dwarfs the spread saving: you fill
precisely on the setups that keep going against you, and miss the ones that work immediately.
Win rate fell 6.2 points. This was the lever I thought most promising, and it is dead.

## Every other lever, on XAUUSD H1

| Lever | n | WR | PF | E[R] |
|---|---|---|---|---|
| baseline 2×ATR | 5,301 | 50.3% | 0.975 | −0.0078 |
| wide stop 4×ATR | 1,819 | 50.3% | 0.993 | −0.0007 |
| **wide stop 6×ATR** | 807 | 53.7% | 1.144 | **+0.0686** |
| H4 timeframe | 1,443 | 50.9% | 1.017 | +0.0100 |
| NY session only | 2,274 | 49.9% | 0.956 | −0.0169 |
| long only | 2,979 | 51.5% | 1.031 | +0.0152 |
| short only | 2,835 | 49.6% | 0.952 | −0.0232 |

Wide stops work exactly as the friction mechanism predicts — friction in R is
`cost / (stop_atr × ATR)`, so widening the stop shrinks it mechanically. Combined with
long-only, **XAUUSD reaches E[R] +0.107, PF 1.261, placebo z=+1.65.** Profitable, and it
beats random entry.

## And then it fails, three ways

### 1. It is drift capture, not signal

| Stop | Trades | Avg bars held | Time in market | E[R] |
|---|---|---|---|---|
| 2×ATR | 5,301 | 12 | ~69% | −0.008 |
| 4×ATR | 1,819 | 46 | ~91% | −0.001 |
| 6×ATR | 807 | 110 | ~97% | +0.069 |
| 8×ATR | 421 | **214** | **~98%** | +0.127 |
| 10×ATR | 221 | 400 | ~96% | +0.120 |

Expectancy rises monotonically with holding period, and at 8×ATR the strategy is in the
market **98% of the time**. That is not a strategy that times anything — it is a
buy-and-hold proxy with entry decoration. The "edge" is gold's 15-year uptrend, collected
slowly.

### 2. It badly underperforms simply holding gold

| | CAGR | Sharpe |
|---|---|---|
| **Buy & hold gold** | **+7.5%** | **+0.64** |
| 6×ATR long only | +2.7% | — |
| 8×ATR long only | +2.0% | — |
| 6×ATR both sides | +1.7% | — |

It takes ~97% of the market exposure, adds transaction costs, and delivers **a third of the
return**. Positive expectancy per trade is not the same as a good investment.

### 3. It fails cross-sectional replication — the sixth time

6×ATR long-only across 33 unseen crypto pairs: **11/33 positive (33%), median E[R] −0.0398,
XAUUSD at the 100th percentile.** Best of 34 again.

## Conclusion

Every cost lever was tested. One class of them (wide stops, long-only) does produce positive
expectancy that beats a random-entry placebo — and it does so by converting the strategy into
a worse, more expensive version of buy-and-hold, and it still does not replicate on
unselected assets.

**The deepest finding of this project is that every path to positive expectancy ran through
holding longer, and holding longer is something buy-and-hold does better and for free.** The
VWAP filter's genuine +0.03R of information is real, is well-powered, and is smaller than the
cost of acting on it — and no amount of execution or exit engineering closes a gap that small
without simply turning the strategy into passive exposure.

Raw data: `vwap_profitability_results.json`, `vwap_widestop_results.json`.
