# Enhancement round -- what was tried, and what survived

Generated 2026-09-22 01:22 UTC from `6289430@Deriv-Demo` (DEMO).

> **Provisional.** Costs read from a DEMO account. Demo spreads and swaps can differ from live. Every figure derived from this file must be re-read on the live account before capital is committed.

## Headline: five of six avenues fail, and that is the finding

Six independent attempts were made to improve Book B. One is retained on design grounds with a near-neutral measured effect; the other five are rejected. **The plain 60/10 blend on gold survives all of them.**

That is worth as much as a positive result would have been. A specification that six independent attempts cannot improve is far more likely to be a real effect than a lucky corner of a parameter grid -- which is exactly what the brief's plateau test is trying to establish. The temptation was to keep searching until something beat it; that search is itself multiple testing, so every evaluation below is counted and the deflated Sharpe recomputed against the larger total.

| # | Avenue | Verdict | Measured effect |
|---|---|---|---|
| 1 | Better volatility estimators (Yang-Zhang, downside semi-vol) | **Rejected** | Both worse than the crude close-to-close default |
| 2 | Dynamic speed / state-conditional tilt (brief Variant 1) | **Rejected** | Sharpe 0.714 vs 0.922 for the static 50/50 blend |
| 3 | Speed ensembling across the lookback range | **Rejected on Sharpe** | 0.80-0.87 vs 0.92; better drawdown, worse return |
| 4 | Extra instruments (XAGUSD, US500) | **Rejected** | Silver marginal, US500 fails outright |
| 5 | Multi-instrument portfolio (gold + silver) | **Rejected** | Halves Sharpe: 0.913 -> 0.488 |
| 6 | Portfolio kill switch (brief section 6) | **Retained, near-neutral** | +0.064 full-sample, but helps in only 2 of 7 rolling windows |

## 1. Volatility estimators -- the crude default wins

The brief says to test Yang-Zhang and downside semi-volatility as variants, and also to *resist sophistication here* because the published time-series momentum work uses a deliberately simple model. Both instincts are vindicated: neither estimator improves on close-to-close.

| estimator | sharpe | cagr | max_dd | calmar | excess_sharpe | trades_per_week | in_market | turnover_per_year |
|---|---|---|---|---|---|---|---|---|
| close | 0.922 | 0.0808 | -0.167 | 0.484 | 0.632 | 0.87 | 0.278 | 58.8 |
| yang_zhang | 0.9 | 0.0737 | -0.156 | 0.472 | 0.61 | 0.87 | 0.278 | 55.2 |
| downside | 0.863 | 0.0896 | -0.178 | 0.504 | 0.573 | 0.87 | 0.278 | 65.5 |

Yang-Zhang does what Baltas & Kosowski predict -- it cuts turnover and slightly improves drawdown, because a less noisy volatility estimate means a less jumpy position size. It just does not pay for itself in return. Keep the crude one.

## 2. Signal variants -- the static blend beats the dynamic tilt

Goulding, Harvey & Mazzoleni's dynamic-speed idea is to tilt weights after Corrections and Rebounds based on how those states have paid historically. Estimated strictly walk-forward (expanding window, shifted, and zero until a state has 500 observations) it **underperforms the static 50/50 blend**. The state-conditional means are too noisy on one instrument to be worth acting on; the paper's evidence comes from equity markets and the brief already flagged that it is untested on gold.

| mode | direction | sharpe | cagr | max_dd | calmar | excess_sharpe | trades_per_week | in_market |
|---|---|---|---|---|---|---|---|---|
| blend5050 | long_only | 0.922 | 0.0808 | -0.167 | 0.484 | 0.632 | 0.87 | 0.278 |
| blend5050 | both | 0.757 | 0.0875 | -0.215 | 0.407 | 0.467 | 1.81 | 0.512 |
| dynamic | long_only | 0.714 | 0.067 | -0.174 | 0.385 | 0.424 | 0.92 | 0.343 |
| dynamic | both | 0.52 | 0.0581 | -0.251 | 0.231 | 0.23 | 1.79 | 0.567 |
| dma | long_only | 0.678 | 0.0653 | -0.276 | 0.237 | 0.388 | 0.42 | 0.379 |
| dma | both | 0.432 | 0.0528 | -0.408 | 0.129 | 0.142 | 0.87 | 0.757 |
| slow_only | long_only | 0.762 | 0.0735 | -0.234 | 0.314 | 0.473 | 0.59 | 0.369 |
| slow_only | both | 0.562 | 0.071 | -0.297 | 0.239 | 0.272 | 1.22 | 0.717 |
| fast_only | long_only | 0.715 | 0.0658 | -0.171 | 0.385 | 0.425 | 1.13 | 0.329 |
| fast_only | both | 0.629 | 0.0769 | -0.251 | 0.306 | 0.339 | 2.09 | 0.62 |

## 3. Speed ensembling -- better drawdown, worse return

Averaging the position across several slow/fast pairs is the standard answer to parameter uncertainty, and it averages *over* the grid rather than selecting *from* it, so it adds no fitting of its own. It does cut max drawdown materially and raises trade frequency. It does not improve Sharpe.

| variant | sharpe | cagr | max_dd | calmar | excess_sharpe | trades_per_week | in_market |
|---|---|---|---|---|---|---|---|
| single 60/10 (current) | 0.919 | 0.0833 | -0.177 | 0.471 | 0.63 | 0.96 | 0.302 |
| ensemble 3 speeds | 0.801 | 0.0647 | -0.141 | 0.458 | 0.512 | 1.31 | 0.405 |
| ensemble 4 speeds | 0.826 | 0.0637 | -0.132 | 0.482 | 0.536 | 1.14 | 0.415 |
| ensemble 5 speeds | 0.868 | 0.0687 | -0.121 | 0.568 | 0.578 | 1.25 | 0.424 |
| ensemble 6 speeds | 0.805 | 0.0629 | -0.141 | 0.447 | 0.515 | 1.25 | 0.442 |

One ensemble shows a better Calmar than the single spec -- but it is one of four definitions tried, and choosing among ensembles is itself a fitting decision. Treated as such, and not adopted. It remains the most defensible *robustness* option if dependence on a single parameter pair ever becomes the bigger worry than the Sharpe gap.

## 4. The fixed spec on every instrument in the brief's universe

Identical parameters, no refitting -- the strongest available test, since the specification was chosen on gold and has never seen these series.

| symbol | direction | years | sharpe | cagr | bench_sharpe | excess_sharpe | beats_bh | trades_per_month |
|---|---|---|---|---|---|---|---|---|
| XAUUSD | long_only | 15.72 | 0.922 | 0.0808 | 0.29 | 0.632 | True | 3.79 |
| XAUUSD | both | 15.72 | 0.757 | 0.0875 | 0.29 | 0.467 | True | 7.85 |
| XAGUSD | long_only | 15.72 | 0.176 | 0.0111 | 0.133 | 0.043 | True | 4.03 |
| XAGUSD | both | 15.72 | 0.091 | 0.0037 | 0.133 | -0.042 | False | 8.65 |
| US100 | long_only | 2.66 | 0.158 | 0.0105 | 0.816 | -0.659 | False | 5.41 |
| US100 | both | 2.66 | -0.408 | -0.0516 | 0.816 | -1.224 | False | 8.6 |
| US500 | long_only | 2.66 | -0.401 | -0.0435 | 0.812 | -1.213 | False | 6.73 |
| US500 | both | 2.66 | -0.655 | -0.0754 | 0.812 | -1.467 | False | 9.26 |

**Gold is the only instrument that works.** Silver clears the benchmark by +0.04 Sharpe over 15.7 years, which is noise rather than an edge; US500 fails as badly as US100 did. All four instruments in the brief's universe have now been tested for momentum, and three of them fail.

## 5. Portfolio construction -- adding silver destroys the book

| portfolio | sharpe | cagr | vol | max_dd | calmar | pct_time_flat | trades_per_week |
|---|---|---|---|---|---|---|---|
| gold only | 0.913 | 0.0798 | 0.0884 | -0.167 | 0.478 | 0.0 | 0.87 |
| gold only + kill switch | 0.976 | 0.0792 | 0.0814 | -0.164 | 0.482 | 0.061 | 0.87 |
| gold+silver inverse-vol | 0.488 | 0.0328 | 0.0711 | -0.185 | 0.178 | 0.0 | 1.8 |
| gold+silver inverse-vol + kill | 0.394 | 0.0237 | 0.0644 | -0.164 | 0.144 | 0.057 | 1.8 |
| gold+silver equal-weight + kill | 0.556 | 0.0357 | 0.0668 | -0.168 | 0.212 | 0.06 | 1.8 |

The gold and silver books correlate only 0.50 and overlap in the market just 17% of the time, so the diversification case looked reasonable. It does not survive contact with the numbers: **adding silver nearly halves portfolio Sharpe**, because a book with no edge contributes risk and cost without contributing return. Diversification cannot manufacture an edge that is not there.

It would have raised trade frequency from 0.87 to 1.8 a week, much closer to the brief's 2-3 target. That is exactly the trade the brief forbids: *never relax a threshold to hit the frequency target*. The rule is about thresholds, but the principle is the same -- the answer to too few trades is fewer trades, not worse ones.

## 6. The kill switch -- retained, but believe it only as insurance

Aggregate realised volatility above its trailing 95th percentile flattens the book. Full-sample it adds +0.064 Sharpe and trims volatility from 0.088 to 0.081, flat about 6% of the time. Rolling windows tell a more honest story:

| from | kill_off | kill_on | delta | pct_flat |
|---|---|---|---|---|
| 2011-01-02 | 0.844 | 0.734 | -0.11 | 0.078 |
| 2013-01-01 | -0.12 | -0.175 | -0.055 | 0.026 |
| 2015-01-01 | 0.369 | 0.311 | -0.057 | 0.089 |
| 2016-12-31 | 0.228 | 0.128 | -0.1 | 0.065 |
| 2018-12-31 | 1.083 | 1.51 | 0.427 | 0.074 |
| 2020-12-30 | 0.177 | 0.137 | -0.04 | 0.018 |
| 2022-12-30 | 1.127 | 1.234 | 0.107 | 0.074 |

It improves only **2 of 7** windows, and essentially the whole full-sample gain comes from one of them (the COVID window, +0.43). In the other five it costs a little. That is the signature of tail insurance, not of an alpha source, and it should be held for that reason rather than for its average contribution.

One structural caveat. The brief's rationale for a single kill switch is that *both* books fail on the same volatility spike, so scaling them separately leaves the portfolio correlated exactly when that costs money. With Book A dead there is only one book, so that rationale does not currently apply. The switch is kept because it is cheap and because the reasoning returns the moment a second book does.

## Overfitting accounting

Searching for improvements is multiple testing. Every evaluation in this round is added to the count and the deflated Sharpe recomputed.

| Quantity | Value |
|---|---|
| grid_trials | 216 |
| enhancement_round_trials | 30 |
| cumulative_trials | 246 |
| observed_sharpe_per_period | 0.024531 |
| expected_max_under_null | 0.010706 |
| deflated_sharpe_cumulative | 0.9856 |

The strategy still clears the 0.95 bar against the **cumulative** trial count, not just the original grid.

## Where this leaves the overall goal

| Goal (brief section 1.4) | Target | Actual | Status |
|---|---|---|---|
| Portfolio trade frequency | 2-3 / week | **0.87** / week | short |
| Book A carries frequency | 1.5-3 / week | 0 | Book A has no signal |
| Book B contribution | 2-4 / month | 0.87 / week | as designed |
| Books running | 2 | 1 | Book A rejected |
| Instruments | 4 | 1 | three fail on momentum |

**The frequency shortfall is structural and should not be closed.** The brief expected Book A to carry the trade count; Book A has no signal, and every legitimate way of replacing that frequency inside the brief's four-instrument universe has now been tested and rejected. Reaching 2-3 trades a week from here would mean adding books that lose money, which is the one thing section 1.4 explicitly rules out.

The honest options are to accept roughly one trade a week on a single validated book, or to widen the instrument universe -- which is outside the brief's scope and is Dutch's call, not this repo's. Time-series momentum is documented across 58 liquid instruments (Moskowitz, Ooi & Pedersen); one instrument is the constraint here, not the method.

## Method

- Every variant is charged the same measured spread and per-night swap, and compared against the same hurdle: buy-and-hold of the same CFD, vol-matched and charged the same financing.
- The dynamic state tilt is estimated expanding-window and shifted, so the weight applied at a bar never saw that bar's outcome.
- The kill-switch threshold is a trailing percentile, never a full-sample one.
- Reproduce with `python src/report_enhancements.py`.
