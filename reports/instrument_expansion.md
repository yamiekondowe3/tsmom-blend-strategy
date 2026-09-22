# Instrument expansion -- gold + bitcoin

Book B's fixed specification (H4, slow 60d / fast 10d blended 50/50, long-only,
flat in the top volatility decile, inverse-vol sizing at 15%) was taken from
the gold-only result and tested across the whole broker. **Not one parameter
was re-tuned per instrument.**

## Verdict

**Book B becomes a two-sleeve portfolio: XAUUSD + BTCUSD, equal weight.**

| | Gold alone | Gold + BTC | Gold + BTC, with kill switch |
|---|---|---|---|
| Sharpe | 0.93 | **1.70** | **1.70** |
| CAGR | 8.2% | 12.7% | 11.9% |
| Max drawdown | −16.7% | −13.3% | **−12.8%** |
| Holdout Sharpe (pre-2020-09) | 0.59 | 1.57 | **1.64** |
| Trades / week | ~0.9 | **2.03** | 2.03 |
| Beats gold alone, rolling 2y windows | — | **6 of 7** | — |

Full period 2011-03 to 2026-09 (the common span of the two sleeves), net of
measured spread and per-night swap. The section 6 kill switch retained in the
enhancement round stays in: on the portfolio it is neutral on Sharpe, costs
0.8 points of CAGR, trims drawdown and improves the holdout, and the brief's
case for a single aggregate trigger applies again now that there are two
sleeves. Flat about 6% of the time. Trade counts exclude the kill switch's own
exits and re-entries, and its flattening is not charged spread -- a small
optimism in that column. The sleeves' returns are almost
uncorrelated (**0.04**), and that is where the improvement comes from: two weak,
independent trend streams combine into a stronger one.

**Trade frequency now meets the brief's 2-3/week target (section 1.4)**, by
adding a second instrument that independently passed validation rather than
by loosening anything.

## How the instruments were chosen -- and why the four controls matter

Testing dozens of instruments and keeping the best is how false discoveries are
manufactured, so selection ran in two stages, and the second stage is the one
that counts.

### Stage 1 -- screen, last 6 years (2020-09 to 2026-09)

47 real instruments across forex majors and minors, metals, energies, softs,
stock indices and crypto majors, plus **5 synthetic random processes as a null
control**. A candidate had to clear three bars at once: excess Sharpe >= 0.20
over *its own* vol-matched, swap-charged buy-and-hold; absolute Sharpe >= 0.40;
and beating that benchmark in >= 60% of rolling 2-year windows.

| Cross-section | Value |
|---|---|
| Median excess Sharpe over buy-and-hold | **−0.33** |
| Share beating buy-and-hold | **19%** |
| Effective independent tests (avg correlation 0.05) | 13.6 |
| Best synthetic (random walk) Sharpe | +0.33 -- the noise floor |

**The strategy does not generalise.** Four in five instruments do worse than
simply holding them. Forex fails almost across the board. Only four
instruments passed: XAUUSD, XAUEUR, BTCUSD, ETHUSD. Full table:
[`universe_screen.md`](universe_screen.md).

The null control behaved: on Deriv's engineered random processes the strategy
scores between −1.03 and +0.33, so the engine is not manufacturing returns.

### Stage 2 -- holdout, the history the screen never saw (pre-2020-09)

Everything before the screen window played no part in picking the survivors,
which makes it a genuine out-of-sample test -- the one control that answers the
multiple-testing problem rather than just correcting for it.

| Survivor | Holdout | Sharpe | Excess vs buy-and-hold | Verdict |
|---|---|---|---|---|
| **XAUUSD** | 2011-01 to 2020-09 (9.7y) | +0.57 | **+0.53** | **pass** |
| **BTCUSD** | 2011-03 to 2020-09 (9.5y) | +1.76 | **+0.53** | **pass** |
| ETHUSD | 2015-08 to 2020-09 (5.1y) | +0.72 | −0.69 | fail |
| XAUEUR | 2020-01 to 2020-09 (0.7y) | — | — | untestable |

ETHUSD was profitable but lost to simply holding ether, so the signal added
nothing. XAUEUR has only nine months of pre-screen history on this broker, and
it is gold priced in euros anyway: it would double the gold exposure while
adding no independent evidence.

## Stress tests

Both sleeves were re-run with costs pushed against them. Excess Sharpe over
buy-and-hold stays positive in every period under every scenario.

| Portfolio scenario (full period) | Sharpe |
|---|---|
| Base | 1.70 |
| 2× spread | 1.42 |
| 2× financing | 1.46 |
| **2× spread + 2× financing** | **1.18** |

**BTC financing was stressed specifically.** BTCUSD carries a swap of −20%/yr in
*both* directions with the triple on Monday. The model charges 7 nights a week.
If Deriv also charges Saturday and Sunday on a 24/7 instrument, the true figure
is 9. That could not be confirmed from the contract spec, so the result had to
survive the worse case: at 9/7 financing BTC's full-period Sharpe moves only
1.48 → 1.42.

## What does not pass, stated plainly

**Deflated Sharpe does not clear 0.95** under the most conservative accounting:
**0.77** full period, **0.56** holdout only, against a cumulative **298 trials**
(246 from the specification grid and enhancement round, plus 52 instruments in
the screen). The test prices every trial at the dispersion of the
cross-instrument screen, and that dispersion is large because the instruments
genuinely differ from each other, not just because of noise. It is still the
number the brief's section 7 asks for, and it is reported rather than argued
away.

The evidence that carries the result is the holdout: two instruments picked on
2020-2026 data **both** beat buy-and-hold by +0.53 Sharpe over the preceding
nine and a half years, which they had no reason to do if the selection were
luck. Weigh the two findings against each other; neither settles it alone.

## Caveats specific to bitcoin

- **Early BTC data is thin.** Deriv's BTCUSD history starts 2011-03, when the
  market was tiny and quotes were unreliable. The holdout leans on that period.
- **Costs are charged conservatively there.** The spread is today's $2.42 in
  absolute terms, applied even when BTC traded at a few hundred dollars. That
  overstates early costs, which argues the early result is if anything
  understated -- but it also means early-period P&L should not be over-read in
  either direction.
- **Crypto costs are screening-grade** (7-day tick window, not the 30 days used
  for the core instruments). Re-measure on the full window before trading.
- **Negative carry both ways.** −20%/yr on a long BTC position is the largest
  single running cost in the book. The strategy survives it because it is in
  the market ~30% of the time; a buy-and-hold holder pays it all year.

## Process defects found and fixed along the way

1. **The broker's group names are not the obvious ones.** There is no "Forex"
   or "Energy" group; guessing them returned an empty universe.
2. **A boundary bug in the history filter rejected every symbol.** Probing for a
   bar at the 6-year cutoff made the measured span 5.999 years, so gold (15.7y)
   failed a >= 6.0 test.
3. **22 of 52 symbols were silently dropped** from the cost table by transient
   tick-download failures -- every forex major, BTC, ETH and gold itself. The
   first screen therefore tested only minors and exotics and reported "none
   pass". It was not reported, the failures were retried, and the screen re-run.
4. **The portfolio trade count was inflated** from 2.0 to 3.9 a week by
   zero-filling gold's position across BTC's weekend bars, booking a fake exit
   every Saturday and re-entry every Monday.

Any of these left in place would have changed the conclusion.

## Reproduce

```bash
python src/report_universe.py --pull   # enumerate, pull, measure costs, screen
python src/topup_costs.py              # retry any symbol whose cost read failed
python src/report_universe.py          # re-screen on the complete cost table
python src/holdout.py                  # stage-2 validation of survivors
python src/portfolio_gold_btc.py       # gold + BTC portfolio -> reports/portfolio_gold_btc.md
```

Read-only against MT5 throughout: `symbols_get`, `symbol_info`,
`copy_rates_from`, `copy_rates_range`, `copy_ticks_range`. No order functions.
Measured on Deriv-Demo 6289430 -- provisional until re-read on the live account.
