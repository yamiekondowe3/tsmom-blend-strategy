# Book B demo journal

One entry per `src/watch_book_b.py` run. FINDING lines are the ones that need attention.

### Wed 2026-09-23 01:19
equity 9,996.93 (start 10,000.00, -0.03%) | peak 10,000.00 | DD -0.03% | held: BTCUSD 0.01
- fill: Tue 22 19:00 BTCUSD buy 0.02 @ 86,435.55  P/L +0.00
- fill: Tue 22 20:37 BTCUSD sell 0.01 @ 86,289.05  P/L -1.47
- parity XAUUSD @ 09-22 20:00: EA == Python
- parity BTCUSD @ 09-22 20:00: EA == Python
- no findings

## Finding 1 (2026-09-23): BTC is not managed while gold is closed

The EA acts in `OnTick`, and `OnTick` only fires on ticks of the chart symbol,
XAUUSD. From Friday's gold close to Sunday's reopen (and in gold's daily break)
the EA does not run, so the BTC sleeve holds whatever it held last.

Tester parity could not see this: it compares only bars where the EA wrote a
row, and the EA writes no rows on those bars.

Measured by freezing BTC's weight on every bar with no XAUUSD bar
(scratch replication of the EA's clock, same costs and financing as `book_b.run`):

| Period | Backtest (24/7) Sharpe | EA as deployed Sharpe | CAGR | Max DD |
|---|---|---|---|---|
| 2011-now | 1.481 | 1.473 | 11.1% vs 11.1% | -12.3% vs -12.2% |
| 2020-now | 1.312 | 1.266 | 12.7% vs 12.3% | -10.4% vs -8.9% |
| 2024-now | 1.078 | 1.089 | 10.0% vs 10.1% | -7.4% vs -7.3% |

- 24.3% of BTC bars fall while the EA is asleep; 25.2% of weight changes land on them.
- **101 of 465 full BTC exits would be delayed** until gold reopens, up to ~48h.

On average the cost is small. The risk is in the tail: a weekend BTC sell-off
that flips the signal is not acted on until Sunday night. The fix is an
`EventSetTimer` + `OnTimer` that runs the same per-bar logic, which is
independent of the chart symbol. **Not applied**: it changes the running EA and
needs a decision. Until then, `watch_book_b.py` reports any weekend gap in which
BTC's signal has flipped and the position has not.
