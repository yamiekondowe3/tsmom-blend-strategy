# tsmom-blend-strategy

Book B of the two-book quant project: **time-series momentum on XAUUSD
(primary) and US100 (secondary)**, using the slow/fast blended signal from
Goulding, Harvey & Mazzoleni (JFE 2023) rather than a single slow signal.
Traded through MT5 on a Deriv account.

Book A, the statistical-arbitrage book, lives in the sibling repo
[`statarb-pairs-strategy`](https://github.com/yamiekondowe3/statarb-pairs-strategy).
The full project brief is in [`docs/handoff.md`](docs/handoff.md).

## Status: scaffolding and data only. No strategy code yet.

This repo currently contains the shared data loader, the broker cost table, and
the coverage report — nothing else. The signal, the backtest, the volatility
overlay and the MQL5 EA are build steps 3, 4 and 6 and have not been started.
Saying so plainly is the point: there is no result here to read yet.

Book B has no gate of its own at this stage. The brief's section 3.3 cost screen
is a *pair* screen and both candidate pairs belong to Book A, so it lives in the
sibling repo. The artifacts in `data/` and `reports/` here were produced by the
same scripts against the same account on the same date.

## Honesty notice

Nothing here has been backtested, and the brief is explicit about the hurdle
this book has to clear when it is:

- **The benchmark is vol-scaled buy-and-hold of the same instrument, not zero.**
  Kim, Tse & Wald (2016) found the large time-series-momentum alphas are mostly
  driven by volatility scaling, and Huang et al. (JFE 2020) found little
  asset-by-asset evidence of TSMOM in or out of sample. Gold's long uptrend will
  make almost any long-biased trend rule look good; only that benchmark
  separates the signal from the drift.
- **Trend following produces long, ugly drawdowns.** Eighteen months flat is
  normal, not a malfunction. If the plan is to abandon the system during that
  stretch, the backtest is irrelevant.

## What is here

Broker cost terms and history depth, read from **Deriv-Demo account 6289430** on
2026-09-21. Demo spreads and swaps can differ from live; every cost artifact is
stamped with a read date and a provisional flag, and must be re-read on the live
account before capital is committed.

Two findings from that read bear directly on this book:

- **US100 has only 2.66 years of history** on this broker (from 2024-01-22),
  against 15.7 years for XAUUSD. The brief asks for a 5-year minimum. That is a
  hard limit of Deriv's own history. A walk-forward on US100 will have very few
  independent windows, which is a real constraint on how much can be concluded
  about B2. See [`reports/data_coverage.md`](reports/data_coverage.md).
- **XAUUSD swap is negative in both directions**, at −3.78%/yr long against
  +1.68%/yr short. Multi-day trend holds pay this nightly, and the brief
  requires modelling it per bar held rather than as an average. See
  [`reports/cost_table.md`](reports/cost_table.md).

Spread figures are measured from tick history split by session — not from
`symbol_info().spread`, which is a single instant and misstates the cost
depending on when it happened to be read. XAUUSD's median London spread is 15
points against the 34 quoted at the daily rollover.

## Layout

```
src/resolve_symbols.py   resolve canonical names to broker spelling; server clock offset
src/pull_history.py      pull D1/H4/H1 history, report what actually arrived
src/build_costs.py       contract specs, swaps, session-split spreads from tick data
common/                  shared library, vendored from the trading-systems workspace
data/                    price CSVs (gitignored); costs.csv and config (tracked)
reports/                 data_coverage.md, cost_table.md
notebooks/  tests/  mql5/   empty — later build steps
```

Deriv does not use standard tickers: US100 is `US Tech 100` on this broker.
Always resolve through `common/data_fetch.py`'s `BROKER_SYMBOL_MAP` rather than
passing a canonical name to MT5 directly.

## Reproducing

Requires the MT5 terminal open and logged in to the account being measured.

```bash
pip install -r requirements.txt
python src/resolve_symbols.py    # writes data/symbol_map.json, broker_config.json
python src/pull_history.py       # writes data/*.csv, reports/data_coverage.md
python src/build_costs.py        # writes data/costs.csv, reports/cost_table.md
```

`build_costs.py` samples ~30 days of tick history across four symbols and takes
several minutes.

## Safety

Everything in this repo is **read-only against MT5**. No script calls
`order_send`, `order_check`, or any function that places, modifies or closes an
order or position. Per the brief (section 2) that constraint holds until build
step 8, and only lifts on explicit instruction.

## Next step

Build step 3: the Book B backtest. Per the brief's section 5 — H4 primary with
D1 as a slow comparison, a slow/fast signal crossed into four states (Bull,
Correction, Bear, Rebound), a static 50/50 blend as the baseline, parameters
chosen from a plateau rather than a peak, and the vol-scaled buy-and-hold
benchmark applied from the start rather than bolted on afterwards.
