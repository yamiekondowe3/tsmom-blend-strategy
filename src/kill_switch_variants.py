"""Decide the kill switch's definition on evidence, not convenience.

Two definitions of "aggregate realised volatility" are defensible under the
brief's section 6, and they are not interchangeable:

  A. BOOK returns -- the volatility of the portfolio's own strategy returns.
     What the enhancement round implemented. Correct in spirit, but an EA
     cannot compute it without either recomputing every sleeve's full weight
     history on every bar (O(n^2), far too slow) or accumulating its own
     returns for two years before the trigger works at all.

  B. MARKET returns -- the volatility of an equal-weighted basket of the traded
     instruments themselves. Computable from bar data alone, so it is live from
     the first bar and needs no warm-up buffer.

B is the one that can actually be deployed. That is a reason to TEST it, not a
reason to adopt it: if it is materially worse than A, the right answer is to
accept A's warm-up, not to quietly redefine the overlay to whatever was easy to
code. This script measures both against no kill switch at all.

Both are computed on the UNION of the two sleeves' timestamps, which is what
Python has always done -- gold has no weekend bars and BTC does, so pairing the
two positionally (as the EA did) silently compares Saturday bitcoin against
Friday gold.

Run: python src/kill_switch_variants.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import src.book_b as bb  # noqa: E402
import src.holdout as ho  # noqa: E402
import src.screen_universe as su  # noqa: E402
import src.portfolio_b as pbk  # noqa: E402
from common.portfolio import summarize  # noqa: E402

SLEEVES = ["XAUUSD", "BTCUSD"]
HOLDOUT_END = "2020-09-21"


def sleeve(sym, costs):
    df = pd.read_csv(ho.DEEP_DIR / f"{sym}_H4.csv", parse_dates=["timestamp"])
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    bpd = bb.bars_per_day(df)
    r = bb.run(df, costs, slow_bars=max(2, int(round(su.SLOW_D * bpd))),
               fast_bars=max(1, int(round(su.FAST_D * bpd))),
               mode="blend5050", direction=su.DIRECTION,
               vol_target=su.VOL_TARGET, max_leverage=su.MAX_LEV)
    return df, r["returns"], r["weights"]


def main() -> int:
    costs = pd.read_csv(ho.DATA / "universe_costs.csv")
    cmap = {r["symbol"]: su.costs_dict(r) for _, r in costs.iterrows()}

    nets, mkts = {}, {}
    for s in SLEEVES:
        df, net, w = sleeve(s, cmap[s])
        nets[s] = net
        mkts[s] = df["close"].astype(float).pct_change()

    net_df = pd.DataFrame(nets).fillna(0.0)
    start = max(v.index.min() for v in nets.values())
    net_df = net_df.loc[start:]
    port = net_df.mean(axis=1)

    # Market basket on the same union grid, 0 where a market is shut.
    mkt = pd.DataFrame(mkts).reindex(net_df.index).fillna(0.0).mean(axis=1)

    ppy = int(round(len(port) / ((port.index[-1] - port.index[0]).days / 365.25)))
    bpd_c = len(port) / port.index.normalize().nunique()
    vw = max(2, int(round(20 * bpd_c)))
    lb = int(round(252 * 2 * bpd_c))

    variants = {
        "A  none": pd.Series(False, index=port.index),
        "B  book returns (current Python)": pbk.kill_switch(port, vw, lb),
        "C  market basket (EA-implementable)": pbk.kill_switch(mkt, vw, lb),
    }

    rows = []
    for name, mask in variants.items():
        r = port.where(~mask, 0.0)
        for label, lo, hi in (("full", None, None), ("holdout", None, HOLDOUT_END),
                              ("selection", "2020-09-22", None)):
            s = summarize(r.loc[lo:hi], periods_per_year=ppy)
            rows.append({"variant": name, "period": label,
                         "sharpe": round(s["sharpe"], 3),
                         "cagr": round(s["cagr"], 4),
                         "max_dd": round(s["max_drawdown"], 3),
                         "pct_flat": round(float(mask.loc[lo:hi].mean()), 3)})
    res = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(res.pivot(index="variant", columns="period",
                    values=["sharpe", "max_dd", "pct_flat"]).to_string())
    print()
    agree = (variants["B  book returns (current Python)"] ==
             variants["C  market basket (EA-implementable)"]).mean()
    print(f"B and C agree on {agree:.1%} of bars")
    res.to_csv(ho.REPORTS / "kill_switch_variants.csv", index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
