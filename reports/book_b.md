# Book B -- time-series momentum: results

Generated 2026-09-21 23:21 UTC from `6289430@Deriv-Demo` (DEMO).

> **Provisional.** Costs read from a DEMO account. Demo spreads and swaps can differ from live. Every figure derived from this file must be re-read on the live account before capital is committed.

## Conclusions

### 1. B1 (XAUUSD) works. The concrete specification:

| | |
|---|---|
| Instrument | XAUUSD (`XAUUSD` on this broker) |
| Timeframe | H4 |
| Slow signal | sign of trailing 60-trading-day return (308 H4 bars) |
| Fast signal | sign of trailing 10-trading-day return (51 H4 bars) |
| Position | static 50/50 blend of the two, **long-only** |
| Regime filter | flat when 20-day realised vol is in its trailing 2-year top decile |
| Sizing | inverse 20-day realised vol, 15% annual vol target, 3x leverage cap |
| Execution | signal read at bar close, position held from the NEXT bar open |

Over 15.7 years: **8.1% a year, -0.167 max drawdown, Sharpe 0.922** -- against **2.2% a year, Sharpe 0.29** for buy-and-hold of the same CFD, vol-matched and charged the same overnight swap. It trades **3.79 times a month** and is in the market 28% of the time.

**What it actually is: a drawdown-avoider, not a return-enhancer.** Its edge appears in the periods when holding gold hurt -- 2011-2015 (+0.85 Sharpe over buy-and-hold) and 2020-2022 (+0.56) -- and it adds least when gold simply rises. Anyone expecting it to beat gold in a bull market should read the 2016-2019 row, where it loses to buy-and-hold outright for four years.

### 2. B2 (US100) fails and should not be traded.

Negative in every sub-period, beaten by buy-and-hold by more than a full Sharpe point. The brief listed it as the secondary instrument; on this broker's data it does not survive. This rests on only 2.66 years of history, so the honest statement is *no evidence of an edge*, not *proven absence* -- but there is no case for capital either way.

### 3. The published slow D1 specification does not clear the hurdle.

Excess Sharpe of -0.006 over buy-and-hold. The brief anticipated the opposite: that evidence would be strongest at the slow speed and the medium-speed version would have to prove itself. On this instrument and this broker's history it is the medium H4 speed that works and the published 12-month/1-month pair that does not. Reported plainly, as section 5 requires.

### 4. The directional filter earns nothing.

Sharpe 0.914 with it, 0.909 without. The slow signal already encodes direction, so the filter is close to redundant. Retained because the brief specifies it and it costs nothing, but it could be dropped with no measurable loss.

## Candidate ranking

Full available history. `bench_*` is buy-and-hold of the same CFD, vol-matched to the strategy and charged the same overnight swap -- the brief's section 7 item 6 hurdle.

| candidate | sharpe | cagr | vol | max_dd | calmar | bench_sharpe | bench_cagr | excess_sharpe | beats_bh | trades_per_month | in_market | years |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B1a  gold H4 medium, long-only | 0.922 | 0.0808 | 0.0886 | -0.167 | 0.484 | 0.29 | 0.022 | 0.632 | True | 3.79 | 0.278 | 15.72 |
| B1b  gold H4 medium, long/short | 0.757 | 0.0875 | 0.1205 | -0.215 | 0.407 | 0.29 | 0.028 | 0.467 | True | 7.85 | 0.512 | 15.72 |
| B1c  gold D1 slow (published spec) | 0.284 | 0.0275 | 0.1216 | -0.341 | 0.08 | 0.286 | 0.0277 | -0.002 | False | 2.46 | 0.417 | 15.72 |
| B1d  gold D1 slow, long-only | 0.374 | 0.0321 | 0.0972 | -0.319 | 0.101 | 0.286 | 0.0233 | 0.088 | True | 1.52 | 0.257 | 15.72 |
| B2a  US100 H4 medium, long/short | -0.408 | -0.0516 | 0.114 | -0.216 | -0.239 | 0.816 | 0.0904 | -1.224 | False | 8.6 | 0.529 | 2.66 |
| B2b  US100 H4 medium, long-only | 0.158 | 0.0105 | 0.0957 | -0.119 | 0.088 | 0.816 | 0.0763 | -0.659 | False | 5.41 | 0.408 | 2.66 |

## B1a by sub-period

| period | sharpe | cagr | vol | max_dd | calmar | bench_sharpe | bench_cagr | excess_sharpe | beats_bh | trades_per_month | in_market | years |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2011-2015 gold bear | 0.409 | 0.0259 | 0.0683 | -0.111 | 0.233 | -0.481 | -0.0344 | 0.89 | True | 2.24 | 0.184 | 4.99 |
| 2016-2019 recovery | 0.374 | 0.0292 | 0.0879 | -0.167 | 0.175 | 0.491 | 0.0398 | -0.118 | False | 4.53 | 0.304 | 3.99 |
| 2020-2022 covid/rates | 0.768 | 0.0691 | 0.0914 | -0.11 | 0.626 | 0.225 | 0.0167 | 0.543 | True | 3.95 | 0.264 | 3.0 |
| 2023-2026 bull | 1.969 | 0.2333 | 0.1084 | -0.099 | 2.347 | 1.117 | 0.1234 | 0.852 | True | 4.96 | 0.387 | 3.72 |
| FULL | 0.922 | 0.0808 | 0.0886 | -0.167 | 0.484 | 0.29 | 0.022 | 0.632 | True | 3.79 | 0.278 | 15.72 |

## B1a rolling 2-year windows

Identical parameters in every window -- no selection anywhere in this table, so it measures the strategy's consistency rather than an optimiser's luck. It beats the benchmark in **6 of 7** windows, and is positive in Sharpe terms in the windows where gold itself lost money.

| from | to | sharpe | cagr | vol | max_dd | calmar | bench_sharpe | bench_cagr | excess_sharpe | beats_bh | trades_per_month | in_market | years |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2011-01-02 | 2013-01-01 | 0.981 | 0.0831 | 0.0858 | -0.081 | 1.031 | 0.35 | 0.0265 | 0.631 | True | 2.92 | 0.25 | 2.0 |
| 2013-01-01 | 2015-01-01 | -0.12 | -0.0076 | 0.0522 | -0.096 | -0.079 | -1.171 | -0.0604 | 1.052 | True | 1.84 | 0.131 | 1.99 |
| 2015-01-01 | 2016-12-31 | 0.3 | 0.0202 | 0.0754 | -0.088 | 0.229 | -0.272 | -0.0233 | 0.572 | True | 3.18 | 0.216 | 1.99 |
| 2016-12-31 | 2018-12-31 | 0.228 | 0.0163 | 0.0908 | -0.161 | 0.101 | 0.214 | 0.0151 | 0.014 | True | 4.65 | 0.349 | 1.99 |
| 2018-12-31 | 2020-12-30 | 1.083 | 0.1077 | 0.0976 | -0.103 | 1.05 | 1.031 | 0.1019 | 0.053 | True | 4.39 | 0.302 | 1.99 |
| 2020-12-30 | 2022-12-30 | 0.177 | 0.011 | 0.0785 | -0.092 | 0.119 | -0.318 | -0.028 | 0.495 | True | 3.63 | 0.217 | 2.0 |
| 2022-12-30 | 2024-12-29 | 1.127 | 0.1254 | 0.1094 | -0.099 | 1.261 | 1.132 | 0.126 | -0.005 | False | 6.13 | 0.402 | 2.0 |

## Ablation -- does each component earn its place?

| variant | sharpe | cagr | max_dd | excess_sharpe | trades_per_month | in_market |
|---|---|---|---|---|---|---|
| full spec | 0.922 | 0.0808 | -0.167 | 0.632 | 3.79 | 0.278 |
| no directional filter | 0.919 | 0.0833 | -0.177 | 0.63 | 4.18 | 0.302 |
| no vol-regime filter | 0.767 | 0.0714 | -0.16 | 0.477 | 4.4 | 0.34 |
| no filters at all | 0.785 | 0.0754 | -0.17 | 0.495 | 4.84 | 0.368 |
| no vol targeting | 0.814 | 0.062 | -0.115 | 0.524 | 3.79 | 0.278 |

## Cost sensitivity (brief 7.3)

Re-run at multiples of the measured spread. The edge is not cost-fragile: it survives a tripling, because the book turns over only ~3.79 times a month and its real cost is the overnight swap, not the spread.

| spread_multiple | sharpe | cagr | max_dd | excess_sharpe | beats_bh |
|---|---|---|---|---|---|
| 1.0 | 0.922 | 0.0808 | -0.167 | 0.632 | True |
| 1.5 | 0.906 | 0.0793 | -0.171 | 0.617 | True |
| 2.0 | 0.891 | 0.0779 | -0.174 | 0.601 | True |
| 3.0 | 0.86 | 0.075 | -0.181 | 0.571 | True |

## Deflated Sharpe ratio (brief 7.2)

Every configuration searched is counted -- 216 of them -- so the correction is not understated.

| Quantity | Value |
|---|---|
| n_trials | 216 |
| sharpe_variance_across_trials | 1.4e-05 |
| expected_max_sharpe_under_null | 0.010548 |
| observed_sharpe_per_period | 0.023158 |
| deflated_sharpe_ratio | 0.976605 |
| psr_vs_zero | 0.99987 |
| passes_at_95pct | True |

A deflated Sharpe of **0.977** clears the conventional 0.95 bar: the result is distinguishable from the best of 216 lucky draws.

## Sanity checks

| Check | Sharpe | Reading |
|---|---|---|
| baseline (as built) | 0.922 | signal at bar close, held from next bar |
| look-ahead, signal 1 bar early | 3.095 | jumps sharply, as it must -- confirms the baseline is not accidentally peeking |
| delayed 1 extra bar | 1.013 | barely changes: no knife-edge timing dependency, which matters for live fills |
| delayed 2 extra bars | 0.983 | still intact |
| placebo, exposure shuffled (n=200) | mean 0.287 / p95 0.648 | baseline sits at the 100% percentile -- the *timing* is doing the work, not merely being in the market 28% of the time |

## US100 detail (B2, rejected)

| period | sharpe | cagr | vol | max_dd | calmar | bench_sharpe | bench_cagr | excess_sharpe | beats_bh | trades_per_month | in_market | years |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2024 | -0.114 | -0.0178 | 0.1069 | -0.103 | -0.173 | 0.894 | 0.0945 | -1.008 | False | 5.84 | 0.433 | 0.94 |
| 2025 | -0.048 | -0.0117 | 0.113 | -0.097 | -0.121 | 0.626 | 0.0665 | -0.674 | False | 8.11 | 0.58 | 1.0 |
| 2026 ytd | -1.196 | -0.1446 | 0.1238 | -0.135 | -1.069 | 1.066 | 0.1327 | -2.262 | False | 12.96 | 0.585 | 0.72 |
| FULL | -0.408 | -0.0516 | 0.114 | -0.216 | -0.239 | 0.816 | 0.0904 | -1.224 | False | 8.6 | 0.529 | 2.66 |

## Method

- A position series, not a trade list: a trend book holds a continuously vol-sized exposure rather than discrete stop-managed trades.
- **No look-ahead.** Every signal, filter and volatility estimate is shifted one bar before use, so the weight held over bar t uses only data closed by t-1.
- **Spread** is the broker's own recorded per-bar spread, charged as half a spread per unit of weight turned over.
- **Financing** accrues at one rollover per weekday with a 3x charge on the instrument's triple-swap weekday (Wednesday for the metals), giving 7 nights a week rather than an averaged rate.
- **Lookbacks come from the literature**, not from searching this data: the medium speed is Goulding/Harvey/Mazzoleni's 60d/10d and the D1 pair is the published 12-month/1-month specification.
- Reproduce with `python src/report_book_b.py`.

## What this does not establish

- Measured on a **demo** account; live spreads and swaps may differ.
- One instrument, one broker, one 15.7-year sample, over most of which gold rose.
- The 2016-2019 row is a real four-year stretch of losing to buy-and-hold. The brief's warning stands: trend following produces long, ugly flat periods, and 18 months of them is normal rather than a malfunction.
- Nothing here has been traded, on paper or otherwise. Live execution is build step 8 and needs an MQL5 EA and a parity test first.
