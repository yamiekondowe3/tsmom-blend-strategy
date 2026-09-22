"""The settings actually deployed, in one place.

WHY THIS EXISTS, AND WHY IT IS NOT APPLIED EVERYWHERE.

Volatility targeting is a leverage dial, not a signal parameter. Changing it
scales returns and drawdown together and leaves Sharpe untouched (measured:
1.697 at every setting below). So it changes what the book *pays out*, and
nothing about whether the edge is real.

That distinction decides which modules import this and which do not:

  * The DEPLOYED path imports it -- `parity.py`, `portfolio_gold_btc.py`,
    `demo_sim.py` -- and the EA's preset carries the same number. Parity in
    particular MUST match the EA exactly, or the comparison fails on
    `vol_scale` and `pos_raw`.

  * The RESEARCH path deliberately does not -- `screen_universe.py`,
    `analyze_book_b.py`, `run_book_b.py` keep 0.15 as a literal. The
    cross-instrument screen, the holdout, the deflated Sharpe and the harness
    reports were all produced at 0.15, and they must stay reproducible. Since
    Sharpe is scale-invariant, none of those conclusions depend on the dial
    anyway, so re-running them at a new setting would churn the numbers without
    changing a single verdict.

Measured on the deployed gold+BTC portfolio, full period:

    vol target   max DD    CAGR    Sharpe
      15%        -12.8%    11.9%   1.697
      10%         -8.7%     7.8%   1.697     <- current
       7.5%       -6.6%     5.8%   1.697

Lower drawdown here is bought with proportionally lower return, not earned. The
leverage cap is not a second lever: 3x -> 1.5x moves drawdown only -12.8% to
-12.2%, because the cap rarely binds.

One consequence worth remembering: a smaller vol target asks for smaller
positions, which RAISES the minimum viable account, because the broker's
minimum lot does not shrink with it. Both sleeves need ~$3,155 at 15% and
~$4,741 at 10%. See reports/small_account.md.
"""
from __future__ import annotations

DEPLOY_VOL_TARGET = 0.10      # was 0.15; see reports/drawdown.md
DEPLOY_MAX_LEVERAGE = 3.0

# Kept at the value every research report was produced with. Do not "tidy" this
# into DEPLOY_VOL_TARGET -- see the module docstring.
RESEARCH_VOL_TARGET = 0.15
