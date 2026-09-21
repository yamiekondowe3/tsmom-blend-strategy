# Cost table -- contract specs, swaps and measured spreads

Read 2026-09-21T21:47:05+00:00 UTC from `6289430@Deriv-Demo` (DEMO).

> **Provisional.** Costs read from a DEMO account. Demo spreads and swaps can differ from live. Every figure derived from this file must be re-read on the live account before capital is committed.

## The table (brief section 3.2)

| Instrument | Typical spread (pts) | Worst-case spread (pts) | Commission | Swap long | Swap short | Min lot | Lot step | Point value |
|---|---|---|---|---|---|---|---|---|
| US100 | 70.0 | 90.0 | 0.0 | -6.03 (-6.03%/yr) | 1.79 (1.79%/yr) | 0.1 | 0.1 | 0.01 |
| US500 | 31.0 | 31.0 | 0.0 | -6.03 (-6.03%/yr) | 1.79 (1.79%/yr) | 0.1 | 0.1 | 0.01 |
| XAUUSD | 15.0 | 28.0 | 0.0 | -45.0 (-3.781%/yr) | 20.0 (1.681%/yr) | 0.01 | 0.01 | 0.01 |
| XAGUSD | 25.0 | 40.0 | 0.0 | -10.41 (-5.755%/yr) | 3.16 (1.747%/yr) | 0.01 | 0.01 | 0.001 |

Commission: **zero, spread-only; confirmed by Dutch 2026-09-21**.

`Point value` is the price increment of one point. Note the two swap conventions in play -- the raw swap numbers are NOT comparable across rows:

- **US100**: `swap_mode=5` (INTEREST_CURRENT), triple-swap on weekday 5 -- -5.041989 price units per unit held per night when long.
- **US500**: `swap_mode=5` (INTEREST_CURRENT), triple-swap on weekday 5 -- -1.283972 price units per unit held per night when long.
- **XAUUSD**: `swap_mode=1` (POINTS), triple-swap on weekday 3 -- -0.45 price units per unit held per night when long.
- **XAGUSD**: `swap_mode=1` (POINTS), triple-swap on weekday 3 -- -0.01041 price units per unit held per night when long.

## Spread by session

Measured from tick history, not from `symbol_info().spread` (which is a single instant and would misstate the cost depending on when it happened to be read). Sessions are UTC; the server clock sits at offset 0.0 h so no conversion applies.

| Symbol | Session | Median (pts) | p95 (pts) | Median (price) | p95 (price) | Ticks sampled |
|---|---|---|---|---|---|---|
| US100 | Asia | 70.0 | 120.0 | 0.7 | 1.2 | 137,869 |
| US100 | London | 70.0 | 90.0 | 0.7 | 0.9 | 138,707 |
| US100 | NewYork | 70.0 | 70.0 | 0.7 | 0.7 | 226,066 |
| US100 | Rollover | 70.0 | 150.0 | 0.7 | 1.5 | 9,309 |
| US100 | ALL | 70.0 | 90.0 | 0.7 | 0.9 | 511,951 |
| US500 | Asia | 31.0 | 31.0 | 0.31 | 0.31 | 127,172 |
| US500 | London | 31.0 | 31.0 | 0.31 | 0.31 | 113,370 |
| US500 | NewYork | 31.0 | 31.0 | 0.31 | 0.31 | 170,493 |
| US500 | Rollover | 31.0 | 31.0 | 0.31 | 0.31 | 8,674 |
| US500 | ALL | 31.0 | 31.0 | 0.31 | 0.31 | 419,709 |
| XAUUSD | Asia | 17.0 | 18.0 | 0.17 | 0.18 | 706,029 |
| XAUUSD | London | 15.0 | 15.0 | 0.15 | 0.15 | 551,355 |
| XAUUSD | NewYork | 15.0 | 30.0 | 0.15 | 0.3 | 805,353 |
| XAUUSD | Rollover | 47.0 | 58.0 | 0.47 | 0.58 | 41,820 |
| XAUUSD | ALL | 15.0 | 28.0 | 0.15 | 0.28 | 2,104,557 |
| XAGUSD | Asia | 27.0 | 37.0 | 0.027 | 0.037 | 346,933 |
| XAGUSD | London | 25.0 | 36.0 | 0.025 | 0.036 | 271,186 |
| XAGUSD | NewYork | 25.0 | 40.0 | 0.025 | 0.04 | 474,245 |
| XAGUSD | Rollover | 40.0 | 50.0 | 0.04 | 0.05 | 11,340 |
| XAGUSD | ALL | 25.0 | 40.0 | 0.025 | 0.04 | 1,103,704 |

## Long-history cross-check

The session table above measures the last 30 days. The broker also records a spread on every H1 bar, which reaches back across the full history on disk. If the recent window were unusually calm, these columns would be visibly wider.

| Symbol | Tick median (price) | Bar median (price) | Bar p95 | Bar p99 | H1 bars |
|---|---|---|---|---|---|
| US100 | 0.7 | 0.7 | 0.7 | 0.7 | 15,498 |
| US500 | 0.31 | 0.31 | 0.36 | 0.36 | 15,722 |
| XAUUSD | 0.15 | 0.22 | 0.5 | 0.7 | 74,822 |
| XAGUSD | 0.025 | 0.029 | 3.0 | 4.0 | 82,393 |

## Method

- Tick source: `copy_ticks_range(..., COPY_TICKS_INFO)` over the last 30 days, pulled in 7-day chunks, retaining every 5th tick to bound memory. Ticks with a zero bid or ask are discarded as placeholders.
- Spread per tick = `ask - bid`, in price units; the points column divides by the symbol's own `point`.
- Swap converted to price units per unit per night: mode 1 -> `swap * point`; mode 5 -> `price * swap/100 / 365`.
- Commission is recorded from the account owner, not defaulted (brief 3.2).
