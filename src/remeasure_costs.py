"""Re-measure the traded instruments' costs on the FULL 30-day tick window.

The cross-instrument screen used a 7-day window to keep ~100 symbols tractable
and labelled those figures screening-grade. The two instruments that actually
survived have to be costed properly before anything is built on them: a median
spread taken over one week can miss a whole regime of quoting conditions, and
the 95th percentile taken over one week is barely meaningful.

READ-ONLY: symbol_info, symbol_info_tick, copy_ticks_range.

Run: python src/remeasure_costs.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import src.universe as un  # noqa: E402

# XAUUSDmicro is included because it is the EXECUTION vehicle for the gold
# sleeve on small accounts: same price and same per-ounce financing as XAUUSD,
# a tenth of the minimum position, and a wider spread that has to be charged
# rather than assumed away.
TRADED = ["XAUUSD", "BTCUSD", "XAUUSDmicro"]
TICK_DAYS = 30


def main() -> int:
    path = un.DATA / "universe_costs.csv"
    costs = pd.read_csv(path)
    before = costs[costs.symbol.isin(TRADED)].set_index("symbol")

    fresh = un.costs_for(TRADED, tick_days=TICK_DAYS, chunk_days=7, subsample=5)
    if fresh.empty:
        print("no tick data returned -- costs unchanged", file=sys.stderr)
        return 1
    fresh = fresh.assign(spread_grade=f"traded ({TICK_DAYS}d)")

    print("\n              typical spread        worst (p95)        swap long %/yr")
    for s in TRADED:
        row = fresh[fresh.symbol == s]
        if row.empty:
            print(f"{s:<12} no tick data returned -- unchanged")
            continue
        a = row.iloc[0]
        if s in before.index:
            b = before.loc[s]
            print(f"{s:<12} {b['typical_spread_price']:>8} -> {a['typical_spread_price']:<12.5f}"
                  f" {b['worst_spread_price']:>8} -> {a['worst_spread_price']:<12.5f}"
                  f" {b['swap_long_annual_pct']:>8} -> {a['swap_long_annual_pct']}")
        else:
            print(f"{s:<12} {'(new)':>8} -> {a['typical_spread_price']:<12.5f}"
                  f" {'(new)':>8} -> {a['worst_spread_price']:<12.5f}"
                  f" {'(new)':>8} -> {a['swap_long_annual_pct']}")

    merged = (pd.concat([costs[~costs.symbol.isin(TRADED)], fresh], ignore_index=True)
                .sort_values("symbol"))
    merged.to_csv(path, index=False)
    print(f"\nupdated {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
