"""Measure costs for universe symbols missing from data/universe_costs.csv and
append them. READ-ONLY against MT5.

Exists because the first cost pass silently lost 22 symbols -- the entire
Forex Major group, BTC, ETH and XAUUSD -- to transient tick-download failures.
Screening without them would have tested only minors and exotics.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import src.universe as un  # noqa: E402


def main() -> int:
    meta = pd.read_csv(un.DATA / "universe_meta.csv")
    costs = pd.read_csv(un.DATA / "universe_costs.csv")
    missing = sorted(set(meta.symbol) - set(costs.symbol))
    print(f"missing cost rows: {len(missing)} -> {missing}", flush=True)
    if not missing:
        return 0
    extra = un.costs_for(missing)
    merged = pd.concat([costs, extra], ignore_index=True).drop_duplicates("symbol", keep="last")
    merged.to_csv(un.DATA / "universe_costs.csv", index=False)
    still = sorted(set(meta.symbol) - set(merged.symbol))
    print(f"recovered {len(extra)}; still missing {len(still)}: {still}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
