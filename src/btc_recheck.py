"""Settle the disagreement between the harness and our own backtest on BTC.

The harness says BTC's entries are worse than random on unseen data. Our own
backtest says the BTC sleeve beats vol-matched buy-and-hold by +0.53 Sharpe over
the same period. Both can be true: they measure different things. The harness
tests stop-managed discrete entries at fixed risk; the deployed system holds a
continuous, vol-sized exposure. The question that decides whether BTC belongs in
the book is narrower:

    in the DEPLOYED framework, does BTC's edge come from timing,
    or from having been long an asset that rose 10,000x?

The test is the same placebo used on gold: keep the exposure profile exactly --
same weights, same distribution, same time in market -- and shuffle WHEN it is
applied. If shuffled timing does as well, the signal is not the source.

Also applies the proportional-spread correction, since charging a constant
$2.42 spread at $5 BTC made the pre-2017 period unreadable.

Run: python src/btc_recheck.py
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
from common.portfolio import summarize  # noqa: E402

HOLDOUT_END = "2020-09-21"
N_PLACEBO = 300


def load(sym: str) -> pd.DataFrame:
    df = pd.read_csv(ho.DEEP_DIR / f"{sym}_H4.csv", parse_dates=["timestamp"])
    df = df.set_index("timestamp").sort_index()
    return df[~df.index.duplicated(keep="last")]


def run_sleeve(sym: str, costs: dict, proportional: bool):
    df = load(sym)
    c = dict(costs)
    bpd = bb.bars_per_day(df)
    if proportional:
        # Spread as a constant FRACTION of price, pinned to today's measured
        # spread. book_b.run takes a scalar, so the run is done at the median
        # historical equivalent for the window being scored.
        frac = c["typical_spread_price"] / float(df["close"].iloc[-1])
        c["typical_spread_price"] = frac * float(df["close"].median())
    r = bb.run(df, c, slow_bars=max(2, int(round(su.SLOW_D * bpd))),
               fast_bars=max(1, int(round(su.FAST_D * bpd))),
               mode="blend5050", direction=su.DIRECTION,
               vol_target=su.VOL_TARGET, max_leverage=su.MAX_LEV)
    return df, r


def placebo(df: pd.DataFrame, w: pd.Series, lo, hi, ppy: int, seed=7) -> dict:
    """Same exposure profile, shuffled timing."""
    ret = df["close"].pct_change().fillna(0.0)
    rng = np.random.default_rng(seed)
    base = summarize((w * ret).loc[lo:hi], periods_per_year=ppy).get("sharpe", 0)
    out = []
    for _ in range(N_PLACEBO):
        perm = pd.Series(rng.permutation(w.to_numpy()), index=w.index)
        s = summarize((perm * ret).loc[lo:hi], periods_per_year=ppy)
        if s:
            out.append(s.get("sharpe", 0))
    out = np.array(out)
    sd = out.std(ddof=1)
    return {"strategy": round(base, 3), "placebo_mean": round(float(out.mean()), 3),
            "placebo_sd": round(float(sd), 3),
            "z": round(float((base - out.mean()) / sd), 2) if sd > 0 else np.nan,
            "pctile": round(float((out < base).mean()), 3)}


def main() -> int:
    costs = pd.read_csv(ho.DATA / "universe_costs.csv")
    cmap = {r["symbol"]: su.costs_dict(r) for _, r in costs.iterrows()}

    rows = []
    for sym in ("XAUUSD", "BTCUSD"):
        for prop in (False, True):
            if sym == "XAUUSD" and prop:
                continue        # gold's price range makes this immaterial
            df, r = run_sleeve(sym, cmap[sym], prop)
            ppy = int(round(bb.periods_per_year(df)))
            w, net = r["weights"], r["returns"]
            for label, lo, hi in (("holdout", None, HOLDOUT_END),
                                  ("selection", "2020-09-22", None),
                                  ("full", None, None)):
                s = summarize(net.loc[lo:hi], periods_per_year=ppy)
                pl = placebo(df, w, lo, hi, ppy)
                rows.append({"symbol": sym,
                             "spread": "proportional" if prop else "constant",
                             "period": label,
                             "sharpe": round(s.get("sharpe", 0), 3),
                             "cagr": round(s.get("cagr", 0), 4), **pl})
    res = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    print(res.to_string(index=False))
    res.to_csv(ho.REPORTS / "btc_placebo.csv", index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
