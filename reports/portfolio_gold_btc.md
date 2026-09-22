# Book B portfolio -- gold + bitcoin

Generated 2026-09-22 20:31 UTC from `6289430@Deriv-Demo` (DEMO).

> **Provisional.** Costs read from a DEMO account. Demo spreads and swaps can differ from live. Every figure derived from this file must be re-read on the live account before capital is committed.

Sleeves: **XAUUSD + BTCUSD**, equal-weight, same fixed specification on each. Return correlation between the sleeves: **0.04**.

## Portfolio vs gold alone

| period | from | to | portfolio_sharpe | portfolio_cagr | portfolio_max_dd | gold_only_sharpe | gold_only_cagr | gold_only_max_dd | trades_per_week |
|---|---|---|---|---|---|---|---|---|---|
| holdout (pre-screen) | 2011-03-23 | 2020-09-21 | 1.568 | 0.0703 | -0.09 | 0.592 | 0.0306 | -0.114 | 1.61 |
| screen window | 2020-09-22 | 2026-09-22 | 1.871 | 0.1053 | -0.056 | 1.339 | 0.094 | -0.067 | 2.72 |
| full | 2011-03-23 | 2026-09-22 | 1.701 | 0.0837 | -0.09 | 0.926 | 0.0547 | -0.114 | 2.03 |

## Kill switch (section 6), like for like

| book | overlay | sharpe | cagr | max_dd | holdout_sharpe | pct_time_flat |
|---|---|---|---|---|---|---|
| gold alone | none | 0.926 | 0.0547 | -0.114 | 0.592 | 0.0 |
| gold alone | kill switch | 1.054 | 0.058 | -0.093 | 0.732 | 0.053 |
| gold + BTC | none | 1.701 | 0.0837 | -0.09 | 1.568 | 0.0 |
| gold + BTC | kill switch | 1.697 | 0.0782 | -0.087 | 1.642 | 0.056 |

## Rolling 2-year windows (Sharpe)

Portfolio beats gold alone in **6 of 7** windows.

| from | to | portfolio | gold | btc | portfolio_beats_gold |
|---|---|---|---|---|---|
| 2011-03-23 | 2013-03-22 | 1.025 | 1.043 | 0.435 | False |
| 2013-03-22 | 2015-03-22 | 1.697 | 0.138 | 2.192 | True |
| 2015-03-22 | 2017-03-21 | 1.493 | 0.212 | 1.63 | True |
| 2017-03-21 | 2019-03-21 | 0.807 | 0.015 | 1.091 | True |
| 2019-03-21 | 2021-03-20 | 3.06 | 1.132 | 2.986 | True |
| 2021-03-20 | 2023-03-20 | 0.811 | 0.704 | 0.508 | True |
| 2023-03-20 | 2025-03-19 | 1.749 | 1.261 | 1.262 | True |

## Cost stress (full period, portfolio Sharpe)

| Scenario | Sharpe |
|---|---|
| base | 1.701 |
| 2x spread | 1.416 |
| 2x financing | 1.459 |
| 2x spread + 2x financing | 1.184 |

## Deflated Sharpe, cumulative trial count

Trials counted: **298** = 246 (spec grid + enhancement round) + 52 (every instrument in the cross-instrument screen, real and synthetic).

| Sample | Deflated Sharpe | Passes 0.95 |
|---|---|---|
| full | 0.767 | False |
| holdout only (pre-2020, unseen by the screen) | 0.559 | False |
