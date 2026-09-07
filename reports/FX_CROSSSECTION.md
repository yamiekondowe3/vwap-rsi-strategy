# FX cross-section — the last candidate falls. Definitively closed.

The ORB/XAUUSD candidate was the only survivor of the entire project: +0.077R over 303
trades, PF 1.159, placebo z=+2.04, 3/5 non-overlapping windows positive. Its one untested
weakness was that it had never been replicated on a peer group — crypto was the wrong
comparison, because an opening-range breakout is defined by a *session open* and crypto trades
24/7 with no real open.

FX is ORB's natural home and gold trades like FX: session-driven, 24/5, same London/NY
structure. This is that test — 21 liquid majors and crosses at H1, identical configuration,
9.7 years each.

## Result

| | |
|---|---|
| FX pairs tested | 21 |
| Positive E[R] | **1/21 (5%)** |
| **XAUUSD's rank** | **100th percentile — the single best of 22** |
| Average pairwise ρ | 0.15 |
| Effective sample | 5.1 of 21 |

The only other positive pair was CHFJPY (+0.055). Every other pair lost.

Win rate is the robust statistic for comparison (see the sizing note below): **XAUUSD 54.5%**
against an FX median near 40%, with the comparable JPY crosses at 41–47%.

**A rule that is positive on 5% of session-driven assets will produce a positive XAUUSD draw
about 5% of the time. One draw at the 100th percentile of its peer group is what selection
looks like, not what an edge looks like.** This is the fourth time in this project that the
same pattern has appeared — ETHUSD at the 96th percentile of crypto, ORB/BTCUSD at the 94th,
VWAP+RSI/BTCUSD at the 100th, and now ORB/XAUUSD at the 100th of FX.

## An unrelated real defect the test exposed

Several FX pairs showed extreme losses (EURUSD −18R, EURGBP −21R per trade). These are not a
measurement artifact — they are a **genuine flaw in the strategy as specified**, and worth
recording:

Position size is `risk_amount / (2 × ATR)`. During quiet hours on FX majors (notably the Asian
session) H1 ATR collapses toward zero while the broker's spread stays at its floor. Size then
explodes, and the fixed spread cost on that oversized position produces a loss of many R even
though the stop is nominally at 1R. **There is no minimum-ATR guard anywhere in either
engine.**

XAUUSD is spared only because gold's ATR never collapses that far relative to its spread
(median spread/ATR 3.9%, and its ATR floor stays well above the spread). This is a latent
blow-up risk that would have been live in any deployment on a lower-volatility instrument, and
it is exactly the kind of defect that only appears when you run a rule across a wide universe
rather than on the one asset it was tuned to.

## Verdict: closed

**Every candidate in this project has now been falsified on data that played no part in
selecting it.** There is no strategy, on any asset, at any timeframe, with any exit or filter
tested, that survives controlled validation.

The XAUUSD ORB candidate is no longer an open question. It cleared the placebo and held across
its own rolling windows — and it still fails, because those tests re-examine the asset that was
chosen for being best. Only replication on an unselected peer group settles it, and it did.

Raw data: `fx_crosssection_results.json`, `fx_crosssection_test.py`.

## Operational note

Running this test made MT5 cache ~21GB of price history server-side and filled the disk. The
cache was cleared back to the five project instruments (19GB recovered) and the test was
re-scoped to 21 pairs at H1 only. Anyone re-running a wide-universe test on an MT5 account
should watch `bases/<server>/history`, not just their own data directory — the terminal's cache
grows independently and silently.
