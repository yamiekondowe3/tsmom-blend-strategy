# tsmom-blend-strategy

Book B of the two-book quant project: **time-series momentum on XAUUSD and
BTCUSD**, using
the slow/fast blended signal from Goulding, Harvey & Mazzoleni (JFE 2023)
rather than a single slow signal. Traded through MT5 on a Deriv account.

Book A, the statistical-arbitrage book, lives in the sibling repo
[`statarb-pairs-strategy`](https://github.com/yamiekondowe3/statarb-pairs-strategy).
The full project brief is in [`docs/handoff.md`](docs/handoff.md).

## Status: TRADING ON DEMO (build step 8). Not live.

Steps 1–8 of 9 are done. `TSMOM_Blend_EA` is attached to XAUUSD H4 on
**Deriv-Demo 6289430** and trading both sleeves — see
[`reports/demo_deployment.md`](reports/demo_deployment.md). The EA **refuses to
trade on a real account** regardless of settings, and `AllowLiveTrading` is
`false` in the committed source; the only place it is true is the demo preset.
Every Python script here remains read-only against MT5.

**Gold now executes on XAUUSDmicro** — signal still computed on XAUUSD (which
has the 15 years of history the lookbacks need), order placed on the micro
contract, which has a tenth the minimum position at an identical measured
spread (0.150 median, 0.280 p95) and swap. Gold's smallest tradable weight
falls from 0.867 to **0.087** against a 0.782 median, so it no longer misses
most of its signals at $10k. The backtest is unchanged (Sharpe 1.701 vs 1.700).

**Minimum account size — a $50 account cannot trade this.** The smallest gold
position is $437 against the ~$39 of exposure the strategy wants there, about
11× too big; the EA holds nothing and logs the requirement rather than taking
an 8.7×-leverage position.

| Configuration | Equity needed (at the 10% vol target) |
|---|---|
| Gold sleeve alone, nearly all signals | ~$2,000 |
| Both sleeves, gold full + BTC partial | ~$5,000 |
| Both sleeves, nearly all signals | ~**$7,000** |

At **$200 neither sleeve can ever open a position** — the smallest gold and BTC
positions on this broker are $436 and $863, i.e. 2.2× and 4.3× the whole
account, and no smaller lot exists. Forcing the minimum lot anyway was
simulated across four regimes: it survives, but at −19% to −57% drawdowns and
up to 5.8× leverage that *rises as the account falls*. See
[`reports/small_account.md`](reports/small_account.md).

Detail in [`reports/demo_deployment.md`](reports/demo_deployment.md).

## Honesty notice

**A validated backtest is not a track record.** This survives the controls the
brief demands — walk-forward, deflated Sharpe, cost sensitivity, a plateau
check, a placebo and a look-ahead test — on one broker's data, and it has never
traded. The gold sleeve rests on a 15.7-year sample over most of which gold
rose; the bitcoin sleeve on a 15.5-year sample whose early years are thin. The
two-instrument portfolio does **not** clear the deflated-Sharpe bar under the
most conservative trial count (see *Instrument expansion*).

## The strategy

| | |
|---|---|
| Instruments | XAUUSD + BTCUSD, equal weight (see *Instrument expansion* below) |
| Timeframe | H4 |
| Slow signal | sign of trailing 60-trading-day return (308 H4 bars gold, 251 BTC) |
| Fast signal | sign of trailing 10-trading-day return (51 H4 bars gold, 42 BTC) |
| Position | static 50/50 blend of the two, **long-only** |
| Regime filter | flat when 20-day realised vol is in its trailing 2-year top decile |
| Sizing | inverse 20-day realised vol (close-to-close), **10%** annual target, 3× cap |
| Kill switch | flat when aggregate realised vol exceeds its trailing 95th percentile |
| Execution | signal read at bar close, position held from the **next** bar |

Lookbacks are the literature's, not values found by searching this data.

### Gold sleeve alone — results, 15.7 years, net of measured spread and per-night swap

| | Strategy | Buy-and-hold (vol-matched, swap charged) |
|---|---|---|
| CAGR | **8.1%** | 2.2% |
| Sharpe | **0.92** | 0.29 |
| Max drawdown | −16.7% | — |
| Trades/month | 3.79 | — |
| Time in market | 27.8% | 100% |

Deflated Sharpe **0.976** against the 0.95 bar, with all 216 searched
configurations counted. Survives 3× the measured spread. Beats the benchmark in
**6 of 7** rolling 2-year windows.

**What it actually is: a drawdown-avoider, not a return-enhancer.** Its edge
shows up when holding gold hurt — 2011–2015 (+0.85 Sharpe over buy-and-hold)
and 2020–2022 (+0.56) — and adds least when gold simply rises. It **lost to
buy-and-hold for the four years 2016–2019**. Anyone expecting it to beat gold in
a bull market has misunderstood it.

Full evidence: [`reports/book_b.md`](reports/book_b.md).

### Three findings that contradict the brief's expectations

1. **US100 (B2) fails and is dropped.** Negative in every sub-period, beaten by
   buy-and-hold by more than a full Sharpe point. With only 2.66 years of
   history the honest statement is *no evidence of an edge* rather than *proven
   absence* — but there is no case for capital.
2. **The published slow D1 specification does not clear the hurdle**
   (excess Sharpe −0.002). The brief expected the slow speed to be the strong
   one and the medium speed to have to prove itself; here it is the reverse.
3. **The directional filter earns nothing** (0.922 with, 0.917 without). The
   slow signal already encodes direction. Kept because the brief specifies it,
   but it could go.

## Enhancement round: five of six avenues failed

Six independent attempts were made to improve on the specification above. One is
retained on design grounds with a near-neutral measured effect; the other five
are rejected. Full detail in [`reports/enhancements.md`](reports/enhancements.md).

| Avenue | Verdict | Effect |
|---|---|---|
| Yang-Zhang / downside semi-vol estimators | rejected | both worse than crude close-to-close |
| Dynamic state tilt (brief Variant 1) | rejected | 0.714 vs 0.922 for the static blend |
| Speed ensembling across the lookback range | rejected on Sharpe | 0.80–0.87 vs 0.92; better drawdown, worse return |
| Extra instruments (XAGUSD, US500) | rejected | silver marginal (+0.04), US500 fails |
| Gold + silver portfolio | rejected | halves Sharpe, 0.913 → 0.488 |
| Portfolio kill switch (section 6) | **retained** | +0.064 full-sample, but helps in only 2 of 7 windows |

**That five failed is the finding, not a disappointment.** A specification six
independent attempts cannot improve is more likely to be a real effect than a
lucky corner of a parameter grid. Deflated Sharpe still clears 0.95
(**0.986**) against the **cumulative** 246-trial count, not just the original
grid — searching for improvements is itself multiple testing and is counted as
such.

Two judgements worth stating plainly:

- **Adding silver would have raised frequency from 0.87 to 1.8 trades/week**,
  much closer to the brief's target — by halving Sharpe. That is the trade
  section 1.4 forbids. The answer to too few trades is fewer trades, not worse
  ones.
- **The kill switch is tail insurance, not alpha.** Essentially its whole
  full-sample gain comes from the COVID window; in five of seven windows it
  costs a little. Note also that the brief's rationale for a *single* kill
  switch — both books failing on the same vol spike — does not currently apply,
  because there is only one book. It is kept because it is cheap and the
  reasoning returns as soon as a second book does.

## Instrument expansion: gold + bitcoin

The universe was widened beyond the brief's four instruments, on instruction.
The fixed specification above — unchanged, no parameter re-tuned — was
screened across **47 real instruments plus 5 synthetic random processes as a
null control**, then the survivors were validated on the history the screen
never saw. Full detail: [`reports/instrument_expansion.md`](reports/instrument_expansion.md).

**The strategy does not generalise.** Median excess Sharpe over buy-and-hold
across the universe is −0.33, and only 19% of instruments beat simply holding
them; forex fails almost across the board. Four passed the screen (XAUUSD,
XAUEUR, BTCUSD, ETHUSD). Of those, **two passed the pre-2020 holdout**:

| Survivor | Holdout (unseen by the screen) | Excess Sharpe vs buy-and-hold |
|---|---|---|
| XAUUSD | 2011–2020, 9.7y | **+0.53** |
| BTCUSD | 2011–2020, 9.5y | **+0.53** |
| ETHUSD | 2015–2020 | −0.69 — rejected |
| XAUEUR | 9 months only | untestable; gold in euros anyway |

### Book B is now a two-sleeve portfolio: XAUUSD + BTCUSD, equal weight

| | Gold alone | **Gold + BTC** (with kill switch) |
|---|---|---|
| Sharpe | 0.93 | **1.70** |
| CAGR | 5.5% | **8.4%** |
| Max drawdown | −11.4% | **−9.0%** |
| Holdout Sharpe | 0.59 | **1.64** |
| Trades / week | ~0.9 | **2.03** |

2011-03 to 2026-09, net of measured spread and per-night swap. The sleeves are
almost uncorrelated (0.04); that is where the improvement comes from. It beats
gold alone in 6 of 7 rolling 2-year windows and still returns Sharpe 1.18 with
spread and financing **both** doubled.

**What does not pass:** deflated Sharpe is **0.77** (full) and **0.56**
(holdout) against a cumulative 298 trials — below the 0.95 bar under the most
conservative accounting. The holdout is the evidence that carries the result;
the DSR is the reason not to over-trust it. BTC's early history (2011–13) is
thin, its swap is −20%/yr both ways, and crypto costs were measured on a 7-day
screening window — re-measure on 30 days before trading.

## Execution: EA + parity test (steps 6–7)

[`mql5/TSMOM_Blend_EA.mq5`](mql5/TSMOM_Blend_EA.mq5) implements the spec for both
sleeves in one multi-symbol expert. Against the Python backtest over 2016–2026,
after warm-up:

| Sleeve | Bars | Fields matching | Trades matched |
|---|---|---|---|
| XAUUSD | 14,234 | 7 of 7 (max diff 5e-9) | **462 / 462** |
| BTCUSD | 13,962 | 7 of 7 (max diff 5e-9) | **585 / 585** |

Zero trades on either side that the other did not take. Strategy Tester
economics on the broker's own spreads, swaps and lot rounding: 100,000 →
322,124 over 10.7 years (~11.6%/yr), against Python's 11.9%.

**The parity test caught two defects that no Python backtest could:**

1. **Hedging-account position stacking.** The first tester run hit a margin stop
   out and ended with 11,538 of a 100,000 deposit. On a hedging account every
   `Buy` opens a *new* position; the EA read only the first one, thought it was
   flat, and bought again every bar. Fixed by netting across all positions and
   closing rather than selling to reduce.
2. **The regime filter needs ~2 years of history loaded.** With a cold cache it
   computes its volatility decile from too small a sample and mis-fires for the
   first year or two. **Before going live, make sure the terminal has at least
   ~2,900 H4 bars per sleeve downloaded.** Signals and sizing are unaffected.

Full detail: [`reports/parity.md`](reports/parity.md).

## Independent harness validation — the strategy has a hard limit

Book B was run through the separate validation harness in `../harness`, written
for a different project. Full detail: [`reports/harness_validation.md`](reports/harness_validation.md).

**It fails, and the failure is informative.** The harness tests discrete,
stop-managed trades at fixed risk; Book B holds a continuous vol-sized exposure.
Against random entries with the same trade count, exits and costs, gold's entry
timing scores **z = +0.42** (needs 2.58) and BTC's **z = −2.94**. Across seven
markets it was not built on, 3 of 7 positive, median E[R] −0.013.

The same question asked *inside* the deployed framework — same exposure profile,
shuffled timing, 300 runs — comes back the other way, on every sleeve and period:

| Sleeve | Period | Strategy | Shuffled timing | z |
|---|---|---|---|---|
| XAUUSD | holdout | 0.754 | 0.144 ± 0.264 | **+2.31** |
| BTCUSD | holdout | 2.596 | 0.897 ± 0.342 | **+4.96** |

Both are true, and together they say something sharper than either alone:

> **The edge is in exposure management — when to be in the market and at what
> size — not in entry timing. Converted into a stop-managed system, it stops
> working.**

Consequences: do **not** deploy this as a stop/target system (the EA already
implements the continuous form); treat **BTC as probationary** (it fails the
independent gates on unseen data and already missed the deflated-Sharpe bar);
and **do not optimise further** — 298+ trials are already counted and more
searching makes the statistics worse, not better.

A costing error surfaced too: a constant $2.42 BTC spread is **50% of BTC's
2011 price**. Corrected to proportional, BTC's harness result improves from
−1.65 to −0.07 (still failing) and its deployed holdout Sharpe from 1.76 to
2.25. **The headline numbers in this README keep the over-conservative constant
spread**, so no result rests on a cost assumption changed after seeing an
unfavourable outcome.

## Drawdown reduced to −9.0%, by holding less

The deployed volatility target moved from 15% to **10%**, taking the
portfolio's worst peak-to-trough from −13.3% to **−9.0%** (−12.8% → −8.7% with
the kill switch). Full detail: [`reports/drawdown.md`](reports/drawdown.md).

| Vol target | Max DD | CAGR | Sharpe |
|---|---|---|---|
| 15% (previous) | −13.3% | 12.7% | **1.701** |
| **10% (current)** | **−9.0%** | **8.4%** | **1.701** |
| 7.5% | −6.6% | 5.8% | 1.697 |

**Sharpe is identical — this is scaling, not improvement.** The book is held
smaller and return falls in the same proportion as risk. Two things follow:
the leverage cap is not a second lever (3× → 1.5× moves drawdown only −12.8% →
−12.2%), and swapping to a lower-Sharpe variant that happens to drawdown less
is strictly dominated by simply scaling this one down. No new trials were spent
— the dial changes no decision the strategy makes, only position size.

The cost: a smaller target asks for smaller positions while the broker's
minimum lot stays put, so **this raises the minimum account size** (BTC sleeve
from ~$5,000 to ~$7,000).

Set in `src/deploy_config.py` and matched by the EA preset. The research path
(`screen_universe.py`, `analyze_book_b.py`, `run_book_b.py`) stays at 0.15 so
the screen, holdout, deflated-Sharpe and harness reports remain reproducible —
and since Sharpe is invariant to the dial, none of those verdicts depend on it.

## Where this sits against the overall goal

| Goal (brief §1.4) | Target | Actual |
|---|---|---|
| Portfolio trade frequency | 2–3 / week | **2.03 / week** |
| Books running | 2 | 1 (Book A has no signal) |
| Instruments trading | 4 | 2 (XAUUSD, BTCUSD) |

**The frequency target is now met**, and it is met the only way the brief
allows: by adding an instrument that independently passed validation, not by
loosening a filter. It was not met inside the brief's original four-instrument
universe, which is why the universe was widened.

### A data defect worth knowing about

The broker's recorded per-bar `spread` column is **not** a usable historical
cost series: XAUUSD reports a median of exactly 0.000 through much of 2019–2023,
and XAGUSD records 3.0 price units in 2011 (a 10% spread on $30 silver) with a
maximum of 125.0. Costs here use the tick-measured constants in
[`data/costs.csv`](data/costs.csv) instead, per the brief's section 3.2. Using
the recorded column directly produced a Book A backtest whose costs came to 318%
of notional — an artifact of bad data, not a result.

## Layout

```
src/book_b.py          signal, filters, overlay, costed position backtest
src/run_book_b.py      config grid, walk-forward, costed CFD benchmark
src/analyze_book_b.py  ablation, sub-periods, sanity checks, deflated Sharpe
src/report_book_b.py   writes reports/book_b.md
src/universe.py        cross-instrument enumeration, pull, tick-measured costs
src/report_universe.py stage 1: screen the universe -> reports/universe_screen.md
src/topup_costs.py     retry symbols whose cost read failed
src/holdout.py         stage 2: validate survivors on pre-screen history
src/portfolio_gold_btc.py  gold + BTC portfolio -> reports/portfolio_gold_btc.md
src/pull_history.py    price history + honest coverage report
src/build_costs.py     contract specs, swaps, session-split spreads from ticks
common/                shared library (validation.py holds the deflated Sharpe)
```

Deriv does not use standard tickers: US100 is `US Tech 100` on this broker.
Always resolve through `common/data_fetch.py`'s `BROKER_SYMBOL_MAP`.

## Reproducing

Requires the MT5 terminal open and logged in to the account being measured.

```bash
pip install -r requirements.txt
python src/resolve_symbols.py    # data/symbol_map.json, broker_config.json
python src/pull_history.py       # data/*.csv, reports/data_coverage.md
python src/build_costs.py        # data/costs.csv, reports/cost_table.md
python src/report_book_b.py      # reports/book_b.md
python src/report_universe.py --pull   # universe screen (slow first time: MT5
python src/topup_costs.py              #   downloads each symbol's history)
python src/report_universe.py
python src/holdout.py
python src/portfolio_gold_btc.py
```

## Safety

**Read-only against MT5.** No script calls `order_send`, `order_check`, or any
function that places, modifies or closes an order or position. Per the brief
(section 2) that holds until build step 8 and lifts only on explicit
instruction.

## Next step

Build step 9: let the demo run a quarter and judge it on execution fidelity —
fills, swaps, session gaps, rollovers, lot granularity — not on P&L, which over
a quarter says nothing about a strategy that holds for weeks. Then decide on
capital against the reservations already on record. Remaining known issue: the terminal needs ~2,900 H4 bars per sleeve cached so the
regime filter starts correct. (The kill-switch timestamp-alignment bug is
fixed: it now runs on the union grid of both sleeves and agrees with Python on
99.89% of bars.) The brief flags
that as the classic backtest-to-live failure and worth more effort than it looks.
