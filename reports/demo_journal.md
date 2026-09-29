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

### Thu 2026-09-24 10:39
Book B equity 9,943.90 (start 10,000.00, -0.56%) | peak 10,000.00 | DD -0.56% | held: BTCUSD 0.01
- parity XAUUSD @ 09-24 08:00: EA == Python
- parity BTCUSD @ 09-24 08:00: EA == Python
- no findings

### Thu 2026-09-24 14:39
Book B equity 9,939.19 (start 10,000.00, -0.61%) | peak 10,000.00 | DD -0.61% | held: BTCUSD 0.01
- parity XAUUSD @ 09-24 12:00: EA == Python
- parity BTCUSD @ 09-24 12:00: EA == Python
- no findings

### Thu 2026-09-24 18:39
Book B equity 9,952.12 (start 10,000.00, -0.48%) | peak 10,000.00 | DD -0.48% | held: BTCUSD 0.01
- parity XAUUSD @ 09-24 16:00: EA == Python
- parity BTCUSD @ 09-24 16:00: EA == Python
- no findings

### Thu 2026-09-24 22:39
Book B equity 9,949.15 (start 10,000.00, -0.51%) | peak 10,000.00 | DD -0.51% | held: BTCUSD 0.01
- parity XAUUSD @ 09-24 20:00: EA == Python
- parity BTCUSD @ 09-24 20:00: EA == Python
- no findings

### Fri 2026-09-25 02:39
Book B equity 9,950.94 (start 10,000.00, -0.49%) | peak 10,000.00 | DD -0.49% | held: BTCUSD 0.01
- parity XAUUSD @ 09-25 00:00: EA == Python
- parity BTCUSD @ 09-25 00:00: EA == Python
- no findings

### Fri 2026-09-25 06:39
Book B equity 9,947.04 (start 10,000.00, -0.53%) | peak 10,000.00 | DD -0.53% | held: BTCUSD 0.01
- parity XAUUSD @ 09-25 04:00: EA == Python
- parity BTCUSD @ 09-25 04:00: EA == Python
- no findings

### Fri 2026-09-25 09:47
Book B equity 9,944.53 (start 10,000.00, -0.55%) | peak 10,000.00 | DD -0.55% | held: BTCUSD 0.01
- parity XAUUSD @ 09-25 04:00: EA == Python
- parity BTCUSD @ 09-25 04:00: EA == Python
- no findings

### Fri 2026-09-25 10:40
Book B equity 9,948.28 (start 10,000.00, -0.52%) | peak 10,000.00 | DD -0.52% | held: BTCUSD 0.01
- parity XAUUSD @ 09-25 08:00: EA == Python
- parity BTCUSD @ 09-25 08:00: EA == Python
- no findings

### Fri 2026-09-25 14:39
Book B equity 9,949.76 (start 10,000.00, -0.50%) | peak 10,000.00 | DD -0.50% | held: BTCUSD 0.01
- parity XAUUSD @ 09-25 12:00: EA == Python
- parity BTCUSD @ 09-25 12:00: EA == Python
- no findings

### Fri 2026-09-25 18:39
Book B equity 9,944.32 (start 10,000.00, -0.56%) | peak 10,000.00 | DD -0.56% | held: BTCUSD 0.01
- parity XAUUSD @ 09-25 16:00: EA == Python
- EVENT XAUUSD: fast signal -1 -> +1
- parity BTCUSD @ 09-25 16:00: EA == Python
- no findings

### Fri 2026-09-25 22:39
Book B equity 9,946.57 (start 10,000.00, -0.53%) | peak 10,000.00 | DD -0.53% | held: BTCUSD 0.01
- parity XAUUSD @ 09-25 20:00: EA == Python
- parity BTCUSD @ 09-25 20:00: EA == Python
- no findings

### Sat 2026-09-26 02:39
Book B equity 9,942.39 (start 10,000.00, -0.58%) | peak 10,000.00 | DD -0.58% | held: BTCUSD 0.01
- parity XAUUSD @ 09-25 20:00: EA == Python
- parity BTCUSD @ 09-25 20:00: EA == Python
- no findings

### Sat 2026-09-26 06:39
Book B equity 9,943.80 (start 10,000.00, -0.56%) | peak 10,000.00 | DD -0.56% | held: BTCUSD 0.01
- parity XAUUSD @ 09-25 20:00: EA == Python
- parity BTCUSD @ 09-25 20:00: EA == Python
- no findings

### Sat 2026-09-26 09:47
Book B equity 9,945.19 (start 10,000.00, -0.55%) | peak 10,000.00 | DD -0.55% | held: BTCUSD 0.01
- parity XAUUSD @ 09-25 20:00: EA == Python
- parity BTCUSD @ 09-25 20:00: EA == Python
- no findings

### Sat 2026-09-26 10:39
Book B equity 9,947.52 (start 10,000.00, -0.52%) | peak 10,000.00 | DD -0.52% | held: BTCUSD 0.01
- parity XAUUSD @ 09-25 20:00: EA == Python
- parity BTCUSD @ 09-25 20:00: EA == Python
- no findings

### Sat 2026-09-26 14:39
Book B equity 9,945.22 (start 10,000.00, -0.55%) | peak 10,000.00 | DD -0.55% | held: BTCUSD 0.01
- parity XAUUSD @ 09-25 20:00: EA == Python
- parity BTCUSD @ 09-25 20:00: EA == Python
- no findings

### Sat 2026-09-26 18:39
Book B equity 9,945.96 (start 10,000.00, -0.54%) | peak 10,000.00 | DD -0.54% | held: BTCUSD 0.01
- parity XAUUSD @ 09-25 20:00: EA == Python
- parity BTCUSD @ 09-25 20:00: EA == Python
- no findings

### Sat 2026-09-26 22:39
Book B equity 9,945.20 (start 10,000.00, -0.55%) | peak 10,000.00 | DD -0.55% | held: BTCUSD 0.01
- parity XAUUSD @ 09-25 20:00: EA == Python
- parity BTCUSD @ 09-25 20:00: EA == Python
- no findings

### Sun 2026-09-27 02:39
Book B equity 9,948.13 (start 10,000.00, -0.52%) | peak 10,000.00 | DD -0.52% | held: BTCUSD 0.01
- parity XAUUSD @ 09-25 20:00: EA == Python
- parity BTCUSD @ 09-25 20:00: EA == Python
- no findings

### Sun 2026-09-27 06:39
Book B equity 9,947.72 (start 10,000.00, -0.52%) | peak 10,000.00 | DD -0.52% | held: BTCUSD 0.01
- parity XAUUSD @ 09-25 20:00: EA == Python
- parity BTCUSD @ 09-25 20:00: EA == Python
- no findings

### Sun 2026-09-27 09:47
Book B equity 9,950.54 (start 10,000.00, -0.49%) | peak 10,000.00 | DD -0.49% | held: BTCUSD 0.01
- parity XAUUSD @ 09-25 20:00: EA == Python
- parity BTCUSD @ 09-25 20:00: EA == Python
- no findings

### Sun 2026-09-27 10:39
Book B equity 9,952.11 (start 10,000.00, -0.48%) | peak 10,000.00 | DD -0.48% | held: BTCUSD 0.01
- parity XAUUSD @ 09-25 20:00: EA == Python
- parity BTCUSD @ 09-25 20:00: EA == Python
- no findings

### Sun 2026-09-27 14:39
Book B equity 9,954.50 (start 10,000.00, -0.46%) | peak 10,000.00 | DD -0.46% | held: BTCUSD 0.01
- parity XAUUSD @ 09-25 20:00: EA == Python
- parity BTCUSD @ 09-25 20:00: EA == Python
- no findings

### Mon 2026-09-28 18:39
Book B equity 9,938.14 (start 10,000.00, -0.62%) | peak 10,000.00 | DD -0.62% | held: flat
- fill: Mon 28 16:00 BTCUSD sell 0.01 @ 83,318.26  P/L -33.06
- parity XAUUSD @ 09-28 16:00: EA == Python
- EVENT XAUUSD: fast signal +1 -> -1
- parity BTCUSD @ 09-28 16:00: EA == Python
- EVENT BTCUSD: fast signal +1 -> -1
- EVENT BTCUSD: exited (w 0.324 -> 0.000)
- no findings

## Finding 3 (2026-09-28): 22.7h offline over gold's reopen, then one stale decision

**What happened.** The terminal's broker connection had been dropping and
reconnecting all weekend (8 reconnects on Sunday morning alone). At Sun 16:10
local it dropped and stayed down until **Mon 14:50** -- 22.7 hours, spanning
gold's Sunday-night reopen. The EA made no decisions for the Mon 00:00, 04:00
and 08:00 bars. The scheduled watcher checks were also silent over the same
window, consistent with the machine sleeping or losing its connection; the
Windows power log shows no sleep events, so the cause is not confirmed.

**Stale first decision.** On reconnect (14:50) the EA acted on the 12:00 bar
before the missing bars had synced, and disagreed with Python on both sleeves:
it kept BTC long (w 0.319) where the full history says flat. At the next bar
(16:00) it matched again and exited BTC. The four decisions since Sunday were
re-checked individually: 2 mismatches, both that 14:50 decision.

**Cost.** None this time. Python would have exited BTC at the 12:00 open
(83,053); the EA sold at 83,318 -- being late made +$2.65 on 0.01 lots. The
weekend gap itself (Finding 1) did not bite: BTC's weight stayed 0.324-0.325.

**Changes.**
- `watch_book_b.py` now flags `TERMINAL OFFLINE` from `terminal_info().connected`.
- Proposed, **not applied**: the EA should skip a bar until
  `SERIES_SYNCHRONIZED` is true and the last closed H4 bar is the one expected,
  so a reconnect never trades on stale history. Same change window as the
  `OnTimer` fix for Finding 1.
- The real fix for both is a host that stays on (VPS or no-sleep settings).

### Mon 2026-09-28 18:41
Book B equity 9,938.14 (start 10,000.00, -0.62%) | peak 10,000.00 | DD -0.62% | held: flat
- parity XAUUSD @ 09-28 16:00: EA == Python
- parity BTCUSD @ 09-28 16:00: EA == Python
- no findings

### Tue 2026-09-29 02:39
Book B equity 9,938.14 (start 10,000.00, -0.62%) | peak 10,000.00 | DD -0.62% | held: flat
- other positions on the account (not Book B): 1 (US SP 500); account equity 9,938.22
- parity XAUUSD @ 09-29 00:00: EA == Python
- parity BTCUSD @ 09-29 00:00: EA == Python
- no findings

### Tue 2026-09-29 06:39
Book B equity 9,938.14 (start 10,000.00, -0.62%) | peak 10,000.00 | DD -0.62% | held: flat
- other positions on the account (not Book B): 1 (US SP 500); account equity 9,936.02
- parity XAUUSD @ 09-29 04:00: EA == Python
- parity BTCUSD @ 09-29 04:00: EA == Python
- no findings

### Tue 2026-09-29 09:47
Book B equity 9,938.14 (start 10,000.00, -0.62%) | peak 10,000.00 | DD -0.62% | held: flat
- other positions on the account (not Book B): 1 (US SP 500); account equity 9,938.04
- parity XAUUSD @ 09-29 04:00: EA == Python
- parity BTCUSD @ 09-29 04:00: EA == Python
- no findings

### Tue 2026-09-29 10:39
Book B equity 9,938.14 (start 10,000.00, -0.62%) | peak 10,000.00 | DD -0.62% | held: flat
- other positions on the account (not Book B): 1 (US SP 500); account equity 9,937.83
- parity XAUUSD @ 09-29 08:00: EA == Python
- parity BTCUSD @ 09-29 08:00: EA == Python
- no findings

### Tue 2026-09-29 14:39
Book B equity 9,938.14 (start 10,000.00, -0.62%) | peak 10,000.00 | DD -0.62% | held: flat
- other positions on the account (not Book B): 1 (US SP 500); account equity 9,939.09
- parity XAUUSD @ 09-29 12:00: EA == Python
- parity BTCUSD @ 09-29 12:00: EA == Python
- no findings

### Tue 2026-09-29 18:37
Book B equity 9,938.14 (start 10,000.00, -0.62%) | peak 10,000.00 | DD -0.62% | held: flat
- other positions on the account (not Book B): 1 (US SP 500); account equity 9,935.56
- parity XAUUSD @ 09-29 16:00: EA == Python
- parity BTCUSD @ 09-29 16:00: EA == Python
- no findings

## Weekly report: 2026-09-22 to 2026-09-29

**One week says nothing about performance.** At a 10% vol target a week's
return has a standard deviation of about 1.4%, and the expected weekly gain at
Sharpe ~1.7 is about 0.16%. A -0.62% week is 0.45 standard deviations -- noise.
The book was also mostly partly invested or flat. What a week *can* judge is
whether the live system does what the backtest assumes. That is what follows.

### Result
Book B equity 9,938.14 from 10,000.00: **-0.62%**, peak-to-trough -0.62%
against a -9.0% backtest maximum. Realised -61.86 over 3 round trips:

| Trade | P/L |
|---|---|
| BTCUSD 0.02 -> 0.01 resize on the vol-target change (Sep 22) | -1.47 |
| XAUUSDmicro 0.5 long, Sep 23 00:00 -> 12:00 (fast signal flipped back) | -27.33 |
| BTCUSD 0.01 long, held from Sep 22, exited Sep 28 16:00 | -33.06 (incl. financing) |

### Execution fidelity: good
- **Parity:** 45 watcher runs, 90 sleeve checks, 0 mismatches on the latest
  decision. A full audit of the 28 Sep outage window found one bad decision
  (Finding 3), taken on unsynced history right after a reconnect.
- **Fills vs targets:** every fill matched the EA's logged target; no
  duplicate positions, including after the manual re-attach, which adopted the
  existing BTC position.
- **Slippage beyond the spread** on the three bar-open fills: gold +0.2bp and
  +0.1bp, BTC +0.8bp -- $0.13 in total. (The two Sep 22 BTC fills were mid-bar
  redeploys and are not comparable to a bar open.)
- **To measure next week:** the live BTCUSD spread read 18.42 at 18:37 Tuesday
  against the 2.42 in the cost model (2.2bp vs 0.3bp at today's price). One
  snapshot proves nothing, but if it holds, BTC costs are understated at
  current prices. It is worth tick-sampling before trusting BTC's cost line.

### The weekend (Finding 1)
Gold closed Fri 25 Sep evening; the EA went quiet as expected. BTC's signal
held steady all weekend (w 0.324-0.325), so the frozen 0.01 BTC position was
exactly what the strategy wanted. **No cost this time.** The risk is
unchanged: 101 of 465 historical BTC exits fall while gold is shut.

### Findings
1. **BTC unmanaged while gold is closed.** Open. Fix: `OnTimer`. Not applied.
2. **EA removed by the VRP start config** (Sep 23 14:23, ~9h unmanaged).
   Resolved by manual attach, which persists in the chart profile. The watcher
   now detects EA removal and measures Book B from its own trades.
3. **22.7h offline over gold's reopen, then one stale decision** (Sep 27-28).
   Cost nil. The watcher now flags a broker disconnect. EA guard (wait for
   `SERIES_SYNCHRONIZED`) proposed, not applied. Root cause is the host.

### Recommendations
- Host the terminal somewhere that does not sleep or drop off Wi-Fi (VPS, or
  no-sleep settings on this laptop). Two of three findings trace to the host.
- Approve the two EA fixes as one change: `OnTimer` + history-sync guard,
  then re-run tester parity before redeploying.
- Keep running. Judge performance after a quarter, not a week.
