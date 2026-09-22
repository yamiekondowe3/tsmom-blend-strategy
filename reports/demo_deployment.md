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

## Can this run on a $50 account? No.

Asked directly, and the answer is no — because of lot granularity, not the
signal. On $50 the strategy wants about **$39** of gold exposure. The smallest
position the broker sells is **$437** (XAUUSDmicro), roughly **11× too big**.

Taking it anyway would mean fixed on/off exposure at ~8.7× leverage with the
inverse-vol sizing gone, which is precisely where the independent harness
located the edge. Historically that variant is not wiped out (worst
peak-to-trough −$28 of $50) but it runs a **56% drawdown** against the
validated −12.8%. It is a different, unvalidated system.

**The EA handles this correctly and automatically.** `TargetLots()` floors to
the lot step and returns zero below the minimum, so on a $50 account it holds
nothing and says why, at startup and on every bar:

```
WARNING XAUUSDmicro: the smallest position is 17.5x what a weight of 1.0 asks
for. This sleeve cannot be sized at this equity and will hold nothing.
```

### Minimum equity

| Configuration | Bare minimum | With sane granularity |
|---|---|---|
| Gold only (XAUUSDmicro) | $635 | **$2,795** |
| Both sleeves (micro gold + BTC) | $4,144 | **$15,869** |
| Both sleeves, standard XAUUSD | $12,706 | $55,893 |

"Bare minimum" means the 10th-percentile in-market weight is representable at
all. "Sane granularity" means about five lot steps at the median weight, so
sizing is not effectively binary. Below ~$2,800 only the gold sleeve can
participate, and coarsely.

## Solved: gold now executes on the micro contract

The gold sleeve's **signal** is still computed on XAUUSD — 24,900 H4 bars back
to 2011, needed for a 308-bar slow signal and a 2,586-bar regime lookback — but
the **order** is placed on **XAUUSDmicro**, whose own history only starts
2025-06-22 and could never support the signal.

Measured over the same 30-day tick window as the other traded instruments, the
micro contract costs the **same**:

| | Median spread | p95 spread | Swap long %/yr | Min position |
|---|---|---|---|---|
| XAUUSD | 0.150 | 0.280 | −3.7601 | $4,371 |
| XAUUSDmicro | **0.150** | **0.280** | −3.7614 | **$437** |

(An earlier single live snapshot showed 0.27 for the micro contract; over 30
days that turns out to be a momentary wide quote, not its typical spread.)

So this is a tenfold improvement in granularity at no cost. Confirmed live at
startup:

```
sleeve 1: signal XAUUSD -> exec XAUUSDmicro | min position 436.53 USD
          = smallest tradable weight 0.087 at equity 9994.77
```

Gold's smallest tradable weight falls from **0.867 to 0.087** against a median
in-market weight of 0.782 — from *below* its own floor to roughly nine lot
steps of headroom. The backtest is unchanged by this (full-period portfolio
Sharpe 1.701 vs 1.700), because the costs are the same.

## The original problem, kept for the record: lot granularity at $10,000

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
