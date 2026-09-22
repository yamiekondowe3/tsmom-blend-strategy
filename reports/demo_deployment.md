# Demo deployment -- build step 8

**Running.** `TSMOM_Blend_EA` is attached to XAUUSD H4 on **Deriv-Demo 6289430**
and trading both sleeves. Deployed 2026-09-22 21:00 UTC on explicit
instruction.

## What is running

| | |
|---|---|
| Account | Deriv-Demo 6289430, $10,000, `trade_mode=0` (demo) |
| Expert | `TSMOM_Blend_EA`, one instance on XAUUSD H4, trading XAUUSD **and** BTCUSD |
| Preset | `mql5/TSMOM_demo.set` |
| Magic number | 20260922 |
| Spec | exactly the parity-verified one -- no parameter changed for deployment |

One multi-symbol instance rather than two charts, so the portfolio kill switch
and the netting decision live in a single place.

### First decisions, 2026-09-22 16:00 bar

```
XAUUSD | slow +1 fast -1 | flat N | scale 0.713 | w 0.0000 | want 0.0000 lots -> 0.00
BTCUSD | slow +1 fast +1 | flat N | scale 0.512 | w 0.5123 | want 0.0296 lots -> 0.02
```

Gold is in a **Correction** state (slow up, fast down); the 50/50 blend cancels
to zero and it holds nothing. That is the specification working, not a failure.
BTC is in **Bull** and opened **0.02 lots at 86,435.55**, $1,729 notional,
17.3% of equity.

## The thing to fix first: lot granularity at $10,000

This is the one material gap between the backtest and this account, and it is
about account size, not the strategy.

| | Minimum position | Smallest tradable weight | Effect at $10k |
|---|---|---|---|
| XAUUSD | 0.01 lots = 100 oz = **$4,354** | **0.867** | only **39.5%** of the last year's in-market bars are tradable at all |
| BTCUSD | 0.01 lots = **$865** | 0.172 | tradable, but coarse: the first fill wanted 0.0296 lots and got 0.02, a **32% shortfall** |

Gold's median in-market weight over the last year is **0.782** — *below* its own
minimum. So at this balance the gold sleeve will sit out most of the signals it
generates, and the ones it does take will be a fixed 0.01 lots regardless of
what the vol target asked for. The backtest holds a continuous weight and
therefore overstates what this account can reproduce.

**Recommended: top the demo balance up to $25,000-$50,000.** At $25k gold's
smallest tradable weight falls to 0.347, comfortably under its 10th-percentile
weight of 0.688, and BTC's granularity error drops from ~32% to ~13%. That is a
change on Deriv's website, not something this project can do.

Until then the deployment is honest but partial: **BTC is trading close to
specification, gold is heavily quantised.** The EA logs every occurrence:

```
XAUUSD: target weight 0.7820 is below the minimum lot at this equity
        -- holding nothing. Needs equity >= 11145.
```

A simulation of lot rounding across the full history (`src/demo_sim.py`) shows
the effect costing only 0.007 Sharpe — but that number is flattered by history,
because gold traded near $1,400 for much of it and the lot floor barely bound.
At today's $4,354 it binds hard. Trust the table above, not that simulation.

## Safety

- The EA **refuses to trade on a real account**, independently of any setting,
  and alerts if one is detected. Only demo execution has been authorised.
- `AllowLiveTrading` defaults to **false** in the committed source. The only
  place it is true is `mql5/TSMOM_demo.set`, which exists because demo
  execution was explicitly authorised.
- Every Python script in this repository remains read-only against MT5; no
  Python code can place an order.
- Positions carry magic number 20260922, so the monitor and any future tooling
  can tell this strategy's positions from anything else on the account.

## Monitoring

```bash
python src/demo_monitor.py     # account, positions, recent deals, EA decisions
```

The EA writes a decision line per sleeve per H4 bar to the Experts log
(`MQL5/Logs/`), including why it is holding nothing when that is the case.

## How to stop it

Any one of these, in increasing order of finality:

1. Turn off **AutoTrading** in the terminal toolbar -- the EA keeps computing
   and logging but places no orders.
2. Remove the EA from the XAUUSD chart.
3. Close the terminal.

None of these closes existing positions. To flatten, close them manually in the
terminal; the EA will not reopen while AutoTrading is off.

## What this is not

A demo run is not evidence of an edge, and nothing here changes the
reservations already recorded:

- The deflated Sharpe does **not** clear 0.95 under the full 298-trial count.
- The independent harness fails the strategy when it is converted into a
  stop-managed system; the edge is in exposure management, not entry timing.
- BTC is the weaker sleeve on every independent test and remains probationary.

The purpose of this run is execution fidelity -- fills, swaps, session gaps,
rollovers, lot granularity -- not further evidence about the signal. A quarter
of demo trading answers "does the implementation behave as designed", and
nothing more.
