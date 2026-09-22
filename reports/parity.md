# Python / MQL5 parity -- build step 7

The brief calls this the classic backtest-to-live failure and says it is worth
more effort than it looks. It earned that on the first run by blowing up the
test account.

## Result: steady-state parity is clean

The EA records its full decision state at every H4 bar; the Python backtest
reproduces the same state; the two are compared bar by bar over 2016-01 to
2026-08.

| Sleeve | Bars compared | Fields matching | Max abs difference | Trades matched |
|---|---|---|---|---|
| XAUUSD | 14,234 | 7 of 7 | 5.0e-09 | **462 / 462** |
| BTCUSD | 13,962 | 7 of 7 | 5.0e-09 | **585 / 585** |

Fields compared: slow signal, fast signal, realised vol, regime threshold,
regime flag, vol scale, target weight. Trade agreement is exact in both
directions -- **zero** bars where the EA traded and Python did not, and zero
where Python traded and the EA did not. The residual 5e-9 is `double`
rounding through the CSV, not a behavioural difference.

Strategy Tester economics over the same window, on the broker's own spreads,
swaps and lot rounding: **100,000 -> 322,124** across 10.7 years, about 11.6% a
year, no margin stop out. Python's portfolio model gives 11.9% a year over its
own (longer) window, so the two agree to well within lot-rounding noise.

## Two real defects this test caught

### 1. Hedging-account position stacking -- would have destroyed the account

The first tester run ended in June 2017 with a **margin stop out on 13% of the
testing interval** and a balance of 11,538 from a 100,000 deposit.

This account is in **hedging** mode, where each `Buy` opens a *separate*
position rather than adding to the existing one. The EA read only the first
matching position, so on every bar it believed it was flat and bought again --
accumulating dozens of simultaneous longs (#1176, #1180, #1184 … all open) until
margin ran out. The Python model holds a single net exposure.

Fixed: position size is now the **net** across all of the EA's positions in a
symbol, and reductions close or partially close existing longs rather than
issuing an opposing `Sell` (which on a hedging account would open yet another
position). Nothing in a Python backtest can surface this -- only running the
real order layer does.

### 2. The regime filter needs a long warm-up, and is wrong without it

All parity mismatches sit in the first stretch of the run and none after:

| Sleeve | Warm-up | Regime-threshold mismatch in warm-up | After warm-up |
|---|---|---|---|
| XAUUSD | 2,689 bars, to 2017-10-03 | 1,094 bars (40.7%) | 0 |
| BTCUSD | 2,192 bars, to 2017-12-04 | 1,357 bars (61.9%) | 0 |

The regime filter takes the 90th percentile of the last ~2,586 realised-vol
windows. Python has the full history on disk; inside the Strategy Tester the EA
can only see bars back to the test start, so early on it computes that
percentile from a smaller sample and gets a threshold up to 57% different. The
knock-on effect is small but real: 110 bars where gold's regime flag differed,
43 where the target weight differed.

**This is not only a test artifact.** A freshly deployed EA with a cold history
cache behaves exactly the same way. Before running this live, the terminal must
have **at least ~2,900 H4 bars (about two years) of history for each sleeve
already downloaded**, or the regime filter will mis-fire for its first year or
two. Signals, realised vol and sizing are unaffected -- those matched from the
very first bar.

## Method

- EA: [`mql5/TSMOM_Blend_EA.mq5`](../mql5/TSMOM_Blend_EA.mq5), compiled 0 errors,
  0 warnings. Multi-symbol, so the portfolio kill switch and sizing live in one
  place.
- Tester config: [`mql5/tester.ini`](../mql5/tester.ini). Model 2, "open prices
  only" -- the EA acts once per completed H4 bar, exactly as the Python
  backtest does, so a finer tick model would only add intrabar noise the
  strategy never looks at.
- Alignment: a row stamped T is the decision applied **over** bar T, computed
  from bars closed at or before T-1 -- Python's `pos.shift(1)`. Getting this
  off by one bar is the easiest way to fake a passing parity test.
- Reproduce: run the tester with that config, then `python src/parity.py`.

## Known remaining difference

The EA's kill switch builds the combined return series by pairing the two
symbols' bars **positionally**, while Python aligns them **by timestamp**. Gold
does not trade at weekends and BTC does, so those are not the same pairing.
It did not affect this comparison (the kill switch never fired differently over
the test window), but it is a genuine discrepancy and should be fixed before
live deployment rather than left to chance.

## Safety

The EA refuses to trade outside the Strategy Tester unless `AllowLiveTrading`
is explicitly set true; it is `false` in the committed config. Nothing here
placed an order on the account. Live or demo execution remains build step 8 and
needs explicit instruction.
