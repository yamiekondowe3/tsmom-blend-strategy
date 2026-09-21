# Data coverage -- what the broker actually provided

Generated 2026-09-21 21:35 UTC from `6289430@Deriv-Demo` (DEMO).

Server clock offset vs UTC: **0.0 h** (measured; method: tick time of 'Volatility 75 Index' vs UTC now). All timestamps in `data/` are UTC.

> **Provisional.** Costs read from a DEMO account. Demo spreads and swaps can differ from live. Every figure derived from this file must be re-read on the live account before capital is committed.

## Headline: the index CFDs are far short of the 5-year minimum

The brief (section 3.1) asks for **5 years minimum** per symbol. These did not reach it:

- **US100 D1** -- 2.66y (from 2024-01-22), short by 2.34y
- **US100 H4** -- 2.66y (from 2024-01-22), short by 2.34y
- **US100 H1** -- 2.66y (from 2024-01-22), short by 2.34y
- **US500 D1** -- 2.66y (from 2024-01-22), short by 2.34y
- **US500 H4** -- 2.66y (from 2024-01-22), short by 2.34y
- **US500 H1** -- 2.66y (from 2024-01-22), short by 2.34y

Deriv's index CFD listings begin 2024-01-22. This is a hard limit of the broker's own history, not a truncation this script can fix: `Max bars in chart` is already 100,000,000 and the request asked for history from 2010.

**What it means for the screen.** Pair A1 (US100/US500) is screened on ~2.66 years. That is adequate for a spread-cost ratio, which is a short-horizon quantity, but it is thin for a half-life estimate and it contains no pre-2024 regime at all -- no 2022 rate shock, no COVID. A1's verdict should be read as provisional on that basis whichever way it lands. Pair A2 (XAUUSD/XAGUSD) has 15.7 years and carries no such caveat.

## Per symbol and timeframe

| Symbol | TF | Bars | From | To | Years | Meets 5y |
|---|---|---|---|---|---|---|
| US100 | D1 | 833 | 2024-01-22 | 2026-09-21 | 2.66 | **NO** |
| US100 | H4 | 4,269 | 2024-01-22 | 2026-09-21 | 2.66 | **NO** |
| US100 | H1 | 15,746 | 2024-01-22 | 2026-09-21 | 2.66 | **NO** |
| US500 | D1 | 833 | 2024-01-22 | 2026-09-21 | 2.66 | **NO** |
| US500 | H4 | 4,269 | 2024-01-22 | 2026-09-21 | 2.66 | **NO** |
| US500 | H1 | 15,740 | 2024-01-22 | 2026-09-21 | 2.66 | **NO** |
| XAUUSD | D1 | 4,852 | 2011-01-02 | 2026-09-21 | 15.72 | yes |
| XAUUSD | H4 | 24,895 | 2011-01-02 | 2026-09-21 | 15.72 | yes |
| XAUUSD | H1 | 92,132 | 2011-01-02 | 2026-09-21 | 15.72 | yes |
| XAGUSD | D1 | 4,860 | 2011-01-02 | 2026-09-21 | 15.72 | yes |
| XAGUSD | H4 | 24,980 | 2011-01-02 | 2026-09-21 | 15.72 | yes |
| XAGUSD | H1 | 92,496 | 2011-01-02 | 2026-09-21 | 15.72 | yes |

## Observed bars per trading day

Measured from the data, not assumed. Used to convert an OU half-life in bars into days for the brief's 5-day drop rule. Assuming 24 H1 bars/day would overstate bars/day (these CFDs take a daily break and close at weekends) and so understate the half-life in days -- biasing pairs *towards* passing.

| Symbol | TF | Bars/day | Bars | Trading days |
|---|---|---|---|---|
| US100 | D1 | 1.0 | 833 | 833 |
| US100 | H4 | 5.1248 | 4,269 | 833 |
| US100 | H1 | 18.9028 | 15,746 | 833 |
| US500 | D1 | 1.0 | 833 | 833 |
| US500 | H4 | 5.1248 | 4,269 | 833 |
| US500 | H1 | 18.8956 | 15,740 | 833 |
| XAUUSD | D1 | 1.0 | 4,852 | 4,852 |
| XAUUSD | H4 | 5.1309 | 24,895 | 4,852 |
| XAUUSD | H1 | 18.9885 | 92,132 | 4,852 |
| XAGUSD | D1 | 1.0 | 4,860 | 4,860 |
| XAGUSD | H4 | 5.1399 | 24,980 | 4,860 |
| XAGUSD | H1 | 19.0321 | 92,496 | 4,860 |

## Leg alignment

A pair can only be traded on bars where **both** legs quote. The overlap is the real sample size; bars present on one leg only are dropped.

| Pair | TF | Overlap | Years | Common bars | Dropped | % dropped |
|---|---|---|---|---|---|---|
| US100/US500 | D1 | 2024-01-22..2026-09-21 | 2.66 | 833 | 0 | 0.0% |
| US100/US500 | H4 | 2024-01-22..2026-09-21 | 2.66 | 4,269 | 0 | 0.0% |
| US100/US500 | H1 | 2024-01-22..2026-09-21 | 2.66 | 15,739 | 8 | 0.05% |
| XAUUSD/XAGUSD | D1 | 2011-01-02..2026-09-21 | 15.72 | 4,849 | 14 | 0.29% |
| XAUUSD/XAGUSD | H4 | 2011-01-02..2026-09-21 | 15.72 | 24,874 | 127 | 0.51% |
| XAUUSD/XAGUSD | H1 | 2011-01-02..2026-09-21 | 15.72 | 91,978 | 672 | 0.73% |

## Method

- Source: `MetaTrader5.copy_rates_range` via `common/data_fetch.py::fetch_mt5`, requesting 2010-01-01 to now so the broker returns its full depth.
- No third-party price feed was used anywhere (brief section 3.1).
- The `spread` column is the broker's own recorded per-bar spread, converted from MT5 integer points into price units.
- Price CSVs are gitignored as bulk data; regenerate with `python src/pull_history.py`.
