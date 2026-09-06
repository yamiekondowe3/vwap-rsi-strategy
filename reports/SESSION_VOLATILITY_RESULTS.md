# Session and volatility-regime filters — results

Exit held fixed at the best mechanism from the prior test (E1_trail: 2×ATR stop, no
target, 3×ATR chandelier trail), H1, so that only the filter varies. Session windows are
UTC and deliberately widened to 4 hours to span both DST regimes — London is UTC+0/+1 and
New York UTC−5/−4, so "08:00 local" drifts by an hour across the year.

Two questions were measured separately, because they are not the same question:
- **Q1 (absolute):** does filtering beat trading unfiltered?
- **Q2 (signal):** does the signal still beat *random entries drawn from the same filtered
  bars*?

## Q1 — the NY open filter genuinely works

| Filter | Mean ΔE[R] vs unfiltered | Improved | Mean PF |
|---|---|---|---|
| **ny_open (12–16 UTC)** | **+0.0428** | **5 / 5** | **1.194** |
| london_ny (union) | +0.0535 | 3 / 5 | 1.217 |
| london_open (07–11 UTC) | −0.0073 | 1 / 3 | 1.024 |
| **vol_regime_p50** | **−0.0933** | **1 / 5** | **0.953** |

**The NY-open filter improved every single configuration it was applied to (5/5)** — a 3.1%
result by chance. It is consistent, economically sensible (NY open is peak liquidity for all
three instruments), and it lifted the headline configuration from PF 1.325 to **PF 1.531**
(XAUUSD VWAP+RSI, payoff 3.32, E[R] +0.305).

**The volatility-regime filter did the opposite of what the research documents implied.**
Restricting to above-median ATR *hurt* in 4 of 5 cases, and was catastrophic for VWAP+RSI on
XAUUSD (PF 1.325 → 0.753, ΔE[R] −0.328). The docs' observation that ORB profits concentrated
in high-volatility years does not translate into "filter for high volatility" — for these
mean-reversion and breakout entries, elevated ATR mostly means wider stops and worse fills.
The one exception was ORB on BTCUSD (PF 1.083, and the highest placebo z in the whole run at
+1.34), which is not enough to rescue the filter.

## Q2 — but none of it is signal

| | Result |
|---|---|
| Filtered configurations tested | 18 |
| Beating the random-entry placebo (z > 1.645) | **0** |
| Expected by chance | 0.9 |
| Bonferroni z threshold | 2.77 |
| Surviving correction | **0** |

**Zero of eighteen.** Random entries confined to the same NY-open bars, with the same
trailing exit and costs, did as well as the strategy's own entries. The session filter is
telling us *when the market is worth trading at all* — it is not evidence that VWAP+RSI or
ORB predicts anything. Note the direction of travel on XAUUSD: adding the NY filter raised
PF from 1.325 to 1.531 while placebo z *fell* from +1.34 to +1.14. Performance went up,
evidence of signal went down.

## The joint gate: nothing passes

| Config | n | PF | Sharpe | Buy & hold | Beats B&H? | Placebo z |
|---|---|---|---|---|---|---|
| VWAP+RSI XAUUSD ny_open | 85 | **1.531** | +0.328 | +0.64 | no | +1.14 |
| VWAP+RSI XAUUSD london_ny | 100 | 1.526 | +0.363 | +0.64 | no | +1.27 |
| VWAP+RSI BTCUSD london_ny | 82 | 1.462 | +0.424 | +1.60 | no | +0.58 |
| ORB BTCUSD ny_open | 2,527 | 1.081 | +0.473 | +1.60 | no | +0.47 |

Four configurations now clear **PF > 1.3** — the target that earlier work called unreachable.
None beats buy-and-hold on a risk-adjusted basis, and none beats its own placebo. The PF
gains come with low trade counts (65–100 trades over 15.7 years, i.e. 4–6 per year), so the
Sharpe stays near 0.3–0.4 regardless of how good the per-trade PF looks.

## What this adds to the picture

**A real, portable finding:** on XAUUSD, USOIL and BTCUSD, the 12:00–16:00 UTC window (the
New York open) is materially better to trade than the rest of the day — consistently, across
two unrelated strategies and three instruments. That is a genuine market-structure result and
it is worth keeping. It applies to *any* strategy on these instruments, including a random
one, which is precisely why it is not a rescue for these two.

**A correction to the source research:** the "trade high-volatility regimes" implication does
not hold here. It was actively harmful in 4 of 5 tests.

**No change to the verdict.** The filters improved *when* we trade, not *what we know*. With
zero of eighteen configurations beating a random-entry control, and buy-and-hold still ahead
on every instrument with a meaningful sample, neither strategy is trade-worthy.

Raw data: `session_volatility_results.json`, `session_volatility_test.py`.
Filters: `common/filters.py` (`named_session_mask`, `volatility_regime_mask`).
