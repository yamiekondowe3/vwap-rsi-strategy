# Exit lever results — you were right to push, and I was wrong

I previously said nothing could help. **That was wrong on two counts**, and testing the
gap changed the picture materially — though not the final answer.

## Correction 1: the win-rate bar was payoff-conditional

I claimed the target needed a 56.5% win rate. That is true only at a **1:1 payoff**, which
was the only thing ever tested. PF > 1.3 needs just 46.4% at a 1.5:1 payoff, or 39.4% at 2:1.

## Correction 2: exits were never tested, and they work

Asymmetric exits changed the payoff profile exactly as predicted:

| Exit | Mean payoff | Mean win rate | Mean PF |
|---|---|---|---|
| E0 fixed 2×ATR stop/target (the only one previously tested) | 0.95 | 50.7% | 0.983 |
| **E1 trailing 3×ATR, no target** | **1.90** | 35.9% | **1.015** |
| E2 scale 50% at 1R + trail | 0.99 | 50.5% | 1.005 |
| **E3 breakeven at 1R + 4×ATR target** | **2.95** | 24.4% | 0.934 |
| E4 timed exit | 0.96 | 50.3% | 0.958 |

And the headline: **VWAP+RSI on XAUUSD H1 with a trailing exit reached PF 1.325**
(win rate 35.5%, payoff 2.44, E[R] +0.185) — clearing the PF > 1.3 bar that I had called
unreachable. So "nothing can help" was simply false.

## But the placebo defeats it

The random-entry control — same trade count, same long/short ratio, same eligible bars,
identical exits and costs — is what settles it. Trailing stops made **random entries
profitable too**:

| XAUUSD VWAP+RSI | Strategy E[R] | Placebo E[R] | z |
|---|---|---|---|
| E0 fixed | −0.0555 | −0.0483 | −0.11 |
| **E1 trailing** | **+0.1849** | **+0.0292** | **+1.34** |

Switching to a trailing exit moved the *placebo* from −0.048 to +0.029. Most of the PF 1.325
is the exit harvesting gold's uptrend, not the signal choosing well. At z = +1.34 the
strategy beat ~91% of random-entry runs — suggestive, but short of the 1.645 threshold, and
far short of the Bonferroni threshold of 2.94 for 30 tests.

## The real finding: there IS signal, it is just smaller than costs

The most interesting result is on BTCUSD, where ORB beats random entry decisively:

| Config | E[R] | PF | placebo z |
|---|---|---|---|
| ORB BTCUSD E4_time | −0.041 | 0.890 | **+4.79** |
| ORB BTCUSD E0_fixed | −0.032 | 0.922 | **+4.23** |
| ORB BTCUSD E2_scale_trail | +0.001 | 0.995 | +2.82 |

z = 4.2–4.8 is not noise — those two survive Bonferroni comfortably. **The ORB signal on
BTCUSD demonstrably contains predictive information.** Random entries with the same exits
average −0.128 R; the signal averages −0.032 R. It is genuinely picking better moments.

**And it still loses money.** The information is real but smaller than the transaction cost
of acting on it. That is a sharper and more useful conclusion than "no edge": the edge exists
and is measurable, it is simply worth less than the spread.

## The joint gate: nothing passes

Only two configurations have **both** positive expectancy and a placebo z > 1.645:

| Config | E[R] | PF | Sharpe | placebo z |
|---|---|---|---|---|
| ORB BTCUSD E2_scale_trail | +0.0009 | 0.995 | +0.014 | +2.82 |
| VWAP+RSI BTCUSD E2_scale_trail | +0.0399 | 1.074 | +0.149 | +1.74 |

Both edges are trivially small (Sharpe 0.014 and 0.149 against a target of 1.0), and neither
survives Bonferroni correction. The configuration with the best economics (XAUUSD E1_trail,
PF 1.325) fails the placebo test; the configurations that pass the placebo test lose money.

## And buy-and-hold beats all of it

| Instrument | Buy & hold Sharpe | Best strategy Sharpe |
|---|---|---|
| XAUUSD | **+0.64** (CAGR +7.5%) | +0.32 |
| BTCUSD | **+1.60** (CAGR +109.4%) | +0.38 |
| USOIL | +0.47 (CAGR +7.7%) | +0.53 ← only apparent win |

The single case where a strategy beats holding is USOIL VWAP+RSI E0_fixed — on **31 trades
over 2.6 years**, with a placebo z of 0.87. That is not a result.

On BTCUSD the comparison is stark: holding returned 109% a year at Sharpe 1.60, while the
best strategy managed Sharpe 0.38. Every hour of this work on BTC has been an elaborate way
to underperform doing nothing.

## Verdict

**Additions that genuinely helped:** trailing and breakeven exits (payoff 0.95 → 1.90–2.95),
which produced the first PF > 1.3 in this project and disproved my earlier claim.

**Why it still fails:** the improvement is drift-harvesting that random entries capture
almost as well; the genuine signal (real, and statistically solid on BTCUSD) is smaller than
transaction costs; and buy-and-hold dominates on a risk-adjusted basis regardless.

**What would actually be needed, now measured rather than asserted:** the BTCUSD ORB signal
is worth roughly +0.10 R per trade relative to random entry, and costs ~0.026 R per round
trip on H1 — yet it still nets negative, because random entry itself is heavily negative on
a volatile instrument. To profit, a signal needs an absolute edge above costs, not merely a
relative edge over random. Nothing tested clears that, and the honest levers are the ones
named before: a different signal class, an information edge, or a market-making role.

Raw data: `exit_lever_results.json`, `exit_lever_test.py`. Machinery: `common/exits.py`,
`common/filters.py`, `common/backtest_core.py`, `common/placebo.py`, `tests_exits.py` (11
tests, including a sanity check that the placebo finds no edge in driftless noise).
