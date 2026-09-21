# tsmom-blend-strategy

Book B of the two-book quant project: **time-series momentum on XAUUSD**, using
the slow/fast blended signal from Goulding, Harvey & Mazzoleni (JFE 2023)
rather than a single slow signal. Traded through MT5 on a Deriv account.

Book A, the statistical-arbitrage book, lives in the sibling repo
[`statarb-pairs-strategy`](https://github.com/yamiekondowe3/statarb-pairs-strategy).
The full project brief is in [`docs/handoff.md`](docs/handoff.md).

## Status: backtested and validated. Not yet traded.

Build steps 1–4 of 9 are done. The MQL5 EA (step 6), the Python/MQL5 parity
test (step 7) and any live or demo execution (step 8) have not been started.
Everything in this repo is read-only against MT5.

## Honesty notice

**A validated backtest is not a track record.** This survives the controls the
brief demands — walk-forward, deflated Sharpe, cost sensitivity, a plateau
check, a placebo and a look-ahead test — on one instrument, one broker, and one
15.7-year sample over most of which gold rose. It has never traded.

## The strategy

| | |
|---|---|
| Instrument | XAUUSD (`XAUUSD` on this broker) |
| Timeframe | H4 |
| Slow signal | sign of trailing 60-trading-day return (308 H4 bars) |
| Fast signal | sign of trailing 10-trading-day return (51 H4 bars) |
| Position | static 50/50 blend of the two, **long-only** |
| Regime filter | flat when 20-day realised vol is in its trailing 2-year top decile |
| Sizing | inverse 20-day realised vol, 15% annual vol target, 3× leverage cap |
| Execution | signal read at bar close, position held from the **next** bar |

Lookbacks are the literature's, not values found by searching this data.

### Results, 15.7 years, net of measured spread and per-night swap

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
```

## Safety

**Read-only against MT5.** No script calls `order_send`, `order_check`, or any
function that places, modifies or closes an order or position. Per the brief
(section 2) that holds until build step 8 and lifts only on explicit
instruction.

## Next step

Build step 6: the MQL5 EA, then the step 7 parity test — running the same date
range through Python and MQL5 and reconciling trade by trade. The brief flags
that as the classic backtest-to-live failure and worth more effort than it looks.
