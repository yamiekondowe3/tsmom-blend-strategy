# Independent harness validation, and what it changes

Book B was put through the separate validation harness in `../harness`, which
was written for a different project and knows nothing about this one. That is
the point of using it.

## The headline

**The harness fails Book B, and it is right to, because it measures something
the deployed strategy does not do.** The same underlying question — is the
signal doing anything, or is it drift? — answered inside the deployed framework
comes back strongly positive. Both results are reported here because together
they say something sharper than either alone:

> **Book B's edge is in exposure management — when to be in the market and at
> what size — not in entry timing for discrete, stop-managed trades. Converted
> into the latter, it stops working.**

That is a real limitation on how this strategy may be deployed, and it is worth
more than a clean pass would have been.

## What the harness found

The harness runs discrete trades, one position at a time, ATR stops from a fixed
menu, results in R-multiples at constant risk per trade. Book B holds a
continuous, vol-sized exposure with no stops. The adaptation tested is "Book B
entries, stop-managed" — a variant, not the deployed system.

| Gate | XAUUSD | BTCUSD (corrected costs) |
|---|---|---|
| G1 unseen window (pre-2020) | **PASS** E[R] +0.132, but t=+1.17, p=0.24 | FAIL E[R] −0.070 (p=0.64) |
| G2 random-entry placebo | **FAIL** z = +0.42 (need 2.58) | **FAIL** z = −2.94 |
| G4 vs buy-and-hold | FAIL +40% vs +133% | FAIL +39% vs +652% |
| G5 cost sensitivity | PASS survives 3× | FAIL |
| | 2 of 4 | 0 of 4 |

G3 cross-section, the same rules on seven markets Book B was not built on, each
charged its own costs: **3 of 7 positive, median E[R] −0.013**. Consistent with
the cross-instrument screen's own finding that the strategy does not generalise.

**G2 is the one that matters.** Against random entries with the same trade
count, direction mix, session, exits and costs, gold's entries score z = +0.42.
Under stop-managed exits, the entry timing is not distinguishable from noise.

### The exit menu — the only optimisation attempted

`harness/registry.py` is a fixed menu of five exits, existing so a "best of N"
carries an N you can correct for. All five, both windows:

- **Gold: all five are positive on the unseen window** (+0.007 to +0.132). That
  consistency is the strongest thing in the harness result.
- **BTC: all five are negative on the unseen window** (−0.070 to −0.124). No
  exit rescues it.
- Selection-to-unseen decay is large: gold's best exit falls +0.467 → +0.132,
  BTC's flips +0.333 → −0.070.

The best exit on the selection window (E1_trail) is also the best on the unseen
window for gold, which is mild evidence it is a real preference rather than a
fitted one. It is not adopted, because the deployed system has no stops.

## A cost-model error this exposed, and the correction

The first harness run gave BTC an unseen E[R] of **−1.65**. That was mostly my
own costing. Every cost in this project charges a **constant** spread in price
units. For gold that is fine. For bitcoin it is indefensible:

| Year | BTC median price | Constant 2.424 spread as % of price |
|---|---|---|
| 2011 | $4.8 | **50.2%** |
| 2012 | $6.8 | 35.6% |
| 2013 | $112 | 2.2% |
| 2020 | $9,691 | 0.025% |
| 2026 | $70,884 | 0.003% |

Charging today's dollar spread at $5 BTC is not conservative, it is wrong, and
it made the pre-2017 holdout unreadable. Corrected to a proportional spread
(the same 0.00282% of price), BTC's unseen E[R] moves from −1.65 to −0.070 —
so the artifact accounted for most of the catastrophe, **but BTC still fails**.

The correction also improves the deployed BTC sleeve: holdout Sharpe 1.76 →
2.25, full-period 1.48 → 1.73. **The headline figures elsewhere in this repo
keep the constant-spread (over-conservative) numbers**, so that no result rests
on a cost assumption that was changed after seeing an unfavourable outcome.

## The same question, asked inside the deployed framework

The harness's G2 has a direct analogue for a continuous system: keep the
exposure profile exactly — same weights, same distribution, same time in market
— and shuffle *when* it is applied. 300 runs per cell:

| Sleeve | Period | Strategy Sharpe | Shuffled timing | z | Percentile |
|---|---|---|---|---|---|
| XAUUSD | holdout | 0.754 | 0.144 ± 0.264 | **+2.31** | 99th |
| XAUUSD | selection | 1.576 | 0.431 ± 0.362 | **+3.16** | 100th |
| XAUUSD | full | 1.098 | 0.262 ± 0.216 | **+3.86** | 100th |
| BTCUSD | holdout | 2.596 | 0.897 ± 0.342 | **+4.96** | 100th |
| BTCUSD | selection | 1.431 | 0.387 ± 0.279 | **+3.74** | 100th |
| BTCUSD | full | 1.999 | 0.660 ± 0.228 | **+5.88** | 100th |

In the framework that is actually deployed, timing is decisively better than
chance on every sleeve in every period — including BTC's holdout, where the
harness said the opposite.

## Reconciling the two

They are not in conflict; they isolate different components.

- The harness holds **sizing constant** (fixed risk per trade) and stops out on
  ATR. What survives that is entry timing alone — and for this signal, little
  does.
- The deployed system's value comes from **being flat 70% of the time** and from
  scaling exposure inversely to volatility. Strip those out, as the harness
  does by construction, and the result goes with them.

This is consistent with everything already found: the ablation showed the
vol-regime filter and vol targeting each earn their place while the directional
filter earns nothing, and Book B was already described as a drawdown-avoider
rather than a return-enhancer.

## What this means for demo trading

1. **Do not deploy this as a stop-managed discrete system.** The harness is
   clear that the entry signal alone does not carry it. The EA already
   implements the continuous vol-sized form; keep it that way.
2. **BTC is the weaker sleeve and should be treated as probationary.** It fails
   the independent gates on unseen data even after the cost correction, its
   deflated Sharpe already did not clear the bar, and its early history is thin.
   Gold is the more robust of the two on every independent test.
3. **Do not optimise further.** The harness's own doctrine applies: a failed
   gate is a result, not an invitation to re-tune — that loop produced eight
   false positives in the project this harness came from. This project has now
   spent 298+ counted trials, and the deflated Sharpe already fails at that
   count. More searching would make the statistics worse, not better.

## Reproduce

```bash
python src/harness_test.py    # gates G1/G2/G4/G5 + G3 cross-section
python src/harness_opt.py     # proportional-spread correction + the exit menu
python src/btc_recheck.py     # shuffled-timing placebo in the deployed framework
```

Read-only against MT5; no orders. Harness data is written to
`data/harness_cache/` with the tick-measured spread declared as a constant,
because `CostModel.for_symbol` refuses to guess one and the broker's recorded
column is unusable historically.
