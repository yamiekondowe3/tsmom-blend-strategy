# Cross-instrument screen -- where else does Book B work?

Generated 2026-09-22 13:25 UTC from `6289430@Deriv-Demo` (DEMO).

> **Provisional.** Costs read from a DEMO account. Demo spreads and swaps can differ from live. Every figure derived from this file must be re-read on the live account before capital is committed.

## What was done

Book B's specification -- H4, slow 60d / fast 10d blended 50/50, long-only, flat in the top volatility decile, sized on inverse 20-day realised vol at a 15% target -- applied **unchanged** to every instrument on this broker with at least 6 years of H4 history. Not one parameter was re-tuned per instrument.

**47 real instruments** were tested, plus **5 synthetic instruments as a null control**. The synthetics are Deriv's engineered random processes, not markets; a momentum signal should not work on them, so they are the rows that say whether the engine is measuring an edge or a bug.

## The multiple-testing problem, and what it does to the answer

Testing 47 instruments and keeping the best is how false discoveries are manufactured. Three numbers decide whether the winners are real:

| Quantity | Value | Reading |
|---|---|---|
| Median excess Sharpe over buy-and-hold | **-0.328** | the typical instrument |
| Share beating costed buy-and-hold | **19%** | 50% would be a coin flip |
| Average pairwise correlation | 0.0536 | how much the tests overlap |
| Effective independent tests | **13.56** | not 47 -- correlated instruments are not separate experiments |
| Expected best Sharpe under the null | 0.022137 | the bar luck alone would clear |

## Null control -- the synthetics

| symbol | sharpe | bench_sharpe | excess_sharpe | beats_bh | window_hit_rate | trades_per_week |
|---|---|---|---|---|---|---|
| Boom 1000 Index | -0.8 | -0.846 | 0.047 | True | 0.333 | 1.84 |
| Crash 1000 Index | -0.26 | -1.066 | 0.806 | True | 1.0 | 1.14 |
| Step Index | -1.032 | -0.826 | -0.207 | False | 0.333 | 1.38 |
| Volatility 100 Index | 0.334 | 0.103 | 0.231 | True | 0.333 | 1.48 |
| Volatility 75 Index | 0.005 | -0.211 | 0.216 | True | 0.667 | 1.26 |

These are random processes with engineered volatility. A momentum signal that scored well here would mean the engine is manufacturing returns rather than finding them.

## Instruments that pass all three bars

A candidate must clear **all** of: excess Sharpe over costed buy-and-hold >= 0.2, absolute Sharpe >= 0.4, and beating the benchmark in >= 60% of rolling 2-year windows. Ranking on Sharpe alone is what the controls above exist to prevent.

| symbol | group | years | sharpe | cagr | max_dd | calmar | bench_sharpe | excess_sharpe | window_hit_rate | trades_per_week | in_market |
|---|---|---|---|---|---|---|---|---|---|---|---|
| XAUUSD | Metals | 6.0 | 1.463 | 0.1456 | -0.102 | 1.425 | 0.651 | 0.812 | 0.667 | 0.96 | 0.308 |
| XAUEUR | Metals | 6.0 | 1.349 | 0.1384 | -0.157 | 0.879 | 0.703 | 0.646 | 1.0 | 1.15 | 0.338 |
| BTCUSD | Crypto | 6.0 | 0.84 | 0.0744 | -0.14 | 0.533 | 0.551 | 0.29 | 0.667 | 1.34 | 0.305 |
| ETHUSD | Crypto | 6.0 | 0.89 | 0.0797 | -0.109 | 0.728 | 0.639 | 0.251 | 0.667 | 1.47 | 0.305 |

## Full cross-section (real instruments, ranked by excess Sharpe)

| symbol | group | years | sharpe | cagr | max_dd | calmar | bench_sharpe | excess_sharpe | window_hit_rate | trades_per_week | in_market | passes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| XAUUSD | Metals | 6.0 | 1.463 | 0.1456 | -0.102 | 1.425 | 0.651 | 0.812 | 0.667 | 0.96 | 0.308 | True |
| XAUEUR | Metals | 6.0 | 1.349 | 0.1384 | -0.157 | 0.879 | 0.703 | 0.646 | 1.0 | 1.15 | 0.338 | True |
| USDMXN | Forex Minor | 6.0 | -0.076 | -0.0086 | -0.2 | -0.043 | -0.552 | 0.476 | 0.667 | 0.71 | 0.162 | False |
| BTCUSD | Crypto | 6.0 | 0.84 | 0.0744 | -0.14 | 0.533 | 0.551 | 0.29 | 0.667 | 1.34 | 0.305 | True |
| USDCHF | Forex Major | 6.0 | 0.37 | 0.0255 | -0.157 | 0.162 | 0.107 | 0.263 | 0.333 | 0.92 | 0.225 | False |
| ETHUSD | Crypto | 6.0 | 0.89 | 0.0797 | -0.109 | 0.728 | 0.639 | 0.251 | 0.667 | 1.47 | 0.305 | True |
| USDCNH | Forex Minor | 6.0 | 0.365 | 0.0202 | -0.156 | 0.129 | 0.25 | 0.115 | 0.667 | 1.14 | 0.218 | False |
| USDPLN | Forex Minor | 6.0 | 0.064 | 0.002 | -0.223 | 0.009 | -0.028 | 0.093 | 0.667 | 0.95 | 0.205 | False |
| USDZAR | Forex Minor | 6.0 | -0.346 | -0.0295 | -0.29 | -0.102 | -0.367 | 0.02 | 0.333 | 1.22 | 0.238 | False |
| USDNOK | Forex Minor | 6.0 | -0.183 | -0.017 | -0.18 | -0.094 | -0.137 | -0.046 | 0.667 | 1.02 | 0.232 | False |
| EURAUD | Forex Major | 6.0 | -0.463 | -0.0396 | -0.244 | -0.163 | -0.405 | -0.058 | 0.333 | 1.19 | 0.234 | False |
| EURNOK | Forex Minor | 6.0 | -0.558 | -0.0451 | -0.279 | -0.162 | -0.498 | -0.061 | 0.333 | 1.08 | 0.23 | False |
| GBPAUD | Forex Major | 6.0 | -0.066 | -0.0089 | -0.198 | -0.045 | -0.004 | -0.062 | 0.333 | 1.13 | 0.281 | False |
| XAGUSDmicro | Metals | 6.0 | 0.41 | 0.0318 | -0.17 | 0.187 | 0.474 | -0.064 | 0.667 | 0.96 | 0.276 | False |
| XAGUSD | Metals | 6.0 | 0.41 | 0.0317 | -0.17 | 0.186 | 0.474 | -0.064 | 0.667 | 0.96 | 0.276 | False |
| XAGEUR | Metals | 6.0 | 0.458 | 0.036 | -0.222 | 0.162 | 0.543 | -0.085 | 0.667 | 1.18 | 0.275 | False |
| EURUSD | Forex Major | 6.0 | -0.444 | -0.0326 | -0.262 | -0.124 | -0.344 | -0.1 | 0.333 | 0.87 | 0.211 | False |
| EURPLN | Forex Minor | 6.0 | -0.562 | -0.0428 | -0.296 | -0.145 | -0.459 | -0.103 | 0.333 | 1.18 | 0.216 | False |
| NZDUSD | Forex Minor | 6.0 | -0.743 | -0.0538 | -0.304 | -0.177 | -0.6 | -0.143 | 0.667 | 0.95 | 0.204 | False |
| EURSEK | Forex Minor | 6.0 | -0.212 | -0.0207 | -0.184 | -0.113 | -0.049 | -0.164 | 0.0 | 1.22 | 0.29 | False |
| CADCHF | Forex Minor | 6.0 | -0.352 | -0.0288 | -0.254 | -0.114 | -0.164 | -0.187 | 0.333 | 1.11 | 0.227 | False |
| EURCHF | Forex Major | 6.0 | -0.349 | -0.024 | -0.223 | -0.107 | -0.147 | -0.203 | 0.333 | 1.01 | 0.207 | False |
| EURGBP | Forex Major | 6.0 | -0.849 | -0.0533 | -0.296 | -0.18 | -0.609 | -0.24 | 0.333 | 1.12 | 0.187 | False |
| AUDCHF | Forex Minor | 6.0 | -0.215 | -0.0201 | -0.272 | -0.074 | 0.112 | -0.328 | 0.333 | 0.99 | 0.266 | False |
| GBPNOK | Forex Minor | 6.0 | -0.525 | -0.0457 | -0.274 | -0.167 | -0.178 | -0.347 | 0.333 | 0.99 | 0.267 | False |
| USDSEK | Forex Minor | 6.0 | -0.146 | -0.0155 | -0.255 | -0.061 | 0.212 | -0.358 | 0.0 | 1.14 | 0.261 | False |
| GBPNZD | Forex Minor | 6.0 | -0.204 | -0.021 | -0.155 | -0.136 | 0.165 | -0.369 | 0.0 | 1.24 | 0.314 | False |
| GBPSEK | Forex Minor | 6.0 | -0.093 | -0.0117 | -0.192 | -0.061 | 0.305 | -0.398 | 0.333 | 1.24 | 0.324 | False |
| GBPCHF | Forex Minor | 6.0 | -0.191 | -0.0165 | -0.25 | -0.066 | 0.208 | -0.398 | 0.333 | 1.15 | 0.255 | False |
| GBPUSD | Forex Major | 6.0 | -0.339 | -0.0282 | -0.274 | -0.103 | 0.064 | -0.403 | 0.0 | 1.33 | 0.264 | False |
| AUDUSD | Forex Major | 6.0 | -0.377 | -0.0329 | -0.322 | -0.102 | 0.03 | -0.407 | 0.333 | 1.19 | 0.27 | False |
| EURCAD | Forex Major | 6.0 | -0.419 | -0.035 | -0.243 | -0.144 | 0.018 | -0.438 | 0.333 | 1.37 | 0.263 | False |
| CHFJPY | Forex Minor | 6.0 | 0.397 | 0.0358 | -0.125 | 0.287 | 0.844 | -0.447 | 0.333 | 1.17 | 0.378 | False |
| USDCAD | Forex Major | 6.0 | -0.155 | -0.0147 | -0.23 | -0.064 | 0.293 | -0.448 | 0.0 | 1.06 | 0.245 | False |
| AUDNZD | Forex Minor | 6.0 | 0.193 | 0.012 | -0.154 | 0.078 | 0.649 | -0.456 | 0.333 | 1.14 | 0.33 | False |
| XPDUSD | Metals | 6.0 | -0.614 | -0.0456 | -0.332 | -0.137 | -0.138 | -0.476 | 0.0 | 1.09 | 0.19 | False |
| CADJPY | Forex Minor | 6.0 | 0.21 | 0.0164 | -0.254 | 0.064 | 0.698 | -0.488 | 0.333 | 1.32 | 0.376 | False |
| AUDJPY | Forex Major | 6.0 | 0.328 | 0.0277 | -0.168 | 0.165 | 0.827 | -0.499 | 0.0 | 1.37 | 0.372 | False |
| USDJPY | Forex Major | 6.0 | 0.381 | 0.0372 | -0.166 | 0.223 | 0.887 | -0.506 | 0.0 | 1.3 | 0.403 | False |
| GBPCAD | Forex Minor | 6.0 | -0.168 | -0.0167 | -0.22 | -0.076 | 0.371 | -0.539 | 0.333 | 1.21 | 0.302 | False |
| XPTUSD | Metals | 6.0 | -0.312 | -0.0269 | -0.288 | -0.093 | 0.339 | -0.651 | 0.0 | 1.26 | 0.224 | False |
| NZDCAD | Forex Minor | 6.0 | -0.903 | -0.0634 | -0.338 | -0.188 | -0.233 | -0.67 | 0.333 | 0.92 | 0.197 | False |
| NZDJPY | Forex Minor | 6.0 | -0.192 | -0.0228 | -0.264 | -0.086 | 0.541 | -0.733 | 0.0 | 1.55 | 0.356 | False |
| EURJPY | Forex Major | 6.0 | 0.115 | 0.0066 | -0.222 | 0.03 | 0.874 | -0.759 | 0.0 | 1.37 | 0.381 | False |
| AUDCAD | Forex Minor | 6.0 | -0.527 | -0.042 | -0.291 | -0.145 | 0.282 | -0.809 | 0.0 | 1.11 | 0.24 | False |
| GBPJPY | Forex Major | 6.0 | 0.058 | 0.0006 | -0.25 | 0.002 | 0.909 | -0.852 | 0.0 | 1.39 | 0.418 | False |
| EURNZD | Forex Minor | 6.0 | -0.721 | -0.0607 | -0.318 | -0.191 | 0.172 | -0.893 | 0.0 | 1.25 | 0.265 | False |

## Method and caveats

- The same fixed specification everywhere; no per-instrument fitting, so the only selection is across instruments and it is countable.
- Each instrument is compared against **its own** vol-matched buy-and-hold, charged that instrument's own nightly swap -- not against zero.
- Spreads are tick-measured but on a **14-day screening window**, shorter than the 30 days used for the core instruments. Median spread is stable enough for a screen; the 95th percentile is not. Anything that survives here must have its costs re-measured properly before it is traded.
- Symbols with fewer than 6 years or 3000 H4 bars were excluded, so nothing is judged on a sample too short to hold several independent windows.
- Read-only throughout: `symbol_info`, `copy_rates_range`, `copy_ticks_range`. No order functions.
- Reproduce with `python src/report_universe.py --pull`.
