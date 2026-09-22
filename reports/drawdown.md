# Reducing the drawdown: what it costs, and what it does not buy

The maximum drawdown was asked to come down. It has: the deployed volatility
target moved from **15% to 10%**, taking the portfolio's worst peak-to-trough
from **−13.3% to −9.0%** (−12.8% to −8.7% with the kill switch applied).

## This is scaling, not improvement

Volatility targeting is a leverage dial. Measured on the deployed gold + BTC
portfolio over the full 2011-03 to 2026-09 period:

| Vol target | Max DD | CAGR | Sharpe |
|---|---|---|---|
| 15% (previous) | −13.3% | 12.7% | **1.701** |
| **10% (current)** | **−9.0%** | **8.4%** | **1.701** |
| 7.5% | −6.6% | 5.8% | **1.697** |

**Sharpe is identical.** Nothing was improved — the book is simply held smaller,
and return falls in the same proportion as risk. Anyone reading the new −9.0%
as a better strategy has misread it; the correct reading is "the same strategy
at two-thirds the size".

The verification for the change was exactly this: Sharpe had to stay at 1.701
to three decimals while CAGR and drawdown both fell to ~2/3. If Sharpe had
moved materially, something other than leverage had changed and the run would
have been stopped.

## Why not something cleverer

**The leverage cap is not a second lever.** Tightening it from 3× to 1.5× moves
the drawdown only −12.8% → −12.2%, because it rarely binds:

| Variant | Max DD | CAGR | Sharpe |
|---|---|---|---|
| 15% vol, 3× cap | −12.8% | 11.9% | 1.697 |
| 15% vol, 1.5× cap | −12.2% | 11.7% | 1.691 |
| 10% vol, 1.0× cap | −8.3% | 7.7% | 1.691 |

**Switching to a lower-drawdown variant is dominated.** The rejected
speed-ensemble from the enhancement round had a better drawdown but a lower
Sharpe (0.80-0.87 against 0.92 on the gold sleeve). That trade is never worth
taking: at any matched drawdown, the higher-Sharpe strategy scaled down returns
more. Scaling the best strategy beats adopting a worse one that happens to be
quieter.

**Nothing new was searched.** 298+ trials are already counted against this
project and the deflated Sharpe already fails at that count. Hunting for a
configuration with a lower drawdown would add trials and make the statistics
worse, not better. Moving the vol target adds no trials at all, because it
changes no decision the strategy makes — every entry, exit and filter is
identical; only the position size differs.

## The cost you should know about

A smaller vol target asks for smaller positions, and the broker's minimum lot
does not shrink to match. So lowering the drawdown **raises** the minimum
account size:

| | 15% vol | 10% vol |
|---|---|---|
| Gold sleeve fully tradable | ~$1,100 | ~$2,000 |
| BTC sleeve fully tradable | ~$5,000 | ~$7,000+ |

That is the real trade-off in this change: a calmer book that needs more
capital to express. See [`small_account.md`](small_account.md).

## Where it is set

`src/deploy_config.py` holds `DEPLOY_VOL_TARGET`, imported by the deployed path
(`parity.py`, `portfolio_gold_btc.py`, `demo_sim.py`) and matched by the EA's
`VolTarget` input in `mql5/TSMOM_demo.set`.

The research path (`screen_universe.py`, `analyze_book_b.py`, `run_book_b.py`)
deliberately stays at 0.15, because the cross-instrument screen, the holdout,
the deflated Sharpe and the harness reports were produced at that setting and
must stay reproducible. Since Sharpe is invariant to the dial, none of those
verdicts depend on it.
