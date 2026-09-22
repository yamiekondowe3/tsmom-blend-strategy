# Can a $200 account trade this? No — and here is the measurement

Asked directly. The answer is no, for a reason that has nothing to do with the
signal: **the smallest position the broker sells is larger than the position the
strategy wants.**

Reproduce with `python src/small_account.py`.

## 1. There is no smaller lot

Every gold- and BTC-linked instrument on the broker, by smallest tradable
position:

| Symbol | Min lot | Contract | Min position | Note |
|---|---|---|---|---|
| BTCETH | 0.01 | 1 | $0.31 | BTC *vs ETH* — not BTC exposure |
| BTCLTC | 0.01 | 1 | $13.68 | BTC vs LTC — not BTC exposure |
| BCHUSD | 0.20 | 1 | $68.47 | Bitcoin **Cash** — a different asset, never validated |
| **XAUUSDmicro** | 0.10 | 1 | **$435.90** | the cheapest real gold |
| **BTCUSD** | 0.01 | 1 | **$862.79** | the only BTC/USD instrument |
| XAUEUR | 0.01 | 100 | $3,807 | |
| XAUUSD | 0.01 | 100 | $4,359 | |

Also checked and rejected: GLD.US at $400 (no cheaper than the micro contract,
and US-hours-only, so it cannot follow a 24-hour H4 signal), Gold Basket at
$10,001, and BTCUSD.conv which is disabled.

**$435.90 and $862.79 are the floors.** On a $200 account those are 2.2× and
4.3× the *entire balance*.

## 2. What each account size can actually hold

At today's prices, against the last year's in-market signals, at the deployed
10% vol target (median weight 0.521 gold, 0.362 BTC):

| Equity | Gold tradable | BTC tradable |
|---|---|---|
| **$200** | **0%** | **0%** |
| $500 | 0% | 0% |
| $1,000 | 0% | 0% |
| $2,000 | 98.3% | 0% |
| $5,000 | 100% | 58.6% |

A $200 account never opens a position. The EA holds nothing whenever the target
is below the minimum lot, so it would sit flat and log the requirement — correct
behaviour, not a fault.

Note these thresholds are **higher than they were at the 15% vol target**,
because a smaller vol target asks for smaller positions while the minimum lot
stays put. Lowering the drawdown and lowering the account minimum pull in
opposite directions.

## 3. What if you take the minimum lot anyway?

The interesting case, because refusing to trade is not what someone with $200
and conviction actually does. Simulated at $200 on both sleeves, forcing the
minimum lot whenever the signal is long, across four regimes:

| Regime | Rule | Final from $200 | Max DD | Peak leverage |
|---|---|---|---|---|
| 2013-15 gold bear | floor | $237.80 | −2.0% | 0.08× |
| 2013-15 gold bear | **forcemin** | $238.09 | −5.4% | 0.66× |
| 2018-19 | floor | $206.75 | −1.5% | 0.67× |
| 2018-19 | **forcemin** | $225.00 | −18.9% | 1.09× |
| 2021-23 crypto winter | floor | $200.00 | 0% | 0× |
| 2021-23 crypto winter | **forcemin** | $440.04 | **−53.0%** | 3.13× |
| 2024-now (bull) | floor | $200.00 | 0% | 0× |
| 2024-now (bull) | **forcemin** | $880.07 | **−57.0%** | 5.75× |

It was **never wiped out** — which is worth saying, because the intuitive answer
is that it would be. The strategy is flat ~70% of the time and long-only, and
that is enough to survive. But:

- **Drawdowns of −19% to −57%**, against −9.0% for the properly sized book. That
  is 2-6× the intended risk and roughly 6× the drawdown that was actually asked
  for.
- **Leverage is uncontrolled and rises as the account falls.** The minimum lot
  is fixed in dollars, so a losing account is forced into *more* leverage, not
  less: at $100 the gold minimum alone is 4.4× equity. Losses compound the risk
  instead of damping it. That is the opposite of how volatility targeting
  behaves, and it is the reason the good outcomes above should not reassure
  anyone.
- **It is not the validated strategy.** Forcing a fixed minimum discards
  volatility targeting entirely — the component the independent harness
  identified as the source of the edge. Nothing in the screen, the holdout, the
  deflated Sharpe or the harness applies to it.
- **The two profitable rows are the two bull markets.** 2021-23 and 2024-now
  both ran huge crypto and gold rallies. This is a small, favourable sample.

## What to do instead

| Goal | Equity needed (10% vol) |
|---|---|
| Gold sleeve alone, nearly all signals | ~$2,000 |
| Both sleeves, gold full + BTC partial | ~$5,000 |
| Both sleeves, nearly all signals | ~$7,000 |

Until then the honest options are to keep the demo running as a paper record,
or to use a broker offering nano lots — not to force this one. A $200 balance
does not fail because the strategy is bad; it fails because the smallest thing
you can buy is bigger than what you want to hold.
