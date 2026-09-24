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

### Wed 2026-09-23 02:39
equity 9,995.05 (start 10,000.00, -0.05%) | peak 10,000.00 | DD -0.05% | held: BTCUSD 0.01, XAUUSDmicro 0.50
- fill: Wed 23 00:00 XAUUSDmicro buy 0.5 @ 4,364.17  P/L +0.00
- parity XAUUSD @ 09-23 00:00: EA == Python
- EVENT XAUUSD: fast signal -1 -> +1
- EVENT XAUUSD: entered (w 0.000 -> 0.475)
- parity BTCUSD @ 09-23 00:00: EA == Python
- no findings

### Wed 2026-09-23 06:39
equity 9,994.75 (start 10,000.00, -0.05%) | peak 10,000.00 | DD -0.05% | held: BTCUSD 0.01, XAUUSDmicro 0.50
- parity XAUUSD @ 09-23 04:00: EA == Python
- parity BTCUSD @ 09-23 04:00: EA == Python
- no findings

### Wed 2026-09-23 09:47
equity 9,973.30 (start 10,000.00, -0.27%) | peak 10,000.00 | DD -0.27% | held: BTCUSD 0.01, XAUUSDmicro 0.50
- parity XAUUSD @ 09-23 04:00: EA == Python
- parity BTCUSD @ 09-23 04:00: EA == Python
- no findings

### Wed 2026-09-23 10:39
equity 9,971.35 (start 10,000.00, -0.29%) | peak 10,000.00 | DD -0.29% | held: BTCUSD 0.01, XAUUSDmicro 0.50
- parity XAUUSD @ 09-23 08:00: EA == Python
- parity BTCUSD @ 09-23 08:00: EA == Python
- no findings

### Wed 2026-09-23 14:39
equity 9,961.10 (start 10,000.00, -0.39%) | peak 10,000.00 | DD -0.39% | held: BTCUSD 0.01
- fill: Wed 23 12:00 XAUUSDmicro sell 0.5 @ 4,309.52  P/L -27.33
- parity XAUUSD @ 09-23 12:00: EA == Python
- EVENT XAUUSD: fast signal +1 -> -1
- EVENT XAUUSD: exited (w 0.474 -> 0.000)
- parity BTCUSD @ 09-23 12:00: EA == Python
- no findings

### Wed 2026-09-23 18:39
equity 9,946.95 (start 10,000.00, -0.53%) | peak 10,000.00 | DD -0.53% | held: BTCUSD 0.01
- parity XAUUSD @ 09-23 12:00: EA == Python
- parity BTCUSD @ 09-23 12:00: EA == Python
- no findings

### Wed 2026-09-23 18:40
Book B equity 9,946.16 (start 10,000.00, -0.54%) | peak 10,000.00 | DD -0.54% | held: BTCUSD 0.01
- **FINDING** EA NOT ATTACHED -- TSMOM_Blend_EA removed 23/09 14:23. Book B is not being managed; any open Book B position is orphaned.
- parity XAUUSD @ 09-23 12:00: EA == Python
- parity BTCUSD @ 09-23 12:00: EA == Python

## Finding 2 (2026-09-23 14:23): Book B was removed from the terminal

At 14:23 local the terminal exited cleanly and relaunched from
`vrp-index-strategy\mql5\start_demo.ini`. That start config loads only
`VRP_Index_EA` (US SP 500, H1, preset `VRP_demo_2000.set`), so
`TSMOM_Blend_EA` was removed. Its last decision was the 12:00 broker bar; the
16:00 bar was never acted on.

- The BTCUSD 0.01 Book B position (magic 20260922) is still open and now
  **unmanaged**.
- The gold sleeve was flat at removal (it exited at 12:00 for -27.33).
- The VRP EA shares the same demo account, so **account equity no longer
  measures Book B**. The watcher now computes Book B equity from magic-20260922
  deals and positions only.
- The watcher missed this for ~4h: the terminal process was alive and EA
  silence was under the 5h threshold. It now also reads the terminal journal
  for `TSMOM_Blend_EA` load/remove events.

Not restarted: the change came from outside this watch, and putting Book B back
means choosing how the two strategies share the one terminal and account.

### Wed 2026-09-23 22:40
Book B equity 9,950.15 (start 10,000.00, -0.50%) | peak 10,000.00 | DD -0.50% | held: BTCUSD 0.01
- **FINDING** EA NOT ATTACHED -- TSMOM_Blend_EA removed 23/09 14:23. Book B is not being managed; any open Book B position is orphaned.
- **FINDING** EA SILENT for 8.7h on a trading day -- last decision logged Wed 14:00.
- parity XAUUSD @ 09-23 12:00: EA == Python
- parity BTCUSD @ 09-23 12:00: EA == Python

### Wed 2026-09-23 23:17
Book B equity 9,948.93 (start 10,000.00, -0.51%) | peak 10,000.00 | DD -0.51% | held: BTCUSD 0.01
- **FINDING** EA SILENT for 9.3h on a trading day -- last decision logged Wed 14:00.
- parity XAUUSD @ 09-23 12:00: EA == Python
- parity BTCUSD @ 09-23 12:00: EA == Python

## 2026-09-23 23:15: Book B re-attached by hand

Dutch attached `TSMOM_Blend_EA` to the XAUUSD H4 chart manually (first with
defaults, which the EA refused to trade -- `AllowLiveTrading=false` -- then with
`TSMOM_demo.set`: exec XAUUSDmicro, 10% vol). A manually attached EA is saved in
the chart profile, so a restart from another strategy's start config should no
longer drop it. Gold was in its daily break (last tick 20:58:59 broker), so
the first decision waits for the reopen.

`VRP_Index_EA` was removed from its US SP 500 H1 chart at 23:16:26; it held no
positions.

### Thu 2026-09-24 00:07
Book B equity 9,950.48 (start 10,000.00, -0.50%) | peak 10,000.00 | DD -0.50% | held: BTCUSD 0.01
- parity XAUUSD @ 09-23 20:00: EA == Python
- parity BTCUSD @ 09-23 20:00: EA == Python
- no findings

### Thu 2026-09-24 02:39
Book B equity 9,948.63 (start 10,000.00, -0.51%) | peak 10,000.00 | DD -0.51% | held: BTCUSD 0.01
- parity XAUUSD @ 09-24 00:00: EA == Python
- parity BTCUSD @ 09-24 00:00: EA == Python
- no findings

### Thu 2026-09-24 06:39
Book B equity 9,944.28 (start 10,000.00, -0.56%) | peak 10,000.00 | DD -0.56% | held: BTCUSD 0.01
- parity XAUUSD @ 09-24 04:00: EA == Python
- parity BTCUSD @ 09-24 04:00: EA == Python
- no findings

### Thu 2026-09-24 09:47
Book B equity 9,949.16 (start 10,000.00, -0.51%) | peak 10,000.00 | DD -0.51% | held: BTCUSD 0.01
- parity XAUUSD @ 09-24 04:00: EA == Python
- parity BTCUSD @ 09-24 04:00: EA == Python
- no findings
