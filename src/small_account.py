"""Can a very small account trade this book? Measured, not asserted.

Two questions, both answered here so the conclusion is reproducible:

1. **Is there a smaller lot anywhere on this broker?** Scans every symbol for
   the cheapest gold and BTC exposure. The answer drives everything else: if a
   smaller vehicle existed, small accounts would simply use it.

2. **What happens if the minimum lot is taken anyway?** The EA's rule is to hold
   nothing when the target position is below the minimum lot, which is why a
   too-small account sits flat. The alternative -- take the minimum regardless --
   is what someone would do if determined to trade a small balance, so it is
   simulated across four market regimes rather than dismissed.

The second question is the important one, because the intuitive answer ("it
would blow up") turns out to be wrong in an interesting way: it does not blow
up, it just runs 2-6x the intended risk, with leverage that RISES as the
account falls.

READ-ONLY against MT5. Run: python src/small_account.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import src.demo_sim as ds  # noqa: E402
import src.holdout as ho  # noqa: E402
import src.screen_universe as su  # noqa: E402

REPORTS = REPO / "reports"

# Execution vehicles: gold on the micro contract (1 oz/lot, min 0.1), BTC on the
# only BTC/USD instrument there is (min 0.01).
EXEC_SPECS = {"XAUUSD": (1.0, 0.1, 0.1), "BTCUSD": (1.0, 0.01, 0.01)}

REGIMES = [("2013-01-01", "2015-12-31", "2013-15 gold bear"),
           ("2018-01-01", "2019-12-31", "2018-19"),
           ("2021-01-01", "2023-12-31", "2021-23 crypto winter"),
           ("2024-01-01", None, "2024-now (bull)")]

EQUITIES = [200.0, 500.0, 1000.0, 2000.0, 5000.0]


def cheapest_vehicles() -> pd.DataFrame:
    """Smallest position available for every gold/BTC-linked instrument."""
    import MetaTrader5 as mt5
    if not mt5.initialize(timeout=60000):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        keys = ("gold", "xau", "bitcoin", "btc")
        rows = []
        for s in mt5.symbols_get():
            hay = (s.name + " " + s.description).lower()
            if not any(k in hay for k in keys):
                continue
            i = mt5.symbol_info(s.name)
            if i is None or i.trade_mode == 0:
                continue
            if not i.visible:
                mt5.symbol_select(s.name, True)
                i = mt5.symbol_info(s.name)
            px = i.bid if i.bid > 0 else 0.0
            if px <= 0:
                continue
            rows.append({"symbol": s.name, "group": s.path.split("\\")[0],
                         "min_lot": i.volume_min, "contract": i.trade_contract_size,
                         "price": round(px, 2),
                         "min_position_usd": round(i.volume_min * px * i.trade_contract_size, 2),
                         "description": i.description[:40]})
        return pd.DataFrame(rows).sort_values("min_position_usd").reset_index(drop=True)
    finally:
        mt5.shutdown()


def main() -> int:
    costs = pd.read_csv(ho.DATA / "universe_costs.csv")
    cmap = {r["symbol"]: su.costs_dict(r) for _, r in costs.iterrows()}
    ds.SLEEVES = dict(EXEC_SPECS)

    veh = cheapest_vehicles()

    # 1. tradability by equity, at TODAY's prices
    trad = []
    for sym in EXEC_SPECS:
        df, w = ds.weights(sym, cmap[sym])
        cs, minlot, step = EXEC_SPECS[sym]
        px_now = float(df["close"].iloc[-1])
        recent = w.loc[w.index.max() - pd.DateOffset(years=1):]
        inmkt = recent[recent > 0]
        for eq in EQUITIES:
            need = minlot * cs * px_now / (ds.ALLOC * eq)
            trad.append({"symbol": sym, "equity": eq,
                         "min_position_usd": round(minlot * cs * px_now, 2),
                         "weight_needed": round(need, 3),
                         "median_weight": round(float(inmkt.median()), 3),
                         "pct_signals_tradable": round(100 * float((inmkt >= need).mean()), 1)})
    trad = pd.DataFrame(trad)

    # 2. $200 across regimes, both rules
    runs = []
    for a, b, label in REGIMES:
        for mode in ("floor", "forcemin"):
            r = ds.simulate(200.0, True, cmap, list(EXEC_SPECS), mode=mode, start=a, end=b)
            runs.append({"regime": label, "mode": mode, **{k: r[k] for k in
                         ("final_equity", "cagr", "sharpe", "max_dd", "ruined",
                          "avg_leverage", "peak_leverage")}})
    runs = pd.DataFrame(runs)

    pd.set_option("display.width", 220)
    print("CHEAPEST GOLD / BTC VEHICLES ON THIS BROKER\n")
    print(veh.to_string(index=False))
    print("\n\nTRADABILITY BY EQUITY (today's prices, last year's signals)\n")
    print(trad.to_string(index=False))
    print("\n\n$200 ACROSS REGIMES, BOTH SLEEVES\n")
    print(runs.to_string(index=False))

    veh.to_csv(REPORTS / "small_account_vehicles.csv", index=False)
    trad.to_csv(REPORTS / "small_account_tradability.csv", index=False)
    runs.to_csv(REPORTS / "small_account_regimes.csv", index=False)
    print("\nwrote reports/small_account_*.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
